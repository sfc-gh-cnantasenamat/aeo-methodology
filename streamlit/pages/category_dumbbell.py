"""Page 3 — Category Performance: per-category Baseline vs C+A dumbbell chart."""
import streamlit as st
import plotly.graph_objects as go
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from utils.db import run_query, config_label

st.title(":material/category: Category Performance")
st.caption("Per-category improvement from Baseline (all OFF) to the best configuration (C+A).")

df = run_query("""
    SELECT CATEGORY,
           AVG(CASE WHEN NOT DOMAIN_PROMPT AND NOT CITATION AND NOT AGENTIC AND NOT SELF_CRITIQUE
                    THEN TOTAL_SCORE / 50.0 * 100 END) AS BASELINE_PCT,
           AVG(CASE WHEN NOT DOMAIN_PROMPT AND CITATION AND AGENTIC AND NOT SELF_CRITIQUE
                    THEN TOTAL_SCORE / 50.0 * 100 END) AS BEST_PCT
    FROM V_AEO_PER_QUESTION_HEATMAP
    GROUP BY CATEGORY
    ORDER BY CATEGORY
""")

df["DELTA"] = df["BEST_PCT"] - df["BASELINE_PCT"]
df = df.sort_values("DELTA", ascending=True).reset_index(drop=True)

# --- Dumbbell chart ---
fig = go.Figure()

# Connecting line
for _, row in df.iterrows():
    fig.add_trace(go.Scatter(
        x=[row["BASELINE_PCT"], row["BEST_PCT"]],
        y=[row["CATEGORY"], row["CATEGORY"]],
        mode="lines",
        line=dict(color="#D1D5DB", width=5),
        showlegend=False,
    ))

# Baseline dots
fig.add_trace(go.Scatter(
    x=df["BASELINE_PCT"], y=df["CATEGORY"],
    mode="markers+text",
    name="Baseline",
    marker=dict(color="#fd3db5", size=10),
    text=df["BASELINE_PCT"].map(lambda v: f"{v:.1f}"),
    textposition="middle left",
    textfont=dict(size=9, color="#ffffff"),
))
# C+A dots
fig.add_trace(go.Scatter(
    x=df["BEST_PCT"], y=df["CATEGORY"],
    mode="markers+text",
    name="C+A (Best)",
    marker=dict(color="#22d3ee", size=10),
    text=df["DELTA"].map(lambda d: f"+{d:.1f}pp"),
    textposition="middle right",
    textfont=dict(size=9, color="#ffffff"),
))

fig.update_layout(
    xaxis_title="Score %",
    xaxis_range=[15, 110],
    yaxis=dict(autorange=True),
    height=900,
    template="plotly_white",
    legend=dict(orientation="h", y=-0.05, x=0.5, xanchor="center"),
    margin=dict(l=220, t=20, b=50),
)
for v in [40, 60, 80, 100]:
    fig.add_vline(x=v, line_color="#E5E7EB", line_width=0.8)

top        = df.iloc[-1]
bot        = df.iloc[0]
avg_delta  = df["DELTA"].mean()
lowest_best = df.nsmallest(1, "BEST_PCT").iloc[0]

col_plot, col_text = st.columns([7, 3])

with col_plot:
    st.plotly_chart(fig, use_container_width=True)

with col_text:
    st.subheader(":material/lightbulb: Key Insights")

    def badge(val, positive):
        bg = "#15803d" if positive else "#9d174d"
        return (
            f'<span style="background:{bg};color:#ffffff;padding:1px 7px;'
            f'border-radius:9999px;font-size:0.85em;font-weight:600;">{val}</span>'
        )

    st.markdown(
        f"""
        <p><strong>All categories improve.</strong> Every category scores higher
        with Citation and Agentic tools enabled, with gains ranging from
        {badge(f"+{bot['DELTA']:.1f}pp", True)} to
        {badge(f"+{top['DELTA']:.1f}pp", True)}.</p>

        <p><strong>{top['CATEGORY']} benefits most.</strong> Starting from a low
        baseline, it gains {badge(f"+{top['DELTA']:.1f}pp", True)}, likely because
        agentic tools retrieve highly specific documentation the model cannot recall
        from training alone.</p>

        <p><strong>{lowest_best['CATEGORY']} remains the hardest category.</strong>
        It starts with the lowest baseline at
        {badge(f"{lowest_best['BASELINE_PCT']:.1f}%", False)} and, even after the
        best model lifts it by {badge(f"+{lowest_best['DELTA']:.1f}pp", True)},
        it still finishes at {badge(f"{lowest_best['BEST_PCT']:.1f}%", False)},
        the lowest score of all categories.</p>

        <p><strong>The average gain across all categories is
        {badge(f"+{avg_delta:.1f}pp", True)}.</strong> The C+A configuration
        delivers meaningful gains across the full breadth of Snowflake
        developer topics.</p>
        """,
        unsafe_allow_html=True,
    )

