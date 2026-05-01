"""Snowflake connection and query helpers for the AEO dashboard.

Environment auto-detection
--------------------------
The app is deployed to two Snowflake accounts:

  snowhouse  SFCOGSOPS-SNOWHOUSE_AWS_US_WEST_2
             WH=SNOWADHOC  SPCS_ROLE=DEVREL_INGEST_RL  ROLE=DEVREL_ADMIN_RL
             SiS app: DEVREL.CNANTASENAMAT_DEV.*
             Skill stage: DEVREL.CNANTASENAMAT_DEV.AEO_SKILL_STAGE

  devrel     SFDEVREL-SFDEVREL_ENTERPRISE
             WH=CHANIN_XS  SPCS_ROLE=ACCOUNTADMIN  ROLE=ACCOUNTADMIN
             SiS app: CHANINN_DEMO_DATA.APPS.*
             Skill stage: CHANINN_DEMO_DATA.APPS.AEO_SKILL_STAGE

ENV is detected at module load via get_active_session().get_current_account().
Falls back to 'snowhouse' for local development (my-snowflake connection).
"""

import os
import re
import streamlit as st
import pandas as pd


def _is_auth_error(exc: Exception) -> bool:
    msg = str(exc)
    return "390114" in msg or "Authentication token has expired" in msg


# ---------------------------------------------------------------------------
# SiS detection — captured at import time, before any Session.builder call.
#
# get_active_session() succeeds in both warehouse-based and container-based SiS.
# SNOWFLAKE_HOST is only injected in SPCS container runtimes, so it cannot be
# used as the sole indicator for warehouse-based SiS deployments.
# ---------------------------------------------------------------------------

_IS_SIS = False
try:
    from snowflake.snowpark.context import get_active_session as _get_sis_session
    _get_sis_session()
    _IS_SIS = True
except Exception:
    pass


# ---------------------------------------------------------------------------
# Environment detection
# ---------------------------------------------------------------------------

# Tracks whether the app is running on the DevRel account (SFDEVREL).
# Used for infrastructure constants (WH, ROLE, SPCS_ROLE) independently of
# the data-path flag ENV.
_DEVREL_ACCOUNT: bool = False


def _detect_env() -> str:
    """Return 'devrel' or 'snowhouse' for data-path selection.

    'devrel'   — V3 data (V3_AEO_SCORES / V3_AEO_TRANSCRIPT) is available.
                 This is true on the DevRel account AND on Snowhouse when the
                 V3 tables have been migrated there.
    'snowhouse' — Fall back to legacy V_AEO_* proxy views.

    Sets the module-level _DEVREL_ACCOUNT flag to True when running on the
    SFDEVREL account, so infrastructure constants (WH, ROLE, SPCS_ROLE) can
    be set independently of the data-path.
    """
    global _DEVREL_ACCOUNT
    if not _IS_SIS:
        return "snowhouse"
    try:
        from snowflake.snowpark.context import get_active_session
        session = get_active_session()
        acct = (session.get_current_account() or "").upper()
        if "SFDEVREL" in acct:
            _DEVREL_ACCOUNT = True
            return "devrel"
        # Snowhouse: check if V3 data has been migrated to this schema.
        try:
            session.sql("SELECT 1 FROM V3_AEO_SCORES LIMIT 1").collect()
            return "devrel"
        except Exception:
            pass
    except Exception:
        pass
    return "snowhouse"


ENV = _detect_env()

# ---------------------------------------------------------------------------
# Environment-specific constants
# Infrastructure constants (WH, ROLE, SPCS_ROLE) are based on the actual
# Snowflake account (_DEVREL_ACCOUNT), not on the data-path ENV flag.
# ---------------------------------------------------------------------------

if _DEVREL_ACCOUNT:
    DB        = "CHANINN_DEMO_DATA"
    SCH       = "APPS"
    WH        = "CHANIN_XS"
    ROLE      = "ACCOUNTADMIN"
    SPCS_ROLE = "ACCOUNTADMIN"
    # Read-only benchmark data lives in AEO_OBSERVABILITY.EVAL_SCHEMA on DevRel;
    # no proxy views exist in CHANINN_DEMO_DATA.APPS.
    READ_DB   = "AEO_OBSERVABILITY"
    READ_SCH  = "EVAL_SCHEMA"
else:  # snowhouse (including local dev)
    DB        = "DEVREL"
    SCH       = "CNANTASENAMAT_DEV"
    WH        = "SNOWADHOC"
    ROLE      = "DEVREL_ADMIN_RL"
    SPCS_ROLE = "DEVREL_MODELING_RL"
    # On Snowhouse, proxy views live in the same schema as writable tables.
    READ_DB   = DB
    READ_SCH  = SCH


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------

