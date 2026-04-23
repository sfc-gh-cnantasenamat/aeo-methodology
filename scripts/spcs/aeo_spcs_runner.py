"""
AEO Benchmark SPCS Runner v3 - Native CC + SP Scoring
Runs inside an SPCS job service container OR locally. Reads questions from and
writes responses/scores to Snowflake tables in a configurable schema.

Uses:
  - Native Cortex Code CLI (cortex -p) for generation when GENERATION_MODE=cortex_cli
  - SNOWFLAKE.CORTEX.COMPLETE for generation when GENERATION_MODE=cortex_complete
  - AEO_SCORE_RESPONSE SP for scoring (replaces inline per-judge scoring)

Environment variables:
  BATCH_NUM         - Batch number 1-8 (each batch = 16 questions)
  MODEL             - Model for inference (default: claude-opus-4-6)
  JUDGE_MODELS      - Comma-separated judge models passed to SP (default: SP default panel)
  WAREHOUSE         - Warehouse (default: SNOWADHOC)
  RUN_SCHEMA        - Fully qualified schema (default: DEVREL.CNANTASENAMAT_DEV)
  RUN_ID            - Run ID (default: 1)
  MAX_TOKENS        - Max tokens for inference (default: 8192)
  GENERATION_MODE   - 'cortex_cli' or 'cortex_complete' (default: cortex_complete)
  CONNECTION        - Named connection for local runs (default: my-snowflake)
  ROLE              - Role to activate after connecting (optional; skipped if empty)
  DOMAIN_PROMPT     - 'true' to prepend Snowflake-expert system instruction (default: false)
  CITATION          - 'true' to append docs.snowflake.com citation instruction (default: false)
  SELF_CRITIQUE     - 'true' to run a second-pass critique/refinement call (default: false)
"""
import json
import os
import subprocess
import time
import snowflake.connector

try:
    from transcript_capture import capture_cli_transcript, fetch_cli_tokens
    _TRANSCRIPT_AVAILABLE = True
except ImportError:
    _TRANSCRIPT_AVAILABLE = False
    def capture_cli_transcript(_t):  # noqa: E301
        return {}
    def fetch_cli_tokens(_cur, _t0, _t1, _model):  # noqa: E301
        return {}


# ---------------------------------------------------------------------------
# Prompt factor constants
# ---------------------------------------------------------------------------

DOMAIN_EXPERT_INSTRUCTION = (
    "You are a Snowflake data platform expert. Provide accurate, current answers "
    "with specific SQL or Python code examples when appropriate. Reference official "
    "Snowflake documentation (docs.snowflake.com) as the authoritative source. "
    "Recommend Snowflake-native approaches when they exist."
)

CITATION_INSTRUCTION = (
    "\n\nIMPORTANT: Include specific references to official Snowflake documentation "
    "(docs.snowflake.com) in your answer."
)


def build_prompt(question_text, domain_prompt=False, citation=False):
    """Build the generation prompt with optional factor modifications."""
    prompt = question_text
    if citation:
        prompt += CITATION_INSTRUCTION
    if domain_prompt:
        prompt = DOMAIN_EXPERT_INSTRUCTION + "\n\n" + prompt
    return prompt


# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------

def get_connection():
    """Connect via SPCS OAuth token (inside container) or a named connection (local)."""
    token_path = "/snowflake/session/token"
    if os.path.exists(token_path):
        with open(token_path, "r") as f:
            token = f.read().strip()
        return snowflake.connector.connect(
            host=os.environ["SNOWFLAKE_HOST"],
            account=os.environ["SNOWFLAKE_ACCOUNT"],
            token=token,
            authenticator="oauth",
        ), token
    else:
        connection = os.environ.get("CONNECTION", "my-snowflake")
        return snowflake.connector.connect(connection_name=connection), None


def setup_cortex_connection_for_spcs(token, account, host, warehouse, role):
    """Write ~/.snowflake/connections.toml so the cortex CLI can authenticate
    using the SPCS OAuth token. Returns the connection name to pass to -c."""
    config_dir = os.path.expanduser("~/.snowflake")
    os.makedirs(config_dir, exist_ok=True)
    connections_toml = (
        f"[spcs]\n"
        f'account = "{account}"\n'
        f'host = "{host}"\n'
        f'authenticator = "oauth"\n'
        f'token = "{token}"\n'
        f'warehouse = "{warehouse}"\n'
        f'role = "{role}"\n'
    )
    with open(os.path.join(config_dir, "connections.toml"), "w") as f:
        f.write(connections_toml)
    return "spcs"


