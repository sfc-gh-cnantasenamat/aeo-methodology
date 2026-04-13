"""
Replay pre-generated AEO benchmark responses into TruLens.

Loads existing responses from AEO_RESPONSES and replays them through the
TruLens-instrumented AEOBenchmarkApp, emitting OTel spans with the actual
response text. No LLM calls are made — AEOBenchmarkApp._preloaded_response
bypasses CORTEX.COMPLETE in generate_response and self_critique_refine.

This initializes TRULENS_APPS / TRULENS_RECORDS tables in Snowhouse and
makes all 16 factorial runs visible in Snowsight AI Observability.

Usage:
    # Replay all 16 runs
    python3 replay_runs_to_trulens.py --profile snowhouse

    # Replay specific runs
    python3 replay_runs_to_trulens.py --profile snowhouse --run-ids 1 2 3

    # Smoke test: first 2 questions of run 1 only
    python3 replay_runs_to_trulens.py --profile snowhouse --run-ids 1 --limit 2
"""

import argparse
import os
import sys
import time

sys.path.insert(0, "/Users/cnantasenamat/Documents/Coco/aeo/observability")

os.environ["TRULENS_OTEL_TRACING"] = "1"

import snowflake.connector
from snowflake.snowpark import Session

from aeo_data import QUESTIONS, load_from_snowflake, reset as reset_data
from aeo_trulens_app import AEOBenchmarkApp, register_app

# ---------------------------------------------------------------------------
# Connection profiles (mirrors aeo_run_orchestrator.py)
# ---------------------------------------------------------------------------

CONNECTION_PROFILES = {
    "devrel": {
        "connection_name": "devrel",
        "warehouse": "COMPUTE_WH",
        "database": "AEO_OBSERVABILITY",
        "schema": "EVAL_SCHEMA",
    },
    "snowhouse": {
        "connection_name": "my-snowflake",
        "role": "DEVREL_INGEST_RL",
        "warehouse": "SNOWADHOC",
        "database": "DEVREL",
        "schema": "CNANTASENAMAT_DEV",
    },
}


def get_connections(profile: str):
    """Return (snowflake.connector conn, Snowpark session) for the profile."""
    cfg = CONNECTION_PROFILES[profile]

    conn = snowflake.connector.connect(connection_name=cfg["connection_name"])
    cur = conn.cursor()
    if "role" in cfg:
        cur.execute(f"USE ROLE {cfg['role']}")
    cur.execute(f"USE WAREHOUSE {cfg['warehouse']}")
    cur.execute(f"USE DATABASE {cfg['database']}")
    cur.execute(f"USE SCHEMA {cfg['schema']}")
    cur.close()

    session = Session.builder.config("connection_name", cfg["connection_name"]).create()
    if "role" in cfg:
        session.sql(f"USE ROLE {cfg['role']}").collect()
    session.sql(f"USE WAREHOUSE {cfg['warehouse']}").collect()
    session.sql(f"USE DATABASE {cfg['database']}").collect()
    session.sql(f"USE SCHEMA {cfg['schema']}").collect()

    return conn, session


def load_run_metadata(conn, run_id: int) -> dict:
    """Load factor flags and model for a run from AEO_RUNS."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT DOMAIN_PROMPT, CITATION, AGENTIC, SELF_CRITIQUE, MODEL
        FROM AEO_RUNS WHERE RUN_ID = %s
        """,
        (run_id,),
    )
    row = cur.fetchone()
    cur.close()
    if not row:
        return None
    domain_prompt, citation, agentic, self_critique, model = row
    mode = "agentic" if agentic else ("augmented" if domain_prompt else "baseline")
    return {
        "mode": mode,
        "model": model,
        "domain_prompt": bool(domain_prompt),
        "cite": bool(citation),
        "self_critique": bool(self_critique),
    }


def load_run_responses(conn, run_id: int, limit: int = None) -> dict:
    """Load pre-generated responses for a run from AEO_RESPONSES."""
    cur = conn.cursor()
    sql = "SELECT QUESTION_ID, RESPONSE_TEXT FROM AEO_RESPONSES WHERE RUN_ID = %s ORDER BY QUESTION_ID"
    if limit:
        sql += f" LIMIT {limit}"
    cur.execute(sql, (run_id,))
    responses = {row[0]: row[1] for row in cur.fetchall()}
    cur.close()
    return responses