@st.cache_resource
def _get_session():
    """Return a Snowpark Session that works in both SiS and local."""
    try:
        from snowflake.snowpark.context import get_active_session
        return get_active_session()
    except Exception:
        from snowflake.snowpark import Session
        session = Session.builder.config("connection_name", "my-snowflake").create()
        session.sql(f"USE ROLE {ROLE}").collect()
        session.sql(f"USE WAREHOUSE {WH}").collect()
        session.sql(f"USE DATABASE {DB}").collect()
        session.sql(f"USE SCHEMA {SCH}").collect()
        return session


def get_session():
    """Public accessor for the Snowpark session (needed by scoring helpers)."""
    return _get_session()


def is_sis() -> bool:
    """Return True when running inside Streamlit in Snowflake (SiS)."""
    return _IS_SIS


def get_current_username() -> str:
    """Return the lowercase Snowflake username for the active session.

    SiS:   reads st.user.user_name.
    Local: reads the 'user' field from the [my-snowflake] section of
           ~/.snowflake/connections.toml.  This means only users whose
           Snowflake credentials are explicitly for 'cnantasenamat' or
           'chaninn' will receive admin rights when running locally.
    """
    if _IS_SIS:
        try:
            return (st.user.user_name or "").lower()
        except Exception:
            return ""
    import tomllib
    from pathlib import Path
    try:
        toml_path = Path.home() / ".snowflake" / "connections.toml"
        with open(toml_path, "rb") as f:
            config = tomllib.load(f)
        return config.get("my-snowflake", {}).get("user", "").lower()
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300, show_spinner="Querying Snowflake…")
def run_query(sql: str) -> pd.DataFrame:
    """Execute SQL and return a DataFrame.

    Automatically qualifies bare AEO view and table names so they resolve
    in SiS where USE DATABASE/SCHEMA is not available.
    Retries once if the cached session has an expired auth token.
    """
    sql = _qualify_tables(sql)
    try:
        return _get_session().sql(sql).to_pandas()
    except Exception as e:
        if _is_auth_error(e):
            _get_session.clear()
            return _get_session().sql(sql).to_pandas()
        raise


def _qualify_tables(sql: str) -> str:
    """Fully-qualify bare AEO table/view names for SiS compatibility.

    Read-only benchmark objects (V_AEO_* views and the core AEO_* tables) are
    qualified against READ_DB.READ_SCH.  On Snowhouse these are proxy views in
    the same schema as the writable tables; on DevRel they live directly in
    AEO_OBSERVABILITY.EVAL_SCHEMA with no proxy layer.

    Writable app tables (AEO_PM_PROMPTS, AEO_SKILL_TESTS,
    AEO_INTERACTIVE_RESULTS, AEO_QUESTION_CANDIDATES) are qualified against
    DB.SCH (CHANINN_DEMO_DATA.APPS on DevRel).
    """
    # Read-only: benchmark source tables and analysis views
    sql = re.sub(
        r'\b(V_AEO_\w+|AEO_QUESTIONS|AEO_RESPONSES|AEO_RUNS'
        r'|AEO_RUN_CONFIG|AEO_SCORES)\b',
        f'{READ_DB}.{READ_SCH}.\\1', sql,
    )
    # Writable: app-specific tables stored in DB.SCH
    sql = re.sub(
        r'\b(AEO_PM_PROMPTS|AEO_SKILL_TESTS'
        r'|AEO_INTERACTIVE_RESULTS|AEO_QUESTION_CANDIDATES'
        r'|V3_AEO_SCORES|V3_AEO_TRANSCRIPT)\b',
        f'{DB}.{SCH}.\\1', sql,
    )
    return sql


def run_write(sql: str, params: list | None = None):
    """Execute a write statement (INSERT/UPDATE/MERGE) with optional params.

    Auto-qualifies AEO table names. Uses qmark (?) binding.
    Returns the result rows (usually empty for INSERTs).
    Retries once if the cached session has an expired auth token.
    """
    sql = _qualify_tables(sql)
    try:
        session = _get_session()
        if params:
            return session.sql(sql, params=params).collect()
        return session.sql(sql).collect()
    except Exception as e:
        if _is_auth_error(e):
            _get_session.clear()
            session = _get_session()
            if params:
                return session.sql(sql, params=params).collect()
            return session.sql(sql).collect()
        raise


# ---------------------------------------------------------------------------
# Chart / config helpers
# ---------------------------------------------------------------------------

def config_label(domain: bool, citation: bool, agentic: bool, self_critique: bool) -> str:
    """Return a short config abbreviation, e.g. 'C+A' or 'Baseline'."""
    parts = []
    if domain:        parts.append("D")
    if citation:      parts.append("C")
    if agentic:       parts.append("A")
    if self_critique: parts.append("S")
    return "+".join(parts) if parts else "Baseline"


def is_agentic(domain: bool, citation: bool, agentic: bool, self_critique: bool) -> bool:
    return bool(agentic)


