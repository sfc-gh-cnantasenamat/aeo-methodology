"""Experimental — Decision Matrix: which config should we ship?"""
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from utils.db import run_query, config_label

st.title(":material/table_chart: Decision Matrix")
st.caption("Compare configuration complexity against performance to find the optimal shipping candidate.")

# --- Load data ---
lb = run_query("SELECT * FROM V_AEO_LEADERBOARD ORDER BY SCORE_PCT DESC")
lb["Config"] = lb.apply(
    lambda r: config_label(r.DOMAIN_PROMPT, r.CITATION, r.AGENTIC, r.SELF_CRITIQUE), axis=1
)
lb["Complexity"] = (
    lb["DOMAIN_PROMPT"].astype(int) + lb["CITATION"].astype(int) +
    lb["AGENTIC"].astype(int)       + lb["SELF_CRITIQUE"].astype(int)
)

# Per-config dimension averages
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
lb = lb.merge(pq[["Config"] + DIM_COLS], on="Config", how="left")

# --- Sidebar ---
with st.sidebar:
    st.header("Filters")
    mh_threshold = st.slider("Min MH % required", 0, 100, 50, 5)

# --- Recommendation chip ---
eligible = lb[lb["MH_PCT"] >= mh_threshold]
if not eligible.empty:
    rec = eligible.iloc[0]
    st.success(
        f"**Recommended config:** {rec['Config']} — "
        f"Score {rec['SCORE_PCT']:.1f}%, MH {rec['MH_PCT']:.1f}%"
    )
else:
    st.warning("No config meets the MH threshold. Lower the slider.")

st.divider()

# --- Scatter: complexity vs score ---
st.subheader("Complexity vs Performance")
col_plot, col_text = st.columns([2, 1])

with col_plot:
    fig = go.Figure()
    for _, row in lb.iterrows():
        color = "#22d3ee" if row["AGENTIC"] else "#fd3db5"
        fig.add_trace(go.Scatter(
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
    fig.update_layout(
        xaxis=dict(title="# Features Enabled", tickvals=[0, 1, 2, 3, 4],
                   gridcolor="#333333", color="#cccccc"),
        yaxis=dict(title="Score %", gridcolor="#333333", color="#cccccc"),
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=420,
        margin=dict(t=20, b=40),
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Bubble size = MH pass %. Cyan = Agentic, Magenta = Non-Agentic.")

with col_text:
    st.subheader(":material/lightbulb: Key Insights")

    def badge(val, positive=True):
        bg = "#15803d" if positive else "#9d174d"
        return (
            f'<span style="background:{bg};color:#ffffff;padding:1px 7px;'
            f'border-radius:9999px;font-size:0.85em;font-weight:600;">{val}</span>'
        )

    top = lb.iloc[0]
    baseline = lb[lb["Config"] == "Baseline"]
    baseline_score = baseline.iloc[0]["SCORE_PCT"] if not baseline.empty else 0.0
    lift = top["SCORE_PCT"] - baseline_score
    top_badge       = badge(f"{top['SCORE_PCT']:.1f}%")
    lift_badge      = badge(f"+{lift:.1f}pp")
    complexity_badge = badge(str(int(top["Complexity"])))

    if not eligible.empty:
        rec_badge = badge(rec["Config"])
        mh_badge  = badge(f"{rec['MH_PCT']:.1f}%")
        rec_text  = (
            f"<p>Given the MH threshold of {mh_threshold}%, {rec_badge} is the "
            f"recommended config, achieving {mh_badge} MH compliance.</p>"
        )
    else:
        rec_text = "<p>No config clears the current MH threshold. Try lowering the slider.</p>"

    st.markdown(
        f"""
        <p>The best-performing config is <strong>{top['Config']}</strong> with a score of
        {top_badge}, using {complexity_badge} features enabled.</p>

        <p>Compared to the Baseline, the top config delivers a lift of {lift_badge}.</p>

        {rec_text}

        <p>Bubble size encodes MH pass rate. Larger bubbles are safer choices for
        production use.</p>
        """,
        unsafe_allow_html=True,
    )

st.divider()

# --- Radar: top 3 configs ---
st.subheader("Dimension breakdown — Top 3 configs")
col_radar, col_ri = st.columns([2, 1])
DIMS = ["Correctness", "Completeness", "Recency", "Citation", "Recommendation"]
top3 = lb.head(3)

with col_radar:
    fig2 = go.Figure()
    colors = ["#22d3ee", "#fd3db5", "#a78bfa"]
    for i, (_, row) in enumerate(top3.iterrows()):
        vals = [row[c] for c in DIM_COLS]
        fig2.add_trace(go.Scatterpolar(
            r=vals + [vals[0]],
            theta=DIMS + [DIMS[0]],
            fill="toself",
            name=row["Config"],
            line=dict(color=colors[i]),
            opacity=0.7,
        ))
    fig2.update_layout(
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
    st.plotly_chart(fig2, use_container_width=True)

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

st.divider()

# --- Marginal gain table ---
st.subheader("Marginal gain per feature")
rows = []
for feat, label in [
    ("DOMAIN_PROMPT", "Domain Prompt"),
    ("CITATION",      "Citation"),
    ("AGENTIC",       "Agentic"),
    ("SELF_CRITIQUE", "Self-Critique"),
]:
    on  = lb[lb[feat] == True]["SCORE_PCT"].mean()
    off = lb[lb[feat] == False]["SCORE_PCT"].mean()
    rows.append({
        "Feature":        label,
        "Avg Score (ON)": round(on, 1),
        "Avg Score (OFF)":round(off, 1),
        "Gain (pp)":      round(on - off, 1),
    })
gain_df = pd.DataFrame(rows)
st.dataframe(
    gain_df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Avg Score (ON)":  st.column_config.ProgressColumn(
            "Avg Score (ON)",  format="%.1f%%", min_value=0, max_value=100, color="auto"),
        "Avg Score (OFF)": st.column_config.ProgressColumn(
            "Avg Score (OFF)", format="%.1f%%", min_value=0, max_value=100, color="auto"),
    },
)