# ===========================================================================
# Priority Matrix
# ===========================================================================
st.divider()
st.header(":material/priority_high: Priority Matrix")
st.caption("Identify which categories offer the highest improvement potential.")

# --- Load per-question data ---
pq = run_query("""
    SELECT q.QUESTION_ID, q.CATEGORY,
           h.DOMAIN_PROMPT, h.CITATION, h.AGENTIC, h.SELF_CRITIQUE,
           h.TOTAL_SCORE, h.MUST_HAVE_PASS
    FROM V_AEO_PER_QUESTION_HEATMAP h
    JOIN AEO_QUESTIONS q ON h.QUESTION_ID = q.QUESTION_ID
""")
pq["Score %"] = (pq["TOTAL_SCORE"] / 50.0 * 100).round(1)

# --- Category stats ---
cat_stats = (
    pq.groupby("CATEGORY")
    .agg(
        mean_score =("Score %", "mean"),
        best_score =("Score %", "max"),
        n_questions=("QUESTION_ID", "nunique"),
    )
    .reset_index()
)
cat_stats["gap"]       = (100 - cat_stats["best_score"]).round(1)
cat_stats["mean_score"] = cat_stats["mean_score"].round(1)
cat_stats["best_score"] = cat_stats["best_score"].round(1)
cat_stats["potential"]  = (
    (cat_stats["best_score"] - cat_stats["mean_score"]) * cat_stats["n_questions"]
).round(1)

overall_mean = cat_stats["mean_score"].mean()
median_gap   = cat_stats["gap"].median()

# --- Bubble chart ---
st.caption(
    "x = current avg score  |  y = gap to best achievable score  |  "
    "bubble size = number of questions"
)
col_bub, col_bub_text = st.columns([7, 3])

with col_bub:
    fig2 = go.Figure()
    for _, row in cat_stats.iterrows():
        fig2.add_trace(go.Scatter(
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
    fig2.add_vline(x=overall_mean, line_dash="dash", line_color="#555555",
                   annotation_text="Avg", annotation_font_color="#888888")
    fig2.add_hline(y=median_gap,   line_dash="dash", line_color="#555555",
                   annotation_text="Median gap", annotation_font_color="#888888")
    fig2.update_layout(
        xaxis=dict(title="Avg Score %", gridcolor="#333333", color="#cccccc"),
        yaxis=dict(title="Gap to best score (pp)", gridcolor="#333333", color="#cccccc"),
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=500,
        margin=dict(t=20),
    )
    st.plotly_chart(fig2, use_container_width=True)

with col_bub_text:
    st.subheader(":material/lightbulb: Key Insights")

    priority_cat = cat_stats.sort_values("potential", ascending=False).iloc[0]
    hardest_cat  = cat_stats.sort_values("mean_score").iloc[0]

    st.markdown(
        f"""
        <p>Top-right quadrant (high score, large gap) are quick wins: the model
        already performs well but the best configs still leave headroom. These
        categories respond best to prompt tuning.</p>

        <p>Bottom-left (low score, small gap) are hard ceilings. Even the best
        config barely improves on the average. These likely require training
        data improvements.</p>

        <p>{badge(priority_cat['CATEGORY'], True)} has the highest total improvement
        potential, meaning the gap between average and best performance is large
        across many questions.</p>

        <p>{badge(hardest_cat['CATEGORY'], False)} is the hardest category
        overall with a mean score of
        {badge(f"{hardest_cat['mean_score']:.1f}%", False)}.</p>
        """,
        unsafe_allow_html=True,
    )

# --- Impact table ---
st.subheader("Category impact table")
show_impact = (
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
    show_impact[["Category", "Avg Score %", "Best Score %", "Gap to Best (pp)",
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
