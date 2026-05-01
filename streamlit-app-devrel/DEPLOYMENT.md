# AEO Benchmark Dashboard — Deployment Reference

The app is deployed to two Snowflake accounts. All environment-specific constants
are auto-detected at runtime in `utils/db.py` via `get_active_session().get_current_account()`.

---

## Environments

### Snowhouse

| Property | Value |
|---|---|
| Account | `SFCOGSOPS-SNOWHOUSE_AWS_US_WEST_2` |
| Connection name | `my-snowflake` |
| Deploy role | `DEVREL_ADMIN_RL` |
| `WH` | `SNOWADHOC` |
| `SPCS_ROLE` | `DEVREL_INGEST_RL` |
| SiS app | `DEVREL.CNANTASENAMAT_DEV.AEO_BENCHMARK_DASHBOARD` |
| Skill stage | `DEVREL.CNANTASENAMAT_DEV.AEO_SKILL_STAGE` |
| SPCS compute pool | `AEO_BENCHMARK_POOL` (CPU_X64_XS, auto_resume) |
| Deploy config | `snowflake.yml` |

### DevRel

| Property | Value |
|---|---|
| Account | `SFDEVREL-SFDEVREL_ENTERPRISE` |
| Connection name | `devrel` |
| Deploy role | `ACCOUNTADMIN` |
| `WH` | `CHANIN_XS` |
| `SPCS_ROLE` | `ACCOUNTADMIN` |
| SiS app | `CHANINN_DEMO_DATA.APPS.AEO_BENCHMARK_DASHBOARD` |
| Skill stage | `CHANINN_DEMO_DATA.APPS.AEO_SKILL_STAGE` |
| SPCS compute pool | `AEO_BENCHMARK_POOL` (CPU_X64_XS, auto_resume) |
| SiS runtime | `SYSTEM$ST_CONTAINER_RUNTIME_PY3_11` on `HOL_COMPUTE_POOL` |
| External access | `PYPI_ACCESS_INTEGRATION` (required for plotly install) |
| Deploy config | `snowflake-devrel.yml` (swapped to `snowflake.yml` during deploy) |

---

## Snowflake objects

**Important:** The two accounts have different storage layouts.

- **Snowhouse**: writable tables and read-only proxy views all live in `DEVREL.CNANTASENAMAT_DEV`.
- **DevRel**: writable tables live in `CHANINN_DEMO_DATA.APPS`; read-only benchmark data lives directly in `AEO_OBSERVABILITY.EVAL_SCHEMA` (no proxy views in `CHANINN_DEMO_DATA.APPS`).

`utils/db.py` handles this via two sets of constants: `DB`/`SCH` for writable objects and `READ_DB`/`READ_SCH` for read-only objects (see Environment auto-detection section).

### Tables (writable) — `CHANINN_DEMO_DATA.APPS` on DevRel

| Table | Purpose |
|---|---|
| `AEO_INTERACTIVE_RESULTS` | SPCS job request/response tracking. Columns: `REQUEST_ID`, `STATUS`, `PROMPT`, `RESPONSE_TEXT`, `CREATED_AT`, `UPDATED_AT`, `COMPLETED_AT`. Note: `COMPLETED_AT` is required by the container script — must exist or SPCS jobs will fail. |
| `AEO_PM_PROMPTS` | Results from Test Your Prompt experiments |
| `AEO_SKILL_TESTS` | Results from Test Your Skill experiments |
| `AEO_QUESTION_CANDIDATES` | Question submissions pending admin review (STATUS: `pending` / `approved` / `rejected`) |
| `AEO_BENCHMARK_<NAME>` | Dynamically created by admin via the "Add to Benchmark Set" feature in Questions Explorer. Name is sanitized to uppercase alphanumeric/underscores. Created with `CREATE TABLE IF NOT EXISTS` so re-submitting the same name appends rows. |

### Read-only benchmark data — `AEO_OBSERVABILITY.EVAL_SCHEMA` on DevRel

Tables: `AEO_QUESTIONS`, `AEO_RUNS`, `AEO_RUN_CONFIG`, `AEO_SCORES`, `AEO_TRANSCRIPT`

