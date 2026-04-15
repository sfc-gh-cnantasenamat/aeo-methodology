"""
AEO Model Comparison Sweep — Baseline Run per Additional Model

Runs the baseline configuration (all factors OFF) for each respondent model
defined in MODEL_SWEEP, using run IDs that continue after the existing 16-run
claude-opus-4-6 factorial experiment.

Usage:
    python3 run_model_comparison.py [--profile snowhouse|devrel] [--dry-run]

Run ID convention:
    1–16  : claude-opus-4-6 (2^4 factorial experiment)
    17    : llama4-maverick  (baseline only)
    18    : openai-gpt-5.4   (baseline only)

To add more models in the future, append to MODEL_SWEEP and increment the
run IDs. Keep the run IDs sequential to avoid gaps in views.
"""

import argparse
import sys
import os

# Add scripts directory to path so we can import the orchestrator
sys.path.insert(0, os.path.dirname(__file__))

from aeo_run_orchestrator import run_benchmark

# ---------------------------------------------------------------------------
# Model sweep configuration
# model_name -> run_id for its baseline run
# ---------------------------------------------------------------------------
MODEL_SWEEP = {
    "llama4-maverick": 17,
    "openai-gpt-5.4":  18,
}

# Baseline configuration: all factors OFF, single-turn CORTEX.COMPLETE
BASELINE_CONFIG = dict(
    mode="baseline",
    domain_prompt=False,
    cite=False,
    self_critique=False,
    max_tokens=8192,
    enable_trulens=False,   # model comparison runs kept separate from TruLens experiment
)


def main():
    parser = argparse.ArgumentParser(
        description="Run baseline AEO benchmark for each additional respondent model."
    )
    parser.add_argument(
        "--profile",
        default="snowhouse",
        choices=["devrel", "snowhouse"],
        help="Snowflake connection profile (default: snowhouse)",
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=list(MODEL_SWEEP.keys()),
        help="Subset of models to run (default: all in MODEL_SWEEP)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would run without executing",
    )
    args = parser.parse_args()

    models_to_run = {m: MODEL_SWEEP[m] for m in args.models if m in MODEL_SWEEP}
    unknown = [m for m in args.models if m not in MODEL_SWEEP]
    if unknown:
        print(f"WARNING: unknown models (not in MODEL_SWEEP): {unknown}")

    print("=== AEO Model Comparison Sweep ===")
    print(f"Profile : {args.profile}")
    print(f"Models  : {list(models_to_run.keys())}")
    print(f"Config  : baseline (all factors OFF)")
    print()

    for model, run_id in models_to_run.items():
        print(f"--- Model: {model} | Run ID: {run_id} ---")
        if args.dry_run:
            print(f"  [DRY RUN] would call run_benchmark(run_id={run_id}, model='{model}', ...)")
            continue

        run_benchmark(
            run_id=run_id,
            model=model,
            profile=args.profile,
            **BASELINE_CONFIG,
        )
        print(f"  Completed run {run_id} for {model}\n")

    if not args.dry_run:
        print("=== All model comparison runs complete ===")
        print()
        print("Verify results:")
        print("  SELECT RUN_ID, MODEL, SCORE_PCT, MH_PCT")
        print("  FROM V_AEO_LEADERBOARD WHERE RUN_ID IN (17, 18);")


if __name__ == "__main__":
    main()
