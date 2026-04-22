"""Experimental — Investment Prioritizer: what should we fix next?"""
import streamlit as st
import plotly.graph_objects as go
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from utils.db import run_query, config_label

st.title(":material/priority_high: Investment Prioritizer")
st.caption("Identify which categories offer the highest improvement potential.")

# --- Load ---
df = run_query("""
    SELECT q.QUESTION_ID, q.CATEGORY,
           h.DOMAIN_PROMPT, h.CITATION, h.AGENTIC, h.SELF_CRITIQUE,
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
    engine_filter = st.radio("Engine", ["All", "Agentic only", "Non-Agentic only"])

if engine_filter == "Agentic only":
    df = df[df["AGENTIC"] == True]
elif engine_filter == "Non-Agentic only":
    df = df[df["AGENTIC"] == False]

# --- Category stats ---
cat_stats = (
    df.groupby("CATEGORY")
    .agg(
        mean_score =("Score %", "mean"),
        best_score =("Score %", "max"),
        n_questions=("QUESTION_ID", "nunique"),
    )
    .reset_index()
)
cat_stats["gap"]    = (100 - cat_stats["best_score"]).round(1)
cat_stats["mean_score"] = cat_stats["mean_score"].round(1)
cat_stats["best_score"] = cat_stats["best_score"].round(1)
# Improvement potential: how much score could be gained if mean reached best
cat_stats["potential"] = (
    (cat_stats["best_score"] - cat_stats["mean_score"]) * cat_stats["n_questions"]
).round(1)

overall_mean   = cat_stats["mean_score"].mean()
median_gap     = cat_stats["gap"].median()

# --- Priority bubble chart ---
st.subheader("Priority matrix")
st.caption(
    "x = current avg score  |  y = gap to best achievable score  |  "
    "bubble size = number of questions"
)
col_bub, col_text = st.columns([7, 3])

with col_bub:
    fig = go.Figure()
    for _, row in cat_stats.iterrows():
        fig.add_trace(go.Scatter(
            x=[row["mean_score"]],
            y=[row["gap"]],
            mode="markers+text",
            marker=dict(
                size=max(row["n_questions"] * 3, 12),
                opacity=0.8,
                color="#22d3ee",
                line=dict(color="#ffffff", width=1),
            ),
            text=[row["CATEGORY"]],
            textposition="top center",
            textfont=dict(color="#ffffff", size=10),
            name=row["CATEGORY"],
            showlegend=False,
            hovertemplate=(
                f"<b>{row['CATEGORY']}</b><br>"
                f"Avg: {row['mean_score']:.1f}%<br>"
                f"Best: {row['best_score']:.1f}%<br>"
                f"Gap: {row['gap']:.1f}pp<br>"
                f"Questions: {row['n_questions']}<extra></extra>"
            ),
        ))
    fig.add_vline(x=overall_mean, line_dash="dash", line_color="#555555",
                  annotation_text="Avg", annotation_font_color="#888888")
    fig.add_hline(y=median_gap,   line_dash="dash", line_color="#555555",
                  annotation_text="Median gap", annotation_font_color="#888888")
    fig.update_layout(
        xaxis=dict(title="Avg Score %", gridcolor="#333333", color="#cccccc"),
        yaxis=dict(title="Gap to best score (pp)", gridcolor="#333333", color="#cccccc"),
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=500,
        margin=dict(t=20),
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

    priority_cat = cat_stats.sort_values("potential", ascending=False).iloc[0]
    hardest_cat  = cat_stats.sort_values("mean_score").iloc[0]

    st.markdown(
        f"""
        <p>Top-right quadrant (high score, large gap) are quick wins: the model
        already performs well but the best configs still leave headroom. These
        categories respond best to prompt tuning.</p>

        <p>Bottom-left (low score, small gap) are hard ceilings — even the best
        config barely improves on the average. These likely require training
        data improvements.</p>

        <p>{badge(priority_cat['CATEGORY'])} has the highest total improvement
        potential, meaning the gap between average and best performance is large
        across many questions.</p>

        <p>{badge(hardest_cat['CATEGORY'], False)} is the hardest category
        overall with a mean score of
        {badge(f"{hardest_cat['mean_score']:.1f}%", False)}.</p>
        """,
        unsafe_allow_html=True,
    )

st.divider()

# --- Impact table ---
st.subheader("Category impact table")
show = (
    cat_stats
    .sort_values("potential", ascending=False)
    .rename(columns={
        "CATEGORY":   "Category",
        "mean_score": "Avg Score %",
        "best_score": "Best Score %",
        "n_questions":"Questions",
        "gap":        "Gap to Best (pp)",
        "potential":  "Improvement Potential",
    })
)
st.dataframe(
    show[["Category", "Avg Score %", "Best Score %", "Gap to Best (pp)",
          "Questions", "Improvement Potential"]],
    use_container_width=True,
    hide_index=True,
    column_config={
        "Avg Score %":  st.column_config.ProgressColumn(
            "Avg Score %",  format="%.1f%%", min_value=0, max_value=100),
        "Best Score %": st.column_config.ProgressColumn(
            "Best Score %", format="%.1f%%", min_value=0, max_value=100),
    },
)
