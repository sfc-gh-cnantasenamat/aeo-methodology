# AGENTS.md

## Overview

AEO (AI Engine Optimization) is a benchmark that measures how accurately AI coding assistants answer Snowflake developer questions. It uses a **2^4 factorial experiment design** with 4 binary factors (Domain Prompt, Citation, Agentic, Self-Critique) tested in all 16 combinations on Claude Opus 4.6. Each of the 128 questions (32 product categories, 4 questions each) is scored by a 3-judge LLM panel on 5 dimensions (Correctness, Completeness, Recency, Citation, Recommendation) plus up to 5 binary must-have elements.

## Repository structure

```
input/                  # Question bank, canonical answers, experiment prompts, run mapping
results/                # Analysis views sliced by category, dimension, factor, engine, etc.
scores/                 # Per-question JSON scoring files for all 16 runs
slides/                 # Markdown source for methodology and results presentations
paper/                  # Internal whitepaper (see Paper section below)
streamlit/              # AEO dashboard (deployed to Streamlit in Snowflake)
streamlit-app-local/    # Local development copy — safe to iterate freely
streamlit-app-snowhouse/ # Snowhouse-specific copy (DEVREL.CNANTASENAMAT_DEV)
streamlit-app-devrel/   # DevRel-specific copy (CHANINN_DEMO_DATA.APPS)
```

### Streamlit app directories

Three separate directories exist to prevent local tweaks from accidentally breaking the deployed versions:

| Directory | Purpose | Target |
|-----------|---------|--------|
| `streamlit-app-local/` | Local development and experimentation. Iterate freely here without risk of breaking either deployed app. | `streamlit run app.py` locally |
| `streamlit-app-snowhouse/` | Snowhouse deployment source. Contains Snowhouse-specific files (`pyproject-snowhouse.toml`, `snowflake.yml` with `STREAMLIT_DEDICATED_POOL`). | `DEVREL.CNANTASENAMAT_DEV.AEO_BENCHMARK_DASHBOARD` |
| `streamlit-app-devrel/` | DevRel deployment source. Contains DevRel-specific files (`snowflake-devrel.yml`, full `pyproject.toml` with PyPI deps via `PYPI_ACCESS_INTEGRATION`). | `CHANINN_DEMO_DATA.APPS.AEO_BENCHMARK_DASHBOARD` |

**Rule:** always make changes in `streamlit-app-local/` first and verify locally before manually propagating to the Snowhouse or DevRel directories and redeploying.

## Snowflake data layer

All benchmark data lives in **`DEVREL.CNANTASENAMAT_DEV`** (local connection: `my-snowflake`).

**Tables:**
- `AEO_QUESTIONS` — 128-question bank with canonical answers and must-have checklists
- `AEO_RUNS` — Run metadata (which factors were active, model, timestamp)
- `AEO_RESPONSES` — Generated responses per run per question (4 columns: `RUN_ID`, `QUESTION_ID`, `RESPONSE_TEXT`, `GENERATED_AT`)
- `AEO_TRANSCRIPT` — Observability data per run per question (25 columns; see schema below)
- `AEO_SCORES` — Judge scores per run per question per dimension

**Views:**
- `V_AEO_LEADERBOARD` — Runs ranked by overall score
- `V_AEO_FACTORIAL_EFFECTS` — Main effects and interaction effects of each factor
- `V_AEO_PER_QUESTION_HEATMAP` — Score matrix (run x question)
- `V_AEO_JUDGE_AGREEMENT` — Inter-judge correlation and disagreement analysis
- `V_AEO_TRANSCRIPT_STATS` — Per-run aggregates: total turns, tool calls (per tool), cache hit pct/rate, avg generation secs

**`AEO_TRANSCRIPT` schema:**

| Column | Type | Description |
|--------|------|-------------|
| `RUN_ID` | VARCHAR | Foreign key to `AEO_RUNS` |
| `QUESTION_ID` | INTEGER | Foreign key to `AEO_QUESTIONS` |
| `N_TURNS` | INTEGER | Number of conversation turns |
| `N_TOOL_CALLS` | INTEGER | Total tool calls across all turns |
| `TOOL_CALL_BASH` | INTEGER | Count of `bash` tool calls |
| `TOOL_CALL_READ` | INTEGER | Count of `read` tool calls |
| `TOOL_CALL_WRITE` | INTEGER | Count of `write` tool calls |
| `TOOL_CALL_EDIT` | INTEGER | Count of `edit` tool calls |
| `TOOL_CALL_GLOB` | INTEGER | Count of `glob` tool calls |
| `TOOL_CALL_GREP` | INTEGER | Count of `grep` tool calls |
| `TOOL_CALL_SQL_EXECUTE` | INTEGER | Count of `sql_execute` tool calls |
| `TOOL_CALL_SKILL` | INTEGER | Count of `skill` tool calls |
| `TOOL_CALL_WEB_FETCH` | INTEGER | Count of `web_fetch` tool calls |
| `TOOL_CALL_WEB_SEARCH` | INTEGER | Count of `web_search` tool calls |
| `TOOL_CALL_OTHER` | INTEGER | Sum of all tool calls not in the tracked list above |
| `N_THINKING_BLOCKS` | INTEGER | Number of extended thinking blocks in the response |
| `TRANSCRIPT_JSONL` | TEXT | Full conversation as newline-delimited JSON |
| `INPUT_TOKENS` | INTEGER | Total prompt tokens (including cache reads/writes) |
| `OUTPUT_TOKENS` | INTEGER | Total completion tokens |
| `CACHE_READ_TOKENS` | INTEGER | Tokens served from the prompt cache |
| `CACHE_WRITE_TOKENS` | INTEGER | Tokens written to the prompt cache |
| `FIRST_REQUEST_ID` | VARCHAR | REQUEST_ID of the first API turn (from `CORTEX_CODE_CLI_USAGE_HISTORY`) |
| `LAST_REQUEST_ID` | VARCHAR | REQUEST_ID of the last API turn |
| `GENERATION_SECS` | FLOAT | Wall-clock seconds from prompt submission to response |

