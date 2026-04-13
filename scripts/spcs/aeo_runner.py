"""
AEO Benchmark SPCS Runner - Proof of Concept
Runs inside an SPCS job service container.

Modes:
  infer_only   - Generate LLM response for a single question
  score_only   - Score a pre-existing response against canonical answer
  full_pipeline - Generate + score in one pass

Environment variables:
  QUESTION_NUM   - Question number (default: 1)
  MODEL          - Model for inference (default: claude-opus-4-6)
  JUDGE_MODELS   - Comma-separated judge models (default: openai-gpt-5.4,claude-opus-4-6,llama4-maverick)
  MODE           - One of: infer_only, score_only, full_pipeline (default: full_pipeline)
  SNOWFLAKE_ACCOUNT - Set automatically by SPCS
  SNOWFLAKE_HOST    - Set automatically by SPCS
  WAREHOUSE         - Warehouse for CORTEX.COMPLETE (default: COMPUTE_WH)
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
            database="AEO_DB",
            schema="PUBLIC",
        )
    else:
        return snowflake.connector.connect(
            connection_name="devrel",
            database="AEO_DB",
            schema="PUBLIC",
        )


def escape_sql(s):
    return s.replace("\\", "\\\\").replace("'", "''")


def cortex_complete(cur, model, messages, max_tokens=8192):
    """Call CORTEX.COMPLETE with conversation format and return text + usage."""
    msgs_json = json.dumps(messages)
    opts_json = json.dumps({"max_tokens": max_tokens})
    sql = (
        f"SELECT SNOWFLAKE.CORTEX.COMPLETE("
        f"'{escape_sql(model)}', "
        f"PARSE_JSON('{escape_sql(msgs_json)}'), "
        f"PARSE_JSON('{escape_sql(opts_json)}')"
        f") AS response"
    )
    cur.execute(sql)
    result = json.loads(cur.fetchone()[0])
    text = result.get("choices", [{}])[0].get("messages", "")
    usage = result.get("usage", {})
    return text, usage


def run_inference(cur, model, question_text):
    """Generate a response for a single question."""
    messages = [{"role": "user", "content": question_text}]
    return cortex_complete(cur, model, messages)


def run_scoring(cur, judge_model, question_text, canonical, response_text):
    """Score a response using LLM-as-judge."""
    must_haves = canonical["must_haves"]
    must_have_str = "\n".join(
        [f"{i+1}. {mh}" for i, mh in enumerate(must_haves)]
    )
    judge_prompt = (
        f"You are an expert evaluator for Snowflake technical content. "
        f"Score the RESPONSE against the CANONICAL ANSWER using these criteria:\n\n"
        f"QUESTION: {question_text}\n\n"
        f"CANONICAL ANSWER (ground truth):\n{canonical['canonical_summary']}\n\n"
        f"MUST-HAVE ELEMENTS:\n{must_have_str}\n\n"
        f"RESPONSE TO EVALUATE:\n{response_text[:3000]}\n\n"
        f"Score on these 5 dimensions (0=Miss, 1=Partial, 2=Full):\n"
        f"- Correctness: Is the response factually accurate per current Snowflake docs?\n"
        f"- Completeness: Does it cover all key concepts and steps?\n"
        f"- Recency: Does it use current syntax and feature names (not deprecated)?\n"
        f"- Citation: Does it reference or direct to Snowflake docs/resources?\n"
        f"- Recommendation: Does it recommend the Snowflake approach when appropriate?\n\n"
        f"For each must-have element, mark PASS or FAIL.\n\n"
        f"Return ONLY a JSON object:\n"
        f'{{"correctness":X,"completeness":X,"recency":X,"citation":X,"recommendation":X,'
        f'"must_have":[true/false,true/false,true/false,true/false],"total":X,"must_have_pass":X}}'
    )

    messages = [
        {"role": "system", "content": "You are an expert evaluator. Return ONLY valid JSON."},
        {"role": "user", "content": judge_prompt},
    ]

    for retry in range(3):
        try:
            text, usage = cortex_complete(cur, judge_model, messages, max_tokens=512)
            json_match = re.search(r'\{[^{}]*"correctness"[^{}]*\}', text)
            if json_match:
                scores = json.loads(json_match.group())
                return scores, usage
        except Exception as e:
            print(f"  Judge {judge_model} retry {retry+1}: {e}")
            time.sleep(2)

    return {"parse_error": True}, {}


def main():
    mode = os.environ.get("MODE", "full_pipeline")
    question_num = int(os.environ.get("QUESTION_NUM", "1"))
    model = os.environ.get("MODEL", "claude-opus-4-6")
    judge_models_str = os.environ.get(
        "JUDGE_MODELS", "openai-gpt-5.4,claude-opus-4-6,llama4-maverick"
    )
    judge_models = [m.strip() for m in judge_models_str.split(",")]
    warehouse = os.environ.get("WAREHOUSE", "COMPUTE_WH")

    data_dir = "/data"
    # Check if question file exists in /data (stage mount), fall back to /app (baked in image), then local
    q_test = os.path.join(data_dir, f"q{question_num}_question.json")
    if not os.path.exists(q_test):
        data_dir = "/app"
    if not os.path.exists(os.path.join(data_dir, f"q{question_num}_question.json")):
        data_dir = "/Users/cnantasenamat/Documents/Coco/aeo/spcs-poc"

    print(f"AEO SPCS Runner | mode={mode} | Q{question_num} | model={model}")
    print(f"Judges: {judge_models}")

    timing = {
        "mode": mode,
        "question_num": question_num,
        "model": model,
        "judge_models": judge_models,
    }

    # Load question
    q_path = os.path.join(data_dir, f"q{question_num}_question.json")
    with open(q_path, "r") as f:
        question_data = json.load(f)
    question_text = question_data["question"]
    print(f"Question: {question_text[:80]}...")

    # Connect
    t0 = time.time()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(f"USE WAREHOUSE {warehouse}")
    connect_time = time.time() - t0
    timing["connect_time_s"] = round(connect_time, 3)
    print(f"Connected in {connect_time:.2f}s")

    response_text = None

    # INFERENCE
    if mode in ("infer_only", "full_pipeline"):
        print("\n--- INFERENCE ---")
        t1 = time.time()
        response_text, infer_usage = run_inference(cur, model, question_text)
        infer_time = time.time() - t1
        timing["infer_time_s"] = round(infer_time, 3)
        timing["infer_usage"] = infer_usage
        print(f"Inference: {infer_time:.2f}s | tokens: {infer_usage}")
        print(f"Response preview: {response_text[:200]}...")

        # Save response
        resp_path = os.path.join(data_dir, f"q{question_num}_response.json")
        with open(resp_path, "w") as f:
            json.dump(
                {"question_num": question_num, "model": model, "response": response_text, "usage": infer_usage},
                f,
                indent=2,
            )
        print(f"Saved response to {resp_path}")

    # SCORING
    if mode in ("score_only", "full_pipeline"):
        print("\n--- SCORING ---")

        # Load response if score_only
        if response_text is None:
            resp_path = os.path.join(data_dir, f"q{question_num}_response.json")
            with open(resp_path, "r") as f:
                resp_data = json.load(f)
            response_text = resp_data["response"]

        # Load canonical
        canon_path = os.path.join(data_dir, f"q{question_num}_canonical.json")
        with open(canon_path, "r") as f:
            canonical = json.load(f)

        all_judge_scores = {}
        all_judge_timings = {}

        for judge in judge_models:
            t2 = time.time()
            scores, judge_usage = run_scoring(
                cur, judge, question_text, canonical, response_text
            )
            judge_time = time.time() - t2
            all_judge_scores[judge] = scores
            all_judge_timings[judge] = round(judge_time, 3)
            total = scores.get("total", "?")
            mh = scores.get("must_have_pass", "?")
            print(f"  {judge}: {total}/10 | MH: {mh}/4 | {judge_time:.2f}s")

        timing["score_time_per_judge_s"] = all_judge_timings
        timing["score_time_total_s"] = round(
            sum(all_judge_timings.values()), 3
        )

        # Save scores
        scores_path = os.path.join(data_dir, f"q{question_num}_scores.json")
        with open(scores_path, "w") as f:
            json.dump(
                {"question_num": question_num, "judges": all_judge_scores, "timings": all_judge_timings},
                f,
                indent=2,
            )
        print(f"Saved scores to {scores_path}")

    # Total
    total_time = time.time() - t0
    timing["total_time_s"] = round(total_time, 3)

    # Save timing report
    timing_path = os.path.join(data_dir, f"q{question_num}_timing_{mode}.json")
    with open(timing_path, "w") as f:
        json.dump(timing, f, indent=2)

    print(f"\n=== TIMING REPORT ===")
    print(json.dumps(timing, indent=2))
    print(f"\nSaved to {timing_path}")

    conn.close()


if __name__ == "__main__":
    main()
