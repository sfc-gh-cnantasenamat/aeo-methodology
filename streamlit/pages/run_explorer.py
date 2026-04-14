"""Page 5 — Questions Explorer: drilldown by run, category, and question type."""
import streamlit as st
import plotly.graph_objects as go
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from utils.db import run_query, config_label

st.title(":material/manage_search: Questions Explorer")
st.caption("Drill into per-question scores for any combination of run, category, and question type.")

# --- Load data ---
df = run_query("""
    SELECT q.QUESTION_ID, q.QUESTION_TEXT, q.CATEGORY, q.QUESTION_TYPE,
           h.RUN_ID, h.DOMAIN_PROMPT, h.CITATION, h.AGENTIC, h.SELF_CRITIQUE,
           h.TOTAL_SCORE, h.MUST_HAVE_PASS,
           h.CORRECTNESS, h.COMPLETENESS, h.RECENCY, h.CITATION_SCORE, h.RECOMMENDATION
    FROM V_AEO_PER_QUESTION_HEATMAP h
    JOIN AEO_QUESTIONS q ON h.QUESTION_ID = q.QUESTION_ID
    ORDER BY h.RUN_ID, q.QUESTION_ID
""")

df["Config"] = df.apply(
    lambda r: config_label(r.DOMAIN_PROMPT, r.CITATION, r.AGENTIC, r.SELF_CRITIQUE), axis=1
)
df["Score %"] = (df["TOTAL_SCORE"] / 50.0 * 100).round(1)

# --- Sidebar filters ---
with st.sidebar:
    st.header("Filters")
    all_configs = sorted(df["Config"].unique())
    sel_configs = st.multiselect("Configuration", all_configs, default=["C+A", "Baseline"])

    all_cats = sorted(df["CATEGORY"].unique())
    sel_cats = st.multiselect("Category", all_cats, default=all_cats)

    all_types = sorted(df["QUESTION_TYPE"].unique())
    sel_types = st.multiselect("Question Type", all_types, default=all_types)

mask = (
    df["Config"].isin(sel_configs) &
    df["CATEGORY"].isin(sel_cats) &
    df["QUESTION_TYPE"].isin(sel_types)
)
filtered = df[mask].copy()

if filtered.empty:
    st.warning("No data matches the current filters.")
    st.stop()

# --- Per-question table ---
st.subheader("Question-level results")
DIMS = ["CORRECTNESS", "COMPLETENESS", "RECENCY", "CITATION_SCORE", "RECOMMENDATION"]

show = filtered[
    ["QUESTION_ID", "QUESTION_TEXT", "CATEGORY", "QUESTION_TYPE",
     "Config", "Score %", "MUST_HAVE_PASS"] + DIMS
].rename(columns={
    "QUESTION_ID":   "Q#",
    "QUESTION_TEXT": "Question",
    "CATEGORY":      "Category",
    "QUESTION_TYPE": "Type",
    "MUST_HAVE_PASS":"MH Pass",
    "CORRECTNESS":   "Correctness",
    "COMPLETENESS":  "Completeness",
    "RECENCY":       "Recency",
    "CITATION_SCORE":"Citation",
    "RECOMMENDATION":"Recommendation",
}).copy()

show["MH Pass"] = show["MH Pass"].apply(lambda x: "Pass" if x == 1 else "Fail")

st.dataframe(
    show,
    column_config={
        "Category": st.column_config.TextColumn("Category"),
        "Config": st.column_config.TextColumn("Config"),
        "Type": st.column_config.TextColumn("Type"),
        "MH Pass": st.column_config.TextColumn("MH Pass"),
        "Score %": st.column_config.ProgressColumn(
            "Score %",
            format="%.1f%%",
            min_value=0,
            max_value=100,
            color="auto",
        ),
        "Correctness": st.column_config.ProgressColumn(
            "Correctness", format="%.1f", min_value=0, max_value=10,
        ),
        "Completeness": st.column_config.ProgressColumn(
            "Completeness", format="%.1f", min_value=0, max_value=10,
        ),
        "Recency": st.column_config.ProgressColumn(
            "Recency", format="%.1f", min_value=0, max_value=10,
        ),
        "Citation": st.column_config.ProgressColumn(
            "Citation", format="%.1f", min_value=0, max_value=10,
        ),
        "Recommendation": st.column_config.ProgressColumn(
            "Recommendation", format="%.1f", min_value=0, max_value=10,
        ),
    },
    use_container_width=True,
    height=500,
)

