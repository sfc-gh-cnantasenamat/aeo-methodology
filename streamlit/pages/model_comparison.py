"""Page — Model Comparison: baseline score across respondent models."""
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from utils.db import run_query

st.title(":material/compare: Model Comparison")
st.caption(
    "Baseline configuration (all factors OFF) scores across respondent models. "
    "Lower scores indicate where a model's parametric knowledge is weakest "
    "before any augmentation."
)

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
df = run_query("SELECT * FROM V_AEO_MODEL_COMPARISON")

if df.empty:
    st.info(
        "No model comparison data yet. Run `scripts/run_model_comparison.py` "
        "to execute baseline runs for additional models."
    )
    st.stop()

MODELS = sorted(df["MODEL"].unique())
COLORS = px.colors.qualitative.Set2[: len(MODELS)]
MODEL_COLOR = dict(zip(MODELS, COLORS))

# ---------------------------------------------------------------------------
# Overall KPIs per model
# ---------------------------------------------------------------------------
overall = (
    df.groupby("MODEL")
    .agg(SCORE_PCT=("SCORE_PCT", "mean"), MH_PCT=("MH_PCT", "mean"))
    .round(1)
    .reset_index()
    .sort_values("SCORE_PCT", ascending=False)
)

st.subheader("Overall Baseline Score by Model")
cols = st.columns(len(overall))
for col, (_, row) in zip(cols, overall.iterrows()):
    col.metric(row["MODEL"], f"{row['SCORE_PCT']:.1f}%", f"MH: {row['MH_PCT']:.1f}%")

st.divider()

# ---------------------------------------------------------------------------
# Question-type breakdown grouped bar chart
# ---------------------------------------------------------------------------
st.subheader(":material/bar_chart: Score by Question Type")

qt = (
    df.groupby(["MODEL", "QUESTION_TYPE"])
    .agg(SCORE_PCT=("SCORE_PCT", "mean"))
    .round(1)
    .reset_index()
)

fig_qt = go.Figure()
for model in MODELS:
    sub = qt[qt["MODEL"] == model].sort_values("QUESTION_TYPE")
    fig_qt.add_trace(
        go.Bar(
            name=model,
            x=sub["QUESTION_TYPE"],
            y=sub["SCORE_PCT"],
            marker_color=MODEL_COLOR[model],
        )
    )
fig_qt.update_layout(
    barmode="group",
    xaxis=dict(title="Question Type", color="#cccccc", gridcolor="#333333"),
    yaxis=dict(title="Score %", range=[0, 100], color="#cccccc", gridcolor="#333333"),
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    legend=dict(orientation="h", y=-0.18),
    height=400,
    margin=dict(t=20, b=60),
)
st.plotly_chart(fig_qt, use_container_width=True)

st.divider()

# ---------------------------------------------------------------------------
# Per-category comparison heatmap (pivot: category vs model)
# ---------------------------------------------------------------------------
st.subheader(":material/grid_view: Per-Category Score by Model")

cat = (
    df.groupby(["CATEGORY", "MODEL"])
    .agg(SCORE_PCT=("SCORE_PCT", "mean"))
    .round(1)
    .reset_index()
)
pivot = cat.pivot(index="CATEGORY", columns="MODEL", values="SCORE_PCT").reset_index()
pivot = pivot.sort_values(MODELS[0] if MODELS else pivot.columns[1])

model_cols = [c for c in pivot.columns if c != "CATEGORY"]

fig_heat = go.Figure(
    go.Heatmap(
        z=pivot[model_cols].values,
        x=model_cols,
        y=pivot["CATEGORY"],
        colorscale="RdYlGn",
        zmin=30,
        zmax=100,
        text=pivot[model_cols].values,
        texttemplate="%{text:.0f}%",
        textfont=dict(size=10),
        hovertemplate="Category: %{y}<br>Model: %{x}<br>Score: %{z:.1f}%<extra></extra>",
    )
)
fig_heat.update_layout(
    xaxis=dict(side="top", tickfont=dict(color="#cccccc")),
    yaxis=dict(tickfont=dict(color="#cccccc", size=10), autorange="reversed"),
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    height=max(500, len(pivot) * 22),
    margin=dict(t=60, b=20, l=260, r=20),
)
st.plotly_chart(fig_heat, use_container_width=True)

st.divider()

# ---------------------------------------------------------------------------
# Dimension breakdown radar: one trace per model
# ---------------------------------------------------------------------------
st.subheader(":material/radar: Scoring Dimensions by Model")

DIMS = ["Correctness", "Completeness", "Recency", "Citation", "Recommendation"]
DIM_COLS = [
    "CORRECTNESS_PCT", "COMPLETENESS_PCT", "RECENCY_PCT",
    "CITATION_PCT", "RECOMMENDATION_PCT",
]

dim_agg = (
    df.groupby("MODEL")[DIM_COLS]
    .mean()
    .round(1)
    .reset_index()
)

fig_radar = go.Figure()
for _, row in dim_agg.iterrows():
    vals = [row[c] for c in DIM_COLS]
    fig_radar.add_trace(
        go.Scatterpolar(
            r=vals + [vals[0]],
            theta=DIMS + [DIMS[0]],
            fill="toself",
            name=row["MODEL"],
            line=dict(color=MODEL_COLOR.get(row["MODEL"])),
            opacity=0.7,
        )
    )
