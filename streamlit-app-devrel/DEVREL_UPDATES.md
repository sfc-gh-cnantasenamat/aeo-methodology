# DevRel AEO Benchmark Dashboard — Session Updates

**Date:** April 30, 2026  
**App:** `CHANINN_DEMO_DATA.APPS.AEO_BENCHMARK_DASHBOARD`  
**Account:** SFDEVREL-SFDEVREL_ENTERPRISE

---

## Summary

Migrated all chart pages from the old `V_AEO_*` views and `AEO_RUNS`/`AEO_SCORES` tables to the new **V3 data** (`V3_AEO_SCORES`, `V3_AEO_TRANSCRIPT`), which contains 3 complete 16-run factorial benchmarks for `claude-opus-4-6`, `claude-opus-4-7`, and `openai-gpt-5.4` (48 runs total, 640 rows each). Added **independent `st.segmented_control` model selectors** to every chart section across all pages so each section can compare models independently.

---

## V3 Data Schema Reference

| Table | Rows | Key columns |
|---|---|---|
| `V3_AEO_SCORES` | 48 runs × 128 questions × 5 judges | `RUN_ID` (string), `QUESTION_ID`, `JUDGE_MODEL`, `CORRECTNESS`, `COMPLETENESS`, `RECENCY`, `CITATION`, `RECOMMENDATION`, `TOTAL_SCORE`, `MUST_HAVE_PASS`, `SCORED_AT` |
| `V3_AEO_TRANSCRIPT` | 48 runs × 128 questions | `RUN_ID`, `QUESTION_ID`, `N_TURNS`, `N_TOOL_CALLS`, `TRANSCRIPT_JSONL`, `INPUT_TOKENS`, `OUTPUT_TOKENS`, `GENERATION_SECS` |

**RUN_ID encoding:** `{model}-{config}` where model is e.g. `claude-opus-4-7` and config suffix encodes flags as letters: `base` = Baseline, `D` = Domain Prompt, `C` = Citation, `A` = Agentic, `S` = Self-Critique. Examples: `claude-opus-4-6-base`, `claude-opus-4-7-CA`, `openai-gpt-5.4-DCAS`.

**Important column difference vs old views:** `V3_AEO_SCORES.CITATION` (dimension score 0-10) vs old `V_AEO_PER_QUESTION_HEATMAP.CITATION_SCORE`. All V3 queries alias it as `AVG(CITATION) AS CITATION_SCORE` to preserve compatibility.

---

## Files Changed

### New: `utils/ui.py`

Shared UI helper used by all chart pages.

- `model_selector(key)` — renders `st.segmented_control` for model selection, queries distinct models from `V3_AEO_SCORES` on DevRel (falls back to `claude-opus-4-6` on Snowhouse). Returns `(friendly_label, model_id)`.
- Guards against `None` (deselected state): `_sel = _sel or (_labels[0] if _labels else "")`.

### Modified: `utils/db.py`

Added V3 SQL helper functions and model label constants:

- `V3_MODEL_LABELS` — dict mapping model IDs to friendly display names (`"Opus 4.6"`, `"Opus 4.7"`, `"GPT 5.4"`).
- `v3_models_sql()` — SQL for distinct model names from `V3_AEO_SCORES`.
- `v3_leaderboard_sql(model)` — V3 equivalent of `V_AEO_LEADERBOARD` for one model. Derives config flag columns from RUN_ID suffix via `CONTAINS(REGEXP_REPLACE(...), 'X')`.
- `v3_per_question_sql(model)` — V3 equivalent of `V_AEO_PER_QUESTION_HEATMAP` for one model. Aliases `AVG(CITATION) AS CITATION_SCORE` for backward compatibility.

Both SQL helpers use `WHERE RUN_ID LIKE '{model}-%'` to filter to one model, enabling per-model `@st.cache_data` caching.

### Modified: `pages/home.py`

- Updated stats query with ENV branch for V3 tables on DevRel.
- Updated "A panel of 3-5 LLM judges" to "A panel of **5 LLM judges**".

### Modified: `pages/leaderboard.py`

Restructured with **3 independent section-level model selectors**:

| Section | Key |
|---|---|
| Rankings Table + KPI metrics | `lb_rankings` |
| Dimension Breakdown — Top 3 Configs | `lb_dimension` |
| Complexity vs Performance | `lb_complexity` |

- Added `load_lb(model)` helper to avoid repeated data-loading code.
- DevRel path: `V_AEO_LEADERBOARD` replaced with `v3_leaderboard_sql(_model)`.
- Dimension Breakdown radar query: `V_AEO_PER_QUESTION_HEATMAP` replaced with direct `V3_AEO_SCORES` aggregation per model.

