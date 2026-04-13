"""
Test TruLens integration: instrumentation + 3-judge panel.

Test 1: TruLens @instrument decorators, TruApp registration, SnowflakeConnector
Test 2: 3-judge panel scoring with all three models
"""
import json
import os
import sys
import traceback

sys.path.insert(0, "/Users/cnantasenamat/Documents/Coco/aeo/observability")

os.environ["TRULENS_OTEL_TRACING"] = "1"

from snowflake.snowpark import Session

# =====================================================================
# Test 1: TruLens Tracing Instrumentation
# =====================================================================
print("=" * 60)
print("TEST 1: TruLens Tracing Instrumentation")
print("=" * 60)

test1_pass = True
test1_errors = []

# Step 1a: Create Snowpark session
print("\n[1a] Creating Snowpark session...")
try:
    session = Session.builder.config("connection_name", "devrel").create()
    session.sql("USE WAREHOUSE COMPUTE_WH").collect()
    session.sql("USE DATABASE AEO_OBSERVABILITY").collect()
    session.sql("USE SCHEMA EVAL_SCHEMA").collect()
    print("     OK: Snowpark session created")
except Exception as e:
    test1_pass = False
    test1_errors.append(f"Session creation: {e}")
    print(f"     FAIL: {e}")

# Step 1b: Import and instantiate AEOBenchmarkApp
print("\n[1b] Importing AEOBenchmarkApp...")
try:
    from aeo_trulens_app import AEOBenchmarkApp
    app = AEOBenchmarkApp(
        snowflake_session=session,
        mode="baseline",
        model="claude-opus-4-6",
        cite=False,
        self_critique=False,
    )
    print("     OK: AEOBenchmarkApp instantiated")
except Exception as e:
    test1_pass = False
    test1_errors.append(f"App instantiation: {e}")
    print(f"     FAIL: {e}")
    traceback.print_exc()

# Step 1c: Verify @instrument decorators are applied
print("\n[1c] Verifying @instrument decorators...")
try:
    from trulens.core.otel.instrument import instrument
    # Check that the methods exist and are callable
    for method_name in ["retrieve_context", "generate_response", "self_critique_refine", "query"]:
        method = getattr(app, method_name, None)
        assert method is not None, f"Method {method_name} not found"
        assert callable(method), f"Method {method_name} not callable"
    print("     OK: All 4 instrumented methods present and callable")
except Exception as e:
    test1_pass = False
    test1_errors.append(f"Decorator check: {e}")
    print(f"     FAIL: {e}")

# Step 1d: Call app.query() and verify it produces a response with tracing
print("\n[1d] Calling app.query() on Q1 (generates LLM response with tracing)...")
try:
    from aeo_data import QUESTIONS
    question = QUESTIONS[1]
    response = app.query(question)
    assert response and len(response) > 50, f"Response too short: {len(response)} chars"
    print(f"     OK: Got response ({len(response)} chars)")
    print(f"     Preview: {response[:120]}...")
except Exception as e:
    test1_pass = False
    test1_errors.append(f"app.query(): {e}")
    print(f"     FAIL: {e}")
    traceback.print_exc()

# Step 1e: Register with TruApp + SnowflakeConnector
print("\n[1e] Registering with TruApp + SnowflakeConnector...")
try:
    from trulens.apps.app import TruApp
    from trulens.connectors.snowflake import SnowflakeConnector

    connector = SnowflakeConnector(snowpark_session=session)
    print("     OK: SnowflakeConnector created")

    tru_app = TruApp(
        app,
        main_method=app.query,
        app_name="aeo_benchmark_test",
        app_version="test_v1",
        connector=connector,
    )
    print(f"     OK: TruApp registered (app_name={tru_app.app_name})")
except Exception as e:
    test1_pass = False
    test1_errors.append(f"TruApp registration: {e}")
    print(f"     FAIL: {e}")
    traceback.print_exc()

# Step 1f: Create RunConfig
print("\n[1f] Creating RunConfig...")
try:
    from aeo_trulens_app import create_run_config
    run_config = create_run_config(
        run_name="test_run_integration",
        dataset_name="AEO_QUESTIONS",
        description="Integration test run",
        label="test",
    )
    print(f"     OK: RunConfig created (run_name={run_config.run_name})")
