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

import re
import streamlit as st
import pandas as pd


# ---------------------------------------------------------------------------
# Environment detection
# ---------------------------------------------------------------------------

def _detect_env() -> str:
    """Return 'devrel' or 'snowhouse' based on the active Snowflake account."""
    try:
        from snowflake.snowpark.context import get_active_session
        session = get_active_session()
        acct = (session.get_current_account() or "").upper()
        if "SFDEVREL" in acct:
            return "devrel"
    except Exception:
        pass
    return "snowhouse"


ENV = _detect_env()

# ---------------------------------------------------------------------------
# Environment-specific constants
# ---------------------------------------------------------------------------

DB   = "DEVREL"
SCH  = "CNANTASENAMAT_DEV"

if ENV == "devrel":
    WH        = "CHANIN_XS"
    ROLE      = "ACCOUNTADMIN"
    SPCS_ROLE = "ACCOUNTADMIN"
else:  # snowhouse (including local dev)
    WH        = "SNOWADHOC"
    ROLE      = "DEVREL_ADMIN_RL"
    SPCS_ROLE = "DEVREL_INGEST_RL"


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
    """Return True when running inside Streamlit in Snowflake (SiS).

    Uses get_active_session() as the canonical probe — it succeeds in SiS
    and raises in a local Python environment.  Cached implicitly because
    _get_session() is already @st.cache_resource.
    """
    try:
        from snowflake.snowpark.context import get_active_session
        get_active_session()
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300, show_spinner="Querying Snowflake…")
def run_query(sql: str) -> pd.DataFrame:
    """Execute SQL and return a DataFrame.

    Automatically qualifies bare AEO view and table names so they resolve
    in SiS where USE DATABASE/SCHEMA is not available.
    """
    sql = _qualify_tables(sql)
    return _get_session().sql(sql).to_pandas()


def _qualify_tables(sql: str) -> str:
    """Fully-qualify bare AEO table/view names for SiS compatibility."""
    return re.sub(
        r'\b(V_AEO_\w+|AEO_QUESTIONS|AEO_RESPONSES|AEO_RUNS'
        r'|AEO_RUN_CONFIG|AEO_SCORES|AEO_PM_PROMPTS|AEO_SKILL_TESTS'
        r'|AEO_INTERACTIVE_RESULTS)\b',
        f'{DB}.{SCH}.\\1', sql,
    )


def run_write(sql: str, params: list | None = None):
    """Execute a write statement (INSERT/UPDATE/MERGE) with optional params.

    Auto-qualifies AEO table names. Uses qmark (?) binding.
    Returns the result rows (usually empty for INSERTs).
    """
    sql = _qualify_tables(sql)
    session = _get_session()
    if params:
        return session.sql(sql, params=params).collect()
    return session.sql(sql).collect()


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