Views: `V_AEO_LEADERBOARD`, `V_AEO_FACTORIAL_EFFECTS`, `V_AEO_PER_QUESTION_HEATMAP`,
`V_AEO_JUDGE_AGREEMENT`, `V_AEO_TRANSCRIPT_STATS`

Note: `AEO_RESPONSES` is now 4 columns only (`RUN_ID`, `QUESTION_ID`, `RESPONSE_TEXT`, `GENERATED_AT`). All observability data (tokens, tool calls, turns, timing) lives in `AEO_TRANSCRIPT`. `V_AEO_MODEL_COMPARISON` does not exist on DevRel as of April 2026. Pages that query it will error on DevRel until it is created.

### Stored procedures — `CHANINN_DEMO_DATA.APPS` on DevRel

| Procedure | Purpose | DevRel-specific notes |
|---|---|---|
| `AEO_SCORE_RESPONSE(question_id, response_text, system_prompt, judges)` | LLM judge panel scoring (5 dimensions + must-haves) | Queries `AEO_OBSERVABILITY.EVAL_SCHEMA.AEO_QUESTIONS` (not the hardcoded Snowhouse path) |
| `AEO_TRIGGER_INTERACTIVE(prompt, warehouse, role, run_schema)` | Launches SPCS job service, returns `REQUEST_ID` | Defaults: `warehouse='CHANIN_XS'`, `role='ACCOUNTADMIN'`, `run_schema='CHANINN_DEMO_DATA.APPS'` |

---

## Deploy commands

### Snowhouse

`STREAMLIT_DEDICATED_POOL` pre-installs all required packages, so no EAI is needed. However, the container runtime requires `pyproject.toml` to be present. Swap in a minimal empty-deps version before deploying, then restore the full one for DevRel use.

```bash
SNOW=/Library/Frameworks/Python.framework/Versions/3.11/bin/snow
cp pyproject.toml pyproject-devrel.toml \
  && cp pyproject-snowhouse.toml pyproject.toml \
  && $SNOW streamlit deploy --replace --prune --connection my-snowflake-deploy \
  && cp pyproject-devrel.toml pyproject.toml \
  && rm pyproject-devrel.toml
```

`my-snowflake-deploy` is a separate entry in `~/.snowflake/connections.toml` that mirrors `my-snowflake` but uses `role = "DEVREL_ADMIN_RL"`. The default `my-snowflake` connection uses `MARKETING_SENSITIVE_RO` which lacks `CREATE STREAMLIT` privilege. The `--rolename` flag on Snow CLI does not override the session role reliably.

### DevRel

Snow CLI always reads `snowflake.yml`, so swap files around the deploy. Run from the `streamlit-app-devrel/` directory (this repo), which contains the DevRel-specific `utils/db.py` with `READ_DB`/`READ_SCH` routing:

```bash
SNOW=/Library/Frameworks/Python.framework/Versions/3.11/bin/snow
cp snowflake.yml snowflake-snowhouse.yml \
  && cp snowflake-devrel.yml snowflake.yml \
  && $SNOW streamlit deploy --replace --connection devrel \
  && cp snowflake-snowhouse.yml snowflake.yml \
  && rm snowflake-snowhouse.yml
```

---

## Environment auto-detection (utils/db.py)

```python
def _detect_env() -> str:
    try:
        from snowflake.snowpark.context import get_active_session
        acct = get_active_session().get_current_account().upper()
        if "SFDEVREL" in acct:
            return "devrel"
    except Exception:
        pass
    return "snowhouse"  # local dev always connects to Snowhouse
```

All constants are set from `ENV` at module load time:

| Constant | Snowhouse | DevRel | Purpose |
|---|---|---|---|
| `DB` | `DEVREL` | `CHANINN_DEMO_DATA` | Writable table database |
| `SCH` | `CNANTASENAMAT_DEV` | `APPS` | Writable table schema |
| `READ_DB` | `DEVREL` | `AEO_OBSERVABILITY` | Read-only benchmark data database |
| `READ_SCH` | `CNANTASENAMAT_DEV` | `EVAL_SCHEMA` | Read-only benchmark data schema |
| `WH` | `SNOWADHOC` | `CHANIN_XS` | Query warehouse |
| `ROLE` | `DEVREL_ADMIN_RL` | `ACCOUNTADMIN` | Session role |
| `SPCS_ROLE` | `DEVREL_INGEST_RL` | `ACCOUNTADMIN` | SPCS job role |