fig_radar.update_layout(
    polar=dict(
        bgcolor="rgba(30,30,30,0.6)",
        radialaxis=dict(range=[0, 100], gridcolor="#555555",
                        tickfont=dict(color="#cccccc")),
        angularaxis=dict(gridcolor="#555555", tickfont=dict(color="#cccccc")),
    ),
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    height=420,
    legend=dict(orientation="h", y=-0.12),
    margin=dict(t=20),
)
st.plotly_chart(fig_radar, use_container_width=True)

st.divider()

# ---------------------------------------------------------------------------
# Raw comparison table
# ---------------------------------------------------------------------------
st.subheader(":material/table: Full Category x Model Table")

display = pivot.copy()
display.columns.name = None
st.dataframe(display, use_container_width=True, hide_index=True)

st.divider()

# ---------------------------------------------------------------------------
# Cortex Code (cortex_cli) vs CORTEX.COMPLETE — agentic lift per model
# (runs 22-24: cortex_cli  vs  runs 18, 20, 21: cortex_complete)
# ---------------------------------------------------------------------------
st.subheader(":material/bolt: Cortex Code vs CORTEX.COMPLETE — Agentic Lift")
st.caption(
    "Baseline conditions (no domain prompt, citation, or self-critique). "
    "cortex_complete = single SNOWFLAKE.CORTEX.COMPLETE call. "
    "cortex_cli = native Cortex Code session with tool access."
)

cli_df = run_query("""
    SELECT r.MODEL,
           r.AGENTIC,
           ROUND(AVG(s.TOTAL_SCORE) / 50.0 * 100, 1) AS SCORE_PCT,
           ROUND(AVG(s.MUST_HAVE_PASS) * 100, 1)      AS MH_PCT
    FROM AEO_RUNS r
    JOIN AEO_SCORES s ON r.RUN_ID = s.RUN_ID
    WHERE r.RUN_ID IN (18, 20, 21, 22, 23, 24)
    GROUP BY r.MODEL, r.AGENTIC
    ORDER BY r.MODEL, r.AGENTIC
""")

if not cli_df.empty:
    cli_df["Mode"] = cli_df["AGENTIC"].map({True: "cortex_cli", False: "cortex_complete"})

    # Models that have both modes
    paired_models = (
        cli_df.groupby("MODEL")["Mode"].nunique()
        .where(lambda x: x == 2).dropna().index.tolist()
    )
    paired = cli_df[cli_df["MODEL"].isin(paired_models)].copy()

    COLORS_MODE = {"cortex_complete": "#fd3db5", "cortex_cli": "#22d3ee"}

    col_bar, col_lift = st.columns([2, 1])

    with col_bar:
        fig_cli = go.Figure()
        for mode in ["cortex_complete", "cortex_cli"]:
            sub = paired[paired["Mode"] == mode].sort_values("MODEL")
            fig_cli.add_trace(go.Bar(
                name=mode,
                x=sub["MODEL"],
                y=sub["SCORE_PCT"],
                marker_color=COLORS_MODE[mode],
                text=sub["SCORE_PCT"].map(lambda v: f"{v:.1f}%"),
                textposition="outside",
            ))
        fig_cli.update_layout(
            barmode="group",
            xaxis=dict(title="Model", color="#cccccc", gridcolor="#333333"),
            yaxis=dict(title="Score %", range=[0, 80], color="#cccccc", gridcolor="#333333"),
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            legend=dict(orientation="h", y=-0.18),
            height=400,
            margin=dict(t=30, b=60),
        )
        st.plotly_chart(fig_cli, use_container_width=True)

    with col_lift:
        st.subheader(":material/lightbulb: Agentic Lift")
        pivot_modes = paired.pivot(index="MODEL", columns="Mode", values="SCORE_PCT").reset_index()
        if "cortex_complete" in pivot_modes.columns and "cortex_cli" in pivot_modes.columns:
            pivot_modes["Lift (pp)"] = (
                pivot_modes["cortex_cli"] - pivot_modes["cortex_complete"]
            ).round(1)
            for _, row in pivot_modes.iterrows():
                lift = row["Lift (pp)"]
                color = "#15803d" if lift >= 0 else "#9d174d"
                st.markdown(
                    f'<p><strong>{row["MODEL"]}</strong>: '
                    f'<span style="background:{color};color:#fff;padding:1px 7px;'
                    f'border-radius:9999px;font-size:0.85em;font-weight:600;">'
                    f'{lift:+.1f}pp</span> '
                    f'({row["cortex_complete"]:.1f}% → {row["cortex_cli"]:.1f}%)</p>',
                    unsafe_allow_html=True,
                )

    # Summary table
    st.subheader(":material/table: Mode Comparison Table")
    summary = paired.pivot(index="MODEL", columns="Mode", values=["SCORE_PCT", "MH_PCT"])
    summary.columns = [f"{m} {c.replace('_PCT', '%')}" for c, m in summary.columns]
    summary = summary.reset_index()
    summary.columns.name = None
    st.dataframe(summary, use_container_width=True, hide_index=True)
