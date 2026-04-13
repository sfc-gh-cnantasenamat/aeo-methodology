"""
Validate AEO TruLens feedback functions against existing scoring results.

Loads existing JSON scores from a completed run, then re-scores a subset
of questions using the new feedback functions and compares results.
"""

import json
import sys
sys.path.insert(0, "/Users/cnantasenamat/Documents/Coco/aeo/observability")

import snowflake.connector
from aeo_data import QUESTIONS, CANONICAL_SUMMARIES, MUST_HAVES
from aeo_feedback_functions import score_full_rubric

# Configuration
EXISTING_RESULTS_PATH = "/Users/cnantasenamat/Documents/Coco/aeo/runs/2026-04-04/run-3-baseline-8192tok/scoring-results-panel.json"
VALIDATION_QUESTIONS = [1, 10, 25, 40, 50]  # Subset to validate
JUDGE_MODEL = "claude-opus-4-6"  # Use one judge for quick validation

# Load existing results
print("Loading existing scoring results...")
try:
    with open(EXISTING_RESULTS_PATH) as f:
        existing_scores = json.load(f)
    print(f"  Loaded {len(existing_scores)} existing scores")
except FileNotFoundError:
    print(f"  File not found: {EXISTING_RESULTS_PATH}")
    print("  Skipping comparison, running standalone validation instead.")
    existing_scores = None

# Load existing responses to score
RESPONSE_PATHS = {
    "claude": "/Users/cnantasenamat/Documents/Coco/aeo/runs/2026-04-04/run-3-baseline-8192tok/responses-claude.md",
}

# Connect to Snowflake
print("Connecting to Snowflake...")
conn = snowflake.connector.connect(connection_name="devrel")
cur = conn.cursor()
cur.execute("USE WAREHOUSE COMPUTE_WH")

# Run validation on subset
print(f"\nValidating {len(VALIDATION_QUESTIONS)} questions with judge: {JUDGE_MODEL}")
print("=" * 70)

results = {}
for q_id in VALIDATION_QUESTIONS:
    question = QUESTIONS[q_id]
    canonical = CANONICAL_SUMMARIES[q_id]
    must_haves = MUST_HAVES[q_id]

    # Use canonical answer as a "perfect response" for validation
    # (should score close to 10/10)
    print(f"\nQ{q_id:02d}: {question[:60]}...")
    print(f"  Scoring canonical answer as response (should be ~10/10)...")

    scores = score_full_rubric(
        conn, JUDGE_MODEL, question, canonical, canonical, must_haves
    )

    results[q_id] = scores
    print(f"  Correctness:     {scores['correctness']}/2")
    print(f"  Completeness:    {scores['completeness']}/2")
    print(f"  Recency:         {scores['recency']}/2")
    print(f"  Citation:        {scores['citation']}/2")
    print(f"  Recommendation:  {scores['recommendation']}/2")
    print(f"  Total:           {scores['total']}/10")
    print(f"  Must-Have Pass:  {scores['must_have_pass']}/4")

    if scores.get("parse_error"):
        print(f"  WARNING: JSON parse error in judge response")
        print(f"  Raw: {scores['raw_response'][:200]}")

# Summary
print("\n" + "=" * 70)
print("VALIDATION SUMMARY")
print("=" * 70)
totals = [r["total"] for r in results.values()]
mh_totals = [r["must_have_pass"] for r in results.values()]
print(f"Questions validated: {len(VALIDATION_QUESTIONS)}")
print(f"Average total score: {sum(totals)/len(totals):.1f}/10")
print(f"Average MH pass:     {sum(mh_totals)/len(mh_totals):.1f}/4")

if all(t >= 7 for t in totals):
    print("\nVALIDATION PASSED: Canonical answers scored 7+ as expected.")
else:
    low = [f"Q{q}" for q, r in results.items() if r["total"] < 7]
    print(f"\nWARNING: Some canonical answers scored below 7: {low}")
    print("This may indicate issues with the judge prompt or canonical summaries.")

# Compare with existing if available
if existing_scores:
    print("\n" + "=" * 70)
    print("COMPARISON WITH EXISTING RESULTS")
    print("=" * 70)
    for q_id in VALIDATION_QUESTIONS:
        q_key = str(q_id)
        if q_key in existing_scores:
            old = existing_scores[q_key]
            new = results[q_id]
            # existing format may vary, try to extract total
            if isinstance(old, dict):
                old_total = old.get("total", old.get("panel_avg", {}).get("total", "N/A"))
            else:
                old_total = "N/A"
            print(f"  Q{q_id:02d}: existing={old_total}  new={new['total']}")

cur.close()
conn.close()
print("\nDone.")
