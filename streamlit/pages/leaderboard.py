"""Page 1 — Leaderboard: 16-run rankings table."""
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from utils.db import run_query, config_label

st.title(":material/leaderboard: Leaderboard")
st.caption("All 16 factorial runs ranked by average score %, with must-have (MH) compliance.")
st.markdown(
    "<style>div[data-testid='stMetricDelta'] svg { display: none !important; }</style>",
    unsafe_allow_html=True,
)

df = run_query("SELECT * FROM V_AEO_LEADERBOARD ORDER BY SCORE_PCT DESC")

# Derive config label and agentic flag
df["Config"] = df.apply(
    lambda r: config_label(r.DOMAIN_PROMPT, r.CITATION, r.AGENTIC, r.SELF_CRITIQUE), axis=1
)
df["Engine"] = df["AGENTIC"].map({True: "Agentic", False: "Non-Agentic"})

# --- KPI metrics ---
best  = df.iloc[0]
worst = df.iloc[-1]
col1, col2, col3, col4, col5, col6 = st.columns(6)
col1.metric("Best Config",     best["Config"],  f"{best['SCORE_PCT']:.1f}%")
col2.metric("Worst Config",    worst["Config"], f"{worst['SCORE_PCT']:.1f}%", delta_color="off")
col3.metric("Avg Score %",     f"{df['SCORE_PCT'].mean():.1f}%")
col4.metric("Avg MH %",        f"{df['MH_PCT'].mean():.1f}%")
col5.metric("Agentic Avg",     f"{df[df['AGENTIC'] == True]['SCORE_PCT'].mean():.1f}%")
col6.metric("Non-Agentic Avg", f"{df[df['AGENTIC'] == False]['SCORE_PCT'].mean():.1f}%")

st.divider()

# --- Rankings table ---
display = df[["RUN_ID", "Config", "Engine", "SCORE_PCT", "MH_PCT",
              "TOTAL_SCORE", "QUESTIONS_SCORED"]].copy()
display.columns = ["Run", "Config", "Engine", "Score %", "MH %",
                   "Total Score", "Questions"]
display.index = range(1, len(display) + 1)
display.index.name = "Rank"

st.dataframe(
    display,
    column_config={
        "Config": st.column_config.TextColumn("Config"),
        "Engine": st.column_config.TextColumn("Engine"),
        "Score %": st.column_config.ProgressColumn(
            "Score %",
            format="%.1f%%",
            min_value=0,
            max_value=100,
        ),
        "MH %": st.column_config.ProgressColumn(
            "MH %",
            format="%.1f%%",
            min_value=0,
            max_value=100,
        ),
        "Total Score": st.column_config.ProgressColumn(
            "Total Score",
            format="%.0f",
            min_value=0,
            max_value=int(display["Total Score"].max()),
        ),
    },
    use_container_width=True,
    height=620,
)

# ===========================================================================
# Dimension Breakdown — Top 3 Configs
# ===========================================================================
st.divider()
st.header(":material/radar: Dimension Breakdown — Top 3 Configs")

# Load per-config dimension averages
pq = run_query("""
    SELECT RUN_ID, DOMAIN_PROMPT, CITATION, AGENTIC, SELF_CRITIQUE,
           AVG(CORRECTNESS)    AS AVG_CORRECTNESS,
           AVG(COMPLETENESS)   AS AVG_COMPLETENESS,
           AVG(RECENCY)        AS AVG_RECENCY,
           AVG(CITATION_SCORE) AS AVG_CITATION,
           AVG(RECOMMENDATION) AS AVG_RECOMMENDATION
    FROM V_AEO_PER_QUESTION_HEATMAP
    GROUP BY RUN_ID, DOMAIN_PROMPT, CITATION, AGENTIC, SELF_CRITIQUE
""")
pq["Config"] = pq.apply(
    lambda r: config_label(r.DOMAIN_PROMPT, r.CITATION, r.AGENTIC, r.SELF_CRITIQUE), axis=1
)
DIM_COLS = ["AVG_CORRECTNESS", "AVG_COMPLETENESS", "AVG_RECENCY", "AVG_CITATION", "AVG_RECOMMENDATION"]
df = df.merge(pq[["Config"] + DIM_COLS], on="Config", how="left")

DIMS = ["Correctness", "Completeness", "Recency", "Citation", "Recommendation"]
top3 = df.head(3)

def badge(val, positive=True):
    bg = "#15803d" if positive else "#9d174d"
    return (
        f'<span style="background:{bg};color:#ffffff;padding:1px 7px;'
        f'border-radius:9999px;font-size:0.85em;font-weight:600;">{val}</span>'
    )

