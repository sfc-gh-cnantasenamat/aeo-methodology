# AEO Benchmark Dashboard — Deployment Reference

The app is deployed to two Snowflake accounts. All environment-specific constants
are auto-detected at runtime in `utils/db.py` via `get_active_session().get_current_account()`.

---

## Environments

### Snowhouse

| Property | Value |
|---|---|
| Account | `SFCOGSOPS-SNOWHOUSE_AWS_US_WEST_2` |
| Connection name | `my-snowflake` (read-only, `MARKETING_SENSITIVE_RO`) |
| Deploy connection (app) | `my-snowflake-deploy` (`role = DEVREL_ADMIN_RL`) |
| Deploy connection (SP) | `my-snowflake-modeling` (`role = DEVREL_MODELING_RL`) |
| Streamlit owner | `DEVREL_ADMIN_RL` |
| SP owner (`AEO_TRIGGER_INTERACTIVE`) | `DEVREL_MODELING_RL` (needs `USAGE` on `AEO_COMPUTE_POOL`) |
| `WH` | `SNOWADHOC` |
| `ROLE` | `DEVREL_ADMIN_RL` |
| `SPCS_ROLE` | `DEVREL_MODELING_RL` |
| SiS app | `DEVREL.CNANTASENAMAT_DEV.AEO_BENCHMARK_DASHBOARD` |
| SiS runtime | Warehouse-based (`query_warehouse: SNOWADHOC`) |
| Skill stage | `DEVREL.CNANTASENAMAT_DEV.AEO_SKILL_STAGE` |
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

Objects exist on **both** accounts under their respective schemas (`DEVREL.CNANTASENAMAT_DEV` on Snowhouse, `CHANINN_DEMO_DATA.APPS` on DevRel). All table references in Python code use the `DB` and `SCH` constants from `utils/db.py` for full qualification.

### Tables (writable)

| Table | Purpose |
|---|---|
| `AEO_INTERACTIVE_RESULTS` | SPCS job request/response tracking |
| `AEO_PM_PROMPTS` | Results from Test Your Prompt experiments |
| `AEO_SKILL_TESTS` | Results from Test Your Skill experiments |
| `AEO_QUESTION_CANDIDATES` | Question submissions pending admin review (STATUS: `pending` / `approved` / `rejected`) |
| `AEO_BENCHMARK_<NAME>` | Dynamically created by admin via the "Add to Benchmark Set" feature in Questions Explorer. Name is sanitized to uppercase alphanumeric/underscores. Created with `CREATE TABLE IF NOT EXISTS` so re-submitting the same name appends rows. |

### Views (read-only proxies over `AEO_OBSERVABILITY.EVAL_SCHEMA`)

`AEO_QUESTIONS`, `AEO_RUNS`, `AEO_RUN_CONFIG`, `AEO_SCORES`, `AEO_TRANSCRIPT`,
`V_AEO_LEADERBOARD`, `V_AEO_FACTORIAL_EFFECTS`, `V_AEO_PER_QUESTION_HEATMAP`,
`V_AEO_MODEL_COMPARISON`, `V_AEO_JUDGE_AGREEMENT`, `V_AEO_TRANSCRIPT_STATS`

Note: `AEO_RESPONSES` is now 4 columns only (`RUN_ID`, `QUESTION_ID`, `RESPONSE_TEXT`, `GENERATED_AT`). All observability data (tokens, tool calls, turns, timing) lives in `AEO_TRANSCRIPT`.

### Stored procedures

| Procedure | Purpose |
|---|---|
| `AEO_SCORE_RESPONSE(question_id, response_text, system_prompt, judges)` | LLM judge panel scoring (5 dimensions + must-haves) |
| `AEO_TRIGGER_INTERACTIVE(prompt, warehouse, role, run_schema)` | Launches SPCS job service, returns `REQUEST_ID` |

---

## Deploy commands

### Snowhouse

The app runs as a **warehouse-based Streamlit** on `SNOWADHOC` (no container runtime or compute pool). The Streamlit is owned by `DEVREL_ADMIN_RL`; deploy with `my-snowflake-deploy`.

