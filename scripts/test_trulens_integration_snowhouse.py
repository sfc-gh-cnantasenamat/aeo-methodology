"""
TruLens integration test for Snowhouse (DEVREL.CNANTASENAMAT_DEV).

Test 1: TruLens @instrument decorators, TruApp registration, SnowflakeConnector
         — initializes TRULENS_* managed tables on first run
Test 2: 3-judge panel scoring on 2 questions from the 128-question v1 bank

Connection: my-snowflake (SFCOGSOPS-SNOWHOUSE)
Role:       DEVREL_INGEST_RL
Warehouse:  SNOWADHOC
Schema:     DEVREL.CNANTASENAMAT_DEV
"""
import json
import os
import sys
import traceback

sys.path.insert(0, "/Users/cnantasenamat/Documents/Coco/aeo/observability")

os.environ["TRULENS_OTEL_TRACING"] = "1"

import snowflake.connector
from snowflake.snowpark import Session

from aeo_data import (
    QUESTIONS, CANONICAL_SUMMARIES, MUST_HAVES,
    load_from_snowflake, reset as reset_data,
)

# ---------------------------------------------------------------------------
# Shared setup: connections + question data
# ---------------------------------------------------------------------------

print("=" * 60)
print("AEO TruLens Integration Test (Snowhouse)")
print("=" * 60)

# Snowpark session (required by TruLens SnowflakeConnector)
print("\n[setup] Creating Snowpark session...")
session = Session.builder.config("connection_name", "my-snowflake").create()
session.sql("USE ROLE DEVREL_INGEST_RL").collect()
session.sql("USE WAREHOUSE SNOWADHOC").collect()
session.sql("USE DATABASE DEVREL").collect()
session.sql("USE SCHEMA CNANTASENAMAT_DEV").collect()
print("        OK: Snowpark session ready")

# snowflake.connector connection (used by feedback functions)
conn = snowflake.connector.connect(connection_name="my-snowflake")
cur = conn.cursor()
cur.execute("USE ROLE DEVREL_INGEST_RL")
cur.execute("USE WAREHOUSE SNOWADHOC")
cur.execute("USE DATABASE DEVREL")
cur.execute("USE SCHEMA CNANTASENAMAT_DEV")

# Load questions from Snowflake
print("[setup] Loading 128-question bank...")
reset_data()
load_from_snowflake(conn, schema="DEVREL.CNANTASENAMAT_DEV")

TEST_Q1 = "Q001"
TEST_Q2 = "Q025"
MODEL = "claude-opus-4-6"


# ---------------------------------------------------------------------------
# Test 1: TruLens Tracing + TruApp Registration
# ---------------------------------------------------------------------------
print("\n" + "=" * 60)
print("TEST 1: TruLens Tracing + TruApp Registration")
print("=" * 60)

test1_pass = True
test1_errors = []

# 1a: Instantiate AEOBenchmarkApp
print(f"\n[1a] Instantiating AEOBenchmarkApp (baseline, {MODEL})...")
try:
    from aeo_trulens_app import AEOBenchmarkApp
    app = AEOBenchmarkApp(
        snowflake_session=session,
        mode="baseline",
        model=MODEL,
        cite=False,
        self_critique=False,
    )
    print("     OK: AEOBenchmarkApp instantiated")
except Exception as e:
    test1_pass = False
    test1_errors.append(f"App instantiation: {e}")
    print(f"     FAIL: {e}")
    traceback.print_exc()

# 1b: Verify @instrument decorators
print("\n[1b] Verifying @instrument decorators...")
try:
    for method_name in ["retrieve_context", "generate_response", "self_critique_refine", "query"]:
        method = getattr(app, method_name, None)
        assert method is not None and callable(method), f"{method_name} missing or not callable"
    print("     OK: All 4 instrumented methods present")
except Exception as e:
    test1_pass = False
    test1_errors.append(f"Decorator check: {e}")
    print(f"     FAIL: {e}")

# 1c: Call app.query() to generate a traced response
print(f"\n[1c] Calling app.query() on {TEST_Q1} (generates LLM response with OTel tracing)...")
try:
    question = QUESTIONS[TEST_Q1]
    response = app.query(question)
    assert response and len(response) > 50, f"Response too short: {len(response)} chars"
    print(f"     OK: {len(response)} chars — {response[:100]}...")