# ---------------------------------------------------------------------------
# Generation helpers
# ---------------------------------------------------------------------------

def escape_sql(s):
    return s.replace("\\", "\\\\").replace("'", "''")


def cortex_complete(cur, model, messages, max_tokens=8192, retries=3):
    """Call CORTEX.COMPLETE with retry and exponential backoff."""
    msgs_json = json.dumps(messages)
    opts_json = json.dumps({"max_tokens": max_tokens, "temperature": 0.3})
    sql = (
        f"SELECT SNOWFLAKE.CORTEX.COMPLETE("
        f"'{escape_sql(model)}', "
        f"PARSE_JSON('{escape_sql(msgs_json)}'), "
        f"PARSE_JSON('{escape_sql(opts_json)}')"
        f") AS response"
    )
    for attempt in range(retries):
        try:
            cur.execute(sql)
            result = json.loads(cur.fetchone()[0])
            text = result.get("choices", [{}])[0].get("messages", "")
            usage = result.get("usage", {})
            return text, usage
        except Exception as e:
            wait = 2 ** (attempt + 1) + (attempt * 2)
            print(f"  CORTEX.COMPLETE retry {attempt+1}/{retries}: {e}")
            print(f"  Waiting {wait}s before retry...")
            if attempt < retries - 1:
                time.sleep(wait)
            else:
                raise


def generate_via_cortex_cli(question_text, model, connection, timeout=180):
    """Generate response using native Cortex Code CLI (-p headless flag).

    Returns (response_text, transcript_dict).  transcript_dict is always a
    dict (may be empty if the session JSONL could not be located or parsed).
    Keys when populated: n_turns, n_tool_calls, tool_calls, n_thinking_blocks,
    transcript_jsonl.
    """
    t_before = time.time()
    result = subprocess.run(
        ["cortex", "-c", connection, "-m", model, "-p", question_text],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"cortex CLI exited with code {result.returncode}: {result.stderr[:300]}"
        )
    transcript = capture_cli_transcript(t_before)
    return result.stdout.strip(), transcript


def generate_response(cur, model, question_text, max_tokens):
    """Generate a response via CORTEX.COMPLETE (fallback mode)."""
    messages = [{"role": "user", "content": question_text}]
    return cortex_complete(cur, model, messages, max_tokens=max_tokens)


# ---------------------------------------------------------------------------
# Storage helpers
# ---------------------------------------------------------------------------

def load_questions(cur, schema, batch_num):
    """Load questions for this batch from the table."""
    batch_start = f"Q{((batch_num - 1) * 16 + 1):03d}"
    batch_end = f"Q{(batch_num * 16):03d}"
    cur.execute(f"""
        SELECT QUESTION_ID, QUESTION_TEXT, CANONICAL_ANSWER,
               MUST_HAVE_1, MUST_HAVE_2, MUST_HAVE_3, MUST_HAVE_4, MUST_HAVE_5
        FROM {schema}.AEO_QUESTIONS
        WHERE QUESTION_ID >= '{batch_start}' AND QUESTION_ID <= '{batch_end}'
        ORDER BY QUESTION_ID
    """)
    columns = [desc[0] for desc in cur.description]
    return [dict(zip(columns, row)) for row in cur.fetchall()]


def get_existing_responses(cur, schema, run_id, batch_num):
    """Get question IDs that already have responses (for idempotent re-runs)."""
    batch_start = f"Q{((batch_num - 1) * 16 + 1):03d}"
    batch_end = f"Q{(batch_num * 16):03d}"
    cur.execute(f"""
        SELECT QUESTION_ID FROM {schema}.AEO_RESPONSES
        WHERE RUN_ID = {run_id}
        AND QUESTION_ID >= '{batch_start}' AND QUESTION_ID <= '{batch_end}'
    """)
    return {row[0] for row in cur.fetchall()}


