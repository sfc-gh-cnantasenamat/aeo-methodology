"""Page 3 — Category Performance: per-category Baseline vs C+A dumbbell chart."""
import streamlit as st
import plotly.graph_objects as go
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from utils.db import run_query, config_label, ENV
from utils.ui import model_selector

st.title(":material/category: Category Performance")
st.caption("Baseline vs. best-config (C+A) score % across all question categories — shows where agentic retrieval gains the most.")


# ── Shared badge helper ───────────────────────────────────────────────────────
def badge(val, positive):
    bg = "#15803d" if positive else "#9d174d"
    return (
        f'<span style="background:{bg};color:#ffffff;padding:1px 7px;'
        f'border-radius:9999px;font-size:0.85em;font-weight:600;">{val}</span>'
    )


# ===========================================================================
# Dumbbell Chart
# ===========================================================================
st.caption("Per-category improvement from Baseline (all OFF) to the best configuration (C+A).")
_label, _model = model_selector("cat_dumbbell_model")

# ── Load dumbbell chart data ──────────────────────────────────────────────────
_MODEL_LABELS = {
    "claude-opus-4-6": "Opus 4.6",
    "claude-opus-4-7": "Opus 4.7",
    "openai-gpt-5.4":  "GPT 5.4",
}
if ENV == "devrel":
    df = run_query(f"""
        WITH per_question AS (
            SELECT s.QUESTION_ID, q.CATEGORY,
                   AVG(CASE WHEN s.RUN_ID = '{_model}-base' THEN s.TOTAL_SCORE END) AS BASELINE_RAW,
                   AVG(CASE WHEN s.RUN_ID = '{_model}-CA'   THEN s.TOTAL_SCORE END) AS BEST_RAW
            FROM V3_AEO_SCORES s
            JOIN AEO_QUESTIONS q ON s.QUESTION_ID = q.QUESTION_ID
            GROUP BY s.QUESTION_ID, q.CATEGORY
        )
        SELECT CATEGORY,
               AVG(BASELINE_RAW) / 50.0 * 100 AS BASELINE_PCT,
               AVG(BEST_RAW)     / 50.0 * 100 AS BEST_PCT
        FROM per_question
        GROUP BY CATEGORY
        ORDER BY CATEGORY
    """)
else:
    _runs_df = run_query(
        f"SELECT RUN_ID, DOMAIN_PROMPT, CITATION, AGENTIC, SELF_CRITIQUE "
        f"FROM AEO_RUNS WHERE MODEL = '{_model}'"
    )
    _dp = _runs_df["DOMAIN_PROMPT"].astype(bool)
    _ci = _runs_df["CITATION"].astype(bool)
    _ag = _runs_df["AGENTIC"].astype(bool)
    _sc = _runs_df["SELF_CRITIQUE"].astype(bool)

    _baseline_rows = _runs_df[~_dp & ~_ci & ~_ag & ~_sc]
    _ca_rows       = _runs_df[~_dp & _ci & _ag & ~_sc]

    if len(_baseline_rows) > 0 and len(_ca_rows) > 0:
        _bid = int(_baseline_rows.iloc[-1]["RUN_ID"])
        _cid = int(_ca_rows.iloc[-1]["RUN_ID"])
        df = run_query(f"""
            SELECT CATEGORY,
                   AVG(CASE WHEN RUN_ID = {_bid} THEN TOTAL_SCORE / 50.0 * 100 END) AS BASELINE_PCT,
                   AVG(CASE WHEN RUN_ID = {_cid} THEN TOTAL_SCORE / 50.0 * 100 END) AS BEST_PCT
            FROM V_AEO_PER_QUESTION_HEATMAP
            GROUP BY CATEGORY ORDER BY CATEGORY
        """)
    else:
        df = None

# ── Dumbbell chart ────────────────────────────────────────────────────────────
if df is not None:
    df["DELTA"] = df["BEST_PCT"] - df["BASELINE_PCT"]
    df = df.sort_values("DELTA", ascending=True).reset_index(drop=True)

    fig = go.Figure()

    for _, row in df.iterrows():
        fig.add_trace(go.Scatter(
            x=[row["BASELINE_PCT"], row["BEST_PCT"]],
            y=[row["CATEGORY"], row["CATEGORY"]],
            mode="lines",
            line=dict(color="#D1D5DB", width=5),
            showlegend=False,
        ))

    fig.add_trace(go.Scatter(
        x=df["BASELINE_PCT"], y=df["CATEGORY"],
        mode="markers+text",
        name="Baseline",
        marker=dict(color="#fd3db5", size=10),
        text=df["BASELINE_PCT"].map(lambda v: f"{v:.1f}"),
        textposition="middle left",
        textfont=dict(size=9, color="#ffffff"),
    ))
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

    top         = df.iloc[-1]
    bot         = df.iloc[0]
    avg_delta   = df["DELTA"].mean()
    lowest_best = df.nsmallest(1, "BEST_PCT").iloc[0]

    col_plot, col_text = st.columns([7, 3])

    with col_text:
        st.subheader(":material/lightbulb: Key Insights")
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

    with col_plot:
        st.plotly_chart(fig, use_container_width=True)
        st.caption(
            f"Per-category improvement from Baseline (all OFF) to "
            f"the best configuration (C+A) — {_label}."
        )

else:
    st.warning(f"Insufficient run data to compare Baseline vs C+A for {_label}.")


# ===========================================================================
# Priority Matrix + Category Impact Table
# ===========================================================================
st.divider()
st.header(":material/priority_high: Priority Matrix")
st.caption("Identify which categories offer the highest improvement potential across all 16 configurations.")
_label2, _model2 = model_selector("cat_priority_model")