`_qualify_tables()` in `db.py` uses two separate regex passes: read-only objects (`V_AEO_*`, `AEO_QUESTIONS`, `AEO_RESPONSES`, `AEO_RUNS`, `AEO_RUN_CONFIG`, `AEO_SCORES`) are prefixed with `READ_DB.READ_SCH`; writable objects (`AEO_PM_PROMPTS`, `AEO_SKILL_TESTS`, `AEO_INTERACTIVE_RESULTS`, `AEO_QUESTION_CANDIDATES`) are prefixed with `DB.SCH`. On Snowhouse, `READ_DB`/`READ_SCH` equal `DB`/`SCH` so behaviour is unchanged.

**Local dev** always falls back to `snowhouse` (no active SiS session). The `my-snowflake` connection in `~/.snowflake/connections.toml` authenticates as `CNANTASENAMAT`. Use the `devrel` connection entry to test against the DevRel account locally.

**Username capture**: use `CURRENT_USER()` inline in SQL `INSERT` statements rather than Python-side detection. This resolves correctly in SiS (logged-in Snowflake user) and local dev (connection user from `connections.toml`) without any extra logic.

---

## SPCS container image

| Account | Image path |
|---|---|
| Snowhouse | `/DEVREL/CNANTASENAMAT_DEV/AEO_REPO/aeo-benchmark:v5` |
| DevRel | `sfdevrel-sfdevrel-enterprise.registry.snowflakecomputing.com/aeo_db/public/aeo_repo/aeo-benchmark:v5` |

The `AEO_TRIGGER_INTERACTIVE` SP on DevRel uses the short path (`/AEO_DB/...`),
which Snowflake resolves to the full registry URL automatically.

Dockerfile v3 (Cortex CLI install, `transcript_capture.py`, `RUN_MODE` dispatch) — image pushed as `:v5` to Snowhouse registry (2026-04-23).

**Image versioning note:** The Docker image tag (`:v4`, `:v5`) and the runner script version ("v3" as in `aeo_spcs_runner.py`) are independent counters. The image tag increments every time a new image is built and pushed to the registry. The script version reflects internal logic changes to the Python runner. Do not conflate them.

### Build and push procedure (Snowhouse)

Get the registry URL:
```sql
USE WAREHOUSE SNOWADHOC;
SHOW IMAGE REPOSITORIES IN SCHEMA DEVREL.CNANTASENAMAT_DEV;
-- copy repository_url from output
```

Build, login, and push:
```bash
REGISTRY="sfcogsops-snowhouse-aws-us-west-2.registry.snowflakecomputing.com/devrel/cnantasenamat_dev/aeo_repo"
SNOW=/Library/Frameworks/Python.framework/Versions/3.11/bin/snow

# Build (always linux/amd64 — SPCS runs on x86)
docker build --platform linux/amd64 \
  -t ${REGISTRY}/aeo-benchmark:v<N> \
  /path/to/aeo/dev/spcs/

# Login via Snow CLI (handles token refresh automatically)
$SNOW spcs image-registry login --connection my-snowflake

# Push
docker push ${REGISTRY}/aeo-benchmark:v<N>
```

After pushing, update all `image:` references in `scripts/spcs/setup-snowhouse.sql` and `scripts/spcs/aeo-job-snowhouse.yaml` to the new tag.

---

## Known pitfalls