```bash
SNOW=/Library/Frameworks/Python.framework/Versions/3.11/bin/snow
$SNOW streamlit deploy --replace --connection my-snowflake-deploy
```

`pyproject.toml` must have `dependencies = []` for Snowhouse (pre-installed packages, no PyPI/EAI needed). Keep a `pyproject-snowhouse.toml` with empty deps and swap if deploying from a machine that also targets DevRel:

```bash
cp pyproject.toml pyproject-devrel.toml \
  && cp pyproject-snowhouse.toml pyproject.toml \
  && $SNOW streamlit deploy --replace --connection my-snowflake-deploy \
  && cp pyproject-devrel.toml pyproject.toml \
  && rm pyproject-devrel.toml
```

### DevRel

Snow CLI always reads `snowflake.yml`, so swap files around the deploy:

```bash
SNOW=/Library/Frameworks/Python.framework/Versions/3.11/bin/snow
cp snowflake.yml snowflake-snowhouse.yml \
  && cp snowflake-devrel.yml snowflake.yml \
  && $SNOW streamlit deploy --replace --connection devrel \
  && cp snowflake-snowhouse.yml snowflake.yml \
  && rm snowflake-snowhouse.yml
```

---

## Snowhouse grants reference

`DEVREL_ADMIN_RL` owns the Streamlit and most tables. `DEVREL_MODELING_RL` owns
`AEO_TRIGGER_INTERACTIVE` and requires the following grants to function correctly
as the SP's `EXECUTE AS OWNER` role:

```sql
USE ROLE DEVREL_ADMIN_RL;

-- SP can INSERT + UPDATE the results table (both needed: INSERT on launch, UPDATE on completion)
GRANT INSERT ON TABLE DEVREL.CNANTASENAMAT_DEV.AEO_INTERACTIVE_RESULTS TO ROLE DEVREL_MODELING_RL;
GRANT UPDATE ON TABLE DEVREL.CNANTASENAMAT_DEV.AEO_INTERACTIVE_RESULTS TO ROLE DEVREL_MODELING_RL;

-- SP can create job services inside the schema
GRANT CREATE SERVICE ON SCHEMA DEVREL.CNANTASENAMAT_DEV TO ROLE DEVREL_MODELING_RL;

-- SP can pull the container image
GRANT READ ON IMAGE REPOSITORY DEVREL.CNANTASENAMAT_DEV.AEO_REPO TO ROLE DEVREL_MODELING_RL;

-- Re-grant USAGE to caller role after any CREATE OR REPLACE on the SP
GRANT USAGE ON PROCEDURE DEVREL.CNANTASENAMAT_DEV.AEO_TRIGGER_INTERACTIVE(VARCHAR, VARCHAR, VARCHAR, VARCHAR)
  TO ROLE DEVREL_ADMIN_RL;
```

`USAGE ON COMPUTE POOL AEO_COMPUTE_POOL` is granted to `DEVREL_MODELING_RL` by `SPCS_ADMIN_RL`
(pool owner). The app owner `DEVREL_ADMIN_RL` does NOT need compute pool access because the
Streamlit is warehouse-based; only the SP owner needs it.

**Non-destructive SP ownership transfer** (needed if recreating the SP as a different owner):
```sql
-- Step 1: transfer ownership atomically (no data/state loss)
GRANT OWNERSHIP ON PROCEDURE DEVREL.CNANTASENAMAT_DEV.AEO_TRIGGER_INTERACTIVE(VARCHAR, VARCHAR, VARCHAR, VARCHAR)
  TO ROLE DEVREL_MODELING_RL REVOKE CURRENT GRANTS;

-- Step 2: recreate as new owner (CREATE OR REPLACE runs as the current session role)
USE ROLE DEVREL_MODELING_RL;
CREATE OR REPLACE PROCEDURE DEVREL.CNANTASENAMAT_DEV.AEO_TRIGGER_INTERACTIVE(...) ...;

-- Step 3: re-grant USAGE (lost on every CREATE OR REPLACE)
GRANT USAGE ON PROCEDURE ... TO ROLE DEVREL_ADMIN_RL;
```

