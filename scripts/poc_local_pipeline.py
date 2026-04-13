"""
POC: Local eval pipeline with profile system and TruLens dual-write.
Generates 2 responses, scores them via TruLens feedback functions,
dual-writes to AEO_SCORES + TruLens tables, verifies, cleans up.

v1: 128 questions from Snowflake, 1-10 scoring scale (max 50/question),
    string question IDs ("Q001"-"Q128"), 5 must-haves (ratio 0.0-1.0).
    TruLens is the primary scoring framework; AEO_SCORES is dual-written.
"""
import sys
import json

sys.path.insert(0, "/Users/cnantasenamat/Documents/Coco/aeo/observability")

from aeo_run_orchestrator import (
    get_connection, store_run_metadata, store_responses, store_scores,
    CONNECTION_PROFILES,
)
from aeo_data import QUESTIONS, CANONICAL_SUMMARIES, MUST_HAVES, load_from_snowflake
from aeo_feedback_functions import score_with_panel_and_trulens, clear_score_cache

POC_RUN_ID = 998

print("=== POC: Local Eval Pipeline with Profile System ===")
print()

for name, cfg in CONNECTION_PROFILES.items():
    print(f"Profile [{name}]: {cfg['connection_name']} -> {cfg['database']}.{cfg['schema']}")
print()

# Step 1: Connect (also loads question data from Snowflake)
print("[1/4] Connecting with devrel profile...")
conn = get_connection(profile="devrel")
print(f"  OK — {len(QUESTIONS)} questions loaded")

# Step 2: Generate 2 responses (first two questions by sorted ID)
poc_qids = sorted(QUESTIONS.keys())[:2]
print(f"[2/4] Generating responses for {', '.join(poc_qids)}...")
cur = conn.cursor()
responses = {}
for qid in poc_qids:
    messages_json = json.dumps([{"role": "user", "content": QUESTIONS[qid]}])
    options_json = json.dumps({"max_tokens": 1024})
    sql = f"""
        SELECT SNOWFLAKE.CORTEX.COMPLETE(
            'claude-opus-4-6',
            PARSE_JSON($${messages_json}$$),
            PARSE_JSON('{options_json}')
        ) AS response
    """
    cur.execute(sql)
    row = cur.fetchone()
    raw = row[0]
    resp = json.loads(raw) if isinstance(raw, str) else raw
    if isinstance(resp, dict) and "choices" in resp:
        text = resp["choices"][0].get("messages", str(resp))
    elif isinstance(resp, dict) and "messages" in resp:
        text = resp["messages"]
    else:
        text = str(resp)
    responses[qid] = text
    print(f"  {qid}: {len(text)} chars")
cur.close()

# Step 3: Score with single judge (POC speed) + TruLens dual-write
print("[3/4] Scoring with single judge + TruLens (claude-opus-4-6)...")
scores = {}
for qid in poc_qids:
    result = score_with_panel_and_trulens(
        conn, QUESTIONS[qid], responses[qid],
        CANONICAL_SUMMARIES[qid], MUST_HAVES[qid],
        judges=["claude-opus-4-6"],
    )
    scores[qid] = result
    avg = result["panel_avg"]
    tl = result["trulens"]
    print(f"  {qid}: total={avg['total']:.1f}/50, mh={avg['must_have_pass']:.2f}, tl_total={tl['aeo_total_score']:.3f}")
    clear_score_cache()

# Step 4: Store and verify
print(f"[4/4] Storing in Snowflake (run_id={POC_RUN_ID})...")
cur = conn.cursor()
cur.execute(f"DELETE FROM AEO_RUNS WHERE RUN_ID = {POC_RUN_ID}")
cur.execute(f"DELETE FROM AEO_RESPONSES WHERE RUN_ID = {POC_RUN_ID}")
cur.execute(f"DELETE FROM AEO_SCORES WHERE RUN_ID = {POC_RUN_ID}")
cur.close()

store_run_metadata(conn, POC_RUN_ID, "POC: local eval pipeline test", {
    "domain_prompt": False, "citation": False, "agentic": False,
    "self_critique": False, "model": "claude-opus-4-6",
})
store_responses(conn, POC_RUN_ID, responses)
store_scores(conn, POC_RUN_ID, scores)

cur = conn.cursor()
cur.execute(f"SELECT COUNT(*) FROM AEO_RUNS WHERE RUN_ID = {POC_RUN_ID}")
print(f"  AEO_RUNS: {cur.fetchone()[0]} row(s)")
cur.execute(f"SELECT COUNT(*) FROM AEO_RESPONSES WHERE RUN_ID = {POC_RUN_ID}")
print(f"  AEO_RESPONSES: {cur.fetchone()[0]} row(s)")
cur.execute(f"SELECT COUNT(*) FROM AEO_SCORES WHERE RUN_ID = {POC_RUN_ID}")
print(f"  AEO_SCORES: {cur.fetchone()[0]} row(s)")

# Clean up
cur.execute(f"DELETE FROM AEO_RUNS WHERE RUN_ID = {POC_RUN_ID}")
cur.execute(f"DELETE FROM AEO_RESPONSES WHERE RUN_ID = {POC_RUN_ID}")
cur.execute(f"DELETE FROM AEO_SCORES WHERE RUN_ID = {POC_RUN_ID}")
cur.close()
conn.close()

print()
print("=== POC COMPLETE ===")
print("Pipeline runs locally: generate -> score -> store -> verify")
print()
print("To run against Snowhouse production:")
print("  python3 aeo_run_orchestrator.py --run-id 100 --mode baseline --profile snowhouse")