## Streamlit dashboard

The interactive benchmark dashboard lives in `streamlit/`. It is deployed to two Snowflake accounts (Snowhouse and DevRel). For full deployment instructions, environment-specific constants, Snowflake objects, SPCS setup, and known pitfalls see `streamlit/DEPLOYMENT.md`.

## Git workflow

Two remotes:
- **`snowflake-eng`** — `https://github.com/snowflake-eng/aeo.git` (engineering org, primary). Uses the `chanin-nantasenamat_snow` PAT stored at `~/.github/chanin-nantasenamat_snow`.
- **`origin`** — `sfc-gh-cnantasenamat` fork (for GH Pages presentations)

Push paper and code changes to `snowflake-eng`. Presentation slides deploy via `origin` to GH Pages.

## Paper

The whitepaper source lives in `paper/paper.md`. A LaTeX/PDF version is maintained in `paper/latex/`.

### Structure

```
paper/
├── paper.md                          # Source of truth (Markdown)
├── assets/                           # Figures referenced by both .md and .tex
│   ├── fig_01_main_effects.png
│   ├── fig_02_dumbbell_chart.png
│   └── fig_03_category_heatmap.png
├── paper.pdf                         # Compiled PDF (copied here after compilation)
├── latex/
│   └── paper.tex                     # LaTeX source (manually synced from paper.md)
└── scripts/
    ├── fig_01_main_effects.py        # Main effects bar chart
    ├── fig_02_dumbbell_chart.py      # Baseline vs best dumbbell chart
    └── fig_03_category_heatmap.py    # Category heatmap (grouped by Agentic)
```

### Regenerating figures

Each script reads from the Snowflake `DEVREL.AEO_OBSERVABILITY` schema and writes its PNG to `paper/assets/`. Run from the repo root:

```bash
python paper/scripts/fig_01_main_effects.py
python paper/scripts/fig_02_dumbbell_chart.py
python paper/scripts/fig_03_category_heatmap.py
```

### Compiling the PDF

Requires TeX Live (`pdflatex`). Run two passes from the `latex/` directory so cross-references resolve:

```bash
cd paper/latex
pdflatex -interaction=nonstopmode paper.tex
pdflatex -interaction=nonstopmode paper.tex
cp paper.pdf ../paper.pdf
```

The `.tex` file uses `../assets/` relative paths for `\includegraphics`, so it must be compiled from inside `paper/latex/`. After compilation, copy the PDF up to `paper/` so it sits alongside `paper.md`.

LaTeX auxiliary files (`.aux`, `.log`, `.out`) are excluded via `.gitignore`.

### Keeping Markdown and LaTeX in sync

`paper.md` is the source of truth. When editing content, update `paper.md` first, then mirror the changes into `paper/latex/paper.tex` and recompile the PDF.

## PM Actionability

### The Central Question

**If a PM provides a prompt or a question, how does that influence the score?**

The benchmark already proves that configuration choices (agentic tools, citation instruction, domain prompt, self-critique) produce a 29.1pp score range. The next step is making that measurable and testable for PMs directly: let them supply their own prompts or questions, trigger an eval, and see exactly how their input changes the score.

### Two Eval Loops

Everything below serves one of two evaluation loops:

#### Loop 1: PM Prompt/Question Testing

A PM provides a system prompt, a question, or both. The benchmark pipeline scores the response and returns per-dimension results compared to the baseline. This answers: "Does my prompt/question formulation improve the answer quality for my product area?"

```
PM provides prompt/question
    → Cortex Code generates response (with prompt applied)
    → 3-judge panel scores response
    → PM sees score delta vs baseline
    → PM iterates on prompt
```

**What this enables:**
- PMs can test whether adding a specific system prompt (e.g., "You are a Cortex Agents expert, always reference the orchestration loop architecture") improves scores for their category
- PMs can test whether rephrasing a question changes the answer quality (e.g., does "debug my agent" score differently than "my Cortex Agent returns empty results, here is the error log")
- PMs can submit new questions not in the current 128-question bank and see how the AI performs, identifying new coverage gaps

#### Loop 2: Bundled CoCo Skills as an Eval Factor

CoCo ships with bundled skills (e.g., `cortex-agent`, `dynamic-tables`, `snowpark-python`, `iceberg`, `semantic-view`, etc.). Each skill injects domain-specific instructions, patterns, and constraints into the agent's context. The benchmark can measure whether having a specific skill loaded improves answer quality for that skill's product category.