### Modified: `pages/questions_explorer.py`

- Added `st.segmented_control` model selector.
- DevRel path: Main data query replaced with `v3_per_question_sql(_model)` joined with `AEO_QUESTIONS`.
- "View generated answer" expander: DevRel path reads `V3_AEO_TRANSCRIPT.TRANSCRIPT_JSONL` and extracts the last assistant message by parsing JSONL lines.
- Config filter simplified from `ConfigModel` (config + model) to `Config` alone.

### Modified: `pages/factors_influence.py`

Restructured with **4 independent section-level model selectors**:

| Section | Key |
|---|---|
| Main Effects | `fi_main_effects` |
| Score Lift by Feature | `fi_score_lift` |
| Factor Interaction Heatmap | `fi_interaction` |
| Dimension Breakdown by Question | `fi_dim_breakdown` |

- Added `load_lb_for_model(model)` and `compute_gains(lb_factorial)` helpers to avoid code duplication.
- `V_AEO_FACTORIAL_EFFECTS` view replaced with dynamic computation directly from the leaderboard DataFrame (ON mean minus OFF mean per factor).
- Key Insights text made fully dynamic — no more hardcoded pp values.
- Fixed SyntaxError: backslash-in-f-string (Python 3.11 incompatible). Badge values now pre-computed as variables before f-string interpolation.

### Modified: `pages/factorial_heatmap.py`

- Added `st.segmented_control` model selector (`fh_model_sel`).
- DevRel path: `V_AEO_PER_QUESTION_HEATMAP` replaced with direct join of `V3_AEO_SCORES` and `AEO_QUESTIONS`, filtered by `RUN_ID LIKE '{model}-%'`.

### Modified: `pages/category_performance.py`

Restructured with **3 independent section-level model selectors**:

| Section | Key |
|---|---|
| Dumbbell Chart | `cat_dumbbell_model` |
| Priority Matrix | `cat_priority_model` |
| Category Impact Table | `cat_impact_model` |

- Caption "Per-category improvement..." moved below the dumbbell chart.
- Category Impact Table now has its own independent selector and data load (`pq_table` / `cat_stats_table`), separate from the Priority Matrix.

### Modified: `pages/test_prompt.py`

- Renamed `cortex-code` model option to `coco-opus-4-6` and added `coco-opus-4-7` and `coco-gpt-5.4`.
- `CORTEX_NATIVE` string constant replaced with `CORTEX_NATIVE_MODELS` dict mapping each `coco-*` variant to its underlying model ID.
- Execution branch now extracts `native_model` per variant and passes `--model <native_model>` to the `cortex --print` CLI call.
- SPCS status caption updated to show the native model name.

### Modified: `pages/test_skill.py`

- Same `coco-*` rename and `CORTEX_NATIVE_MODELS` dict as `test_prompt.py`.
- UI hint strings updated: "Non-coco models", "coco model via the skill stage".
- Removed standalone `CORTEX_NATIVE = "cortex-code"` line.
- `--model <native_model>` passed to `cortex --print` CLI call.
- SPCS status caption updated to "Running CoCo ({native_model}) via SPCS".

### Modified: `snowflake-devrel.yml`

Added `utils/ui.py` to the artifacts list so it is deployed with the app.

---

## Layout Convention (all pages)

Every chart section now follows this consistent pattern:

```
st.header(...)             <- section title
st.caption(...)            <- section description
model_selector(key)        <- st.segmented_control (DevRel only, unique key per section)
<data loading for section>
<chart>
```

The top-level single model selector has been removed from all pages. Each section is fully independent.

---

## Snowhouse Compatibility

All V3 code is gated behind `if ENV == "devrel"` blocks. Snowhouse paths are preserved with the original `V_AEO_*` view queries. `V3_AEO_SCORES` and `V3_AEO_TRANSCRIPT` do not exist on Snowhouse and are never queried there. Snowhouse loads all shared data once at page top (no per-section selectors).

---

## Deployment

```bash
SNOW=/Library/Frameworks/Python.framework/Versions/3.11/bin/snow
cd /Users/cnantasenamat/Documents/Coco/aeo/repo/streamlit-app-devrel
cp snowflake.yml snowflake-snowhouse.yml && cp snowflake-devrel.yml snowflake.yml
$SNOW streamlit deploy --replace --connection devrel
cp snowflake-snowhouse.yml snowflake.yml && rm snowflake-snowhouse.yml
```

After deploy, trigger metadata refresh:
```sql
ALTER STREAMLIT CHANINN_DEMO_DATA.APPS.AEO_BENCHMARK_DASHBOARD SET QUERY_WAREHOUSE = CHANIN_XS;
```

