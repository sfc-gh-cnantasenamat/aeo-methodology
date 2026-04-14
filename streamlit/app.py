"""AEO Benchmark Dashboard — entry point."""
import streamlit as st

st.set_page_config(
    page_title="AEO Benchmark Dashboard",
    layout="wide",
    initial_sidebar_state="expanded",
)

pages = st.navigation(
    {
        "": [
            st.Page("pages/leaderboard.py",       title="Leaderboard",          icon=":material/leaderboard:"),
            st.Page("pages/main_effects.py",       title="Main Effects",          icon=":material/insights:"),
            st.Page("pages/category_dumbbell.py",  title="Category Performance",  icon=":material/category:"),
            st.Page("pages/factorial_heatmap.py",  title="Factorial Heatmap",     icon=":material/grid_view:"),
            st.Page("pages/run_explorer.py",       title="Questions Explorer",    icon=":material/manage_search:"),
        ],
        "Experimental": [
            st.Page("pages/experimental/decision_matrix.py",      title="Decision Matrix",          icon=":material/table_chart:"),
            st.Page("pages/experimental/failure_atlas.py",         title="Failure Atlas",            icon=":material/warning:"),
            st.Page("pages/experimental/feature_roi.py",           title="Feature ROI",              icon=":material/show_chart:"),
            st.Page("pages/experimental/investment_prioritizer.py",title="Investment Prioritizer",   icon=":material/priority_high:"),
            st.Page("pages/experimental/what_if_explorer.py",      title="What-If Explorer",         icon=":material/science:"),
        ],
    },
    position="top",
)

pages.run()
