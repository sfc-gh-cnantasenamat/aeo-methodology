"""
End-to-end verification test for the AEO TruLens pipeline on Snowhouse.

Tests the full flow against DEVREL.CNANTASENAMAT_DEV:
  1. Generate a response via CORTEX.COMPLETE
  2. Score it with the judge panel (single judge for speed)
  3. Store results in Snowflake tables
  4. Query results back via SQL views
  5. Verify data integrity
  6. Clean up test data

Connection: my-snowflake (SFCOGSOPS-SNOWHOUSE)
Role:       DEVREL_INGEST_RL
Warehouse:  SNOWADHOC
Schema:     DEVREL.CNANTASENAMAT_DEV
"""
import json
import sys
sys.path.insert(0, "/Users/cnantasenamat/Documents/Coco/aeo/observability")

import snowflake.connector
from aeo_data import QUESTIONS, CANONICAL_SUMMARIES, MUST_HAVES, load_from_snowflake
from aeo_feedback_functions import score_full_rubric

TEST_RUN_ID = 999
TEST_QUESTION_IDS = ["Q001", "Q002"]
JUDGE = "claude-opus-4-6"
MODEL = "claude-opus-4-6"

print("=" * 60)
print("AEO TruLens Pipeline: E2E Verification (Snowhouse)")
print("=" * 60)

# Connect
conn = snowflake.connector.connect(connection_name="my-snowflake")
cur = conn.cursor()
cur.execute("USE ROLE DEVREL_INGEST_RL")
cur.execute("USE WAREHOUSE SNOWADHOC")
cur.execute("USE DATABASE DEVREL")
cur.execute("USE SCHEMA CNANTASENAMAT_DEV")

# Load question data from Snowflake
print("\nLoading question bank from Snowflake...")
load_from_snowflake(conn, schema="DEVREL.CNANTASENAMAT_DEV")

# Clean up any previous test data
cur.execute("DELETE FROM AEO_RUNS WHERE RUN_ID = %s", (TEST_RUN_ID,))
cur.execute("DELETE FROM AEO_RUN_CONFIG WHERE RUN_ID = %s", (TEST_RUN_ID,))
cur.execute("DELETE FROM AEO_RESPONSES WHERE RUN_ID = %s", (TEST_RUN_ID,))
cur.execute("DELETE FROM AEO_SCORES WHERE RUN_ID = %s", (TEST_RUN_ID,))

# Step 1: Generate responses
print("\n[1/5] Generating responses...")
responses = {}
for qid in TEST_QUESTION_IDS:
    question = QUESTIONS[qid]
    messages_json = json.dumps([{"role": "user", "content": question}])
    options_json = json.dumps({"max_tokens": 2048})

    cur.execute(
        "SELECT SNOWFLAKE.CORTEX.COMPLETE(%s, PARSE_JSON(%s), PARSE_JSON(%s)) AS response",
        (MODEL, messages_json, options_json),
    )
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
    print(f"  {qid}: {len(text)} chars generated")

# Step 2: Score responses
print("\n[2/5] Scoring with judge...")
scores = {}
for qid in TEST_QUESTION_IDS:
    must_haves = MUST_HAVES.get(qid, [])
    result = score_full_rubric(
        conn, JUDGE, QUESTIONS[qid], responses[qid],
        CANONICAL_SUMMARIES[qid], must_haves,
    )
    scores[qid] = result
    print(f"  {qid}: total={result['total']}/50, mh={result['must_have_pass']:.2f}")

# Step 3: Store in Snowflake
print("\n[3/5] Storing in Snowflake tables...")

cur.execute(
    """INSERT INTO AEO_RUNS
        (RUN_ID, RUN_DATE, DESCRIPTION, DOMAIN_PROMPT, CITATION, AGENTIC, SELF_CRITIQUE, MODEL)
       VALUES (%s, CURRENT_TIMESTAMP(), %s, %s, %s, %s, %s, %s)""",
    (TEST_RUN_ID, "E2E verification test (Snowhouse)", False, False, False, False, MODEL),
)

cur.execute(
    """INSERT INTO AEO_RUN_CONFIG
        (RUN_ID, MODEL, DOMAIN_PROMPT, CITE, JUDGE_MODELS, MAX_TOKENS, STATUS)
       VALUES (%s, %s, %s, %s, %s, %s, %s)""",
    (TEST_RUN_ID, MODEL, False, False, JUDGE, 2048, "COMPLETE"),
)

