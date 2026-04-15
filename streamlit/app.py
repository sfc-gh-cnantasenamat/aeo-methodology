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

pages = st.navigation(
    [
        st.Page("pages/home.py",              title="Home",                  icon=":material/home:"),
        st.Page("pages/leaderboard.py",       title="Leaderboard",          icon=":material/leaderboard:"),
        st.Page("pages/main_effects.py",       title="Main Effects",          icon=":material/insights:"),
        st.Page("pages/category_dumbbell.py",  title="Category Performance",  icon=":material/category:"),
        st.Page("pages/factorial_heatmap.py",  title="Factorial Heatmap",     icon=":material/grid_view:"),
        st.Page("pages/run_explorer.py",       title="Questions Explorer",    icon=":material/manage_search:"),
    ],
    position="top",
)

pages.run()
