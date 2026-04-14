"""Page 3 — Category Performance: per-category Baseline vs C+A dumbbell chart."""
import streamlit as st
import plotly.graph_objects as go
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from utils.db import run_query

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