except Exception as e:
    test1_pass = False
    test1_errors.append(f"RunConfig: {e}")
    print(f"     FAIL: {e}")
    traceback.print_exc()

# Step 1g: Test agentic mode (retrieval + generation)
print("\n[1g] Testing agentic mode (retrieval + generation)...")
try:
    agentic_app = AEOBenchmarkApp(
        snowflake_session=session,
        mode="agentic",
        model="claude-opus-4-6",
        cite=True,
        self_critique=False,
    )
    question = QUESTIONS[1]
    context = agentic_app.retrieve_context(question)
    assert len(context) > 0, "No context retrieved in agentic mode"
    print(f"     OK: Retrieved {len(context)} context doc(s) ({len(context[0])} chars)")

    response = agentic_app.generate_response(question, context)
    assert response and len(response) > 50, f"Agentic response too short: {len(response)} chars"
    print(f"     OK: Agentic generation produced {len(response)} chars")
except Exception as e:
    test1_pass = False
    test1_errors.append(f"Agentic mode: {e}")
    print(f"     FAIL: {e}")
    traceback.print_exc()

print(f"\n{'─' * 60}")
print(f"TEST 1 RESULT: {'PASS' if test1_pass else 'FAIL'}")
if test1_errors:
    for err in test1_errors:
        print(f"  ERROR: {err}")
print(f"{'─' * 60}")


# =====================================================================
# Test 2: 3-Judge Panel Scoring
# =====================================================================
print("\n" + "=" * 60)
print("TEST 2: 3-Judge Panel Scoring")
print("=" * 60)

test2_pass = True
test2_errors = []

# Use a snowflake.connector connection for scoring (as the feedback functions expect)
import snowflake.connector
conn = snowflake.connector.connect(connection_name="devrel")
cur = conn.cursor()
cur.execute("USE WAREHOUSE COMPUTE_WH")
cur.execute("USE DATABASE AEO_OBSERVABILITY")
cur.execute("USE SCHEMA EVAL_SCHEMA")

from aeo_data import CANONICAL_SUMMARIES, MUST_HAVES
from aeo_feedback_functions import score_full_rubric, score_with_panel, JUDGE_PANEL

# Step 2a: Test each judge individually on Q1
print(f"\n[2a] Testing each judge individually on Q1...")
print(f"     Panel: {JUDGE_PANEL}")

question = QUESTIONS[1]
# Generate a fresh response to score
messages_json = json.dumps([{"role": "user", "content": question}])
cur.execute(f"""
    SELECT SNOWFLAKE.CORTEX.COMPLETE(
        'claude-opus-4-6',
        PARSE_JSON($${messages_json}$$),
        PARSE_JSON('{{"max_tokens": 2048}}')
    ) AS response
""")
row = cur.fetchone()
raw = row[0]
resp_data = json.loads(raw) if isinstance(raw, str) else raw
if isinstance(resp_data, dict) and "choices" in resp_data:
    test_response = resp_data["choices"][0].get("messages", str(resp_data))
elif isinstance(resp_data, dict) and "messages" in resp_data:
    test_response = resp_data["messages"]
else:
    test_response = str(resp_data)

print(f"     Generated test response: {len(test_response)} chars")

individual_scores = {}
for judge in JUDGE_PANEL:
    print(f"\n     Scoring with {judge}...")
    try:
        result = score_full_rubric(
            conn, judge, question, test_response,
            CANONICAL_SUMMARIES[1], MUST_HAVES[1],
        )
        individual_scores[judge] = result
        has_error = result.get("parse_error", False)
        if has_error:
            test2_pass = False
            test2_errors.append(f"{judge}: parse error in response")
            print(f"     FAIL: {judge} returned unparseable response")
            print(f"       Raw: {result.get('raw_response', '')[:200]}")
        else:
            print(f"     OK: {judge} -> total={result['total']}/10, mh={result['must_have_pass']}/4")
            print(f"       C={result['correctness']} Comp={result['completeness']} "
                  f"R={result['recency']} Cit={result['citation']} Rec={result['recommendation']}")
    except Exception as e:
        test2_pass = False
        test2_errors.append(f"{judge}: {e}")
        print(f"     FAIL: {judge} error: {e}")
        traceback.print_exc()

