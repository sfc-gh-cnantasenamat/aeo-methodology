"""
AEO TruLens Integration: Quick Start Guide

This script demonstrates how to use the full TruLens-integrated AEO pipeline
from end to end, including Snowsight AI Observability.

v1: 128 questions from Snowflake, 1-10 scoring scale (max 50/question),
    string question IDs ("Q001"-"Q128"), 5 must-haves (ratio 0.0-1.0).

Prerequisites:
    pip install snowflake-ml-python snowflake.core trulens-core \
                trulens-connectors-snowflake trulens-providers-cortex

Snowsight Navigation:
    After running evaluations, view results in Snowsight:
    1. Go to AI & ML > Cortex AI > Evaluations
    2. Select app_name "aeo_benchmark"
    3. Click on a specific run to see per-record metrics
    4. Use the comparison view to compare runs side by side
"""

import sys
sys.path.insert(0, "/Users/cnantasenamat/Documents/Coco/aeo/observability")


def demo_standalone_scoring():
    """
    Demo 1: Standalone scoring with TruLens dual-write.
    Scores a single question and shows both raw (1-10) and TruLens (0.0-1.0) results.
    """
    import snowflake.connector
    from aeo_data import (
        QUESTIONS, CANONICAL_SUMMARIES, MUST_HAVES, load_from_snowflake,
    )
    from aeo_feedback_functions import (
        score_full_rubric, score_with_panel_and_trulens, clear_score_cache,
    )

    conn = snowflake.connector.connect(connection_name="devrel")
    cur = conn.cursor()
    cur.execute("USE WAREHOUSE COMPUTE_WH")
    cur.execute("USE DATABASE AEO_OBSERVABILITY")
    cur.execute("USE SCHEMA EVAL_SCHEMA")

    # Load question data from Snowflake
    load_from_snowflake(conn)

    # Score a single question with one judge
    qid = "Q001"
    print(f"Scoring {qid} with single judge...")
    result = score_full_rubric(
        conn,
        judge_model="claude-opus-4-6",
        question=QUESTIONS[qid],
        response="Snowflake Cortex offers AI_COMPLETE, AI_CLASSIFY, and AI_EXTRACT.",
        canonical_answer=CANONICAL_SUMMARIES[qid],
        must_haves=MUST_HAVES[qid],
    )
    print(f"  Total: {result['total']}/50, MH: {result['must_have_pass']:.2f}")

    # Score with full 3-judge panel + TruLens normalization
    print(f"\nScoring {qid} with 3-judge panel + TruLens...")
    panel = score_with_panel_and_trulens(
        conn,
        question=QUESTIONS[qid],
        response="Snowflake Cortex offers AI_COMPLETE, AI_CLASSIFY, and AI_EXTRACT.",
        canonical_answer=CANONICAL_SUMMARIES[qid],
        must_haves=MUST_HAVES[qid],
    )
    avg = panel["panel_avg"]
    tl = panel["trulens"]
    print(f"  Panel avg: {avg['total']:.1f}/50, MH: {avg['must_have_pass']:.2f}")
    print(f"  TruLens normalized: total={tl['aeo_total_score']:.3f}, mh={tl['aeo_must_have_coverage']:.3f}")
    clear_score_cache()

    cur.close()
    conn.close()


def demo_full_run():
    """
    Demo 2: Full benchmark run with Snowflake storage.
    Generates responses, scores with panel, stores in Snowflake tables.
    """
    from aeo_run_orchestrator import run_benchmark

    # Run a baseline benchmark (run_id=100 for demo)
    run_benchmark(
        run_id=100,
        mode="baseline",
        model="claude-opus-4-6",
        domain_prompt=False,
        cite=False,
        self_critique=False,
        max_tokens=8192,
        judges=["claude-opus-4-6"],  # Single judge for speed
    )


