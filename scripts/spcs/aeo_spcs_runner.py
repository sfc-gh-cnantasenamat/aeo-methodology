"""
AEO Benchmark SPCS Runner v2 - Table-based I/O
Runs inside an SPCS job service container. Reads questions from and writes
responses/scores to Snowflake tables in a configurable schema.

Environment variables:
  BATCH_NUM      - Batch number 1-8 (each batch = 16 questions)
  MODEL          - Model for inference (default: claude-opus-4-6)
  JUDGE_MODELS   - Comma-separated judge models
  WAREHOUSE      - Warehouse for CORTEX.COMPLETE (default: COMPUTE_WH)
  RUN_SCHEMA     - Fully qualified schema (default: AEO_OBSERVABILITY.SPCS_EVAL)
  RUN_ID         - Run ID (default: 1)
  MAX_TOKENS     - Max tokens for inference (default: 8192)
"""
import json
import os
import re
import time
import snowflake.connector


def get_connection():
    """Connect to Snowflake using SPCS OAuth token or local connection."""
    token_path = "/snowflake/session/token"
    if os.path.exists(token_path):
        with open(token_path, "r") as f:
            token = f.read().strip()
        return snowflake.connector.connect(
            host=os.environ["SNOWFLAKE_HOST"],
            account=os.environ["SNOWFLAKE_ACCOUNT"],
            token=token,
            authenticator="oauth",
        )
    else:
        return snowflake.connector.connect(connection_name="devrel")


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
    """Get (question_id, judge_model) pairs that already have scores."""
    batch_start = f"Q{((batch_num - 1) * 16 + 1):03d}"
    batch_end = f"Q{(batch_num * 16):03d}"
    cur.execute(f"""
        SELECT QUESTION_ID, JUDGE_MODEL FROM {schema}.AEO_SCORES
        WHERE RUN_ID = {run_id}
        AND QUESTION_ID >= '{batch_start}' AND QUESTION_ID <= '{batch_end}'
    """)
    return {(row[0], row[1]) for row in cur.fetchall()}


def generate_response(cur, model, question_text, max_tokens):
    """Generate a response for a single question."""
    messages = [{"role": "user", "content": question_text}]
    return cortex_complete(cur, model, messages, max_tokens=max_tokens)


def insert_response(cur, schema, run_id, question_id, response_text):
    """Insert a generated response into the table."""
    cur.execute(f"""
        INSERT INTO {schema}.AEO_RESPONSES (RUN_ID, QUESTION_ID, RESPONSE_TEXT, GENERATED_AT)
        VALUES (%s, %s, %s, CURRENT_TIMESTAMP())
    """, (run_id, question_id, response_text))


def score_response(cur, judge_model, question_text, canonical_answer,
                   must_haves, response_text):
    """Score a response using LLM-as-judge. Returns parsed scores dict."""
    mh_list = "\n".join(
        f"{i+1}. {mh}" for i, mh in enumerate(must_haves) if mh
    )
    mh_count = sum(1 for mh in must_haves if mh)

    judge_prompt = (
        f"You are an expert evaluator for Snowflake technical content. "
        f"Score the RESPONSE against the CANONICAL ANSWER.\n\n"
        f"QUESTION: {question_text}\n\n"
        f"CANONICAL ANSWER (ground truth):\n{canonical_answer[:3000]}\n\n"
        f"MUST-HAVE ELEMENTS:\n{mh_list}\n\n"
        f"RESPONSE TO EVALUATE:\n{response_text[:3000]}\n\n"
        f"Score on these 5 dimensions (each 1-10):\n"
        f"- Correctness: Are the technical facts accurate?\n"
        f"- Completeness: Does it cover all key aspects from the canonical answer?\n"
        f"- Recency: Does it use current Snowflake features and syntax?\n"
        f"- Citation: Does it reference official docs or authoritative sources?\n"
        f"- Recommendation: Does it suggest Snowflake-native best practices?\n\n"
        f"For each must-have element (1-{mh_count}), mark PASS (true) or FAIL (false).\n\n"
        f"Return ONLY a JSON object:\n"
        f'{{"correctness":X,"completeness":X,"recency":X,"citation":X,"recommendation":X,'
        f'"must_have":[true/false,...],"total":X,"must_have_pass":X}}'
    )

    messages = [
        {"role": "system", "content": "You are an expert evaluator. Return ONLY valid JSON."},
        {"role": "user", "content": judge_prompt},
    ]

    text, usage = cortex_complete(cur, judge_model, messages, max_tokens=1024)
    json_match = re.search(r'\{[^{}]*"correctness"[^{}]*\}', text)
    if json_match:
        return json.loads(json_match.group()), text
    return None, text


