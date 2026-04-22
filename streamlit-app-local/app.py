"""AEO Benchmark Dashboard — entry point."""
import streamlit as st

# Detect SiS — must be before any other Streamlit calls
_running_in_sis = False
try:
    from snowflake.snowpark.context import get_active_session
    get_active_session()
    _running_in_sis = True
except Exception:
    _running_in_sis = False

if not _running_in_sis:
    st.set_page_config(
        page_title="AEO Benchmark Dashboard",
        layout="wide",
        initial_sidebar_state="expanded",
    )
else:
    # SiS supports layout but not page_title, page_icon, or menu_items
    st.set_page_config(layout="wide")

# Register all pages for routing; sidebar is built manually below
page = st.navigation(
    {
        "": [
            st.Page("pages/home.py",               title="Home",                 icon=":material/home:"),
            st.Page("pages/category_performance.py", title="Category Performance", icon=":material/category:"),
            st.Page("pages/questions_explorer.py", title="Questions Explorer",   icon=":material/manage_search:"),
            st.Page("pages/test_prompt.py",        title="Test your Prompt",     icon=":material/science:"),
            st.Page("pages/test_skill.py",         title="Test your Skill",      icon=":material/extension:"),
        ],
        "Analysis": [
            st.Page("pages/leaderboard.py",       title="Leaderboard",          icon=":material/leaderboard:"),
            st.Page("pages/factors_influence.py", title="Factors Influence",    icon=":material/insights:"),
            st.Page("pages/factorial_heatmap.py", title="Factorial Heatmap",    icon=":material/grid_view:"),
        ],
    },
    position="hidden",
)

# ── Manual sidebar ───────────────────────────────────────────────────────────

_ANALYSIS_TITLES = {
    "Leaderboard", "Factors Influence", "Factorial Heatmap",
}

st.sidebar.title(":material/query_stats: AEO Benchmark")

st.sidebar.page_link("pages/home.py",               label="Home",                 icon=":material/home:")
st.sidebar.page_link("pages/category_performance.py", label="Category Performance", icon=":material/category:")
st.sidebar.page_link("pages/questions_explorer.py", label="Questions Explorer",   icon=":material/manage_search:")
st.sidebar.page_link("pages/test_prompt.py",        label="Test your Prompt",     icon=":material/science:")
st.sidebar.page_link("pages/test_skill.py",         label="Test your Skill",      icon=":material/extension:")

# Expand automatically when the active page is an analysis page
with st.sidebar.expander("Analysis", expanded=page.title in _ANALYSIS_TITLES):
    st.page_link("pages/leaderboard.py",       label="Leaderboard",       icon=":material/leaderboard:")
    st.page_link("pages/factors_influence.py", label="Factors Influence", icon=":material/insights:")
    st.page_link("pages/factorial_heatmap.py", label="Factorial Heatmap", icon=":material/grid_view:")

page.run()