def load_run_scores(conn, run_id: int) -> dict:
    """
    Load pre-computed scores for a run, averaged across all 3 judge models.

    Returns {question_id: {metric: float}} with values normalized to [0, 1]:
      - correctness, completeness, recency, citation, recommendation: /10
      - total_score: /50
      - must_have_pass: already 0-1
    """
    cur = conn.cursor()
    cur.execute(
        """
        SELECT QUESTION_ID,
               AVG(CORRECTNESS)    / 10.0 AS correctness,
               AVG(COMPLETENESS)   / 10.0 AS completeness,
               AVG(RECENCY)        / 10.0 AS recency,
               AVG(CITATION)       / 10.0 AS citation,
               AVG(RECOMMENDATION) / 10.0 AS recommendation,
               AVG(TOTAL_SCORE)    / 50.0 AS total_score,
               AVG(MUST_HAVE_PASS)         AS must_have_pass
        FROM AEO_SCORES
        WHERE RUN_ID = %s
        GROUP BY QUESTION_ID
        """,
        (run_id,),
    )
    scores = {}
    for row in cur.fetchall():
        qid = row[0]
        scores[qid] = {
            "correctness":    float(row[1] or 0),
            "completeness":   float(row[2] or 0),
            "recency":        float(row[3] or 0),
            "citation":       float(row[4] or 0),
            "recommendation": float(row[5] or 0),
            "total_score":    float(row[6] or 0),
            "must_have_pass": float(row[7] or 0),
        }
    cur.close()
    return scores


class ScoreLookup:
    """
    Lookup provider for pre-computed AEO scores.

    Each method signature matches TruLens Feedback convention:
      fn(question: str, response: str) -> float

    Scores are keyed by question text (from the QUESTIONS dict) so the
    feedback function can match on the actual input string at evaluation time.
    """

    def __init__(self, scores_by_qid: dict, questions: dict):
        # Build {question_text: {metric: value}} for O(1) lookup
        self._by_text = {
            questions[qid]: metrics
            for qid, metrics in scores_by_qid.items()
            if qid in questions
        }

    def _get(self, question: str, metric: str) -> float:
        return self._by_text.get(question, {}).get(metric, 0.0)

    def correctness(self, question: str, response: str) -> float:
        return self._get(question, "correctness")

    def completeness(self, question: str, response: str) -> float:
        return self._get(question, "completeness")

    def recency(self, question: str, response: str) -> float:
        return self._get(question, "recency")

    def citation(self, question: str, response: str) -> float:
        return self._get(question, "citation")

    def recommendation(self, question: str, response: str) -> float:
        return self._get(question, "recommendation")

    def total_score(self, question: str, response: str) -> float:
        return self._get(question, "total_score")

    def must_have_pass(self, question: str, response: str) -> float:
        return self._get(question, "must_have_pass")