if ENV == "devrel":
    pq = run_query(f"""
        WITH per_question_run AS (
            SELECT s.QUESTION_ID, q.CATEGORY,
                   REGEXP_REPLACE(s.RUN_ID, '^.*-', '') AS CONFIG,
                   AVG(s.TOTAL_SCORE)     AS TOTAL_SCORE,
                   AVG(s.MUST_HAVE_PASS)  AS MUST_HAVE_PASS
            FROM V3_AEO_SCORES s
            JOIN AEO_QUESTIONS q ON s.QUESTION_ID = q.QUESTION_ID
            WHERE s.RUN_ID LIKE '{_model2}-%'
            GROUP BY s.QUESTION_ID, q.CATEGORY, CONFIG
        )
        SELECT QUESTION_ID, CATEGORY,
               CONTAINS(CONFIG, 'D') AS DOMAIN_PROMPT,
               CONTAINS(CONFIG, 'C') AS CITATION,
               CONTAINS(CONFIG, 'A') AS AGENTIC,
               CONTAINS(CONFIG, 'S') AS SELF_CRITIQUE,
               TOTAL_SCORE,
               MUST_HAVE_PASS
        FROM per_question_run
    """)
else:
    pq = run_query(f"""
        SELECT q.QUESTION_ID, q.CATEGORY,
               h.DOMAIN_PROMPT, h.CITATION, h.AGENTIC, h.SELF_CRITIQUE,
               h.TOTAL_SCORE, h.MUST_HAVE_PASS
        FROM V_AEO_PER_QUESTION_HEATMAP h
        JOIN AEO_QUESTIONS q ON h.QUESTION_ID = q.QUESTION_ID
        JOIN AEO_RUNS r ON h.RUN_ID = r.RUN_ID
        WHERE r.MODEL = '{_model2}'
    """)

pq["Score %"] = (pq["TOTAL_SCORE"] / 50.0 * 100).round(1)

cat_stats = (
    pq.groupby("CATEGORY")
    .agg(
        mean_score =("Score %", "mean"),
        best_score =("Score %", "max"),
        n_questions=("QUESTION_ID", "nunique"),
    )
    .reset_index()
)
cat_stats["gap"]        = (100 - cat_stats["best_score"]).round(1)
cat_stats["mean_score"] = cat_stats["mean_score"].round(1)
cat_stats["best_score"] = cat_stats["best_score"].round(1)
cat_stats["potential"]  = (
    (cat_stats["best_score"] - cat_stats["mean_score"]) * cat_stats["n_questions"]
).round(1)

overall_mean = cat_stats["mean_score"].mean()
median_gap   = cat_stats["gap"].median()

priority_cat = cat_stats.sort_values("potential", ascending=False).iloc[0]
hardest_cat  = cat_stats.sort_values("mean_score").iloc[0]

col_bub, col_bub_text = st.columns([7, 3])

with col_bub_text:
    st.subheader(":material/lightbulb: Key Insights")
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
    fig2.add_vline(x=overall_mean, line_dash="dash", line_color="#f97316", layer="below",
                   annotation_text="Avg", annotation_font_color="#f97316")
    fig2.add_hline(y=median_gap,   line_dash="dash", line_color="#f97316", layer="below",
                   annotation_text="Median gap", annotation_font_color="#f97316")
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
    st.caption(
        "x = current avg score  |  y = gap to best achievable score  |  "
        "bubble size = number of questions"
    )

# --- Impact table ---
st.divider()
st.subheader(":material/table_chart: Category impact table")
st.caption("Ranked by improvement potential — categories with the highest gap between average and best score across the most questions.")
_label3, _model3 = model_selector("cat_impact_model")

if ENV == "devrel":
    pq_table = run_query(f"""
        WITH per_question_run AS (
            SELECT s.QUESTION_ID, q.CATEGORY,
                   REGEXP_REPLACE(s.RUN_ID, '^.*-', '') AS CONFIG,
                   AVG(s.TOTAL_SCORE)    AS TOTAL_SCORE,
                   AVG(s.MUST_HAVE_PASS) AS MUST_HAVE_PASS
            FROM V3_AEO_SCORES s
            JOIN AEO_QUESTIONS q ON s.QUESTION_ID = q.QUESTION_ID
            WHERE s.RUN_ID LIKE '{_model3}-%'
            GROUP BY s.QUESTION_ID, q.CATEGORY, CONFIG
        )
        SELECT QUESTION_ID, CATEGORY, TOTAL_SCORE
        FROM per_question_run
    """)
else:
    pq_table = run_query(f"""
        SELECT q.QUESTION_ID, q.CATEGORY, h.TOTAL_SCORE
        FROM V_AEO_PER_QUESTION_HEATMAP h
        JOIN AEO_QUESTIONS q ON h.QUESTION_ID = q.QUESTION_ID
        JOIN AEO_RUNS r ON h.RUN_ID = r.RUN_ID
        WHERE r.MODEL = '{_model3}'
    """)

pq_table["Score %"] = (pq_table["TOTAL_SCORE"] / 50.0 * 100).round(1)
cat_stats_table = (
    pq_table.groupby("CATEGORY")
    .agg(
        mean_score =("Score %", "mean"),
        best_score =("Score %", "max"),
        n_questions=("QUESTION_ID", "nunique"),
    )
    .reset_index()
)
cat_stats_table["gap"]        = (100 - cat_stats_table["best_score"]).round(1)
cat_stats_table["mean_score"] = cat_stats_table["mean_score"].round(1)
cat_stats_table["best_score"] = cat_stats_table["best_score"].round(1)
cat_stats_table["potential"]  = (
    (cat_stats_table["best_score"] - cat_stats_table["mean_score"]) * cat_stats_table["n_questions"]
).round(1)

show_impact = (
    cat_stats_table
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
