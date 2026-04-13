"""
End-to-end verification test for the AEO TruLens pipeline.

Tests the full flow:
  1. Generate a response via CORTEX.COMPLETE
  2. Score it with the judge panel (single judge for speed)
  3. Store results in Snowflake tables
  4. Query results back via SQL views
  5. Verify data integrity
"""
import json
import sys
sys.path.insert(0, "/Users/cnantasenamat/Documents/Coco/aeo/observability")

import snowflake.connector
from aeo_data import QUESTIONS, CANONICAL_SUMMARIES, MUST_HAVES
from aeo_feedback_functions import score_full_rubric

TEST_RUN_ID = 999  # Use a high ID to avoid conflicts
TEST_QUESTION_IDS = [1, 13]  # Two questions for quick test
JUDGE = "claude-opus-4-6"
MODEL = "claude-opus-4-6"

print("=" * 60)
print("AEO TruLens Pipeline: End-to-End Verification")
print("=" * 60)

# Connect
conn = snowflake.connector.connect(connection_name="devrel")
cur = conn.cursor()
cur.execute("USE WAREHOUSE COMPUTE_WH")
cur.execute("USE DATABASE AEO_OBSERVABILITY")
cur.execute("USE SCHEMA EVAL_SCHEMA")

# Clean up any previous test data
cur.execute(f"DELETE FROM AEO_RUNS WHERE RUN_ID = {TEST_RUN_ID}")
cur.execute(f"DELETE FROM AEO_SCORES WHERE RUN_ID = {TEST_RUN_ID}")
cur.execute(f"DELETE FROM AEO_RESPONSES WHERE RUN_ID = {TEST_RUN_ID}")

# Step 1: Generate responses
print("\n[1/5] Generating responses...")
responses = {}
for q_id in TEST_QUESTION_IDS:
    question = QUESTIONS[q_id]
    messages = json.dumps([{"role": "user", "content": question}])
    options = json.dumps({"max_tokens": 2048})

    cur.execute(f"""
        SELECT SNOWFLAKE.CORTEX.COMPLETE(
            '{MODEL}',
            PARSE_JSON($${messages}$$),
            PARSE_JSON('{options}')
        ) AS response
    """)
    row = cur.fetchone()
    raw = row[0]
    resp = json.loads(raw) if isinstance(raw, str) else raw
    if isinstance(resp, dict) and "choices" in resp:
        text = resp["choices"][0].get("messages", str(resp))
    elif isinstance(resp, dict) and "messages" in resp:
        text = resp["messages"]
    else:
        text = str(resp)
    responses[q_id] = text
    print(f"  Q{q_id:02d}: {len(text)} chars generated")

# Step 2: Score responses
print("\n[2/5] Scoring with judge...")
scores = {}
for q_id in TEST_QUESTION_IDS:
    result = score_full_rubric(
        conn, JUDGE, QUESTIONS[q_id], responses[q_id],
        CANONICAL_SUMMARIES[q_id], MUST_HAVES[q_id],
    )
    scores[q_id] = result
    print(f"  Q{q_id:02d}: total={result['total']}/10, mh={result['must_have_pass']}/4")

# Step 3: Store in Snowflake
print("\n[3/5] Storing in Snowflake tables...")

# Run metadata
cur.execute(
    """INSERT INTO AEO_RUNS (RUN_ID, RUN_DATE, DESCRIPTION,
        DOMAIN_PROMPT, CITATION, AGENTIC, SELF_CRITIQUE, MODEL)
    VALUES (%s, CURRENT_TIMESTAMP(), %s, %s, %s, %s, %s, %s)""",
    (TEST_RUN_ID, "E2E verification test", False, False, False, False, MODEL),
)

# Responses
for q_id, text in responses.items():
    cur.execute(
        "INSERT INTO AEO_RESPONSES (RUN_ID, QUESTION_ID, RESPONSE_TEXT) VALUES (%s, %s, %s)",
        (TEST_RUN_ID, f"Q{q_id:02d}", text),
    )

