"""Snowflake connection and query helpers for the AEO dashboard."""

import streamlit as st
import pandas as pd

DB   = "DEVREL"
SCH  = "CNANTASENAMAT_DEV"
WH   = "SNOWADHOC"


@st.cache_resource(show_spinner="Connecting to Snowflake…")
def _get_session():
    """Get a Snowpark session — works in both SiS and local dev.

    In SiS:  get_active_session() returns the framework-managed session.
    Locally: falls back to a named connection in ~/.snowflake/connections.toml.
    """
    try:
        from snowflake.snowpark.context import get_active_session
        return get_active_session()
    except Exception:
        from snowflake.snowpark import Session
        return Session.builder.config("connection_name", "my-snowflake").create()


@st.cache_data(ttl=300, show_spinner="Querying Snowflake…")
def run_query(sql: str) -> pd.DataFrame:
    session = _get_session()
    session.sql(f"USE WAREHOUSE {WH}").collect()
    session.sql(f"USE DATABASE {DB}").collect()
    session.sql(f"USE SCHEMA {SCH}").collect()
    return session.sql(sql).to_pandas()


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