def replay_run(
    run_id: int,
    conn,
    session,
    connector,
    limit: int = None,
    profile: str = "snowhouse",
    use_native: bool = False,
) -> int:
    """
    Replay a single run's responses into TruLens using LOG_INGESTION mode.

    Uses run.start(input_df=df) with Mode.LOG_INGESTION to create virtual OTel
    spans from pre-existing question/response pairs without re-invoking the LLM.
    After ingestion, calls run.compute_metrics() to attach scores as metric
    results visible in Snowsight Evaluations.

    connector: shared SnowflakeConnector (created once in replay_all).
    use_native: if True, use AEOCortexProvider (LLM-based, AEO rubrics) instead
                of ScoreLookup (pre-computed scores, no LLM calls).
    Returns number of records ingested.
    """
    import pandas as pd
    from trulens.core import Metric
    from trulens.core.run import RunConfig, Mode, RunStatus

    print(f"\n{'─' * 60}")
    print(f"Run {run_id}")

    # Load metadata
    meta = load_run_metadata(conn, run_id)
    if meta is None:
        print(f"  SKIP: no metadata in AEO_RUNS for run_id={run_id}")
        return 0

    print(f"  mode={meta['mode']} model={meta['model']} domain={meta['domain_prompt']} "
          f"cite={meta['cite']} sc={meta['self_critique']}")

    # Load responses and scores
    responses = load_run_responses(conn, run_id, limit=limit)
    if not responses:
        print(f"  SKIP: no responses in AEO_RESPONSES for run_id={run_id}")
        return 0
    print(f"  {len(responses)} responses loaded")

    if not use_native:
        scores = load_run_scores(conn, run_id)
        lookup = ScoreLookup(scores, QUESTIONS)
        print(f"  {len(scores)} pre-computed scores loaded")

    # Build DataFrame of valid question/response pairs for LOG_INGESTION
    rows = []
    for qid in sorted(responses.keys()):
        question = QUESTIONS.get(qid)
        response_text = responses.get(qid)
        if not question:
            continue
        if not response_text or response_text.startswith("Error:"):
            continue
        rows.append({
            "QUESTION_ID": qid,
            "QUESTION_TEXT": question,
            "RESPONSE_TEXT": response_text,
        })
    df = pd.DataFrame(rows)
    if df.empty:
        print(f"  SKIP: no valid rows to ingest")
        return 0
    print(f"  {len(df)} rows to ingest")

    # Build app (needed for TruApp registration)
    from aeo_data import GENERIC_DOMAIN_PROMPT
    system_prompt = GENERIC_DOMAIN_PROMPT if meta["domain_prompt"] else None
    app = AEOBenchmarkApp(
        snowflake_session=session,
        mode=meta["mode"],
        model=meta["model"],
        system_prompt=system_prompt,
        cite=meta["cite"],
        self_critique=meta["self_critique"],
    )

    # Version string encodes the run's factorial position
    app_version = (
        f"run{run_id:02d}"
        f"_{'dp' if meta['domain_prompt'] else 'nodp'}"
        f"_{'cite' if meta['cite'] else 'nocite'}"
        f"_{'ag' if meta['mode'] == 'agentic' else 'noag'}"
        f"_{'sc' if meta['self_critique'] else 'nosc'}"
    )

    if use_native:
        # Native Cortex LLM evaluation — applies AEO rubrics via CORTEX.COMPLETE.
        # Pre-loads question metadata so correctness/completeness/must_have_pass
        # compare against canonical answers and semantic must-have criteria,
        # matching the AEO benchmark's ground-truth evaluation approach.
        from aeo_cortex_provider import AEOCortexProvider, build_native_metrics
        q_cur = conn.cursor()
        q_cur.execute("""
            SELECT QUESTION_TEXT, CANONICAL_ANSWER,
                   MUST_HAVE_1, MUST_HAVE_2, MUST_HAVE_3, MUST_HAVE_4, MUST_HAVE_5
            FROM DEVREL.CNANTASENAMAT_DEV.AEO_QUESTIONS
        """)
        question_metadata = {}
        for row in q_cur.fetchall():
            q_text, canonical, mh1, mh2, mh3, mh4, mh5 = row
            question_metadata[q_text] = {
                "canonical_answer": canonical,
                "must_haves": [m for m in [mh1, mh2, mh3, mh4, mh5] if m],
            }
        aeo_provider = AEOCortexProvider(snowpark_session=session, question_metadata=question_metadata)
        metrics = build_native_metrics(aeo_provider)
        print(f"  Native Cortex evaluation (judges: {aeo_provider._models}, {len(question_metadata)} questions loaded)")
    else:
        # Lookup-based metrics — no LLM calls, instant evaluation.
        # Scores are averaged across claude-opus-4-6, llama4-maverick, openai-gpt-5.4
        # and normalized to [0, 1].
        metrics = [
            Metric(implementation=lookup.correctness,    name="correctness").on_input_output(),
            Metric(implementation=lookup.completeness,   name="completeness").on_input_output(),
            Metric(implementation=lookup.recency,        name="recency").on_input_output(),
            Metric(implementation=lookup.citation,       name="citation").on_input_output(),
            Metric(implementation=lookup.recommendation, name="recommendation").on_input_output(),
            Metric(implementation=lookup.total_score,    name="total_score").on_input_output(),
            Metric(implementation=lookup.must_have_pass, name="must_have_pass").on_input_output(),
        ]

    # Register TruApp (no feedbacks passed — they go to run.compute_metrics())
    tru_app = register_app(
        app, session,
        app_name="aeo_benchmark",
        app_version=app_version,
        connector=connector,
    )
    print(f"  TruLens registered: version={app_version}")

    # Create RunConfig with LOG_INGESTION mode — run.start() creates virtual
    # OTel spans from input_df without calling the LLM.
    run_config = RunConfig(
        run_name=app_version,
        dataset_name=app_version,   # label only; we pass input_df directly
        mode=Mode.LOG_INGESTION,
        dataset_spec={
            "input_id":           "QUESTION_ID",
            "record_root.input":  "QUESTION_TEXT",
            "record_root.output": "RESPONSE_TEXT",
        },
    )

    # Attempt to add the run. If it already exists with stale metadata
    # (source_info=None from a previous OtelRecordingContext replay), the
    # get_run() fallback inside add_run() raises a Pydantic validation error.
    # In that case, drop the stale run via the DAO and recreate.
    try:
        run = tru_app.add_run(run_config)
    except Exception as first_err:
        if "source_info" in str(first_err) or "already exists" in str(first_err):
            print(f"  Stale run found — dropping and recreating...")
            import json as _json
            payload = _json.dumps({
                "object_name": "AEO_BENCHMARK",
                "object_type": "EXTERNAL AGENT",
                "run_name": app_version,
                "object_version": app_version,
            })
            try:
                session.sql(
                    "SELECT SYSTEM$AIML_RUN_OPERATION('DELETE', ?)",
                    params=[payload],
                ).collect()
                print(f"  Run dropped OK")
            except Exception as drop_err:
                print(f"  WARN: DROP failed: {drop_err}")
            run = tru_app.add_run(run_config)
        else:
            raise

    # Ingest virtual spans (no LLM calls)
    print(f"  Ingesting {len(df)} virtual spans...")
    run.start(input_df=df)

    # Poll for ingestion completion (server-side SYSTEM$ proc is async)
    print(f"  Waiting for INVOCATION_COMPLETED...", end="", flush=True)
    for _ in range(120):   # up to 2 minutes
        status = run.get_status()
        if status in (
            RunStatus.INVOCATION_COMPLETED,
            RunStatus.INVOCATION_PARTIALLY_COMPLETED,
            RunStatus.FAILED,
        ):
            break
        print(".", end="", flush=True)
        time.sleep(2)
    print(f" {status.value}")

    if status == RunStatus.FAILED:
        print(f"  WARN: run failed during ingestion — skipping compute_metrics")
        return len(df)

    # Compute metrics (lookup functions run client-side, result stored in Snowflake)
    print(f"  Computing metrics...")
    result = run.compute_metrics(metrics=metrics)
    print(f"  compute_metrics: {result}")

    return len(df)