```
Run question with skill loaded
    → Cortex Code uses skill context to generate response
    → 3-judge panel scores response
    → Compare: skill-assisted score vs bare agentic score
    → Identifies which skills actually help and which don't
```

**What this enables:**
- Measure the marginal score lift of each bundled skill against its relevant category questions
- Identify skills that need improvement (low lift or negative lift)
- Prioritize skill development effort based on measured quality impact
- Track skill quality over time as skills are updated

**Collaboration with Gilberto:** Gilberto owns the CoCo skills ecosystem. The AEO benchmark provides the measurement layer for skill quality. The collaboration model is:
- AEO provides the eval harness: question bank, scoring pipeline, and results infrastructure
- Gilberto provides the skill catalog and skill-loading mechanism
- Together: run each category's questions with and without the relevant skill, measure the delta, and use that data to prioritize skill improvements
- Shared output: a skill quality leaderboard showing which skills deliver the most (and least) answer quality improvement

### Core Insight (Documentation Gaps)

Low AI scores on a product category are primarily a **documentation coverage signal**, not an AI configuration problem. PMs cannot control how developers phrase questions or which retrieval configuration a tool uses. What they can control is the quality, completeness, and structure of the documentation that AI systems retrieve from. The benchmark measures the ceiling on answer quality given the current state of documentation.

### PM Action Framework

The paper (Section: Product Category Intelligence) maps weakest question type to documentation gap type to recommended first action:

| Weakest Type | Documentation Gap | Recommended Action |
|---|---|---|
| **Debug** (41% of categories) | Troubleshooting guides, runbooks, common error patterns are missing or sparse | Publish how-to-debug guides per feature, document common error messages and resolutions, add diagnostic decision trees |
| **Compare** (28% of categories) | Decision guides and "when to use X vs Y" content are absent | Publish explicit comparison pages, add architectural decision guidance, document tradeoffs |
| **Implement** (25% of categories) | How-to guides are incomplete, missing working code, or reflect outdated APIs | Audit step-by-step tutorials for completeness, add working end-to-end code examples, update deprecated syntax |
| **Explain** (6% of categories) | Conceptual overview pages are thin or absent | Strengthen concept docs, add architecture diagrams, explain "why this feature exists" |

**How a PM uses this:** open the per-category table in the paper, find their product area, read the Weakest column, then follow the corresponding row above to identify the specific documentation type to invest in first.

### What Exists Today

#### Paper (paper/paper.md)

The paper is the primary PM-actionable artifact:

- **Product Category Intelligence section** with a 32-row table showing per-category overall score, per-question-type breakdown, and weakest type highlighted
- **PM Action Framework** mapping each gap type to a concrete documentation action
- **Category-specific observations** calling out the highest-priority gaps (Snowflake Postgres, Data Quality & Observability, Cortex Agents, etc.)
- **Summary and Conclusion** both direct PMs to the relevant sections with explicit "first action" guidance

#### Streamlit Dashboard (streamlit/)

Six pages are wired into the main navigation:

| Page | PM Value | Status |
|------|----------|--------|
| Home | 5W+H context, live stats | Deployed |
| Leaderboard | Ranked configs with dimension breakdown, complexity vs performance | Deployed |
| Main Effects | Factor-level impact with error bars, score lift by feature, interaction heatmap | Deployed |
| Category Performance | Baseline vs C+A dumbbell chart, priority matrix, category impact table | Deployed |
| Factorial Heatmap | 32-category x 16-run full heatmap, agentic vs non-agentic grouping | Deployed |
| Questions Explorer | Per-question drilldown with filters by config, category, question type | Deployed |

Five experimental pages built but **not wired into main nav**:

| Page | PM Value | Status |
|------|----------|--------|
| Decision Matrix | Config recommendation with MH threshold slider | Built, not in nav |
| Failure Atlas | Fundamental vs fixable failure classification | Built, not in nav |
| Feature ROI | Score lift per feature with interaction effects | Built, not in nav |
| Investment Prioritizer | Priority bubble chart, category impact ranking | Built, not in nav |
| What-If Explorer | Adjustable dimension weights, rank shift analysis | Built, not in nav |
| Model Comparison | Cross-model baseline scores by type, category, dimension | Built, not in nav |

#### AEO Benchmark Skill (aeo-benchmark)

The existing CoCo skill (`~/.cortex/skills/aeo-benchmark/SKILL.md`) can deploy the schema, run benchmarks (Task DAG or SPCS), monitor progress, backfill gaps, and query results. It operates the scoring pipeline but does not yet support the two PM eval loops described above.

### What's Missing

#### Priority 1: PM Prompt/Question Eval Loop

This is the highest-priority gap. The goal: a PM types a prompt or question, hits "Score", and sees the result.

**Implementation approach:**

1. **Streamlit "Prompt Lab" page.** A new page with:
   - Text input for a custom system prompt (optional)
   - Text input for a custom question (or select from the existing 128-question bank)
   - Category selector (to compare against baseline for that category)
   - "Run Eval" button that triggers a single-question scoring run
   - Results panel showing: per-dimension scores, must-have pass/fail, score delta vs baseline, and the full AI response vs canonical answer side-by-side