# --- Dimension radar for a selected question ---
st.divider()
st.subheader("Dimension breakdown")
q_options = sorted(filtered["QUESTION_ID"].unique())
sel_q = st.selectbox("Select a question to inspect", q_options)

q_df = filtered[filtered["QUESTION_ID"] == sel_q]
if not q_df.empty:
    q_text = q_df.iloc[0]["QUESTION_TEXT"]
    st.markdown(f"**{sel_q}**: {q_text}")

    fig2 = go.Figure()
    dims = ["Correctness", "Completeness", "Recency", "Citation", "Recommendation"]
    dim_cols = ["CORRECTNESS", "COMPLETENESS", "RECENCY", "CITATION_SCORE", "RECOMMENDATION"]
    for _, row in q_df.iterrows():
        vals = [row[c] for c in dim_cols]
        fig2.add_trace(go.Scatterpolar(
            r=vals + [vals[0]],
            theta=dims + [dims[0]],
            fill="toself",
            name=row["Config"],
            opacity=0.7,
        ))
    fig2.update_layout(
        polar=dict(
            bgcolor="rgba(30,30,30,0.6)",
            radialaxis=dict(
                range=[0, 10],
                gridcolor="#555555",
                linecolor="#555555",
                tickfont=dict(color="#cccccc"),
            ),
            angularaxis=dict(
                gridcolor="#555555",
                linecolor="#555555",
                tickfont=dict(color="#cccccc"),
            ),
        ),
        title=f"Dimension scores — {sel_q}",
        height=420,
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )

    col_radar, col_text = st.columns([2, 1])

    with col_radar:
        st.plotly_chart(fig2, use_container_width=True)

    with col_text:
        st.subheader(":material/lightbulb: Key Insights")

        def badge(val, positive):
            bg = "#15803d" if positive else "#9d174d"
            return (
                f'<span style="background:{bg};color:#ffffff;padding:1px 7px;'
                f'border-radius:9999px;font-size:0.85em;font-weight:600;">{val}</span>'
            )

        q_category = q_df.iloc[0]["CATEGORY"]
        q_type     = q_df.iloc[0]["QUESTION_TYPE"]
        n_configs  = len(q_df)

        best_row  = q_df.loc[q_df["Score %"].idxmax()]
        worst_row = q_df.loc[q_df["Score %"].idxmin()]
        score_gap = best_row["Score %"] - worst_row["Score %"]

        dim_means = q_df[dim_cols].mean()
        best_dim  = dims[dim_means.argmax()]
        worst_dim = dims[dim_means.argmin()]

        # Per-config score summary sorted descending
        ranked = q_df.sort_values("Score %", ascending=False)
        score_parts = []
        for _, row in ranked.iterrows():
            cfg = row["Config"]
            sc  = row["Score %"]
            score_parts.append(f"<strong>{cfg}</strong>: {badge(f'{sc:.1f}%', sc >= 60)}")
        scores_html = " &nbsp;|&nbsp; ".join(score_parts)

        best_score_badge  = badge(f"{best_row['Score %']:.1f}%", True)
        worst_score_badge = badge(f"{worst_row['Score %']:.1f}%", False)
        gap_badge         = badge(f"+{score_gap:.1f}pp", True)
        best_config       = best_row['Config']
        worst_config      = worst_row['Config']
        best_score_only   = badge(f"{best_row['Score %']:.1f}%", True)

        if n_configs > 1:
            comparison = (
                f"<p><strong>{best_config} performs best</strong> on this question "
                f"with a score of {best_score_badge}, compared to "
                f"{worst_score_badge} for {worst_config}, "
                f"a gap of {gap_badge}.</p>"
            )
        else:
            comparison = (
                f"<p>Only one configuration is selected. "
                f"<strong>{best_config}</strong> scores "
                f"{best_score_only} on this question.</p>"
            )

        st.markdown(
            f"""
            <p>A <strong>{q_type}</strong> question in
            <strong>{q_category}</strong>.</p>

            <p>{scores_html}</p>

            {comparison}

            <p><strong>{best_dim} is the strongest dimension</strong> on average
            across the selected configurations for this question.</p>

            <p><strong>{worst_dim} is the weakest dimension,</strong> suggesting
            this question challenges the model on that criterion regardless of
            configuration.</p>
            """,
            unsafe_allow_html=True,
        )