| Pitfall | Root cause | Fix applied |
|---|---|---|
| `aeo_feedback_functions` import error in SiS | Local observability module; not installable in SiS environment | Removed top-level import; `JUDGE_PANEL` now defined inline in `utils/scoring.py` |
| `st.navigation()` AttributeError on DevRel | DevRel warehouse runtime has Streamlit older than 1.36 | Switched to `SYSTEM$ST_CONTAINER_RUNTIME_PY3_11` + `HOL_COMPUTE_POOL` in `snowflake-devrel.yml` |
| `ModuleNotFoundError: plotly` on DevRel | `HOL_COMPUTE_POOL` image does not pre-install plotly | Added `PYPI_ACCESS_INTEGRATION` + `pyproject.toml` in `snowflake-devrel.yml`; Snowhouse uses `STREAMLIT_DEDICATED_POOL` which pre-installs plotly so no EAI needed there |
| `AEO_PM_PROMPTS` / `AEO_SKILL_TESTS` missing | Tables not created on new account | Create manually using DDL from `GET_DDL` on the other account |
| `AEO_INTERACTIVE_RESULTS` missing | Not created on Snowhouse during initial setup | Created with `USE ROLE DEVREL_ADMIN_RL; CREATE TABLE IF NOT EXISTS ...` |
| `AEO_SCORE_RESPONSE` SP missing | SP must be created per-account | Retrieve DDL via `GET_DDL('PROCEDURE', ...)` on the source account and run on the target |
| `DB`/`SCH` hardcoded to Snowhouse values on DevRel | `DB` and `SCH` were declared as module-level constants before the `ENV` branch, so DevRel always wrote to `DEVREL.CNANTASENAMAT_DEV` instead of `CHANINN_DEMO_DATA.APPS` | Moved `DB` and `SCH` inside the `if ENV == "devrel"` / `else` block in `utils/db.py`. Verified with `CREATE TABLE IF NOT EXISTS` + `INSERT` + `SELECT` on both accounts. |
| `AEO_QUESTION_CANDIDATES` missing | New table added for question submission workflow | Create with DDL from `scripts/setup_pm_tables.sql`. Columns: `SUBMISSION_ID`, `SUBMITTED_BY`, `FIRST_NAME`, `LAST_NAME`, `QUESTION_TEXT`, `CATEGORY`, `QUESTION_TYPE`, `CANONICAL_ANSWER`, `MUST_HAVE_1..5`, `STATUS`, `SUBMITTED_AT`, `REVIEWED_AT`, `REVIEWED_BY`, `ADMIN_NOTES` |
| SPCS job exits `FAILED`: `USE ROLE` fails | `DEVREL_INGEST_RL` role does not exist on DevRel. Container calls `USE ROLE {role}` at startup | `SPCS_ROLE` is now `ACCOUNTADMIN` on DevRel, `DEVREL_INGEST_RL` on Snowhouse. Auto-selected by `_detect_env()` in `utils/db.py` |
| SPCS job exits `FAILED`: `USE WAREHOUSE` fails | `SNOWADHOC` warehouse does not exist on DevRel | `WH` is now `CHANIN_XS` on DevRel, `SNOWADHOC` on Snowhouse. Auto-selected by `_detect_env()` |
| `snow streamlit deploy --rolename` ignored | Snow CLI flag does not reliably override the session role | Added `my-snowflake-deploy` entry to `~/.snowflake/connections.toml` (mirrors `my-snowflake` with `role = "DEVREL_ADMIN_RL"`) |
| `Failed to get the version of the Streamlit library … >=1.48.0` on Snowhouse | Snowflake's static analyser detects `:orange-badge[...]` / `:blue-badge[...]` inline markdown syntax and sets a `>=1.48.0` version requirement. `STREAMLIT_DEDICATED_POOL` has an older pre-installed Streamlit that cannot be upgraded via `environment.yml`. | Replace all `:color-badge[text]` with `:color[text]` (plain colored text, supported since 1.16). Do not use the badge inline markdown syntax on Snowhouse. |
| `Failed to retrieve packages … dns error … pypi.org/simple/pandas` on Snowhouse | Full `pyproject.toml` (with deps listed) was deployed to Snowhouse. `STREAMLIT_DEDICATED_POOL` pre-installs all packages so no PyPI fetch is needed, but listing them causes the runtime to attempt it and fail with a DNS error (no EAI). | Always use the pyproject swap in the Snowhouse deploy command: `cp pyproject-snowhouse.toml pyproject.toml` before deploying, restore after. `pyproject-snowhouse.toml` has `dependencies = []`. |
| `PYPI_ACCESS_INTEGRATION` not authorized for `DEVREL_ADMIN_RL` on Snowhouse | `DEVREL_ADMIN_RL` does not have `USAGE` on the EAI | Not needed on Snowhouse — `STREAMLIT_DEDICATED_POOL` pre-installs plotly. Remove EAI from `snowflake.yml` |
| `snowflake.yml` becomes identical to `snowflake-devrel.yml` | Swap-restore command interrupted or partially failed | Reconstructed from `SHOW STREAMLITS` + `GET_DDL`. Correct Snowhouse config: `DEVREL.CNANTASENAMAT_DEV`, `SNOWADHOC`, `STREAMLIT_DEDICATED_POOL`, no EAI |
| `Object 'CHANINN_DEMO_DATA.APPS.AEO_RUNS' does not exist` on DevRel | DevRel has no proxy views in `CHANINN_DEMO_DATA.APPS`; read-only data lives directly in `AEO_OBSERVABILITY.EVAL_SCHEMA` | Added `READ_DB`/`READ_SCH` constants to `utils/db.py`; split `_qualify_tables()` into two passes so read-only objects route to `AEO_OBSERVABILITY.EVAL_SCHEMA` |
| `Object 'CHANINN_DEMO_DATA.APPS.AEO_TRIGGER_INTERACTIVE' does not exist` | SP not created in new account schema | Create SP in `CHANINN_DEMO_DATA.APPS` with DevRel-specific defaults (`CHANIN_XS`, `ACCOUNTADMIN`, `CHANINN_DEMO_DATA.APPS`) |
| `Object 'CHANINN_DEMO_DATA.APPS.AEO_SCORE_RESPONSE' does not exist` | SP not created in new account schema | Create SP in `CHANINN_DEMO_DATA.APPS`; replace hardcoded `DEVREL.CNANTASENAMAT_DEV.AEO_QUESTIONS` reference with `AEO_OBSERVABILITY.EVAL_SCHEMA.AEO_QUESTIONS` |
| SPCS job `FAILED`: `invalid identifier 'COMPLETED_AT'` | `AEO_INTERACTIVE_RESULTS` created from Snowhouse DDL which lacked `COMPLETED_AT`; container script requires it | `ALTER TABLE CHANINN_DEMO_DATA.APPS.AEO_INTERACTIVE_RESULTS ADD COLUMN COMPLETED_AT TIMESTAMP_NTZ;` (also applied to Snowhouse for parity) |
| `AEO_TRANSCRIPT` missing on DevRel | New table not yet created in `AEO_OBSERVABILITY.EVAL_SCHEMA` | Create with DDL from `GET_DDL` on Snowhouse. 25 columns including `TOOL_CALL_*` per-tool counts, `INPUT_TOKENS`, `OUTPUT_TOKENS`, `CACHE_READ_TOKENS`, `CACHE_WRITE_TOKENS`, `FIRST_REQUEST_ID`, `LAST_REQUEST_ID`, `GENERATION_SECS`. |
| `V_AEO_TRANSCRIPT_STATS` missing on DevRel | View not yet created in `AEO_OBSERVABILITY.EVAL_SCHEMA` | Recreate from `GET_DDL` on Snowhouse. Uses `LEFT JOIN AEO_TRANSCRIPT` so runs without transcript data still appear. |
| Runner executed locally in production | `REQUIRE_SPCS` env var not set in job spec, allowing accidental local execution | All production job specs (`setup-snowhouse.sql`, `aeo-job-snowhouse.yaml`) set `REQUIRE_SPCS: "true"`. Runner raises `RuntimeError` at startup if `/snowflake/session/token` is absent. Omit the var (or set to `false`) only for local dev. |
| `CACHE_READ_TOKENS` / `CACHE_WRITE_TOKENS` are NULL for `cortex_complete` runs | `SNOWFLAKE.CORTEX.COMPLETE` does not return cache token breakdown; `CORTEX_FUNCTIONS_USAGE_HISTORY` investigated but only provides total tokens with no user filter. | Expected and acceptable. `INPUT_TOKENS` and `OUTPUT_TOKENS` are populated from the inline `usage` field. Cache columns are only available for `cortex_cli` runs via `CORTEX_CODE_CLI_USAGE_HISTORY`. |

