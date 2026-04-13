"""
Run AEOCortexProvider native evaluation on Run 1 (baseline) and Run 7
(agentic+citation) for 20 questions each, comparing against pre-computed
AEO scores. Results saved to observability/tmp/aeo_native_comparison.{json,txt}.
"""
import os, sys, json, time
os.environ["TRULENS_OTEL_TRACING"] = "1"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import snowflake.connector
from snowflake.snowpark import Session

print("Connecting to Snowflake...")
conn = snowflake.connector.connect(connection_name="my-snowflake")
cur = conn.cursor()
cur.execute("USE ROLE DEVREL_INGEST_RL")
cur.execute("USE WAREHOUSE SNOWADHOC")
cur.execute("USE DATABASE DEVREL")
cur.execute("USE SCHEMA CNANTASENAMAT_DEV")

session = Session.builder.config("connection_name", "my-snowflake").create()
session.sql("USE ROLE DEVREL_INGEST_RL").collect()
session.sql("USE WAREHOUSE SNOWADHOC").collect()
print("Connected.\n")

from aeo_cortex_provider import AEOCortexProvider

provider = AEOCortexProvider(snowpark_session=session)
print(f"AEOCortexProvider ready (judge: {provider._models})\n")

def load_sample(run_id, n=5):
    cur.execute(f"""
        SELECT q.QUESTION_ID, q.QUESTION_TEXT, r.RESPONSE_TEXT,
               ROUND(AVG(s.CORRECTNESS),    2) AS aeo_correctness,
               ROUND(AVG(s.COMPLETENESS),   2) AS aeo_completeness,
               ROUND(AVG(s.RECENCY),        2) AS aeo_recency,
               ROUND(AVG(s.CITATION),       2) AS aeo_citation,
               ROUND(AVG(s.RECOMMENDATION), 2) AS aeo_recommendation,
               ROUND(AVG(s.TOTAL_SCORE),    2) AS aeo_total,
               ROUND(AVG(s.MUST_HAVE_PASS), 2) AS aeo_must_have,
               q.CANONICAL_ANSWER, q.MUST_HAVE_1, q.MUST_HAVE_2,
               q.MUST_HAVE_3, q.MUST_HAVE_4, q.MUST_HAVE_5
        FROM AEO_QUESTIONS q
        JOIN AEO_RESPONSES r ON r.QUESTION_ID = q.QUESTION_ID AND r.RUN_ID = {run_id}
        JOIN AEO_SCORES    s ON s.QUESTION_ID = q.QUESTION_ID AND s.RUN_ID = {run_id}
        GROUP BY q.QUESTION_ID, q.QUESTION_TEXT, r.RESPONSE_TEXT,
                 q.CANONICAL_ANSWER, q.MUST_HAVE_1, q.MUST_HAVE_2,
                 q.MUST_HAVE_3, q.MUST_HAVE_4, q.MUST_HAVE_5
        ORDER BY q.QUESTION_ID
        LIMIT {n}
    """)
    return cur.fetchall()

results = {}

SAMPLE_N = 20

for run_id, run_label in [(1, "run01_baseline"), (7, "run07_agentic_citation")]:
    print(f"=== {run_label} ===")
    rows = load_sample(run_id, n=SAMPLE_N)
    run_results = []

    for (qid, question, response,
         aeo_corr, aeo_comp, aeo_rec, aeo_cite, aeo_rec2, aeo_total, aeo_mhp,
         canonical, mh1, mh2, mh3, mh4, mh5) in rows:
        print(f"  {qid}: {question[:58]}...")
        must_haves = [mh1, mh2, mh3, mh4, mh5]
        row = {
            "question_id":     qid,
            "question":        question,
            "response_length": len(response),
            "aeo_scores": {
                "correctness":    float(aeo_corr    or 0),
                "completeness":   float(aeo_comp    or 0),
                "recency":        float(aeo_rec     or 0),
                "citation":       float(aeo_cite    or 0),
                "recommendation": float(aeo_rec2    or 0),
                "total":          float(aeo_total   or 0),
                "total_pct":      round(float(aeo_total or 0) / 50 * 100, 1),
                "must_have_pass": float(aeo_mhp     or 0),
            },
            "native_scores": {},
            "elapsed_s": {},
        }

        metric_calls = [
            ("correctness",    lambda: provider.correctness(question, response, canonical_answer=canonical)),
            ("completeness",   lambda: provider.completeness(question, response, canonical_answer=canonical)),
            ("recency",        lambda: provider.recency(question, response)),
            ("citation",       lambda: provider.citation_quality(question, response)),
            ("recommendation", lambda: provider.recommendation(question, response)),
            ("must_have_pass", lambda: provider.must_have_pass(question, response, must_haves=must_haves)),
        ]

        for metric_name, fn in metric_calls:
            t0 = time.time()
            try:
                score = fn()
                elapsed = round(time.time() - t0, 1)
                row["native_scores"][metric_name] = round(float(score), 4)
                row["elapsed_s"][metric_name] = elapsed
                print(f"    {metric_name:<16} native={score:.3f}  aeo={row['aeo_scores'].get(metric_name, 'n/a')}  ({elapsed}s)")
            except Exception as e:
                elapsed = round(time.time() - t0, 1)
                row["native_scores"][metric_name] = None
                row["elapsed_s"][metric_name] = elapsed
                print(f"    {metric_name:<16} ERROR: {e}  ({elapsed}s)")

        run_results.append(row)
        print()

    results[run_label] = run_results
    print()