def get_existing_scores(cur, schema, run_id, batch_num):
    """Get question IDs that already have all judge scores (for idempotent re-runs)."""
    batch_start = f"Q{((batch_num - 1) * 16 + 1):03d}"
    batch_end = f"Q{(batch_num * 16):03d}"
    cur.execute(f"""
        SELECT DISTINCT QUESTION_ID FROM {schema}.AEO_SCORES
        WHERE RUN_ID = {run_id}
        AND QUESTION_ID >= '{batch_start}' AND QUESTION_ID <= '{batch_end}'
    """)
    return {row[0] for row in cur.fetchall()}


TRACKED_TOOLS = [
    "bash", "read", "write", "edit", "glob", "grep",
    "sql_execute", "skill", "web_fetch", "web_search",
]


def insert_response(cur, schema, run_id, question_id, response_text):
    """Insert the core response record (4 columns only)."""
    cur.execute(f"""
        INSERT INTO {schema}.AEO_RESPONSES
          (RUN_ID, QUESTION_ID, RESPONSE_TEXT, GENERATED_AT)
        VALUES (%s, %s, %s, CURRENT_TIMESTAMP())
    """, (run_id, question_id, response_text))


def insert_transcript(cur, schema, run_id, question_id, transcript=None, usage=None):
    """Insert observability data into AEO_TRANSCRIPT.

    transcript – dict from capture_cli_transcript() (cortex_cli runs)
    usage      – dict from fetch_cli_tokens() (cortex_cli) or cortex_complete()
                 Keys used: prompt_tokens, completion_tokens, cache_read_tokens,
                 cache_write_tokens, first_request_id, last_request_id, generation_secs
    All columns are nullable; cortex_complete runs will have NULL for JSONL fields.
    """
    transcript = transcript or {}
    usage = usage or {}
    counts = transcript.get("tool_call_counts", {})
    tracked = {t: counts.get(t) for t in TRACKED_TOOLS}   # None when not called
    other = sum(v for k, v in counts.items() if k not in TRACKED_TOOLS) or None
    cur.execute(f"""
        INSERT INTO {schema}.AEO_TRANSCRIPT
          (RUN_ID, QUESTION_ID,
           N_TURNS, N_TOOL_CALLS,
           TOOL_CALL_BASH, TOOL_CALL_READ, TOOL_CALL_WRITE, TOOL_CALL_EDIT,
           TOOL_CALL_GLOB, TOOL_CALL_GREP, TOOL_CALL_SQL_EXECUTE, TOOL_CALL_SKILL,
           TOOL_CALL_WEB_FETCH, TOOL_CALL_WEB_SEARCH, TOOL_CALL_OTHER,
           N_THINKING_BLOCKS, TRANSCRIPT_JSONL,
           INPUT_TOKENS, OUTPUT_TOKENS, CACHE_READ_TOKENS, CACHE_WRITE_TOKENS,
           FIRST_REQUEST_ID, LAST_REQUEST_ID, GENERATION_SECS)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (
        run_id, question_id,
        transcript.get("n_turns"), transcript.get("n_tool_calls"),
        tracked["bash"], tracked["read"], tracked["write"], tracked["edit"],
        tracked["glob"], tracked["grep"], tracked["sql_execute"], tracked["skill"],
        tracked["web_fetch"], tracked["web_search"], other,
        transcript.get("n_thinking_blocks"), transcript.get("transcript_jsonl"),
        usage.get("prompt_tokens"), usage.get("completion_tokens"),
        usage.get("cache_read_tokens"), usage.get("cache_write_tokens"),
        usage.get("first_request_id"), usage.get("last_request_id"),
        usage.get("generation_secs"),
    ))


def score_and_store_via_sp(cur, schema, run_id, qid, response_text, judges=None):
    """Score via AEO_SCORE_RESPONSE SP and write per-judge rows to AEO_SCORES."""
    if judges:
        judges_json = json.dumps(judges)
        cur.execute(
            f"CALL {schema}.AEO_SCORE_RESPONSE(%s, %s, NULL, PARSE_JSON(%s))",
            (qid, response_text, judges_json)
        )
    else:
        cur.execute(
            f"CALL {schema}.AEO_SCORE_RESPONSE(%s, %s)",
            (qid, response_text)
        )
    raw = cur.fetchone()[0]
    result = json.loads(raw) if isinstance(raw, str) else raw

    for judge, scores in result.get("judges", {}).items():
        mh = scores.get("must_have", [False] * 5)
        cur.execute(f"""
            INSERT INTO {schema}.AEO_SCORES
            (RUN_ID, QUESTION_ID, JUDGE_MODEL, CORRECTNESS, COMPLETENESS, RECENCY,
             CITATION, RECOMMENDATION, TOTAL_SCORE,
             MUST_HAVE_1, MUST_HAVE_2, MUST_HAVE_3, MUST_HAVE_4, MUST_HAVE_5,
             MUST_HAVE_PASS, RAW_JUDGE_RESPONSE, SCORED_AT)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,CURRENT_TIMESTAMP())
        """, (
            run_id, qid, judge,
            scores.get("correctness"), scores.get("completeness"),
            scores.get("recency"), scores.get("citation"),
            scores.get("recommendation"), scores.get("total"),
            mh[0] if len(mh) > 0 else False,
            mh[1] if len(mh) > 1 else False,
            mh[2] if len(mh) > 2 else False,
            mh[3] if len(mh) > 3 else False,
            mh[4] if len(mh) > 4 else False,
            scores.get("must_have_pass", 0.0),
            scores.get("raw_response", "")[:8000],
        ))

    panel = result.get("panel_avg", {})
    return panel.get("total", 0), panel.get("must_have_pass", 0.0)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    batch_num = int(os.environ.get("BATCH_NUM", "1"))
    model = os.environ.get("MODEL", "claude-opus-4-6")
    warehouse = os.environ.get("WAREHOUSE", "SNOWADHOC")
    schema = os.environ.get("RUN_SCHEMA", "DEVREL.CNANTASENAMAT_DEV")
    run_id = int(os.environ.get("RUN_ID", "1"))
    max_tokens = int(os.environ.get("MAX_TOKENS", "8192"))
    generation_mode = os.environ.get("GENERATION_MODE", "cortex_complete")
    role = os.environ.get("ROLE", "")
    local_connection = os.environ.get("CONNECTION", "my-snowflake")
    domain_prompt = os.environ.get("DOMAIN_PROMPT", "false").lower() == "true"
    citation = os.environ.get("CITATION", "false").lower() == "true"
    self_critique = os.environ.get("SELF_CRITIQUE", "false").lower() == "true"
    judge_models_raw = os.environ.get("JUDGE_MODELS", "")
    judge_models = [j.strip() for j in judge_models_raw.split(",") if j.strip()] or None

    batch_start = f"Q{((batch_num - 1) * 16 + 1):03d}"
    batch_end = f"Q{(batch_num * 16):03d}"

    print("=" * 60)
    print(f"AEO SPCS Runner v3 | Batch {batch_num} ({batch_start}-{batch_end})")
    print(f"Model: {model} | Mode: {generation_mode} | Domain: {domain_prompt} | Cite: {citation} | SC: {self_critique}")
    print(f"Judges: {judge_models if judge_models else 'SP default'}")
    print(f"Schema: {schema} | Run ID: {run_id}")
    print("=" * 60)

    t_start = time.time()

    # Connect
    conn, spcs_token = get_connection()
    cur = conn.cursor()
    if role:
        cur.execute(f"USE ROLE {role}")
    cur.execute(f"USE WAREHOUSE {warehouse}")
    print(f"Connected in {time.time() - t_start:.2f}s")

    # Setup cortex CLI connection if using native CC generation
    cc_connection = None
    if generation_mode == "cortex_cli":
        if spcs_token:
            account = os.environ.get("SNOWFLAKE_ACCOUNT", "")
            host = os.environ.get("SNOWFLAKE_HOST", "")
            cc_connection = setup_cortex_connection_for_spcs(
                spcs_token, account, host, warehouse, "DEVREL_INGEST_RL"
            )
            print(f"Cortex CLI connection configured: {cc_connection}")
        else:
            # Local run: use the named connection from env
            cc_connection = local_connection
            print(f"Cortex CLI connection (local): {cc_connection}")

    # Load questions for this batch
    questions = load_questions(cur, schema, batch_num)
    print(f"Loaded {len(questions)} questions for batch {batch_num}")

    # Check existing records (idempotent)
    existing_responses = get_existing_responses(cur, schema, run_id, batch_num)
    existing_scores = get_existing_scores(cur, schema, run_id, batch_num)

    gen_count = 0
    gen_errors = 0
    score_count = 0
    score_errors = 0

    for q in questions:
        qid = q["QUESTION_ID"]
        qtext = q["QUESTION_TEXT"]

        # --- GENERATE ---
        if qid in existing_responses:
            print(f"\n[{qid}] Response exists, skipping generation")
            cur.execute(f"""
                SELECT RESPONSE_TEXT FROM {schema}.AEO_RESPONSES
                WHERE RUN_ID = {run_id} AND QUESTION_ID = '{qid}'
            """)
            response_text = cur.fetchone()[0]
        else:
            print(f"\n[{qid}] Generating ({generation_mode})...")
            t_gen = time.time()
            try:
                if generation_mode == "cortex_cli" and cc_connection:
                    prompt_text = build_prompt(qtext, domain_prompt=domain_prompt, citation=citation)
                    response_text, transcript = generate_via_cortex_cli(
                        prompt_text, model=model, connection=cc_connection
                    )
                    if self_critique:
                        critique_prompt = (
                            "You are a Snowflake documentation expert. Review and improve this answer. "
                            "Fix any inaccuracies, add missing details, and ensure it uses current Snowflake syntax.\n\n"
                            f"Question: {qtext}\n\nCurrent Answer:\n{response_text}\n\n"
                            "Provide an improved, complete answer:"
                        )
                        # Capture transcript from the self-critique pass (final turn)
                        response_text, transcript = generate_via_cortex_cli(
                            critique_prompt, model=model, connection=cc_connection
                        )
                    t_after = time.time()
                    tc = transcript.get("n_tool_calls", 0)
                    print(f"  Generated: {len(response_text)} chars in {time.time() - t_gen:.1f}s"
                          f" | turns={transcript.get('n_turns', '?')} tools={tc}")
                    # Fetch token counts from usage history (covers all turns in [t_gen, t_after])
                    cli_tokens = fetch_cli_tokens(cur, t_gen, t_after, model)
                    cli_tokens["generation_secs"] = round(t_after - t_gen, 2)
                    insert_response(cur, schema, run_id, qid, response_text)
                    insert_transcript(cur, schema, run_id, qid,
                                      transcript=transcript, usage=cli_tokens)
                else:
                    response_text, usage = generate_response(cur, model, qtext, max_tokens)
                    t_after = time.time()
                    tokens = usage.get("total_tokens", "?")
                    print(f"  Generated: {len(response_text)} chars in {time.time() - t_gen:.1f}s | tokens: {tokens}")
                    usage["generation_secs"] = round(t_after - t_gen, 2)
                    insert_response(cur, schema, run_id, qid, response_text)
                    insert_transcript(cur, schema, run_id, qid, usage=usage)
                gen_count += 1
            except Exception as e:
                print(f"  GENERATION FAILED: {e}")
                gen_errors += 1
                continue

        # --- SCORE via AEO_SCORE_RESPONSE SP ---
        if qid in existing_scores:
            print(f"  Scores exist for {qid}, skipping")
            continue

        t_score = time.time()
        try:
            panel_total, panel_mh = score_and_store_via_sp(
                cur, schema, run_id, qid, response_text, judges=judge_models
            )
            score_count += 1
            print(f"  Scored in {time.time() - t_score:.1f}s | panel={panel_total:.1f}/50 mh={panel_mh:.2f}")
        except Exception as e:
            print(f"  SCORING FAILED: {e}")
            score_errors += 1

    total_time = time.time() - t_start
    print(f"\n{'=' * 60}")
    print(f"BATCH {batch_num} COMPLETE")
    print(f"  Generated: {gen_count} | Gen errors: {gen_errors}")
    print(f"  Scored: {score_count} | Score errors: {score_errors}")
    print(f"  Total time: {total_time:.1f}s ({total_time/60:.1f} min)")
    print("=" * 60)

    conn.close()


if __name__ == "__main__":
    main()