def demo_trulens_observability():
    """
    Demo 3: TruLens + Snowsight AI Observability integration.
    Registers the app, creates a run, and computes TruLens built-in metrics.
    Requires trulens packages installed.
    """
    from snowflake.snowpark import Session
    from aeo_data import load_from_snowflake
    from aeo_trulens_app import AEOBenchmarkApp, register_app, create_run_config

    # Create Snowpark session
    session = Session.builder.configs({"connection_name": "devrel"}).create()
    session.sql("USE WAREHOUSE COMPUTE_WH").collect()
    session.sql("USE DATABASE AEO_OBSERVABILITY").collect()
    session.sql("USE SCHEMA EVAL_SCHEMA").collect()

    # Load question data (needed by the app's _find_question_id)
    import snowflake.connector
    conn = snowflake.connector.connect(connection_name="devrel")
    cur = conn.cursor()
    cur.execute("USE WAREHOUSE COMPUTE_WH")
    cur.execute("USE DATABASE AEO_OBSERVABILITY")
    cur.execute("USE SCHEMA EVAL_SCHEMA")
    load_from_snowflake(conn)
    cur.close()
    conn.close()

    # Create and register the app
    app = AEOBenchmarkApp(
        snowflake_session=session,
        mode="baseline",
        model="claude-opus-4-6",
    )

    tru_app = register_app(
        app, session,
        app_name="aeo_benchmark",
        app_version="baseline_v1",
    )

    # Create a run config pointing to our questions table
    run_config = create_run_config(
        run_name="aeo_baseline_demo",
        dataset_name="AEO_QUESTIONS",
        description="Baseline demo run",
        label="demo",
    )

    # Add and execute the run
    run = tru_app.add_run(run_config=run_config)
    run.start()

    # Compute built-in TruLens metrics
    run.compute_metrics([
        "answer_relevance",
        "correctness",
    ])

    print("Done! View results in Snowsight: AI & ML > Cortex AI > Evaluations")
    session.close()


def demo_query_results():
    """
    Demo 4: Query stored results via SQL.
    Shows how to use the analysis views.
    """
    import snowflake.connector

    conn = snowflake.connector.connect(connection_name="devrel")
    cur = conn.cursor()
    cur.execute("USE WAREHOUSE COMPUTE_WH")

    # Leaderboard
    print("=== AEO LEADERBOARD ===")
    cur.execute("SELECT * FROM AEO_OBSERVABILITY.EVAL_SCHEMA.V_AEO_LEADERBOARD")
    for row in cur.fetchall():
        print(f"  Run {row[0]}: {row[8]}% score, {row[10]}% MH")

    # Factorial effects
    print("\n=== FACTORIAL EFFECTS ===")
    cur.execute("SELECT * FROM AEO_OBSERVABILITY.EVAL_SCHEMA.V_AEO_FACTORIAL_EFFECTS")
    for row in cur.fetchall():
        print(f"  {row[0]}: score={row[1]}pp, MH={row[2]}pp")

    cur.close()
    conn.close()


def demo_rescore():
    """
    Demo 5: Re-score an existing run using the TruLens pipeline.
    Uses responses already in AEO_RESPONSES, scores them fresh, dual-writes.
    """
    from aeo_run_orchestrator import rescore_existing_run

    # Re-score run 1 (baseline) with single judge for speed
    rescore_existing_run(
        run_id=1,
        judges=["claude-opus-4-6"],
        profile="devrel",
        enable_trulens=False,
    )


if __name__ == "__main__":
    import sys
    demo = sys.argv[1] if len(sys.argv) > 1 else "standalone"

    if demo == "standalone":
        demo_standalone_scoring()
    elif demo == "full_run":
        demo_full_run()
    elif demo == "trulens":
        demo_trulens_observability()
    elif demo == "query":
        demo_query_results()
    elif demo == "rescore":
        demo_rescore()
    else:
        print(f"Unknown demo: {demo}")
        print("Options: standalone, full_run, trulens, query, rescore")
