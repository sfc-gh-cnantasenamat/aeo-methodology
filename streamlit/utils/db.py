"""Snowflake connection and query helpers for the AEO dashboard."""

import re
import streamlit as st
import pandas as pd

DB   = "DEVREL"
SCH  = "CNANTASENAMAT_DEV"
WH   = "SNOWADHOC"
ROLE = "DEVREL_ADMIN_RL"


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


@st.cache_data(ttl=300, show_spinner="Querying Snowflake…")
def run_query(sql: str) -> pd.DataFrame:
    """Execute SQL and return a DataFrame.

    Automatically qualifies bare AEO view and table names so they resolve
    in SiS where USE DATABASE/SCHEMA is not available.
    """
    # Qualify bare V_AEO_* views and AEO_* tables
    sql = re.sub(r'\b(V_AEO_\w+|AEO_QUESTIONS|AEO_RESPONSES|AEO_RUNS|AEO_RUN_CONFIG|AEO_SCORES)\b',
                 f'{DB}.{SCH}.\\1', sql)
    return _get_session().sql(sql).to_pandas()


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