2. **Scoring backend.** The Streamlit page calls `SNOWFLAKE.CORTEX.COMPLETE` with the PM's prompt/question, then scores the response with the 3-judge panel. For non-agentic mode this is a single SQL call per judge. For agentic mode, this requires a Cortex Code session (which may need to be manual or use the future API).

3. **Batch mode.** After the single-question flow works, extend to "run my prompt against all N questions in category X" for a full category evaluation. This reuses the existing Task DAG or orchestrator pipeline with the PM's prompt injected as the system prompt.

**Key design decisions:**
- Start with non-agentic scoring only (single `CORTEX.COMPLETE` call). This is fast, cheap, and sufficient to measure prompt impact.
- Store PM-submitted prompts and their scores in a new table (`AEO_PM_EXPERIMENTS`) so results persist and are comparable over time.
- Show the delta: "your prompt scored X% vs the baseline of Y% for this category."

#### Priority 2: Bundled Skill Eval Loop (Collab with Gilberto)

Measure whether CoCo bundled skills improve answer quality for their target categories.

**Implementation approach:**

1. **Skill-to-category mapping.** Create a mapping table (`AEO_SKILL_CATEGORY_MAP`) linking each bundled skill to its relevant AEO question categories. Example: `cortex-agent` skill maps to "Cortex Agents" category, `dynamic-tables` skill maps to "Dynamic Tables" category, etc.

2. **Skill-assisted runs.** For each skill, run its mapped category questions through Cortex Code with the skill loaded, and separately without the skill. Score both with the 3-judge panel.

3. **Skill quality leaderboard.** A new view (`V_AEO_SKILL_LIFT`) and Streamlit page showing: skill name, category, score with skill, score without skill, delta, and per-dimension breakdown. This becomes the shared artifact between AEO and CoCo skills teams.

4. **Regression detection.** When a skill is updated, re-run its category questions and compare to the previous score. Flag regressions.

**Collaboration model with Gilberto:**
- Chanin provides: eval harness, question bank, scoring pipeline, results infrastructure, Streamlit visualization
- Gilberto provides: skill catalog, skill-loading mechanism for CoCo sessions, skill update notifications
- Joint: define the skill-to-category mapping, run initial skill eval sweep, interpret results, prioritize skill improvements
- Cadence: after each major skill update cycle, re-run the skill eval and review the delta together

#### Priority 3: Wire Up Existing Experimental Pages

Promote the 5 experimental pages and Model Comparison into the main nav. Group navigation into "Analysis" (existing 6 pages) and "PM Tools" (experimental + Model Comparison) sections.

#### Priority 4: Supporting Features

- **Response Viewer page.** AI response vs canonical answer side-by-side, per-judge scores, must-have pass/fail. Critical for PMs to understand *why* a question scored poorly.
- **Export capability.** CSV or Snowflake table export of filtered results.
- **PM Category Dashboard.** Category selector, weakest question type diagnosis, documentation gap mapping, links to failing questions.

### Key Categories Needing Documentation Investment

Based on current benchmark results under the best configuration (C+A), these categories have the largest gaps:

| Priority | Category | Overall | Weakest Type | Gap | Documentation Need |
|----------|----------|--------:|--------------|----:|-----|
| 1 | Snowflake Postgres | 61.8% | Debug (39.3%) | 22.5pp | Troubleshooting: health checks, tuning, connection management |
| 2 | Cortex Agents | 78.5% | Debug (52.7%) | 25.8pp | Troubleshooting: agent failure modes, multi-step task debugging |
| 3 | Data Quality & Observability | 69.2% | Compare (50.7%) | 18.5pp | Decision guidance: when to use DMFs vs other approaches |
| 4 | Snowsight | 76.8% | Debug (53.3%) | 23.5pp | Troubleshooting: UI config errors, deployment issues |
| 5 | Data Loading | 77.2% | Debug (54.7%) | 22.5pp | Troubleshooting: COPY INTO errors, Snowpipe failures |
| 6 | Dynamic Tables | 75.0% | Compare (64.0%) | 11.0pp | Decision guidance: DT vs streams/tasks architecture choices |
| 7 | Cortex AI Functions | 83.0% | Debug (64.0%) | 19.0pp | Troubleshooting: unexpected results, function-specific error guides |

### Design Principles

1. **Prompt in, score out.** The core interaction is: PM provides input, system returns a score. Everything else is supporting context.
2. **Show the delta.** Raw scores are meaningless without a baseline. Always show "your prompt scored X% vs baseline Y%, a delta of Z pp."
3. **Filter to their scope.** A PM for Cortex Agents should not scroll past 31 other categories. Category selection is the first interaction.
4. **Show the evidence.** After the score, show the actual AI response vs canonical answer so PMs can validate the diagnosis.
5. **Make it shareable.** Export and permalink support so PMs can share findings with engineering and PMM partners.
6. **Measure skills, not just prompts.** The bundled skill eval loop is equally important. Skills are the primary mechanism through which the CoCo team improves answer quality at scale.

## To-Do

### Priority 1: PM Prompt/Question Eval Loop

- [ ] Design `AEO_PM_EXPERIMENTS` table schema (prompt text, question ID or custom question, category, scores, timestamp, user)
- [ ] Build scoring backend: accept a prompt + question, call `CORTEX.COMPLETE`, score with 3-judge panel, return results
- [ ] Build Streamlit "Prompt Lab" page: prompt input, question input/selector, category selector, "Run Eval" button, results panel with delta vs baseline
- [ ] Add batch mode: "run my prompt against all questions in category X"
- [ ] Store and display history of PM experiments for comparison over time