Note: `GRANT OWNERSHIP ON STREAMLIT` is **not supported** in Snowflake. To change a Streamlit's
owner you must drop and redeploy it with the target role. For warehouse-based Streamlits,
`DEVREL_ADMIN_RL` is used as the owner because it has access to all required tables and views.

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

All constants (`DB`, `SCH`, `WH`, `ROLE`, `SPCS_ROLE`) are set from `ENV` at module load time:

| Constant | Snowhouse | DevRel |
|---|---|---|
| `DB` | `DEVREL` | `CHANINN_DEMO_DATA` |
| `SCH` | `CNANTASENAMAT_DEV` | `APPS` |
| `WH` | `SNOWADHOC` | `CHANIN_XS` |
| `ROLE` | `DEVREL_ADMIN_RL` | `ACCOUNTADMIN` |
| `SPCS_ROLE` | `DEVREL_MODELING_RL` | `ACCOUNTADMIN` |

**Local dev** always falls back to `snowhouse` (no active SiS session). The `my-snowflake` connection in `~/.snowflake/connections.toml` authenticates as `CNANTASENAMAT`. Use the `devrel` connection entry to test against the DevRel account locally.

**Username capture**: use `CURRENT_USER()` inline in SQL `INSERT` statements rather than Python-side detection. This resolves correctly in SiS (logged-in Snowflake user) and local dev (connection user from `connections.toml`) without any extra logic.

---

## SPCS container image

| Account | Purpose | Image path |
|---|---|---|
| Snowhouse | Interactive (SiS `AEO_TRIGGER_INTERACTIVE` SP) | `/DEVREL/CNANTASENAMAT_DEV/AEO_REPO/aeo-benchmark:v4` |
| Snowhouse | Batch runs (`aeo-job-snowhouse.yaml`) | `/DEVREL/CNANTASENAMAT_DEV/AEO_REPO/aeo-benchmark:v5` |
| DevRel | Interactive + batch | `sfdevrel-sfdevrel-enterprise.registry.snowflakecomputing.com/aeo_db/public/aeo_repo/aeo-benchmark:v5` |

The `AEO_TRIGGER_INTERACTIVE` SP on DevRel uses the short path (`/AEO_DB/...`),
which Snowflake resolves to the full registry URL automatically.

**Image v4 (Snowhouse interactive):** Built 2026-04-27 from `dev/spcs/Dockerfile`. Includes
`aeo_spcs_interactive.py`, `transcript_capture.py`, Cortex CLI, and `RUN_MODE` dispatch in CMD.
The v3 image predated `aeo_spcs_interactive.py` and lacked the `if/else` CMD — it always ran
`aeo_spcs_runner.py` (batch mode) regardless of `RUN_MODE=interactive`. It also hardcoded
`USE ROLE DEVREL_INGEST_RL` at line 238 instead of reading the `ROLE` env var.