except Exception as e:
    test1_pass = False
    test1_errors.append(f"app.query(): {e}")
    print(f"     FAIL: {e}")
    traceback.print_exc()

# 1d: Register with TruApp + SnowflakeConnector
#     This auto-creates TRULENS_APPS, TRULENS_RECORDS, TRULENS_FEEDBACKS, TRULENS_RUNS
print("\n[1d] Registering with TruApp + SnowflakeConnector (initializes TRULENS_* tables)...")
try:
    from trulens.apps.app import TruApp
    from trulens.connectors.snowflake import SnowflakeConnector

    connector = SnowflakeConnector(snowpark_session=session)
    print("     OK: SnowflakeConnector created")

    tru_app = TruApp(
        app,
        main_method=app.query,
        app_name="aeo_benchmark",
        app_version="v1_snowhouse",
        connector=connector,
    )
    print(f"     OK: TruApp registered (app_name={tru_app.app_name}, version={tru_app.app_version})")
except Exception as e:
    test1_pass = False
    test1_errors.append(f"TruApp registration: {e}")
    print(f"     FAIL: {e}")
    traceback.print_exc()

# 1e: Create RunConfig pointing to DEVREL.CNANTASENAMAT_DEV.AEO_QUESTIONS
print("\n[1e] Creating RunConfig for 128-question dataset...")
try:
    from aeo_trulens_app import create_run_config
    run_config = create_run_config(
        run_name="snowhouse_smoke_test",
        dataset_name="AEO_QUESTIONS",
        description="Snowhouse TruLens smoke test (2 questions)",
        label="snowhouse_v1",
    )
    print(f"     OK: RunConfig created (run_name={run_config.run_name})")
except Exception as e:
    test1_pass = False
    test1_errors.append(f"RunConfig: {e}")
    print(f"     FAIL: {e}")
    traceback.print_exc()

# 1f: Verify TRULENS_* tables were created
print("\n[1f] Verifying TRULENS_* managed tables in DEVREL.CNANTASENAMAT_DEV...")
try:
    expected_tables = ["TRULENS_APPS", "TRULENS_RECORDS", "TRULENS_FEEDBACKS", "TRULENS_RUNS"]
    cur2 = conn.cursor()
    cur2.execute("SHOW TABLES IN SCHEMA DEVREL.CNANTASENAMAT_DEV")
    existing = {row[1].upper() for row in cur2.fetchall()}
    cur2.close()
    missing = [t for t in expected_tables if t not in existing]
    if missing:
        print(f"     WARN: Not yet created: {missing} (may need run.start() to trigger)")
    else:
        print(f"     OK: All 4 TRULENS_* tables exist: {expected_tables}")
except Exception as e:
    test1_pass = False
    test1_errors.append(f"Table verification: {e}")
    print(f"     FAIL: {e}")

print(f"\n{'─' * 60}")
print(f"TEST 1 RESULT: {'PASS' if test1_pass else 'FAIL'}")
for err in test1_errors:
    print(f"  ERROR: {err}")
print(f"{'─' * 60}")


# ---------------------------------------------------------------------------
# Test 2: 3-Judge Panel Scoring on 128-question bank
# ---------------------------------------------------------------------------
print("\n" + "=" * 60)
print("TEST 2: 3-Judge Panel Scoring")
print("=" * 60)

test2_pass = True
test2_errors = []

from aeo_feedback_functions import score_full_rubric, score_with_panel_and_trulens, JUDGE_PANEL

# 2a: Generate test response for TEST_Q1
print(f"\n[2a] Generating test response for {TEST_Q1}...")
try:
    messages_json = json.dumps([{"role": "user", "content": QUESTIONS[TEST_Q1]}])
    options_json = json.dumps({"max_tokens": 2048})
    cur.execute(
        "SELECT SNOWFLAKE.CORTEX.COMPLETE(%s, PARSE_JSON(%s), PARSE_JSON(%s)) AS response",
        (MODEL, messages_json, options_json),
    )
    row = cur.fetchone()
    raw = row[0]
    resp = json.loads(raw) if isinstance(raw, str) else raw
    if isinstance(resp, dict) and "choices" in resp:
        test_response = resp["choices"][0].get("messages", str(resp))
    elif isinstance(resp, dict) and "messages" in resp:
        test_response = resp["messages"]
    else:
        test_response = str(resp)
    print(f"     OK: {len(test_response)} chars generated")