def replay_all(
    run_ids: list,
    profile: str = "snowhouse",
    limit: int = None,
    use_native: bool = False,
):
    """Replay all specified run_ids into TruLens."""
    print("=" * 60)
    print("AEO TruLens Replay")
    print(f"Profile: {profile} | Runs: {run_ids}")
    if limit:
        print(f"Limit: first {limit} questions per run (smoke test)")
    if use_native:
        print("Metrics: native Cortex LLM evaluation (AEO rubrics)")
    else:
        print("Metrics: pre-computed AEO scores (lookup, no LLM calls)")
    print("=" * 60)

    conn, session = get_connections(profile)

    # Create one SnowflakeConnector (and therefore one TruSession) shared
    # across all runs — re-creating it per run causes "TruSession with
    # different connector" errors since TruSession is a singleton.
    from trulens.connectors.snowflake import SnowflakeConnector
    connector = SnowflakeConnector(snowpark_session=session)

    # Load question bank
    print("\n[setup] Loading question bank...")
    reset_data()
    cfg = CONNECTION_PROFILES[profile]
    load_from_snowflake(conn, schema=f"{cfg['database']}.{cfg['schema']}")
    print(f"        {len(QUESTIONS)} questions loaded")

    total_recorded = 0
    failed_runs = []

    for run_id in run_ids:
        try:
            n = replay_run(run_id, conn, session, connector, limit=limit, profile=profile, use_native=use_native)
            total_recorded += n
        except Exception as e:
            print(f"\nERROR on run {run_id}: {e}")
            import traceback; traceback.print_exc()
            failed_runs.append(run_id)

    print(f"\n{'=' * 60}")
    print("REPLAY COMPLETE")
    print(f"  Total records written to TruLens: {total_recorded}")
    if failed_runs:
        print(f"  Failed runs: {failed_runs}")
    else:
        print("  All runs completed successfully")
    print(f"{'=' * 60}")
    print("\nView in Snowsight: AI & ML > Cortex AI > Evaluations")

    # Flush the BatchSpanProcessor before closing so the async export to
    # the Snowflake stage completes while the session is still alive.
    try:
        from trulens.core.session import TruSession
        tru_session = TruSession()
        processor = getattr(tru_session, "_experimental_otel_span_processor", None)
        if processor is not None:
            print("\n[teardown] Flushing OTel span processor...")
            processor.force_flush(timeout_millis=30_000)
            print("           OK")
    except Exception as e:
        print(f"[teardown] Flush warning (non-fatal): {e}")

    conn.close()
    session.close()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Replay pre-generated AEO responses into TruLens"
    )
    parser.add_argument(
        "--profile", default="snowhouse", choices=["devrel", "snowhouse"],
    )
    parser.add_argument(
        "--run-ids", nargs="+", type=int, default=list(range(1, 17)),
        help="Run IDs to replay (default: 1-16)",
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Limit to first N questions per run (for smoke testing)",
    )
    parser.add_argument(
        "--native", action="store_true", default=False,
        help=(
            "Use native Cortex LLM scoring (AEO rubrics via CORTEX.COMPLETE) "
            "instead of pre-computed AEO scores. Each question makes 5 LLM calls."
        ),
    )
    args = parser.parse_args()

    replay_all(
        run_ids=args.run_ids,
        profile=args.profile,
        limit=args.limit,
        use_native=args.native,
    )
