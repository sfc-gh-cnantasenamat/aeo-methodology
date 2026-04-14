"""Page 2 — Main Effects: factorial effect of each factor on Score % and MH %."""
import streamlit as st
import plotly.graph_objects as go
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from utils.db import run_query

st.title(":material/insights: Main Effects")
st.caption(
    "Average marginal effect of each factor across all 8 paired comparisons "
    "(ON minus OFF), in percentage points."
)

df = run_query("SELECT * FROM V_AEO_FACTORIAL_EFFECTS")

# Sort by absolute score effect descending
df = df.sort_values("SCORE_EFFECT_PP", ascending=False).reset_index(drop=True)

def bar_color(vals):
    return ["#4dac26" if v >= 0 else "#d01c8b" for v in vals]

fig = go.Figure()

fig.add_trace(go.Bar(
    name="Score effect (pp)",
    y=df["FACTOR"],
    x=df["SCORE_EFFECT_PP"],
    orientation="h",
    marker_color=bar_color(df["SCORE_EFFECT_PP"]),
    text=df["SCORE_EFFECT_PP"].map(lambda v: f"{v:+.1f}pp"),
    textposition="outside",
    width=0.35,
    offset=-0.2,
))
fig.add_trace(go.Bar(
    name="Must-Have effect (pp)",
    y=df["FACTOR"],
    x=df["MH_EFFECT_PP"],
    orientation="h",
    marker_color=bar_color(df["MH_EFFECT_PP"]),
    opacity=0.5,
    text=df["MH_EFFECT_PP"].map(lambda v: f"{v:+.1f}pp"),
    textposition="outside",
    width=0.35,
    offset=0.2,
))

x_lim = max(abs(df["SCORE_EFFECT_PP"].max()), abs(df["MH_EFFECT_PP"].max()),
            abs(df["SCORE_EFFECT_PP"].min()), abs(df["MH_EFFECT_PP"].min())) + 3

fig.add_vline(x=0, line_color="black", line_width=1)
fig.update_layout(
    barmode="overlay",
    xaxis_title="Effect (percentage points)",
    yaxis_title="",
    xaxis_range=[-x_lim, x_lim],
    height=500,
    margin=dict(t=20, b=60),
    template="plotly_white",
    legend=dict(orientation="h", y=-0.18, x=0.5, xanchor="center"),
)
col_plot, col_text = st.columns([2, 1])

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
        <p><strong>Agentic tools dominate.</strong> Enabling tool access lifts Score by
        {badge("+10.9 pp", True)} and Must-Have compliance by {badge("+19.2 pp", True)},
        the largest positive effect across both metrics.</p>

        <p><strong>Citation has a split personality.</strong> It improves Score by
        {badge("+8.8 pp", True)}, suggesting richer answers, but depresses Must-Have
        compliance by {badge("−4.6 pp", False)}. Citations appear to dilute the specific
        facts judges require.</p>

        <p><strong>Domain Prompt is nearly neutral.</strong> Its effects on Score
        {badge("−0.8 pp", False)} and Must-Have {badge("−0.1 pp", False)} are close to
        zero, indicating the system prompt framing tested here adds little on top of
        other factors.</p>

        <p><strong>Self-Critique backfires.</strong> It is the only factor that hurts
        Score {badge("−2.7 pp", False)} and strongly suppresses Must-Have compliance
        {badge("−9.8 pp", False)}. The review loop may cause the model to hedge or remove
        specific details the rubric requires.</p>
        """,
        unsafe_allow_html=True,
    )