**Image versioning note:** The Docker image tag (`:v4`, `:v5`) and the runner script version
("v3" as in `aeo_spcs_runner.py`) are independent counters. The image tag increments every
time a new image is built and pushed to the registry. The script version reflects internal
logic changes to the Python runner. Do not conflate them.

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
| SPCS job exits `FAILED`: `USE ROLE` fails | `DEVREL_INGEST_RL` role does not exist on DevRel. Container calls `USE ROLE {role}` at startup | `SPCS_ROLE` is now `ACCOUNTADMIN` on DevRel, `DEVREL_MODELING_RL` on Snowhouse. Auto-selected by `_detect_env()` in `utils/db.py` |
| SPCS interactive job runs batch mode instead of interactive | Image v3 was built before `aeo_spcs_interactive.py` existed; its CMD always executed `aeo_spcs_runner.py` regardless of `RUN_MODE=interactive` | Rebuilt image as v4 from `dev/spcs/Dockerfile` (has correct `if/else` CMD dispatch). Update `IMAGE_PATH` in `AEO_TRIGGER_INTERACTIVE` SP to `:v4`. |
| SPCS interactive job: `Requested role 'DEVREL_INGEST_RL' is not assigned to the executing user` | Image v3 hardcoded `cur.execute("USE ROLE DEVREL_INGEST_RL")` instead of reading the `ROLE` env var | Fixed in v4 image (`aeo_spcs_interactive.py` uses `os.environ.get("ROLE", "")` and no hardcoded role) |
| SPCS interactive job: `Insufficient privileges … UPDATE on AEO_INTERACTIVE_RESULTS` | `DEVREL_MODELING_RL` had `INSERT` but not `UPDATE`; container inserts on launch and updates on completion | `GRANT UPDATE ON TABLE DEVREL.CNANTASENAMAT_DEV.AEO_INTERACTIVE_RESULTS TO ROLE DEVREL_MODELING_RL` |
| `Unknown user-defined function AEO_SCORE_RESPONSE` in SiS | SiS session ran as the Streamlit owner role which had not yet switched to `DEVREL_ADMIN_RL` where the SP lives | `_get_session()` now calls `USE ROLE {ROLE}` and `USE WAREHOUSE {WH}` in a nested try in the SiS path |
| `Invalid connection_name 'my-snowflake', known ones are []` in SiS | `USE ROLE` in SiS path failed (role mismatch), outer except triggered local-dev path which tried to build a new Session with a named connection — not available in SiS | Two-part fix: (1) nested try-except in `_get_session()` so `USE ROLE` failure never falls to local-dev path; (2) Streamlit ownership restored to `DEVREL_ADMIN_RL` so session already has the correct role |
| `aeo_feedback_functions` import error on custom questions in SiS | `from aeo_feedback_functions import score_full_rubric` was in the per-judge scoring path for SiS custom questions; that package is not installable in SiS | Removed the SiS-specific branch; always use `_score_full_rubric_local` which calls `CORTEX.COMPLETE` directly through the active session |
| `st.experimental_user` deprecation warning / AttributeError | Deprecated API used in `test_prompt.py` and `test_skill.py` | Changed to `st.user.user_name` in both files |
| `AxiosError: Request failed with status code 500` on file upload (Test your Skill) | An uncaught exception in the history `run_query` during the upload-triggered page rerun caused the SiS server to return 500 | Wrapped entire history section in `try/except Exception` in `test_skill.py` so query failures show a warning instead of crashing the page |
| SPCS job exits `FAILED`: `USE WAREHOUSE` fails | `SNOWADHOC` warehouse does not exist on DevRel | `WH` is now `CHANIN_XS` on DevRel, `SNOWADHOC` on Snowhouse. Auto-selected by `_detect_env()` |
| `snow streamlit deploy --rolename` ignored | Snow CLI flag does not reliably override the session role | Added `my-snowflake-deploy` entry to `~/.snowflake/connections.toml` (mirrors `my-snowflake` with `role = "DEVREL_ADMIN_RL"`) |
| `Failed to get the version of the Streamlit library … >=1.48.0` on Snowhouse | Snowflake's static analyser detects `:orange-badge[...]` / `:blue-badge[...]` inline markdown syntax and sets a `>=1.48.0` version requirement. `STREAMLIT_DEDICATED_POOL` has an older pre-installed Streamlit that cannot be upgraded via `environment.yml`. | Replace all `:color-badge[text]` with `:color[text]` (plain colored text, supported since 1.16). Do not use the badge inline markdown syntax on Snowhouse. |
| `Failed to retrieve packages … dns error … pypi.org/simple/pandas` on Snowhouse | Full `pyproject.toml` (with deps listed) was deployed to Snowhouse. `STREAMLIT_DEDICATED_POOL` pre-installs all packages so no PyPI fetch is needed, but listing them causes the runtime to attempt it and fail with a DNS error (no EAI). | Always use the pyproject swap in the Snowhouse deploy command: `cp pyproject-snowhouse.toml pyproject.toml` before deploying, restore after. `pyproject-snowhouse.toml` has `dependencies = []`. |
| `PYPI_ACCESS_INTEGRATION` not authorized for `DEVREL_ADMIN_RL` on Snowhouse | `DEVREL_ADMIN_RL` does not have `USAGE` on the EAI | Not needed on Snowhouse — `STREAMLIT_DEDICATED_POOL` pre-installs plotly. Remove EAI from `snowflake.yml` |
| `snowflake.yml` becomes identical to `snowflake-devrel.yml` | Swap-restore command interrupted or partially failed | Reconstructed from `SHOW STREAMLITS` + `GET_DDL`. Correct Snowhouse config: `DEVREL.CNANTASENAMAT_DEV`, `SNOWADHOC`, `STREAMLIT_DEDICATED_POOL`, no EAI |
| `AEO_TRANSCRIPT` missing on new account | New table not yet created | Create on both accounts: `DEVREL.CNANTASENAMAT_DEV` (Snowhouse) and `AEO_OBSERVABILITY.EVAL_SCHEMA` (DevRel). DDL in `scripts/spcs/setup-snowhouse.sql`. 25 columns including `TOOL_CALL_*` per-tool counts, `INPUT_TOKENS`, `OUTPUT_TOKENS`, `CACHE_READ_TOKENS`, `CACHE_WRITE_TOKENS`, `FIRST_REQUEST_ID`, `LAST_REQUEST_ID`, `GENERATION_SECS`. |
| `V_AEO_TRANSCRIPT_STATS` missing | View not yet created on new account | Recreate from `GET_DDL` on Snowhouse. Uses `LEFT JOIN AEO_TRANSCRIPT` so runs without transcript data still appear. |
| Runner executed locally in production | `REQUIRE_SPCS` env var not set in job spec, allowing accidental local execution | All production job specs (`setup-snowhouse.sql`, `aeo-job-snowhouse.yaml`) set `REQUIRE_SPCS: "true"`. Runner raises `RuntimeError` at startup if token file is absent. Omit the var (or set to `false`) only for local dev. |
| `CACHE_READ_TOKENS` / `CACHE_WRITE_TOKENS` are NULL for `cortex_complete` runs | `SNOWFLAKE.CORTEX.COMPLETE` does not return cache token breakdown; `CORTEX_FUNCTIONS_USAGE_HISTORY` investigated but only provides total tokens with no user filter. | Expected and acceptable. `INPUT_TOKENS` and `OUTPUT_TOKENS` are populated from the inline `usage` field. Cache columns are only available for `cortex_cli` runs via `CORTEX_CODE_CLI_USAGE_HISTORY`.

