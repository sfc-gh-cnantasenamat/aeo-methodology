"""Snowflake connection and query helpers for the AEO dashboard."""

import streamlit as st
import pandas as pd

DB   = "DEVREL"
SCH  = "CNANTASENAMAT_DEV"
WH   = "SNOWADHOC"


@st.cache_data(ttl=300, show_spinner="Querying Snowflake…")
def run_query(sql: str) -> pd.DataFrame:
    """Execute SQL and return a DataFrame.

    get_active_session() is called here (at render time inside @st.cache_data),
    not at module level. Module-level calls fail in SiS because st.Page()
    pre-imports page modules before the Snowpark session context is ready.
    Inside @st.cache_data the full request context is available.
    """
    try:
        from snowflake.snowpark.context import get_active_session
        sess = get_active_session()
    except Exception:
        from snowflake.snowpark import Session
        sess = Session.builder.config("connection_name", "my-snowflake").create()
    sess.sql(f"USE WAREHOUSE {WH}").collect()
    sess.sql(f"USE DATABASE {DB}").collect()
    sess.sql(f"USE SCHEMA {SCH}").collect()
    return sess.sql(sql).to_pandas()


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