def insert_score(cur, schema, run_id, question_id, judge_model, scores, raw_text):
    """Insert a judge score into the table."""
    if scores is None:
        scores = {}

    must_have = scores.get("must_have", [])
    mh1 = must_have[0] if len(must_have) > 0 else False
    mh2 = must_have[1] if len(must_have) > 1 else False
    mh3 = must_have[2] if len(must_have) > 2 else False
    mh4 = must_have[3] if len(must_have) > 3 else False
    mh5 = must_have[4] if len(must_have) > 4 else False

    cur.execute(f"""
        INSERT INTO {schema}.AEO_SCORES
        (RUN_ID, QUESTION_ID, JUDGE_MODEL, CORRECTNESS, COMPLETENESS, RECENCY,
         CITATION, RECOMMENDATION, TOTAL_SCORE, MUST_HAVE_1, MUST_HAVE_2,
         MUST_HAVE_3, MUST_HAVE_4, MUST_HAVE_5, MUST_HAVE_PASS,
         RAW_JUDGE_RESPONSE, SCORED_AT)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP())
    """, (
        run_id, question_id, judge_model,
        scores.get("correctness"), scores.get("completeness"),
        scores.get("recency"), scores.get("citation"),
        scores.get("recommendation"), scores.get("total"),
        mh1, mh2, mh3, mh4, mh5,
        scores.get("must_have_pass"),
        (raw_text or "")[:8000],
    ))


def main():
    batch_num = int(os.environ.get("BATCH_NUM", "1"))
    model = os.environ.get("MODEL", "claude-opus-4-6")
    judge_models_str = os.environ.get(
        "JUDGE_MODELS", "openai-gpt-5.4,claude-opus-4-6,llama4-maverick"
    )
    judge_models = [m.strip() for m in judge_models_str.split(",")]
    warehouse = os.environ.get("WAREHOUSE", "COMPUTE_WH")
    schema = os.environ.get("RUN_SCHEMA", "AEO_OBSERVABILITY.SPCS_EVAL")
    run_id = int(os.environ.get("RUN_ID", "1"))
    max_tokens = int(os.environ.get("MAX_TOKENS", "8192"))

    batch_start = f"Q{((batch_num - 1) * 16 + 1):03d}"
    batch_end = f"Q{(batch_num * 16):03d}"

    print(f"=" * 60)
    print(f"AEO SPCS Runner v2 | Batch {batch_num} ({batch_start}-{batch_end})")
    print(f"Model: {model} | Judges: {judge_models}")
    print(f"Schema: {schema} | Run ID: {run_id}")
    print(f"=" * 60)

    t_start = time.time()

    # Connect
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(f"USE WAREHOUSE {warehouse}")
    print(f"Connected in {time.time() - t_start:.2f}s")

    # Load questions for this batch
    questions = load_questions(cur, schema, batch_num)
    print(f"Loaded {len(questions)} questions for batch {batch_num}")

    # Check existing responses (idempotent)
    existing_responses = get_existing_responses(cur, schema, run_id, batch_num)
    existing_scores = get_existing_scores(cur, schema, run_id, batch_num)

    gen_count = 0
    gen_errors = 0
    score_count = 0
    score_errors = 0

    for q in questions:
        qid = q["QUESTION_ID"]
        qtext = q["QUESTION_TEXT"]
        canonical = q["CANONICAL_ANSWER"]
        must_haves = [q.get(f"MUST_HAVE_{i}") for i in range(1, 6)]

        # --- GENERATE ---
        if qid in existing_responses:
            print(f"\n[{qid}] Response exists, skipping generation")
            # Still need to fetch the response text for scoring
            cur.execute(f"""
                SELECT RESPONSE_TEXT FROM {schema}.AEO_RESPONSES
                WHERE RUN_ID = {run_id} AND QUESTION_ID = '{qid}'
            """)
            response_text = cur.fetchone()[0]
        else:
            print(f"\n[{qid}] Generating response...")
            t_gen = time.time()
            try:
                response_text, usage = generate_response(cur, model, qtext, max_tokens)
                insert_response(cur, schema, run_id, qid, response_text)
                gen_count += 1
                tokens = usage.get("total_tokens", "?")
                print(f"  Generated in {time.time() - t_gen:.1f}s | tokens: {tokens}")
            except Exception as e:
                print(f"  GENERATION FAILED: {e}")
                gen_errors += 1
                continue

        # --- SCORE ---
        for judge in judge_models:
            if (qid, judge) in existing_scores:
                print(f"  [{qid}] Score by {judge} exists, skipping")
                continue

            t_score = time.time()
            try:
                scores, raw_text = score_response(
                    cur, judge, qtext, canonical, must_haves, response_text
                )
                insert_score(cur, schema, run_id, qid, judge, scores, raw_text)
                score_count += 1
                total = scores.get("total", "?") if scores else "parse_err"
                print(f"  {judge}: {total}/50 | {time.time() - t_score:.1f}s")
            except Exception as e:
                print(f"  SCORING FAILED ({judge}): {e}")
                score_errors += 1

    total_time = time.time() - t_start
    print(f"\n{'=' * 60}")
    print(f"BATCH {batch_num} COMPLETE")
    print(f"  Generated: {gen_count} | Gen errors: {gen_errors}")
    print(f"  Scored: {score_count} | Score errors: {score_errors}")
    print(f"  Total time: {total_time:.1f}s ({total_time/60:.1f} min)")
    print(f"{'=' * 60}")

    conn.close()


if __name__ == "__main__":
    main()
