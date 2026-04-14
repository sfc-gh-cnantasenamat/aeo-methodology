"""Experimental — Feature ROI: is the added complexity worth it?"""
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from utils.db import run_query, config_label

st.title(":material/show_chart: Feature ROI")
st.caption("Measure the marginal score lift from each configuration feature and their interactions.")

lb = run_query("SELECT * FROM V_AEO_LEADERBOARD ORDER BY SCORE_PCT DESC")
lb["Config"] = lb.apply(
    lambda r: config_label(r.DOMAIN_PROMPT, r.CITATION, r.AGENTIC, r.SELF_CRITIQUE), axis=1
)

FEATURES = [
    ("DOMAIN_PROMPT", "Domain Prompt"),
    ("CITATION",      "Citation"),
    ("AGENTIC",       "Agentic"),
    ("SELF_CRITIQUE", "Self-Critique"),
]

def badge(val, positive=True):
    bg = "#15803d" if positive else "#9d174d"
    return (
        f'<span style="background:{bg};color:#ffffff;padding:1px 7px;'
        f'border-radius:9999px;font-size:0.85em;font-weight:600;">{val}</span>'
    )

# --- Marginal gain per feature ---
gains = []
for col, label in FEATURES:
    on      = lb[lb[col] == True]["SCORE_PCT"].mean()
    off     = lb[lb[col] == False]["SCORE_PCT"].mean()
    mh_on   = lb[lb[col] == True]["MH_PCT"].mean()
    mh_off  = lb[lb[col] == False]["MH_PCT"].mean()
    gains.append({
        "Feature":         label,
        "col":             col,
        "Score ON":        round(on, 1),
        "Score OFF":       round(off, 1),
        "Score Lift (pp)": round(on - off, 1),
        "MH Lift (pp)":    round(mh_on - mh_off, 1),
    })
gain_df = pd.DataFrame(gains)

st.subheader("Score lift by feature")
col_bar, col_text = st.columns([2, 1])

with col_bar:
    colors = ["#22d3ee" if g >= 0 else "#fd3db5" for g in gain_df["Score Lift (pp)"]]
    fig = go.Figure(go.Bar(
        x=gain_df["Feature"],
        y=gain_df["Score Lift (pp)"],
        marker_color=colors,
        text=[f"{v:+.1f}pp" for v in gain_df["Score Lift (pp)"]],
        textposition="outside",
        textfont=dict(color="#ffffff"),
    ))
    fig.add_hline(y=0, line_color="#555555")
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        yaxis=dict(title="Score lift (pp)", gridcolor="#333333", color="#cccccc"),
        height=380,
        margin=dict(t=20),
    )
    st.plotly_chart(fig, use_container_width=True)

with col_text:
    st.subheader(":material/lightbulb: Key Insights")
    best_feat  = gain_df.loc[gain_df["Score Lift (pp)"].idxmax()]
    worst_feat = gain_df.loc[gain_df["Score Lift (pp)"].idxmin()]
    best_lift  = badge(f"+{best_feat['Score Lift (pp)']:.1f}pp")
    worst_lift = badge(
        f"{worst_feat['Score Lift (pp)']:+.1f}pp",
        worst_feat["Score Lift (pp)"] >= 0,
    )
    st.markdown(
        f"""
        <p><strong>{best_feat['Feature']}</strong> delivers the highest marginal
        score lift at {best_lift} on average across all 16 configurations.</p>

        <p><strong>{worst_feat['Feature']}</strong> shows the smallest lift at
        {worst_lift}, suggesting diminishing returns or interference with other
        features.</p>

        <p>Positive bars mean the feature consistently improves scores when
        enabled. Negative bars indicate it may hurt performance in certain
        configuration combinations.</p>
        """,
        unsafe_allow_html=True,
    )

st.divider()

# --- Interaction effects ---
st.subheader("Feature interaction effects")
st.caption(
    "Synergy > 0: the pair outperforms the sum of individual gains (superadditive). "
    "Synergy < 0: features interfere with each other."
)

feat_cols  = [f[0] for f in FEATURES]
feat_names = [f[1] for f in FEATURES]

baseline_mask = (
    (lb["DOMAIN_PROMPT"] == False) & (lb["CITATION"] == False) &
    (lb["AGENTIC"] == False)       & (lb["SELF_CRITIQUE"] == False)
)
baseline_score = lb[baseline_mask]["SCORE_PCT"].mean()

rows_int = []
for i in range(len(FEATURES)):
    for j in range(i + 1, len(FEATURES)):
        fi, fj = feat_cols[i], feat_cols[j]
        ni, nj = feat_names[i], feat_names[j]
        both        = lb[(lb[fi] == True) & (lb[fj] == True)]["SCORE_PCT"].mean()
        ind_i       = gain_df[gain_df["col"] == fi]["Score Lift (pp)"].values[0]
        ind_j       = gain_df[gain_df["col"] == fj]["Score Lift (pp)"].values[0]
        actual_lift = both - baseline_score
        synergy     = round(actual_lift - (ind_i + ind_j), 1)
        rows_int.append({
            "Pair":                f"{ni} + {nj}",
            "Combined Avg %":      round(both, 1),
            "Expected Lift (pp)":  round(ind_i + ind_j, 1),
            "Actual Lift (pp)":    round(actual_lift, 1),
            "Synergy (pp)":        synergy,
        })

int_df = pd.DataFrame(rows_int).sort_values("Synergy (pp)", ascending=False)
st.dataframe(
    int_df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Combined Avg %":     st.column_config.ProgressColumn(
            "Combined Avg %",     format="%.1f%%", min_value=0, max_value=100),
        "Expected Lift (pp)": st.column_config.ProgressColumn(
            "Expected Lift (pp)", format="%.1f",   min_value=-10, max_value=20),
        "Actual Lift (pp)":   st.column_config.ProgressColumn(
            "Actual Lift (pp)",   format="%.1f",   min_value=-10, max_value=20),
    },
)

st.divider()

# --- Full marginal gain table ---
st.subheader("Marginal gain detail")
show = gain_df[["Feature", "Score OFF", "Score ON", "Score Lift (pp)", "MH Lift (pp)"]].copy()
st.dataframe(
    show,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Score ON":  st.column_config.ProgressColumn(
            "Avg Score (ON)",  format="%.1f%%", min_value=0, max_value=100),
        "Score OFF": st.column_config.ProgressColumn(
            "Avg Score (OFF)", format="%.1f%%", min_value=0, max_value=100),
    },
)
