# TruLens Integration — Resume Notes

## Status: In Progress

Last worked on: April 2026

---

## Architecture Overview

Two parallel scoring approaches exist side-by-side:

| Approach | Script | Table | Scale | Judges | Prompt style |
|---|---|---|---|---|---|
| SP (`AEO_SCORE_RESPONSE`) | `aeo_score_all.py --sp-only` | `AEO_SCORES` | 1–10 | 5 | Combined (all dims in one prompt) |
| Provider (`AEOCortexProvider`) | `aeo_score_all.py --provider-only` | `AEO_SCORES_PROVIDER` | 0–1 | 3 | Isolated (one prompt per dim) |

The comparison view `V_AEO_SCORES_COMPARISON` joins both (normalizing SP to 0–1) with delta columns.

---

## File Locations

```
dev/spcs/aeo_score_all.py                      # Dual-scoring script (SP + Provider)
dev/observability/replay_runs_to_trulens.py    # TruLens replay script
dev/observability/aeo_cortex_provider.py       # AEOCortexProvider class
repo/scripts/replay_runs_to_trulens.py         # Canonical copy in repo
```

---

## Current Data State

| Table | Rows | Notes |
|---|---|---|
| `AEO_SCORES` | 11,264 | All 24 runs × 128 questions × ~3–5 judges (SP) |
| `AEO_SCORES_PROVIDER` | 3 | Run 24, Q001–Q003 only (test run) |
| `AEO_TRANSCRIPT` | 0 | Forward-only, no backfill performed |
| `V_AEO_SCORES_COMPARISON` | — | View joining both tables with deltas |

---

## TruLens Mode: Non-`--native` (Working)

Uses `ScoreLookup` with pre-computed scores from `AEO_SCORES`. Records ingest successfully and metric scores are populated in Snowsight Evaluations.

**Command to run all 24 runs:**
```bash
cd /Users/cnantasenamat/Documents/Coco/aeo/dev/observability
python3 replay_runs_to_trulens.py --profile snowhouse --run-ids 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24
```

**Smoke test (run 24, 3 questions):**
```bash
python3 replay_runs_to_trulens.py --profile snowhouse --run-ids 24 --limit 3
```

**Snowsight location:** AI & ML > Evaluations (Snowhouse / SFCOGSOPS-SNOWHOUSE, AWS US West 2)

---

## TruLens Mode: `--native` (Broken — metric scores null)

`AEOCortexProvider` is a plain Python class, not a TruLens `Provider` subclass. TruLens cannot serialize its methods for `compute_metrics`, so records ingest (`INVOCATION_COMPLETED`) but `metrics: null`.

**Test result (run 24, 3 questions):**
- App registered: `run24_nodp_nocite_ag_nosc`
- 3 records ingested, status `INVOCATION_COMPLETED`
- Metric scores: null

**Fix required (not yet done):** Make `AEOCortexProvider` extend the TruLens `Provider` base class so TruLens can serialize its methods.

---

## Dual Scoring Script

**Script:** `dev/spcs/aeo_score_all.py`

```bash
# Score run 24, all questions, both approaches
python3 aeo_score_all.py --run-ids 24

# Score specific runs, limit for testing
python3 aeo_score_all.py --run-ids 24 --limit 3

# SP only or Provider only
python3 aeo_score_all.py --run-ids 24 --sp-only
python3 aeo_score_all.py --run-ids 24 --provider-only
```

**must_haves wiring:** Script fetches `MUST_HAVE_1`–`MUST_HAVE_5` from `AEO_QUESTIONS` and passes them as `question_metadata["must_haves"]`. Without this, `must_have_pass` falls back to a docs URL regex returning `0.0`.

---

## Scoring Gap (SP vs Provider)

After aligning the recency rubric, a residual gap of ~−0.247 on recency remains. This is structural:
- SP uses a **combined prompt** (all dimensions together) → anchoring effect inflates recency when other dims score high
- Provider uses **isolated prompts** (one per dimension) → stricter, no anchoring

This gap is accepted as a known structural difference, not a bug.

---

## Pending Work

1. **Fill `AEO_SCORES_PROVIDER` for all 24 runs** — run `aeo_score_all.py --provider-only --run-ids 1 2 ... 24`
2. **Replay all 24 runs to TruLens** (non-`--native`) — populates Snowsight Evaluations with working metric scores
3. **Optional: Fix `--native` mode** — extend `AEOCortexProvider` from TruLens `Provider` base class

---

## Snowflake Config

- **Connection:** `my-snowflake` (Snowhouse / SFCOGSOPS-SNOWHOUSE)
- **Schema:** `DEVREL.CNANTASENAMAT_DEV`
- **Warehouse:** `SNOWADHOC`
- **DDL role:** `DEVREL_ADMIN_RL`
- **Ingestion role:** `DEVREL_INGEST_RL`