### Priority 2: Bundled Skill Eval Loop (Collab with Gilberto)

- [ ] Create `AEO_SKILL_CATEGORY_MAP` table mapping bundled skills to AEO question categories
- [ ] Build skill-assisted run workflow: run category questions with skill loaded vs without skill
- [ ] Create `V_AEO_SKILL_LIFT` view: skill name, category, score with/without skill, delta, per-dimension breakdown
- [ ] Build Streamlit "Skill Quality" page showing skill leaderboard
- [ ] Set up regression detection: flag score drops when skills are updated
- [ ] Coordinate with Gilberto on skill-loading mechanism and initial eval sweep

### Priority 3: Wire Up Existing Pages

- [ ] Add experimental pages (Decision Matrix, Failure Atlas, Feature ROI, Investment Prioritizer, What-If Explorer) and Model Comparison to `app.py` navigation
- [ ] Group navigation into "Analysis" and "PM Tools" sections

### Priority 4: Supporting Features

- [ ] Build Response Viewer page: AI response vs canonical answer side-by-side, per-judge scores, must-have pass/fail
- [ ] Build PM Category Dashboard page: category selector, weakest question type diagnosis, documentation gap mapping
- [ ] Add CSV/table export to filtered results across all pages

### Infrastructure

- [ ] Scoring comparison: custom pipeline vs TruLens native feedback functions
- [ ] Automate benchmark on a scheduled cadence for regression detection
- [ ] Replicate full 2^4 factorial across additional respondent models (GPT-5.4, Maverick)
- [ ] Expand question bank to 8-12 questions per category for more reliable per-category estimates

## Design System

### Color Palette

Snowflake brand colors used across all charts and visualizations in the Streamlit app:

| Role | Hex | Usage |
|------|-----|-------|
| Primary / Model 1 | `#29B5E8` | First model bar, primary UI accent (`primaryColor` in config.toml) |
| Secondary / Model 2 | `#FF9F36` | Second model bar |
| Tertiary / Model 3 | `#D45B90` | Third model bar |
| Quaternary / Model 4 | `#7D44CF` | Fourth model bar (if applicable) |
| Baseline | `#888888` | Baseline (run 1) comparison bar, neutral grey |

Colors cycle in order when more than 4 models are present. Baseline bars use `opacity=0.7` to visually subordinate them to the model bars.

---

## Session Log: 2026-04-20 — SPCS Interactive Mode + SiS Deployment

### What Was Built

#### SPCS Interactive Mode (SiS → SPCS → Table → SiS poll)

Streamlit in Snowflake (SiS) cannot run the `cortex` binary directly. To preserve native Cortex Code generation in the deployed app, a job-trigger pattern was implemented:

1. **`AEO_INTERACTIVE_RESULTS` table** — queue table; SiS inserts a `pending` row with the prompt, the SPCS container reads the prompt, runs `cortex --print`, and writes the result back as `complete` or `error`.

2. **`AEO_TRIGGER_INTERACTIVE` stored procedure** (`spcs-v2/setup-interactive.sql`) — Python-language SP that:
   - Generates a UUID for the request
   - Inserts the prompt into `AEO_INTERACTIVE_RESULTS` with `status='pending'` via parameterised query
   - Builds a job-service YAML spec inline and fires `EXECUTE JOB SERVICE` using `dq = '$' + '$'` to avoid the literal `$$` that would prematurely terminate the SP body
   - Returns the `request_id` to the caller

3. **`spcs-v2/aeo_spcs_interactive.py`** — single-question SPCS container entrypoint:
   - Reads `REQUEST_ID` from env (injected per-job in the spec)
   - Fetches the prompt from the table
   - Runs `cortex -c spcs --print <prompt>` via subprocess
   - Writes the response (or error message) back to the table so SiS never polls indefinitely

4. **`streamlit/utils/spcs.py`** — SiS-side helper:
   - Calls `AEO_TRIGGER_INTERACTIVE` SP to launch the job
   - Polls `AEO_INTERACTIVE_RESULTS` every 3 seconds with a 300-second timeout (covers SPCS cold-start)
   - Returns the response text or a timeout error string

5. **`spcs-v2/Dockerfile`** updated with `RUN_MODE`-based CMD dispatch:
   - `RUN_MODE=interactive` → `aeo_spcs_interactive.py`
   - default → `aeo_spcs_runner_v2.py` (batch mode unchanged)

#### `is_sis()` Environment Detection

Added `is_sis()` to `streamlit/utils/db.py` as the canonical SiS probe:

```python
def is_sis() -> bool:
    try:
        from snowflake.snowpark.context import get_active_session
        get_active_session()
        return True
    except Exception:
        return False
```

`get_active_session()` succeeds only inside SiS; it raises locally. This replaces the binary `shutil.which("cortex")` check and is evaluated once at module load time (`IS_SIS = is_sis()`).

Both `pages/test_prompt.py` and `pages/test_skill.py` were updated:
- `if not IS_SIS` → existing subprocess path (local `cortex` binary)
- `else` → `run_via_spcs(session, prompt, run_schema=RUN_SCHEMA, warehouse=WH)`