---

## Debugging SPCS container failures

When `AEO_TRIGGER_INTERACTIVE` throws `Job AEO_INTERACT_xxx failed to complete. Exited with status: FAILED`, get the container logs immediately — the job name is in the error message:

```sql
CALL SYSTEM$GET_SERVICE_LOGS(
    'DEVREL.CNANTASENAMAT_DEV.AEO_INTERACT_<short_id>',
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
| `AEO SPCS Runner v3` header + `USE ROLE DEVREL_INGEST_RL` hardcoded | Image built from old script before `RUN_MODE` dispatch was added | Rebuild image from `dev/spcs/Dockerfile` as `:v4` and update SP `IMAGE_PATH` |
| `cortex CLI found` + `Status: complete` but then `UPDATE ... Insufficient privileges` | SP owner has `INSERT` but not `UPDATE` on `AEO_INTERACTIVE_RESULTS` | `GRANT UPDATE ON TABLE ... TO ROLE DEVREL_MODELING_RL` |
| `cortex CLI found` but no further output | Container started but timed out or crashed | Check image version; re-test with direct `CALL AEO_TRIGGER_INTERACTIVE(...)` |

To reproduce and inspect a failure interactively without going through the SiS app
(Snowhouse — use `DEVREL_ADMIN_RL` to call, SP runs as `DEVREL_MODELING_RL`):

```sql
USE ROLE DEVREL_ADMIN_RL;
USE WAREHOUSE SNOWADHOC;
CALL DEVREL.CNANTASENAMAT_DEV.AEO_TRIGGER_INTERACTIVE(
    'test prompt',
    'SNOWADHOC',           -- warehouse
    'DEVREL_MODELING_RL',  -- role (SP owner role)
    'DEVREL.CNANTASENAMAT_DEV'
);
```