# Colour palette
AGENTIC_COLOR    = "#2166ac"   # blue
NONAGENTIC_COLOR = "#b2182b"   # red
GREEN            = "#4dac26"
RED              = "#d01c8b"


# ---------------------------------------------------------------------------
# V3 data SQL helpers (DevRel only — V3_AEO_SCORES & V3_AEO_TRANSCRIPT)
# ---------------------------------------------------------------------------

# Human-readable labels for model identifiers (DevRel V3 + Snowhouse AEO_RUNS)
V3_MODEL_LABELS: dict[str, str] = {
    "claude-opus-4-6": "Opus 4.6",
    "claude-opus-4-7": "Opus 4.7",
    "openai-gpt-5.4":  "GPT 5.4",
    "gemini-3.1-pro":  "Gemini 3.1 Pro",
    "llama4-maverick": "Llama4 Maverick",
}


def v3_models_sql() -> str:
    """SQL returning distinct model names from V3_AEO_SCORES, sorted."""
    return (
        "SELECT DISTINCT REGEXP_REPLACE(RUN_ID, '-(base|[DCAS]+)$', '') AS MODEL "
        "FROM V3_AEO_SCORES ORDER BY MODEL"
    )


def snowhouse_models_sql() -> str:
    """SQL returning distinct model names from AEO_RUNS (Snowhouse), sorted.

    Filters to models with >= 2 runs to exclude single exploratory runs
    and match the 3 benchmark models (claude-opus-4-6, claude-opus-4-7, openai-gpt-5.4).
    """
    return (
        "SELECT MODEL FROM AEO_RUNS "
        "GROUP BY MODEL HAVING COUNT(*) >= 2 ORDER BY MODEL"
    )


def v3_leaderboard_sql(model: str) -> str:
    """SQL equivalent of V_AEO_LEADERBOARD for a single V3 model.

    Returns one row per run_id with aggregated SCORE_PCT, MH_PCT, and config
    flag columns (bool) derived from the RUN_ID suffix encoding.
    """
    return f"""
        SELECT RUN_ID,
               CONTAINS(REGEXP_REPLACE(RUN_ID, '^.*-', ''), 'D') AS DOMAIN_PROMPT,
               CONTAINS(REGEXP_REPLACE(RUN_ID, '^.*-', ''), 'C') AS CITATION,
               CONTAINS(REGEXP_REPLACE(RUN_ID, '^.*-', ''), 'A') AS AGENTIC,
               CONTAINS(REGEXP_REPLACE(RUN_ID, '^.*-', ''), 'S') AS SELF_CRITIQUE,
               AVG(TOTAL_SCORE) / 50.0 * 100 AS SCORE_PCT,
               AVG(MUST_HAVE_PASS) * 100     AS MH_PCT,
               AVG(TOTAL_SCORE)              AS TOTAL_SCORE,
               COUNT(DISTINCT QUESTION_ID)   AS QUESTIONS_SCORED,
               REGEXP_REPLACE(RUN_ID, '-(base|[DCAS]+)$', '') AS MODEL
        FROM V3_AEO_SCORES
        WHERE RUN_ID LIKE '{model}-%'
        GROUP BY RUN_ID
    """


def v3_per_question_sql(model: str) -> str:
    """SQL equivalent of V_AEO_PER_QUESTION_HEATMAP for a single V3 model.

    Returns one row per (QUESTION_ID, RUN_ID) with per-judge averages and
    config flag columns derived from the RUN_ID suffix encoding.
    Note: AVG(CITATION) is aliased CITATION_SCORE to match old view columns.
    """
    return f"""
        SELECT QUESTION_ID, RUN_ID,
               CONTAINS(REGEXP_REPLACE(RUN_ID, '^.*-', ''), 'D') AS DOMAIN_PROMPT,
               CONTAINS(REGEXP_REPLACE(RUN_ID, '^.*-', ''), 'C') AS CITATION,
               CONTAINS(REGEXP_REPLACE(RUN_ID, '^.*-', ''), 'A') AS AGENTIC,
               CONTAINS(REGEXP_REPLACE(RUN_ID, '^.*-', ''), 'S') AS SELF_CRITIQUE,
               AVG(TOTAL_SCORE)     AS TOTAL_SCORE,
               AVG(MUST_HAVE_PASS)  AS MUST_HAVE_PASS,
               AVG(CORRECTNESS)     AS CORRECTNESS,
               AVG(COMPLETENESS)    AS COMPLETENESS,
               AVG(RECENCY)         AS RECENCY,
               AVG(CITATION)        AS CITATION_SCORE,
               AVG(RECOMMENDATION)  AS RECOMMENDATION,
               REGEXP_REPLACE(RUN_ID, '-(base|[DCAS]+)$', '') AS MODEL
        FROM V3_AEO_SCORES
        WHERE RUN_ID LIKE '{model}-%'
        GROUP BY QUESTION_ID, RUN_ID
    """