#### Streamlit in Snowflake Deployment

Created `streamlit/snowflake.yml` (`definition_version: 2`) and `streamlit/pyproject.toml`, then deployed to Snowhouse:

```
App: DEVREL.CNANTASENAMAT_DEV.AEO_BENCHMARK_DASHBOARD
Runtime: SYSTEM$ST_CONTAINER_RUNTIME_PY3_11
Compute pool: STREAMLIT_DEDICATED_POOL
Warehouse: SNOWADHOC
```

Deployed with:
```bash
SNOW=/Library/Frameworks/Python.framework/Versions/3.11/bin/snow
cd /Users/cnantasenamat/Documents/Coco/aeo/repo/streamlit
$SNOW streamlit deploy --replace --connection snowhouse-deploy
```

To redeploy: re-add `[snowhouse-deploy]` to `connections.toml` (same PAT as `my-snowflake`, role `DEVREL_ADMIN_RL`), run the command above, then remove the entry.

---

### What Went Well

- **`$$` escape trick** (`dq = '$' + '$'`) cleanly solved the SP body quoting conflict without rewriting the SP as a JavaScript or SQL-language procedure.
- **Prompt-in-table pattern** — storing the prompt in the queue table rather than the job-service YAML env block sidesteps YAML escaping issues and env var length limits entirely.
- **`is_sis()` probe** — using `get_active_session()` as the detector is zero-config: no env var to set, no build-time flag, works identically across local dev and SiS.
- **`RUN_MODE` dispatch** in the Dockerfile keeps a single image for both batch and interactive modes; no extra registry push needed.
- **Temporary connection alias** pattern (`[snowhouse-deploy]` with `DEVREL_ADMIN_RL`) is a clean workaround for PAT-based auth that ignores `--role` flags.

---

### Fixes Made