# Scores (as panel_avg since we used single judge)
for q_id, result in scores.items():
    mh = result.get("must_have", [False, False, False, False])
    cur.execute(
        """INSERT INTO AEO_SCORES (RUN_ID, QUESTION_ID, JUDGE_MODEL,
            CORRECTNESS, COMPLETENESS, RECENCY, CITATION, RECOMMENDATION,
            TOTAL_SCORE, MUST_HAVE_1, MUST_HAVE_2, MUST_HAVE_3, MUST_HAVE_4,
            MUST_HAVE_PASS)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (
            TEST_RUN_ID, f"Q{q_id:02d}", "panel_avg",
            result["correctness"], result["completeness"], result["recency"],
            result["citation"], result["recommendation"], result["total"],
            mh[0] if len(mh) > 0 else False,
            mh[1] if len(mh) > 1 else False,
            mh[2] if len(mh) > 2 else False,
            mh[3] if len(mh) > 3 else False,
            result["must_have_pass"],
        ),
    )
print("  Stored run metadata, responses, and scores.")

# Step 4: Query back via views
print("\n[4/5] Querying results back...")

cur.execute(f"SELECT COUNT(*) FROM AEO_RUNS WHERE RUN_ID = {TEST_RUN_ID}")
run_count = cur.fetchone()[0]

cur.execute(f"SELECT COUNT(*) FROM AEO_RESPONSES WHERE RUN_ID = {TEST_RUN_ID}")
resp_count = cur.fetchone()[0]

cur.execute(f"SELECT COUNT(*) FROM AEO_SCORES WHERE RUN_ID = {TEST_RUN_ID}")
score_count = cur.fetchone()[0]

cur.execute(f"""
    SELECT QUESTION_ID, TOTAL_SCORE, MUST_HAVE_PASS
    FROM AEO_SCORES
    WHERE RUN_ID = {TEST_RUN_ID} AND JUDGE_MODEL = 'panel_avg'
    ORDER BY QUESTION_ID
""")
stored_scores = cur.fetchall()

print(f"  AEO_RUNS:      {run_count} row(s)")
print(f"  AEO_RESPONSES: {resp_count} row(s)")
print(f"  AEO_SCORES:    {score_count} row(s)")
print(f"  Stored scores:")
for row in stored_scores:
    print(f"    {row[0]}: total={row[1]}, mh={row[2]}")

# Step 5: Verify data integrity
print("\n[5/5] Verifying data integrity...")
checks_passed = 0
checks_total = 0

# Check 1: Row counts
checks_total += 1
if run_count == 1 and resp_count == len(TEST_QUESTION_IDS) and score_count == len(TEST_QUESTION_IDS):
    checks_passed += 1
    print("  PASS: Row counts match expected")
else:
    print(f"  FAIL: Row counts - runs={run_count}, responses={resp_count}, scores={score_count}")

# Check 2: Scores match what we computed
checks_total += 1
all_match = True
for row in stored_scores:
    q_id_str = row[0]  # e.g., "Q01"
    q_id = int(q_id_str[1:])
    stored_total = float(row[1])
    expected_total = float(scores[q_id]["total"])
    if abs(stored_total - expected_total) > 0.01:
        print(f"  FAIL: {q_id_str} stored={stored_total} vs computed={expected_total}")
        all_match = False
if all_match:
    checks_passed += 1
    print("  PASS: Stored scores match computed scores")

# Check 3: Questions table has data
checks_total += 1
cur.execute("SELECT COUNT(*) FROM AEO_QUESTIONS")
q_count = cur.fetchone()[0]
if q_count == 50:
    checks_passed += 1
    print("  PASS: AEO_QUESTIONS has 50 rows")
else:
    print(f"  FAIL: AEO_QUESTIONS has {q_count} rows (expected 50)")

# Check 4: Views compile
checks_total += 1
views_ok = True
for view in ["V_AEO_LEADERBOARD", "V_AEO_FACTORIAL_EFFECTS",
             "V_AEO_PER_QUESTION_HEATMAP", "V_AEO_JUDGE_AGREEMENT"]:
    try:
        cur.execute(f"SELECT * FROM {view} LIMIT 1")
        cur.fetchall()
    except Exception as e:
        print(f"  FAIL: View {view} error: {e}")
        views_ok = False
if views_ok:
    checks_passed += 1
    print("  PASS: All 4 SQL views compile and execute")

# Clean up test data
cur.execute(f"DELETE FROM AEO_RUNS WHERE RUN_ID = {TEST_RUN_ID}")
cur.execute(f"DELETE FROM AEO_SCORES WHERE RUN_ID = {TEST_RUN_ID}")
cur.execute(f"DELETE FROM AEO_RESPONSES WHERE RUN_ID = {TEST_RUN_ID}")

print(f"\n{'=' * 60}")
print(f"VERIFICATION RESULT: {checks_passed}/{checks_total} checks passed")
if checks_passed == checks_total:
    print("ALL CHECKS PASSED - Pipeline is operational.")
else:
    print(f"WARNING: {checks_total - checks_passed} check(s) failed.")
print(f"{'=' * 60}")

cur.close()
conn.close()