col_radar, col_ri = st.columns([2, 1])

with col_radar:
    fig_radar = go.Figure()
    colors = ["#22d3ee", "#fd3db5", "#a78bfa"]
    for i, (_, row) in enumerate(top3.iterrows()):
        vals = [row[c] for c in DIM_COLS]
        fig_radar.add_trace(go.Scatterpolar(
            r=vals + [vals[0]],
            theta=DIMS + [DIMS[0]],
            fill="toself",
            name=row["Config"],
            line=dict(color=colors[i]),
            opacity=0.7,
        ))
    fig_radar.update_layout(
        polar=dict(
            bgcolor="rgba(30,30,30,0.6)",
            radialaxis=dict(range=[0, 10], gridcolor="#555555",
                            tickfont=dict(color="#cccccc")),
            angularaxis=dict(gridcolor="#555555", tickfont=dict(color="#cccccc")),
        ),
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        height=380,
        legend=dict(orientation="h", y=-0.12),
        margin=dict(t=20),
    )
    st.plotly_chart(fig_radar, use_container_width=True)

with col_ri:
    st.subheader(":material/lightbulb: Key Insights")
    top1 = top3.iloc[0]
    dim_vals  = {d: top1[c] for d, c in zip(DIMS, DIM_COLS)}
    best_dim  = max(dim_vals, key=dim_vals.get)
    worst_dim = min(dim_vals, key=dim_vals.get)
    cfg_badges = " ".join(badge(top3.iloc[i]["Config"]) for i in range(len(top3)))
    st.markdown(
        f"""
        <p>The top 3 configs are {cfg_badges}.</p>

        <p>For the leading config, {badge(best_dim)} is the strongest dimension
        while {badge(worst_dim, False)} is the weakest, indicating where further
        tuning may yield the most gains.</p>
        """,
        unsafe_allow_html=True,
    )

# ===========================================================================
# Complexity vs Performance
# ===========================================================================
st.divider()
st.header(":material/scatter_plot: Complexity vs Performance")

df["Complexity"] = (
    df["DOMAIN_PROMPT"].astype(int) + df["CITATION"].astype(int) +
    df["AGENTIC"].astype(int)       + df["SELF_CRITIQUE"].astype(int)
)

col_scatter, col_st = st.columns([2, 1])

with col_scatter:
    fig_scatter = go.Figure()
    for _, row in df.iterrows():
        color = "#22d3ee" if row["AGENTIC"] else "#fd3db5"
        fig_scatter.add_trace(go.Scatter(
            x=[row["Complexity"]],
            y=[row["SCORE_PCT"]],
            mode="markers+text",
            marker=dict(
                size=row["MH_PCT"] / 4 + 8,
                color=color,
                opacity=0.85,
                line=dict(color="#ffffff", width=1),
            ),
            text=[row["Config"]],
            textposition="top center",
            textfont=dict(color="#ffffff", size=11),
            name=row["Config"],
            showlegend=False,
            hovertemplate=(
                f"<b>{row['Config']}</b><br>"
                f"Score: {row['SCORE_PCT']:.1f}%<br>"
                f"MH: {row['MH_PCT']:.1f}%<extra></extra>"
            ),
        ))
    fig_scatter.update_layout(
        xaxis=dict(title="# Features Enabled", tickvals=[0, 1, 2, 3, 4],
                   gridcolor="#333333", color="#cccccc"),
        yaxis=dict(title="Score %", gridcolor="#333333", color="#cccccc"),
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=420,
        margin=dict(t=20, b=40),
    )
    st.plotly_chart(fig_scatter, use_container_width=True)
    st.caption("Bubble size = MH pass %. Cyan = Agentic, Magenta = Non-Agentic.")

with col_st:
    st.subheader(":material/lightbulb: Key Insights")
    top = df.iloc[0]
    baseline = df[df["Config"] == "Baseline"]
    baseline_score = baseline.iloc[0]["SCORE_PCT"] if not baseline.empty else 0.0
    lift = top["SCORE_PCT"] - baseline_score
    top_badge       = badge(f"{top['SCORE_PCT']:.1f}%")
    lift_badge      = badge(f"+{lift:.1f}pp")
    complexity_badge = badge(str(int(top["Complexity"])))

    st.markdown(
        f"""
        <p>The best-performing config is <strong>{top['Config']}</strong> with a score of
        {top_badge}, using {complexity_badge} features enabled.</p>

        <p>Compared to the Baseline, the top config delivers a lift of {lift_badge}.</p>

        <p>Bubble size encodes MH pass rate. Larger bubbles are safer choices for
        production use.</p>
        """,
        unsafe_allow_html=True,
    )