| # | Problem | Fix |
|---|---------|-----|
| 1 | `SYSTEM$ST_CONTAINER_RUNTIME_PY3_11` requires `compute_pool` in `snowflake.yml` | Added `compute_pool: STREAMLIT_DEDICATED_POOL` to the entity definition |
| 2 | `my-snowflake` PAT is locked to `MARKETING_SENSITIVE_RO`; `--role DEVREL_ADMIN_RL` was silently ignored by Snow CLI | Added temporary `[snowhouse-deploy]` connection entry in `connections.toml` using the same PAT but with `role = "DEVREL_ADMIN_RL"`; removed after deploy |
| 3 | `DEVREL_ADMIN_RL` lacks `USAGE` on `PYPI_ACCESS_INTEGRATION` | Removed `external_access_integrations` block from `snowflake.yml`; container runtime pre-installs plotly, pandas, and snowflake packages so PyPI access is not required |
| 4 | Literal `$$` inside a `$$`-quoted SP body terminates the body early | Used `dq = '$' + '$'` so the string is assembled at Python runtime, never appearing as a literal `$$` in the SQL source |
| 5 | `snow streamlit deploy --role` flag silently ignored for PAT auth | Confirmed via `SELECT CURRENT_ROLE()` — role stayed `MARKETING_SENSITIVE_RO`; workaround is the dedicated connection entry (fix #2) |

---

## Session Log: 2026-04-23 — Transcript Capture, Token Attribution, AEO_TRANSCRIPT Table

### What Was Built

#### `AEO_TRANSCRIPT` table (new)

Observability data previously crammed into `AEO_RESPONSES` was extracted into a dedicated `AEO_TRANSCRIPT` table (25 columns). `AEO_RESPONSES` now has only 4 columns: `RUN_ID`, `QUESTION_ID`, `RESPONSE_TEXT`, `GENERATED_AT`. The transcript table holds all per-question runtime metrics: turn counts, tool call breakdowns, token counts, cache metrics, request IDs, and generation time.

Exists on both schemas:
- Snowhouse: `DEVREL.CNANTASENAMAT_DEV.AEO_TRANSCRIPT`
- DevRel: `AEO_OBSERVABILITY.EVAL_SCHEMA.AEO_TRANSCRIPT`

#### Token attribution via `CORTEX_CODE_CLI_USAGE_HISTORY`

`cortex_cli` runs previously left `INPUT_TOKENS`/`OUTPUT_TOKENS` as NULL because the Cortex CLI does not print token counts. Token data is now fetched post-generation from:

```
SNOWFLAKE.ACCOUNT_USAGE.CORTEX_CODE_CLI_USAGE_HISTORY
```

Key facts about this view:
- Near-real-time (seconds to minutes latency); a `FETCH_TOKENS_DELAY_SECS = 5` sleep is used before querying.
- No `SESSION_ID` column — token rows cannot be joined to a specific session directly.
- Attribution uses a **time-window query**: `WHERE USER_NAME = CURRENT_USER() AND USAGE_TIME BETWEEN t_before AND t_after`. This works because questions are processed sequentially within each batch.
- `TOKENS_GRANULAR` format: `{"claude-opus-4-6": {"input": N, "output": N, "cache_read_input": N, "cache_write_input": N}}`
- `input` in `TOKENS_GRANULAR` is raw input tokens only (excludes cache); `INPUT_TOKENS` stored in `AEO_TRANSCRIPT` = `input + cache_read_input + cache_write_input`.
- `FIRST_REQUEST_ID` = `MIN_BY(REQUEST_ID, USAGE_TIME)` over the time window; `LAST_REQUEST_ID` = `MAX_BY(REQUEST_ID, USAGE_TIME)`.

#### `transcript_capture.py` additions

New function `fetch_cli_tokens(cur, t_before, t_after, model) -> dict` added to `scripts/spcs/transcript_capture.py`. It:
1. Sleeps `FETCH_TOKENS_DELAY_SECS` to allow the view to catch up.
2. Validates the model name against `_MODEL_NAME_RE` before interpolating into SQL (injection guard).
3. Returns a dict with keys: `prompt_tokens`, `completion_tokens`, `cache_read_tokens`, `cache_write_tokens`, `first_request_id`, `last_request_id`.

#### Per-tool `TOOL_CALL_*` columns

`TOOL_CALLS VARIANT` (a JSON array) was replaced with 11 individual integer columns. Tracked tools:

```
bash, read, write, edit, glob, grep, sql_execute, skill, web_fetch, web_search
```

`TOOL_CALL_OTHER` catches all tool calls not in the tracked list so that `N_TOOL_CALLS = sum(all TOOL_CALL_* columns)` always holds.

#### `V_AEO_TRANSCRIPT_STATS` view

Recreated on Snowhouse with a `LEFT JOIN` to `AEO_TRANSCRIPT` so runs without transcript data still appear. Includes:
- `TOTAL_TOOL_CALL_*` for all 11 tool columns
- `CACHE_HIT_PCT` = `cache_read / total_input * 100` (cost efficiency metric)
- `CACHE_HIT_RATE` = `cache_read / (cache_read + cache_write) * 100` (traditional hit rate)
- `AVG_GENERATION_SECS`

#### Dockerfile updated (v3)

`scripts/spcs/Dockerfile` now:
- Installs the Cortex CLI via `curl` (required for `cortex_cli` generation mode).
- Adds a hard-fail guard: `RUN ls /root/.local/bin/cortex || exit 1`.
- Copies `transcript_capture.py` alongside `aeo_spcs_runner.py`.
- `CMD` dispatches on `RUN_MODE`: `interactive` runs `aeo_spcs_interactive.py`; default runs `aeo_spcs_runner.py`.

#### JSONL availability inside Docker/SPCS confirmed

Tested by running `cortex -p` inside a `python:3.11-slim` container. The CLI (v1.0.66) wrote the conversation JSONL to `/root/.snowflake/cortex/conversations/` — the same path `transcript_capture.py` reads from. No extra volume mounts or config needed.

---

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Time-window token attribution instead of session join | `CORTEX_CODE_CLI_USAGE_HISTORY` has no `SESSION_ID`; sequential processing makes time-window attribution unambiguous |
| `TOOL_CALL_OTHER` catch-all column | Ensures `N_TOOL_CALLS` is always the sum of all per-tool columns; new tools accumulate here without a schema change |
| Separate `AEO_TRANSCRIPT` table | Keeps `AEO_RESPONSES` minimal (response text only) and allows transcript data to be NULL-absent for non-`cortex_cli` runs without nulling out response rows |
| `CACHE_HIT_PCT` vs `CACHE_HIT_RATE` | Both kept: `CACHE_HIT_PCT` = cost efficiency (fraction of total input served from cache); `CACHE_HIT_RATE` = traditional cache effectiveness (hits as fraction of all cache activity) |

---

### Fixes Made

| # | Problem | Fix |
|---|---------|-----|
| 1 | `INPUT_TOKENS` / `OUTPUT_TOKENS` were NULL for `cortex_cli` runs | Added `fetch_cli_tokens()` querying `CORTEX_CODE_CLI_USAGE_HISTORY` post-generation |
| 2 | `ALTER TABLE ADD COLUMN col1, col2` rejected by Snowflake | Snowflake requires one `ADD COLUMN` clause per `ALTER TABLE` statement; ran separate statements |
| 3 | Model name interpolated into SQL without validation | Added `_MODEL_NAME_RE = re.compile(r'^[\w][\w\-\.]*$')` guard before interpolation |
| 4 | `PARSE_JSON(%s)` in a `VALUES` parameterized query fails | Replaced with a `SELECT` form; then removed entirely when `TOOL_CALLS VARIANT` column was dropped |

---

## Session Log: 2026-04-23 — SPCS Image v5, Build/Push Procedure

### What Was Done

#### Docker image v5 built and pushed

The Dockerfile was updated to v3 logic (Cortex CLI install, `transcript_capture.py` copy, `RUN_MODE` dispatch). The resulting image was built and pushed to the Snowhouse registry as `:v5`:

```bash
REGISTRY="sfcogsops-snowhouse-aws-us-west-2.registry.snowflakecomputing.com/devrel/cnantasenamat_dev/aeo_repo"

docker build --platform linux/amd64 \
  -t ${REGISTRY}/aeo-benchmark:v5 \
  /Users/cnantasenamat/Documents/Coco/aeo/dev/spcs/

snow spcs image-registry login --connection my-snowflake

docker push ${REGISTRY}/aeo-benchmark:v5
```

Image digest: `sha256:d45eb57d9854725c9e5b324bf73cc8e7004c960618fde86241e84ca89f26151c`

#### Image versioning clarification

The Docker image tag (`:v4`, `:v5`) and the runner script internal version ("v2", "v3" as in `aeo_spcs_runner.py` filename) are independent counters:

| Counter | Current value | What it tracks |
|---------|--------------|----------------|
| Runner script version | v3 (`aeo_spcs_runner.py`) | Python logic changes: generation modes, transcript capture, token attribution |
| Docker image tag | `:v5` | Every `docker build + push` to the Snowflake registry |

The image tag increments once per push regardless of how many script changes are bundled in that push. Do not conflate the two.

#### Files added to `scripts/spcs/` in the repo

Previously these files existed only in the local `dev/spcs/` working directory. They are now tracked in the repo:

| File | Purpose |
|------|---------|
| `setup-snowhouse.sql` | Snowhouse SPCS infrastructure DDL + 8-batch job launch SQL |
| `aeo-job-snowhouse.yaml` | Single-batch SPCS job spec (used for ad-hoc runs) |
| `transcript_capture.py` | JSONL transcript reader + `CORTEX_CODE_CLI_USAGE_HISTORY` token fetcher |
| `aeo_spcs_runner.py` | v3 batch runner (updated from v2 already in repo) |

#### `snow spcs image-registry login` is the correct login method

`docker login <registry>` with stored credentials fails when the session token expires. The correct approach is:

```bash
snow spcs image-registry login --connection my-snowflake
```

This refreshes the token via the Snow CLI and updates Docker's credential store. Run it immediately before every `docker push`.

---

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Always `--platform linux/amd64` for builds | SPCS compute pools run on x86; building on Apple Silicon without the flag produces an arm64 image that silently fails to start |
| Login via `snow spcs image-registry login` not `docker login` | `docker login` with cached tokens expires; Snow CLI refreshes the session token automatically |
| Keep image tag and script version as independent counters | Script can be updated and pushed multiple times between image rebuilds; conflating them creates confusion about what is deployed |

---

## Session Log: 2026-04-23 — REQUIRE_SPCS Guard, Token Coverage Investigation

### What Was Done

#### `REQUIRE_SPCS=true` guard added to runner and all job specs

`aeo_spcs_runner.py` now checks for the SPCS OAuth token file at startup when `REQUIRE_SPCS=true`:

```python
if os.environ.get("REQUIRE_SPCS", "false").lower() == "true":
    if not os.path.exists("/snowflake/session/token"):
        raise RuntimeError(
            "REQUIRE_SPCS=true but /snowflake/session/token not found. "
            "This runner must be launched via EXECUTE JOB SERVICE inside SPCS, "
            "not run directly on a local machine."
        )
```

`/snowflake/session/token` is injected by SPCS at container startup and never exists on a local machine. The guard is opt-in so local dev still works by omitting the env var.

`REQUIRE_SPCS: "true"` was added to all 8 batch env blocks in `setup-snowhouse.sql` and to `aeo-job-snowhouse.yaml`.

#### `cortex_complete` token coverage confirmed — no additional work needed

`SNOWFLAKE.CORTEX.COMPLETE` returns token usage inline in the response JSON:

```json
{"usage": {"prompt_tokens": N, "completion_tokens": N, "total_tokens": N}}
```

The existing `insert_transcript()` call already maps these to `INPUT_TOKENS` and `OUTPUT_TOKENS`. No additional query is needed.

`CORTEX_FUNCTIONS_USAGE_HISTORY` was investigated as a potential source of additional metadata for `cortex_complete` calls. It was ruled out: it only provides a total `TOKENS` count with no user filter, no input/output breakdown, and no request ID. It adds nothing over the inline response.

#### Token coverage comparison by generation mode

| Column | `cortex_cli` | `cortex_complete` |
|--------|-------------|-------------------|
| `INPUT_TOKENS` | `CORTEX_CODE_CLI_USAGE_HISTORY` | Inline `usage.prompt_tokens` |
| `OUTPUT_TOKENS` | `CORTEX_CODE_CLI_USAGE_HISTORY` | Inline `usage.completion_tokens` |
| `CACHE_READ_TOKENS` | `CORTEX_CODE_CLI_USAGE_HISTORY` | NULL (not in CORTEX.COMPLETE response) |
| `CACHE_WRITE_TOKENS` | `CORTEX_CODE_CLI_USAGE_HISTORY` | NULL |
| `FIRST_REQUEST_ID` | `CORTEX_CODE_CLI_USAGE_HISTORY` | NULL (no equivalent for SQL calls) |
| `LAST_REQUEST_ID` | `CORTEX_CODE_CLI_USAGE_HISTORY` | NULL |
| `GENERATION_SECS` | Wall-clock timing | Wall-clock timing |

---

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| `REQUIRE_SPCS` is opt-in via env var | Keeps local dev and smoke tests unblocked while enforcing containerization in production job specs |
| Fail-fast at `main()` entry not mid-run | Catches misconfigured local runs immediately rather than after generating and scoring questions |
| Do not query `CORTEX_FUNCTIONS_USAGE_HISTORY` for `cortex_complete` token attribution | View lacks user filter and input/output split; inline response already provides what is needed |
