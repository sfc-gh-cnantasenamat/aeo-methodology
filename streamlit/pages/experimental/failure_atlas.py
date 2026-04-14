"""Experimental — Failure Atlas: where does the model fail?"""
import streamlit as st
import plotly.graph_objects as go
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from utils.db import run_query, config_label

st.title(":material/warning: Failure Atlas")
st.caption("Map systemic failures across categories and configurations to separate fixable from fundamental problems.")

# --- Load ---
df = run_query("""
    SELECT q.QUESTION_ID, q.QUESTION_TEXT, q.CATEGORY, q.QUESTION_TYPE,
           h.RUN_ID, h.DOMAIN_PROMPT, h.CITATION, h.AGENTIC, h.SELF_CRITIQUE,
           h.TOTAL_SCORE, h.MUST_HAVE_PASS
    FROM V_AEO_PER_QUESTION_HEATMAP h
    JOIN AEO_QUESTIONS q ON h.QUESTION_ID = q.QUESTION_ID
""")
df["Config"]  = df.apply(
    lambda r: config_label(r.DOMAIN_PROMPT, r.CITATION, r.AGENTIC, r.SELF_CRITIQUE), axis=1
)
df["Score %"] = (df["TOTAL_SCORE"] / 50.0 * 100).round(1)

# --- Sidebar ---
with st.sidebar:
    st.header("Filters")
    all_configs = sorted(df["Config"].unique())
    sel_configs = st.multiselect("Configurations", all_configs, default=all_configs)

filt = df[df["Config"].isin(sel_configs)]
if filt.empty:
    st.warning("No data for the selected configurations.")
    st.stop()

# --- Heatmap: category x config ---
st.subheader("Category x Config failure map")
pivot = filt.groupby(["CATEGORY", "Config"])["Score %"].mean().unstack(fill_value=0).round(1)

col_hm, col_text = st.columns([7, 3])

with col_hm:
    fig = go.Figure(go.Heatmap(
        z=pivot.values,
        x=pivot.columns.tolist(),
        y=pivot.index.tolist(),
        colorscale="RdYlGn",
        zmin=0, zmax=100,
        text=pivot.values.round(1),
        texttemplate="%{text}%",
        textfont=dict(size=10),
        colorbar=dict(
            title="Score %",
            orientation="h",
            x=0.5, xanchor="center",
            y=-0.18, thickness=12, len=0.5,
        ),
    ))
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=520,
        margin=dict(l=200, t=20, b=80),
        xaxis=dict(tickfont=dict(size=10), tickangle=45),
        yaxis=dict(tickfont=dict(size=10)),
    )
    st.plotly_chart(fig, use_container_width=True)

with col_text:
    st.subheader(":material/lightbulb: Key Insights")

    def badge(val, positive=True):
        bg = "#15803d" if positive else "#9d174d"
        return (
            f'<span style="background:{bg};color:#ffffff;padding:1px 7px;'
            f'border-radius:9999px;font-size:0.85em;font-weight:600;">{val}</span>'
        )

    cat_means = pivot.mean(axis=1).sort_values()
    worst_cat  = cat_means.index[0]
    best_cat   = cat_means.index[-1]
    worst_score_badge = badge(f"{cat_means.iloc[0]:.1f}%", False)
    best_score_badge  = badge(f"{cat_means.iloc[-1]:.1f}%", True)

    st.markdown(
        f"""
        <p>{badge(worst_cat, False)} has the lowest average score at
        {worst_score_badge} across all selected configs.</p>

        <p>{badge(best_cat)} performs best at {best_score_badge}.</p>

        <p>Red cells that stay red across all configs indicate fundamental
        knowledge gaps — these require training or data improvements, not
        prompt tuning.</p>

        <p>Cells that are red for some configs but green for others are
        configuration-sensitive failures, more likely addressable through
        prompt engineering.</p>
        """,
        unsafe_allow_html=True,
    )

st.divider()

# --- Fundamental vs Fixable classification ---
st.subheader("Fundamental vs Fixable failures")
st.caption("Fundamental: consistently low across all configs. Fixable: low on some configs but high on others.")

q_stats = (
    filt.groupby("QUESTION_ID")
    .agg(
        mean_score =("Score %", "mean"),
        std_score  =("Score %", "std"),
        max_score  =("Score %", "max"),
        QUESTION_TEXT=("QUESTION_TEXT", "first"),
        CATEGORY   =("CATEGORY", "first"),
    )
    .reset_index()
    .fillna(0)
)

q_stats["Failure Type"] = "Passing"
q_stats.loc[
    (q_stats["mean_score"] < 50) & (q_stats["std_score"] < 15),
    "Failure Type"
] = "Fundamental"
q_stats.loc[
    (q_stats["mean_score"] < 50) & (q_stats["std_score"] >= 15),
    "Failure Type"
] = "Fixable"

n_fund = int((q_stats["Failure Type"] == "Fundamental").sum())
n_fix  = int((q_stats["Failure Type"] == "Fixable").sum())
n_pass = int((q_stats["Failure Type"] == "Passing").sum())

c1, c2, c3 = st.columns(3)
c1.metric("Fundamental failures", n_fund)
c2.metric("Fixable failures",     n_fix)
c3.metric("Passing questions",    n_pass)

failing = (
    q_stats[q_stats["Failure Type"] != "Passing"]
    [["QUESTION_ID", "QUESTION_TEXT", "CATEGORY", "mean_score", "std_score", "max_score", "Failure Type"]]
    .sort_values("mean_score")
    .rename(columns={
        "QUESTION_ID":   "Q#",
        "QUESTION_TEXT": "Question",
        "CATEGORY":      "Category",
        "mean_score":    "Avg Score %",
        "std_score":     "Std Dev",
        "max_score":     "Best Score %",
        "Failure Type":  "Type",
    })
)

if failing.empty:
    st.info("No failing questions under the current configuration filter.")
else:
    st.dataframe(
        failing,
        use_container_width=True,
        height=400,
        hide_index=True,
        column_config={
            "Avg Score %":  st.column_config.ProgressColumn(
                "Avg Score %",  format="%.1f%%", min_value=0, max_value=100, color="auto"),
            "Best Score %": st.column_config.ProgressColumn(
                "Best Score %", format="%.1f%%", min_value=0, max_value=100, color="auto"),
        },
    )