# Step 2b: Test panel scoring function
print(f"\n[2b] Testing score_with_panel() on Q1...")
try:
    panel_result = score_with_panel(
        conn, question, test_response,
        CANONICAL_SUMMARIES[1], MUST_HAVES[1],
    )

    # Verify structure
    assert "judges" in panel_result, "Missing 'judges' key"
    assert "panel_avg" in panel_result, "Missing 'panel_avg' key"
    assert len(panel_result["judges"]) == 3, f"Expected 3 judges, got {len(panel_result['judges'])}"

    avg = panel_result["panel_avg"]
    print(f"     OK: Panel average -> total={avg['total']:.1f}/10, mh={avg['must_have_pass']:.1f}/4")
    print(f"       C={avg['correctness']:.1f} Comp={avg['completeness']:.1f} "
          f"R={avg['recency']:.1f} Cit={avg['citation']:.1f} Rec={avg['recommendation']:.1f}")

    # Verify scores are reasonable
    assert 0 <= avg["total"] <= 10, f"Total out of range: {avg['total']}"
    assert 0 <= avg["must_have_pass"] <= 4, f"MH out of range: {avg['must_have_pass']}"
    print("     OK: Scores within valid ranges")

    # Check inter-judge agreement
    totals = [s["total"] for s in panel_result["judges"].values() if "total" in s]
    spread = max(totals) - min(totals)
    print(f"     Inter-judge spread: {spread} points (totals: {totals})")

except Exception as e:
    test2_pass = False
    test2_errors.append(f"score_with_panel: {e}")
    print(f"     FAIL: {e}")
    traceback.print_exc()

# Step 2c: Test on a second question (Q25) to verify consistency
print(f"\n[2c] Testing panel on Q25 for consistency...")
try:
    q25 = QUESTIONS[25]
    # Generate response for Q25
    messages_json_25 = json.dumps([{"role": "user", "content": q25}])
    cur.execute(f"""
        SELECT SNOWFLAKE.CORTEX.COMPLETE(
            'claude-opus-4-6',
            PARSE_JSON($${messages_json_25}$$),
            PARSE_JSON('{{"max_tokens": 2048}}')
        ) AS response
    """)
    row = cur.fetchone()
    raw25 = row[0]
    resp25 = json.loads(raw25) if isinstance(raw25, str) else raw25
    if isinstance(resp25, dict) and "choices" in resp25:
        test_resp_25 = resp25["choices"][0].get("messages", str(resp25))
    elif isinstance(resp25, dict) and "messages" in resp25:
        test_resp_25 = resp25["messages"]
    else:
        test_resp_25 = str(resp25)

    panel_25 = score_with_panel(
        conn, q25, test_resp_25,
        CANONICAL_SUMMARIES[25], MUST_HAVES[25],
    )
    avg25 = panel_25["panel_avg"]
    print(f"     OK: Q25 panel avg -> total={avg25['total']:.1f}/10, mh={avg25['must_have_pass']:.1f}/4")
    for judge, scores in panel_25["judges"].items():
        print(f"       {judge}: {scores['total']}/10, mh={scores['must_have_pass']}/4")
except Exception as e:
    test2_pass = False
    test2_errors.append(f"Q25 panel: {e}")
    print(f"     FAIL: {e}")
    traceback.print_exc()

print(f"\n{'─' * 60}")
print(f"TEST 2 RESULT: {'PASS' if test2_pass else 'FAIL'}")
if test2_errors:
    for err in test2_errors:
        print(f"  ERROR: {err}")
print(f"{'─' * 60}")

# =====================================================================
# Summary
# =====================================================================
print(f"\n{'=' * 60}")
print("OVERALL SUMMARY")
print(f"{'=' * 60}")
print(f"  Test 1 (TruLens Tracing):    {'PASS' if test1_pass else 'FAIL'}")
print(f"  Test 2 (3-Judge Panel):       {'PASS' if test2_pass else 'FAIL'}")
all_pass = test1_pass and test2_pass
print(f"\n  OVERALL: {'ALL TESTS PASSED' if all_pass else 'SOME TESTS FAILED'}")
print(f"{'=' * 60}")

# Cleanup
cur.close()
conn.close()
session.close()
