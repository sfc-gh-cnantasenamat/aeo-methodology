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
| `SPCS_ROLE` | `DEVREL_INGEST_RL` | `ACCOUNTADMIN` |

**Local dev** always falls back to `snowhouse` (no active SiS session). The `my-snowflake` connection in `~/.snowflake/connections.toml` authenticates as `CNANTASENAMAT`. Use the `devrel` connection entry to test against the DevRel account locally.

**Username capture**: use `CURRENT_USER()` inline in SQL `INSERT` statements rather than Python-side detection. This resolves correctly in SiS (logged-in Snowflake user) and local dev (connection user from `connections.toml`) without any extra logic.

---

## SPCS container image

| Account | Image path |
|---|---|
| Snowhouse | `/AEO_DB/PUBLIC/AEO_REPO/aeo-benchmark:v4` |
| DevRel | `sfdevrel-sfdevrel-enterprise.registry.snowflakecomputing.com/aeo_db/public/aeo_repo/aeo-benchmark:v4` |

The `AEO_TRIGGER_INTERACTIVE` SP on DevRel uses the short path (`/AEO_DB/...`),
which Snowflake resolves to the full registry URL automatically.

**Pending:** Dockerfile was updated to v3 (adds Cortex CLI install, copies `transcript_capture.py`, `RUN_MODE` dispatch). Next image push should be tagged `:v5` and the SP specs updated to match.

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
| `AEO_TRANSCRIPT` missing on new account | New table not yet created | Create on both accounts: `DEVREL.CNANTASENAMAT_DEV` (Snowhouse) and `AEO_OBSERVABILITY.EVAL_SCHEMA` (DevRel). DDL in `scripts/spcs/setup-snowhouse.sql`. 25 columns including `TOOL_CALL_*` per-tool counts, `INPUT_TOKENS`, `OUTPUT_TOKENS`, `CACHE_READ_TOKENS`, `CACHE_WRITE_TOKENS`, `FIRST_REQUEST_ID`, `LAST_REQUEST_ID`, `GENERATION_SECS`. |
| `V_AEO_TRANSCRIPT_STATS` missing | View not yet created on new account | Recreate from `GET_DDL` on Snowhouse. Uses `LEFT JOIN AEO_TRANSCRIPT` so runs without transcript data still appear. |

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
| `cortex CLI found` but no further output | Container started but timed out or crashed | Check image version; re-test with direct `CALL AEO_TRIGGER_INTERACTIVE(...)` |

To reproduce and inspect a failure interactively without going through the SiS app:

```sql
USE WAREHOUSE COMPUTE_WH;
CALL DEVREL.CNANTASENAMAT_DEV.AEO_TRIGGER_INTERACTIVE(
    'test prompt',
    'CHANIN_XS',      -- warehouse
    'ACCOUNTADMIN',   -- role
    'DEVREL.CNANTASENAMAT_DEV'
);
```

