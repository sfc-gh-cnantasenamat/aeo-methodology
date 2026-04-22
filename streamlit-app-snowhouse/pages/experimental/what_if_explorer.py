"""Experimental — What-If Explorer: stress-test config rankings."""
import streamlit as st
import plotly.graph_objects as go
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from utils.db import run_query, config_label

st.title(":material/science: What-If Explorer")
st.caption(
    "Adjust dimension weights and exclude categories to stress-test "
    "config rankings under different priorities."
)

# --- Load ---
pq = run_query("""
    SELECT q.QUESTION_ID, q.CATEGORY,
           h.RUN_ID, h.DOMAIN_PROMPT, h.CITATION, h.AGENTIC, h.SELF_CRITIQUE,
           h.CORRECTNESS, h.COMPLETENESS, h.RECENCY, h.CITATION_SCORE, h.RECOMMENDATION,
           h.TOTAL_SCORE, h.MUST_HAVE_PASS
    FROM V_AEO_PER_QUESTION_HEATMAP h
    JOIN AEO_QUESTIONS q ON h.QUESTION_ID = q.QUESTION_ID
""")
pq["Config"]  = pq.apply(
    lambda r: config_label(r.DOMAIN_PROMPT, r.CITATION, r.AGENTIC, r.SELF_CRITIQUE), axis=1
)
pq["Score %"] = (pq["TOTAL_SCORE"] / 50.0 * 100).round(1)

# --- Sidebar: weights and exclusions ---
with st.sidebar:
    st.header("Dimension weights")
    w_corr = st.slider("Correctness",    0, 10, 10)
    w_comp = st.slider("Completeness",   0, 10, 10)
    w_rec  = st.slider("Recency",        0, 10, 10)
    w_cit  = st.slider("Citation",       0, 10, 10)
    w_reco = st.slider("Recommendation", 0, 10, 10)

    st.header("Category exclusions")
    all_cats  = sorted(pq["CATEGORY"].unique())
    excl_cats = st.multiselect("Exclude categories", all_cats, default=[])

# --- Guard ---
total_weight = w_corr + w_comp + w_rec + w_cit + w_reco
if total_weight == 0:
    st.warning("All weights are zero. Set at least one weight above 0.")
    st.stop()

# --- Filter and compute custom score ---
filt = pq[~pq["CATEGORY"].isin(excl_cats)].copy()
filt["Custom Score"] = (
    filt["CORRECTNESS"]    * w_corr +
    filt["COMPLETENESS"]   * w_comp +
    filt["RECENCY"]        * w_rec  +
    filt["CITATION_SCORE"] * w_cit  +
    filt["RECOMMENDATION"] * w_reco
) / total_weight

custom_rank = (
    filt.groupby("Config")["Custom Score"]
    .mean()
    .reset_index()
    .sort_values("Custom Score", ascending=False)
    .reset_index(drop=True)
)
custom_rank.index += 1
custom_rank.index.name = "Custom Rank"
custom_rank["Custom Score"] = custom_rank["Custom Score"].round(2)

# Original rank (equal weights, all categories)
orig_rank = (
    pq.groupby("Config")["Score %"]
    .mean()
    .reset_index()
    .sort_values("Score %", ascending=False)
    .reset_index(drop=True)
)
orig_rank.index += 1
orig_rank.index.name = "Original Rank"
orig_rank = orig_rank.rename(columns={"Score %": "Original Score %"})
orig_rank["Original Score %"] = orig_rank["Original Score %"].round(1)

merged = (
    custom_rank.reset_index()
    .merge(orig_rank.reset_index(), on="Config")
)
merged["Rank Change"] = merged["Original Rank"] - merged["Custom Rank"]

# --- Rank shift bar chart ---
st.subheader("Ranking shifts vs equal-weight baseline")
col_chart, col_text = st.columns([2, 1])

with col_chart:
    fig = go.Figure()
    for _, row in merged.iterrows():
        if row["Rank Change"] > 0:
            color = "#22d3ee"
        elif row["Rank Change"] < 0:
            color = "#fd3db5"
        else:
            color = "#666666"
        rc = int(row["Rank Change"])
        fig.add_trace(go.Bar(
            x=[row["Config"]],
            y=[rc],
            marker_color=color,
            text=[f"{rc:+d}"],
            textposition="outside",
            textfont=dict(color="#ffffff"),
            showlegend=False,
        ))
    fig.add_hline(y=0, line_color="#555555")
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        yaxis=dict(title="Rank change", gridcolor="#333333", color="#cccccc"),
        height=380,
        margin=dict(t=20),
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Cyan = moved up. Magenta = moved down. Gray = unchanged.")

with col_text:
    st.subheader(":material/lightbulb: Key Insights")

    def badge(val, positive=True):
        bg = "#15803d" if positive else "#9d174d"
        return (
            f'<span style="background:{bg};color:#ffffff;padding:1px 7px;'
            f'border-radius:9999px;font-size:0.85em;font-weight:600;">{val}</span>'
        )

    top_custom  = merged.iloc[0]
    n_up        = int((merged["Rank Change"] > 0).sum())
    n_down      = int((merged["Rank Change"] < 0).sum())
    n_stable    = int((merged["Rank Change"] == 0).sum())
    excl_text   = (
        f"excluding {len(excl_cats)} "
        f"categor{'y' if len(excl_cats) == 1 else 'ies'}"
        if excl_cats else "all categories included"
    )

    st.markdown(
        f"""
        <p>Under the current weights ({excl_text}),
        {badge(top_custom['Config'])} ranks first with a weighted
        score of {badge(f"{top_custom['Custom Score']:.2f}/10")}.</p>

        <p>{n_up} config(s) moved up and {n_down} moved down compared
        to the equal-weight baseline. {n_stable} remained stable.</p>

        <p>Large rank shifts indicate configs that specialise in specific
        dimensions. A config that rises when Recency is weighted higher
        excels at time-sensitive questions.</p>

        <p>Configs with no rank change perform consistently regardless of
        how dimensions are weighted — a sign of well-rounded reliability.</p>
        """,
        unsafe_allow_html=True,
    )

st.divider()

# --- Full ranking table ---
st.subheader("Full ranking comparison")
st.dataframe(
    merged[["Custom Rank", "Config", "Custom Score",
            "Original Rank", "Original Score %", "Rank Change"]],
    use_container_width=True,
    hide_index=True,
    column_config={
        "Custom Score":      st.column_config.ProgressColumn(
            "Custom Score",      format="%.2f", min_value=0, max_value=10),
        "Original Score %":  st.column_config.ProgressColumn(
            "Original Score %",  format="%.1f%%", min_value=0, max_value=100),
    },
)