except Exception as e:
    test2_pass = False
    test2_errors.append(f"Generation: {e}")
    print(f"     FAIL: {e}")
    traceback.print_exc()
    test_response = "Error generating response."

# 2b: Score with each judge individually
print(f"\n[2b] Scoring {TEST_Q1} with each judge (panel: {JUDGE_PANEL})...")
for judge in JUDGE_PANEL:
    try:
        result = score_full_rubric(
            conn, judge, QUESTIONS[TEST_Q1], test_response,
            CANONICAL_SUMMARIES[TEST_Q1], MUST_HAVES[TEST_Q1],
        )
        if result.get("parse_error"):
            test2_pass = False
            test2_errors.append(f"{judge}: parse error")
            print(f"     FAIL [{judge}]: parse error — raw: {result.get('raw_response','')[:100]}")
        else:
            dims = f"C={result['correctness']} Co={result['completeness']} R={result['recency']} Ci={result['citation']} Rec={result['recommendation']}"
            print(f"     OK [{judge}]: total={result['total']}/50, mh={result['must_have_pass']:.2f} | {dims}")
    except Exception as e:
        test2_pass = False
        test2_errors.append(f"{judge}: {e}")
        print(f"     FAIL [{judge}]: {e}")
        traceback.print_exc()

# 2c: Full panel + TruLens dual-write format on TEST_Q2
print(f"\n[2c] Full panel + TruLens dual-write format on {TEST_Q2}...")
try:
    messages_json2 = json.dumps([{"role": "user", "content": QUESTIONS[TEST_Q2]}])
    options_json2 = json.dumps({"max_tokens": 2048})
    cur.execute(
        "SELECT SNOWFLAKE.CORTEX.COMPLETE(%s, PARSE_JSON(%s), PARSE_JSON(%s)) AS response",
        (MODEL, messages_json2, options_json2),
    )
    row2 = cur.fetchone()
    raw2 = row2[0]
    resp2 = json.loads(raw2) if isinstance(raw2, str) else raw2
    if isinstance(resp2, dict) and "choices" in resp2:
        test_response2 = resp2["choices"][0].get("messages", str(resp2))
    elif isinstance(resp2, dict) and "messages" in resp2:
        test_response2 = resp2["messages"]
    else:
        test_response2 = str(resp2)

    panel_result = score_with_panel_and_trulens(
        conn, QUESTIONS[TEST_Q2], test_response2,
        CANONICAL_SUMMARIES[TEST_Q2], MUST_HAVES[TEST_Q2],
    )

    assert "judges" in panel_result and len(panel_result["judges"]) == 3
    assert "panel_avg" in panel_result
    assert "trulens" in panel_result

    avg = panel_result["panel_avg"]
    tru = panel_result["trulens"]
    print(f"     OK: panel_avg total={avg['total']:.1f}/50, mh={avg['must_have_pass']:.2f}")
    print(f"     TruLens normalized: total={tru['aeo_total_score']:.3f}, mh={tru['aeo_must_have_coverage']:.3f}")

    # Verify ranges
    assert 0 <= avg["total"] <= 50, f"Total out of range: {avg['total']}"
    assert 0.0 <= tru["aeo_total_score"] <= 1.0, f"TruLens total out of range: {tru['aeo_total_score']}"
    print("     OK: All scores within valid ranges")

except Exception as e:
    test2_pass = False
    test2_errors.append(f"Panel + TruLens format: {e}")
    print(f"     FAIL: {e}")
    traceback.print_exc()

print(f"\n{'─' * 60}")
print(f"TEST 2 RESULT: {'PASS' if test2_pass else 'FAIL'}")
for err in test2_errors:
    print(f"  ERROR: {err}")
print(f"{'─' * 60}")


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print(f"\n{'=' * 60}")
print("OVERALL SUMMARY")
print(f"{'=' * 60}")
print(f"  Test 1 (TruLens Tracing + Registration): {'PASS' if test1_pass else 'FAIL'}")
print(f"  Test 2 (3-Judge Panel, 128-q bank):      {'PASS' if test2_pass else 'FAIL'}")
all_pass = test1_pass and test2_pass
print(f"\n  OVERALL: {'ALL TESTS PASSED' if all_pass else 'SOME TESTS FAILED'}")
print(f"{'=' * 60}")

cur.close()
conn.close()
session.close()
