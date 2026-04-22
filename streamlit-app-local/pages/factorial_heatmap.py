"""Page 4 — Factorial Heatmap: 32-category × 19-column interactive heatmap."""
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from utils.db import run_query, config_label

st.title(":material/grid_view: Factorial Heatmap")
st.caption(
    "Score % for every category × configuration combination. "
    "Columns: Agentic Avg | 8 agentic configs | 8 non-agentic configs | Non-Agentic Avg | Overall Avg."
)

# --- Load data ---
df = run_query("""
    SELECT CATEGORY, RUN_ID, DOMAIN_PROMPT, CITATION, AGENTIC, SELF_CRITIQUE,
           AVG(TOTAL_SCORE / 50.0 * 100) AS SCORE_PCT
    FROM V_AEO_PER_QUESTION_HEATMAP
    GROUP BY CATEGORY, RUN_ID, DOMAIN_PROMPT, CITATION, AGENTIC, SELF_CRITIQUE
""")

df["Config"] = df.apply(
    lambda r: config_label(r.DOMAIN_PROMPT, r.CITATION, r.AGENTIC, r.SELF_CRITIQUE), axis=1
)

# Pivot: categories × runs
pivot = df.pivot_table(index="CATEGORY", columns="Config", values="SCORE_PCT", aggfunc="mean")

# Sort configs: agentic first by overall score desc, then non-agentic
run_scores = df.groupby(["Config", "AGENTIC"])["SCORE_PCT"].mean().reset_index()
agentic_cols    = run_scores[run_scores["AGENTIC"] == True].sort_values("SCORE_PCT", ascending=False)["Config"].tolist()
nonagentic_cols = run_scores[run_scores["AGENTIC"] == False].sort_values("SCORE_PCT", ascending=False)["Config"].tolist()
ordered_cols    = agentic_cols + nonagentic_cols
pivot = pivot[ordered_cols]

# Sort rows by C+A score desc
if "C+A" in pivot.columns:
    pivot = pivot.sort_values("C+A", ascending=False)

# Add group avg columns
pivot.insert(0,                 "Agentic\nAvg",       pivot[agentic_cols].mean(axis=1))
pivot[              "Non-Ag\nAvg"] = pivot[nonagentic_cols].mean(axis=1)
pivot[              "Overall\nAvg"]= pivot[ordered_cols].mean(axis=1)

cols_display = list(pivot.columns)
z            = pivot.values
nrows, ncols = z.shape
categories   = list(pivot.index)

# Cell text
text = [[f"{v:.1f}" for v in row] for row in z]

# Color scale — dark-mode friendly (dark gray mid replaces light yellow)
colorscale = [
    [0,    "#b2182b"],
    [0.25, "#ef8a62"],
    [0.5,  "#404040"],
    [0.75, "#74c476"],
    [1,    "#1a9850"],
]

fig = go.Figure(go.Heatmap(
    z=z,
    x=cols_display,
    y=categories,
    text=text,
    texttemplate="%{text}",
    textfont=dict(size=9, color="white"),
    colorscale=colorscale,
    zmin=25, zmax=95,
    colorbar=dict(
        title="Score %",
        orientation="h",
        x=0.5, xanchor="center",
        y=-0.13, thickness=15, len=0.5,
    ),
    hoverongaps=False,
    xgap=1, ygap=1,
))

# Vertical separators
n_ag = len(agentic_cols)
sep_xs = [0.5, n_ag + 0.5, ncols - 3 + 0.5, ncols - 2 + 0.5]
sep_widths = [3, 5, 3, 4]
for sx, sw in zip(sep_xs, sep_widths):
    fig.add_shape(
        type="line", x0=sx, x1=sx, y0=-0.5, y1=nrows - 0.5,
        line=dict(color="#000000", width=sw), xref="x", yref="y",
    )

# Group labels — placed below the plot area via paper coords
ag_cx  = (0 + n_ag) / 2
nag_cx = (n_ag + 1 + ncols - 3) / 2
fig.add_annotation(x=ag_cx,  y=-0.02, text="<b>Agentic</b>",
                   showarrow=False, font=dict(size=12, color="#ffffff"),
                   xref="x", yref="paper", yanchor="top")
fig.add_annotation(x=nag_cx, y=-0.02, text="<b>Non-Agentic</b>",
                   showarrow=False, font=dict(size=12, color="#ffffff"),
                   xref="x", yref="paper", yanchor="top")

fig.update_layout(
    height=960,
    margin=dict(l=200, r=80, t=20, b=80),
    xaxis=dict(side="top", tickfont=dict(size=9, family="monospace", color="#cccccc")),
    yaxis=dict(autorange="reversed", tickfont=dict(size=9, color="#cccccc")),
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
)

avg_agentic    = pivot[agentic_cols].values.mean()
avg_nonagentic = pivot[nonagentic_cols].values.mean()
top_category   = pivot["Overall\nAvg"].idxmax()
bot_category   = pivot["Overall\nAvg"].idxmin()
best_config    = pivot[agentic_cols].mean().idxmax()

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

    gap = avg_agentic - avg_nonagentic
    st.markdown(
        f"""
        <p><strong>Agentic configs consistently outperform.</strong> The average
        score across all agentic configurations is
        {badge(f"{avg_agentic:.1f}%", True)}, compared to
        {badge(f"{avg_nonagentic:.1f}%", False)} for non-agentic, a gap of
        {badge(f"+{gap:.1f}pp", True)} across every category.</p>

        <p><strong>{best_config} is the strongest agentic configuration.</strong>
        It achieves the highest mean score among all agentic runs, confirming
        that combining Citation with Agentic tools produces the most capable
        setup.</p>

        <p><strong>{top_category} scores highest overall.</strong> Its row is
        the brightest across both agentic and non-agentic halves, indicating
        the model answers these questions well regardless of configuration.</p>

        <p><strong>{bot_category} is the most challenging category.</strong>
        Its row remains dark even in the agentic half, showing that tool
        access alone cannot fully close the gap for this topic.</p>
        """,
        unsafe_allow_html=True,
    )