# ── output dir ────────────────────────────────────────────────────────────────
out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tmp")
os.makedirs(out_dir, exist_ok=True)

# ── JSON ──────────────────────────────────────────────────────────────────────
json_path = os.path.join(out_dir, "aeo_native_comparison.json")
with open(json_path, "w") as f:
    json.dump({"judge_model": provider._models, "sample_per_run": 5, "runs": results}, f, indent=2)
print(f"JSON saved: {json_path}")

# ── Text summary ──────────────────────────────────────────────────────────────
txt_path = os.path.join(out_dir, "aeo_native_comparison.txt")
COLS = ["correctness", "completeness", "recency", "citation", "recommendation", "must_have_pass"]

def fmt(v): return f"{v:.3f}" if v is not None else " ERR"
def avg(rows, src, key):
    vals = [r[src][key] for r in rows if r[src].get(key) is not None]
    return round(sum(vals) / len(vals), 3) if vals else None

with open(txt_path, "w") as f:
    f.write("AEO Native TruLens Evaluation: Pre-computed vs AEOCortexProvider\n")
    f.write(f"Judge: {provider._models}  |  Sample: {SAMPLE_N} questions per run\n")
    f.write("=" * 90 + "\n\n")

    for run_label, run_rows in results.items():
        f.write(f"Run: {run_label}\n")
        f.write("-" * 90 + "\n")
        hdr = f"{'QID':<6} {'Metric':<16} {'AEO (0-10)':>10} {'Native (0-1)':>12} {'AEO norm':>9} {'Delta':>7}\n"
        f.write(hdr)
        f.write("-" * 90 + "\n")

        for r in run_rows:
            a = r["aeo_scores"]
            n = r["native_scores"]
            f.write(f"{r['question_id']}\n")
            for col in COLS:
                aeo_raw  = a.get(col)
                nat      = n.get(col)
                aeo_norm = round(aeo_raw / 10.0, 3) if col != "must_have_pass" and aeo_raw is not None else (aeo_raw if aeo_raw is not None else None)
                delta    = round(nat - aeo_norm, 3) if (nat is not None and aeo_norm is not None) else None
                aeo_disp = f"{aeo_raw:.2f}" if aeo_raw is not None else " n/a"
                f.write(
                    f"{'':6} {col:<16} {aeo_disp:>10} {fmt(nat):>12} "
                    f"{fmt(aeo_norm):>9} {(f'{delta:+.3f}' if delta is not None else ' n/a'):>7}\n"
                )
            f.write(f"{'':6} {'aeo_total_pct':16} {'':>10} {'':>12} {a['total_pct']:>8.1f}%\n")
            f.write("\n")

        f.write("-" * 90 + "\n")
        f.write(f"{'AVG':<6}\n")
        for col in COLS:
            aeo_avg  = avg(run_rows, "aeo_scores", col)
            nat_avg  = avg(run_rows, "native_scores", col)
            aeo_norm = round(aeo_avg / 10.0, 3) if col != "must_have_pass" and aeo_avg is not None else aeo_avg
            delta    = round(nat_avg - aeo_norm, 3) if (nat_avg is not None and aeo_norm is not None) else None
            aeo_disp = f"{aeo_avg:.2f}" if aeo_avg is not None else " n/a"
            f.write(
                f"{'':6} {col:<16} {aeo_disp:>10} {fmt(nat_avg):>12} "
                f"{fmt(aeo_norm):>9} {(f'{delta:+.3f}' if delta is not None else ' n/a'):>7}\n"
            )
        total_avg = avg(run_rows, "aeo_scores", "total_pct")
        f.write(f"{'':6} {'aeo_total_pct':16} {'':>10} {'':>12} {total_avg:>8.1f}%\n")
        f.write("\n\n")

    f.write("=" * 90 + "\n\n")
    f.write("Run 1 vs Run 7 summary\n")
    f.write("-" * 90 + "\n")
    for run_label, run_rows in results.items():
        f.write(f"  {run_label:<30}  AEO total: {avg(run_rows,'aeo_scores','total_pct'):.1f}%\n")
        for col in COLS:
            nat = avg(run_rows, "native_scores", col)
            aeo = avg(run_rows, "aeo_scores", col)
            aeo_n = round(aeo / 10.0, 3) if col != "must_have_pass" and aeo is not None else aeo
            delta = round(nat - aeo_n, 3) if (nat is not None and aeo_n is not None) else None
            f.write(f"    {col:<16}  native={fmt(nat)}  aeo_norm={fmt(aeo_n)}  delta={f'{delta:+.3f}' if delta is not None else 'n/a'}\n")
        f.write("\n")

    f.write("\nNotes:\n")
    f.write("  AEO (0-10): raw score averaged across 3 judges (claude-opus-4-6, llama4-maverick, openai-gpt-5.4)\n")
    f.write("  Native (0-1): 3-judge panel (claude-opus-4-6, llama4-maverick, openai-gpt-5.4) using AEO rubric prompts\n")
    f.write("  AEO norm: AEO/10 for comparison to native 0-1 scale\n")
    f.write("  Delta: native minus aeo_norm (positive = native scored higher)\n")
    f.write("  correctness/completeness: evaluated against CANONICAL_ANSWER from AEO_QUESTIONS\n")
    f.write("  must_have_pass: evaluated against MUST_HAVE_1-5 semantic criteria via LLM judge panel\n")

print(f"Text saved: {txt_path}")
session.close()
conn.close()
print("\nDone.")