---

## Debugging SPCS container failures

When `AEO_TRIGGER_INTERACTIVE` throws `Job AEO_INTERACT_xxx failed to complete. Exited with status: FAILED`, get the container logs immediately — the job name is in the error message.

**Snowhouse:**
```sql
CALL SYSTEM$GET_SERVICE_LOGS(
    'DEVREL.CNANTASENAMAT_DEV.AEO_INTERACT_<short_id>',
    '0',
    'aeo-interactive',
    100
);
```

**DevRel:**
```sql
CALL SYSTEM$GET_SERVICE_LOGS(
    'CHANINN_DEMO_DATA.APPS.AEO_INTERACT_<short_id>',
    '0',
    'aeo-interactive',
    100
);
```

Common log errors and their fixes:

| Log error | Cause | Fix |
|---|---|---|
| `USE ROLE {role}` → `Object does not exist` | Role name invalid for this account | Update `SPCS_ROLE` in `utils/db.py` |
| `USE WAREHOUSE {wh}` → `Object does not exist` | Warehouse name invalid for this account | Update `WH` in `utils/db.py` |
| `invalid identifier 'COMPLETED_AT'` | `AEO_INTERACTIVE_RESULTS` table is missing the `COMPLETED_AT` column | `ALTER TABLE CHANINN_DEMO_DATA.APPS.AEO_INTERACTIVE_RESULTS ADD COLUMN COMPLETED_AT TIMESTAMP_NTZ;` |
| `cortex CLI found` but no further output | Container started but timed out or crashed | Check image version; re-test with direct `CALL AEO_TRIGGER_INTERACTIVE(...)` |
| CoCo responds "I'm in a restricted session where several tools are blocked" | `aeo_spcs_interactive.py` was not calling `setup_cortex_connection_for_spcs()`, so `~/.snowflake/connections.toml` was never written and CoCo could not authenticate to Snowflake | Fixed in `aeo-benchmark:v5`: interactive runner now calls `setup_cortex_connection_for_spcs(token, account, host, warehouse, role)` before `cortex -c spcs ...` invocation |
| CoCo responds "Web browsing and web search tools are blocked" | CoCo requires user approval for high-risk tools (web_search, web_fetch) and silently skips them in headless `-p` mode where it cannot interactively prompt for permission. This is NOT a network policy issue. | Add `--dangerously-allow-all-tool-calls` to the cortex CLI invocation: `cortex -c spcs -m model -p prompt --dangerously-allow-all-tool-calls`. This auto-approves all tool calls and unlocks full agentic web access. Fixed in `aeo-benchmark:v7`. |
| `cortex -c spcs -m model prompt` (no `-p`) crashes with `Raw mode is not supported on the current process.stdin` | CoCo's CLI uses the Ink (React terminal UI) library which requires raw mode/TTY for interactive rendering. Piping stdin without a TTY crashes Ink before processing the prompt. | Always use `-p` flag for subprocess invocation in containers: `cortex -c spcs -m model -p prompt`. The `-p` flag does NOT restrict tools; it bypasses Ink's TTY requirement. V3 agentic runs confirmed tool usage with `-p` on accounts with SPCS egress. |
| `Unknown user-defined function DEVREL.CNANTASENAMAT_DEV.AEO_TRIGGER_INTERACTIVE` after re-creating SP | `CREATE OR REPLACE PROCEDURE` drops all existing grants. The SiS app (running as `DEVREL_ADMIN_RL`) loses EXECUTE access. | Always re-grant after recreating: `GRANT USAGE ON PROCEDURE DEVREL.CNANTASENAMAT_DEV.AEO_TRIGGER_INTERACTIVE(VARCHAR, VARCHAR, VARCHAR, VARCHAR) TO ROLE DEVREL_ADMIN_RL;` |
| `aeo_spcs_interactive.py` missing from local repo | File was referenced in Dockerfile COPY but never committed to the repo (likely created directly in the build context and lost) | File recreated and committed to `scripts/spcs/aeo_spcs_interactive.py` in v3 branch. Must be present for `docker build` to succeed. |

To reproduce and inspect a failure interactively without going through the SiS app:

**Snowhouse:**
```sql
USE WAREHOUSE SNOWADHOC;
CALL DEVREL.CNANTASENAMAT_DEV.AEO_TRIGGER_INTERACTIVE(
    'test prompt',
    'SNOWADHOC',
    'DEVREL_INGEST_RL',
    'DEVREL.CNANTASENAMAT_DEV'
);
```

**DevRel:**
```sql
USE WAREHOUSE CHANIN_XS;
CALL CHANINN_DEMO_DATA.APPS.AEO_TRIGGER_INTERACTIVE(
    'test prompt',
    'CHANIN_XS',
    'ACCOUNTADMIN',
    'CHANINN_DEMO_DATA.APPS'
);
```

