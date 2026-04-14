"""Snowflake connection and query helpers for the AEO dashboard."""

import streamlit as st
import pandas as pd

DB   = "DEVREL"
SCH  = "CNANTASENAMAT_DEV"
WH   = "SNOWADHOC"


@st.cache_resource(show_spinner="Connecting to Snowflake…")
def _local_connection():
    """Local-only connector — only called when not running in SiS."""
    import snowflake.connector
    return snowflake.connector.connect(
        connection_name="my-snowflake",
        warehouse=WH,
        database=DB,
        schema=SCH,
    )


@st.cache_data(ttl=300, show_spinner="Querying Snowflake…")
def run_query(sql: str) -> pd.DataFrame:
    # st.connection("snowflake") is Streamlit's official SiS connection API.
    # It uses Streamlit's framework-level session management (not Python
    # contextvars), so it works in SiS regardless of cache/thread context.
    # Locally without [connections.snowflake] in secrets.toml it raises,
    # so we fall through to the connector.
    try:
        conn = st.connection("snowflake")
        sess = conn.session
    except Exception:
        sess = None

    if sess is not None:
        sess.sql(f"USE WAREHOUSE {WH}").collect()
        sess.sql(f"USE DATABASE {DB}").collect()
        sess.sql(f"USE SCHEMA {SCH}").collect()
        return sess.sql(sql).to_pandas()

    # Local development fallback
    cur = _local_connection().cursor()
    cur.execute(f"USE WAREHOUSE {WH}")
    cur.execute(f"USE DATABASE {DB}")
    cur.execute(f"USE SCHEMA {SCH}")
    cur.execute(sql)
    df = cur.fetch_pandas_all()
    cur.close()
    return df


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