for qid, text in responses.items():
    cur.execute(
        "INSERT INTO AEO_RESPONSES (RUN_ID, QUESTION_ID, RESPONSE_TEXT) VALUES (%s, %s, %s)",
        (TEST_RUN_ID, qid, text),
    )

for qid, result in scores.items():
    mh = result.get("must_have", [False] * 5)
    while len(mh) < 5:
        mh.append(False)
    cur.execute(
        """INSERT INTO AEO_SCORES
            (RUN_ID, QUESTION_ID, JUDGE_MODEL,
             CORRECTNESS, COMPLETENESS, RECENCY, CITATION, RECOMMENDATION,
             TOTAL_SCORE, MUST_HAVE_1, MUST_HAVE_2, MUST_HAVE_3, MUST_HAVE_4,
             MUST_HAVE_PASS, MUST_HAVE_5)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (
            TEST_RUN_ID, qid, JUDGE,
            result["correctness"], result["completeness"], result["recency"],
            result["citation"], result["recommendation"], result["total"],
            mh[0], mh[1], mh[2], mh[3], result["must_have_pass"], mh[4],
        ),
    )
print("  Stored run metadata, config, responses, and scores.")

# Step 4: Query back via views
print("\n[4/5] Querying results back...")

cur.execute("SELECT COUNT(*) FROM AEO_RUNS WHERE RUN_ID = %s", (TEST_RUN_ID,))
run_count = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM AEO_RESPONSES WHERE RUN_ID = %s", (TEST_RUN_ID,))
resp_count = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM AEO_SCORES WHERE RUN_ID = %s", (TEST_RUN_ID,))
score_count = cur.fetchone()[0]

cur.execute(
    "SELECT QUESTION_ID, TOTAL_SCORE, MUST_HAVE_PASS FROM AEO_SCORES WHERE RUN_ID = %s ORDER BY QUESTION_ID",
    (TEST_RUN_ID,),
)
stored_scores = cur.fetchall()

print(f"  AEO_RUNS:       {run_count} row(s)")
print(f"  AEO_RESPONSES:  {resp_count} row(s)")
print(f"  AEO_SCORES:     {score_count} row(s)")
for row in stored_scores:
    print(f"    {row[0]}: total={row[1]}, mh={row[2]:.2f}")

# Step 5: Verify data integrity
print("\n[5/5] Verifying data integrity...")
checks_passed = 0
checks_total = 0

# Check 1: Row counts
checks_total += 1
expected = len(TEST_QUESTION_IDS)
if run_count == 1 and resp_count == expected and score_count == expected:
    checks_passed += 1
    print("  PASS: Row counts match expected")
else:
    print(f"  FAIL: Row counts - runs={run_count}, responses={resp_count}, scores={score_count} (expected 1/{expected}/{expected})")

# Check 2: Stored scores match computed scores
checks_total += 1
all_match = True
for row in stored_scores:
    qid = row[0]
    stored_total = float(row[1])
    expected_total = float(scores[qid]["total"])
    if abs(stored_total - expected_total) > 0.01:
        print(f"  FAIL: {qid} stored={stored_total} vs computed={expected_total}")
        all_match = False
if all_match:
    checks_passed += 1
    print("  PASS: Stored scores match computed scores")

# Check 3: AEO_QUESTIONS has 128 rows
checks_total += 1
cur.execute("SELECT COUNT(*) FROM AEO_QUESTIONS")
q_count = cur.fetchone()[0]
if q_count == 128:
    checks_passed += 1
    print("  PASS: AEO_QUESTIONS has 128 rows")
else:
    print(f"  FAIL: AEO_QUESTIONS has {q_count} rows (expected 128)")

# Check 4: Views compile and execute
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
cur.execute("DELETE FROM AEO_RUNS WHERE RUN_ID = %s", (TEST_RUN_ID,))
cur.execute("DELETE FROM AEO_RUN_CONFIG WHERE RUN_ID = %s", (TEST_RUN_ID,))
cur.execute("DELETE FROM AEO_RESPONSES WHERE RUN_ID = %s", (TEST_RUN_ID,))
cur.execute("DELETE FROM AEO_SCORES WHERE RUN_ID = %s", (TEST_RUN_ID,))
print("\n  Test data cleaned up.")

print(f"\n{'=' * 60}")
print(f"VERIFICATION RESULT: {checks_passed}/{checks_total} checks passed")
if checks_passed == checks_total:
    print("ALL CHECKS PASSED - Snowhouse pipeline is operational.")
else:
    print(f"WARNING: {checks_total - checks_passed} check(s) failed.")
print(f"{'=' * 60}")

cur.close()
conn.close()
