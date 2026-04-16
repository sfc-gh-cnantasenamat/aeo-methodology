"""Page 2 — Main Effects: factorial effect of each factor on Score % and MH %."""
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from utils.db import run_query, config_label

# ---------------------------------------------------------------------------
# Load leaderboard data early — needed for error bar computation below
# ---------------------------------------------------------------------------
lb = run_query("SELECT * FROM V_AEO_LEADERBOARD ORDER BY SCORE_PCT DESC")
lb["Config"] = lb.apply(
    lambda r: config_label(r.DOMAIN_PROMPT, r.CITATION, r.AGENTIC, r.SELF_CRITIQUE), axis=1
)

# Factorial analysis requires only the 2^4 design runs (claude-opus-4-6).
# Baseline-only runs for other models are excluded because the naive
# mean comparison (ON minus OFF) is confounded when OFF rows contain
# different respondent models.
lb_factorial = lb[lb["MODEL"] == "claude-opus-4-6"].copy()

FEATURES = [
    ("DOMAIN_PROMPT", "Domain Prompt"),
    ("CITATION",      "Citation"),
    ("AGENTIC",       "Agentic"),
    ("SELF_CRITIQUE", "Self-Critique"),
]

ALL_FACTOR_COLS = [col for col, _ in FEATURES]


def compute_effect_se(df, factor_col, metric_col):
    """SE via 8 paired contrasts in a 2^4 factorial design.

    For factor F, the other 3 factors define 8 unique combinations. For each
    combination the difference (F=ON) − (F=OFF) is a paired contrast. The SE
    of the mean effect is std(contrasts, ddof=1) / sqrt(8).
    """
    other_cols = [c for c in ALL_FACTOR_COLS if c != factor_col]
    diffs = []
    for _, grp in df.groupby(other_cols):
        on_val  = grp[grp[factor_col] == True][metric_col]
        off_val = grp[grp[factor_col] == False][metric_col]
        if len(on_val) >= 1 and len(off_val) >= 1:
            diffs.append(float(on_val.mean()) - float(off_val.mean()))
    arr = np.array(diffs)
    return float(np.std(arr, ddof=1) / np.sqrt(len(arr)))


st.title(":material/insights: Main Effects")
st.caption(
    "Average marginal effect of each factor across all 8 paired comparisons "
    "(ON minus OFF), in percentage points. Error bars = ±1 SE (8 paired contrasts)."
)

df = run_query("SELECT * FROM V_AEO_FACTORIAL_EFFECTS")

# Sort by absolute score effect descending
df = df.sort_values("SCORE_EFFECT_PP", ascending=False).reset_index(drop=True)

# Map view FACTOR label → lb_factorial column name, then compute SE per row
label_to_col = {label: col for col, label in FEATURES}
score_se = [compute_effect_se(lb_factorial, label_to_col[f], "SCORE_PCT") for f in df["FACTOR"]]
mh_se    = [compute_effect_se(lb_factorial, label_to_col[f], "MH_PCT")    for f in df["FACTOR"]]

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
    error_x=dict(type="data", array=score_se, visible=True,
                 color="rgba(0,0,0,0.55)", thickness=1.5, width=5),
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
    error_x=dict(type="data", array=mh_se, visible=True,
                 color="rgba(0,0,0,0.55)", thickness=1.5, width=5),
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

# ===========================================================================
# Score Lift by Feature
# ===========================================================================
st.divider()
st.header(":material/show_chart: Score Lift by Feature")
st.caption("Marginal score lift from each configuration feature and their interactions.")

# lb, lb_factorial, and FEATURES are already defined at the top of the file.

def badge2(val, positive=True):
    bg = "#15803d" if positive else "#9d174d"
    return (
        f'<span style="background:{bg};color:#ffffff;padding:1px 7px;'
        f'border-radius:9999px;font-size:0.85em;font-weight:600;">{val}</span>'
    )

# --- Marginal gain per feature ---
gains = []
for col, label in FEATURES:
    on      = lb_factorial[lb_factorial[col] == True]["SCORE_PCT"].mean()
    off     = lb_factorial[lb_factorial[col] == False]["SCORE_PCT"].mean()
    mh_on   = lb_factorial[lb_factorial[col] == True]["MH_PCT"].mean()
    mh_off  = lb_factorial[lb_factorial[col] == False]["MH_PCT"].mean()
    gains.append({
        "Feature":         label,
        "col":             col,
        "Score ON":        round(on, 1),
        "Score OFF":       round(off, 1),
        "Score Lift (pp)": round(on - off, 1),
        "MH Lift (pp)":    round(mh_on - mh_off, 1),
    })
gain_df = pd.DataFrame(gains)

col_bar, col_bar_text = st.columns([2, 1])

with col_bar:
    colors = ["#22d3ee" if g >= 0 else "#fd3db5" for g in gain_df["Score Lift (pp)"]]
    fig_lift = go.Figure(go.Bar(
        x=gain_df["Feature"],
        y=gain_df["Score Lift (pp)"],
        marker_color=colors,
        text=[f"{v:+.1f}pp" for v in gain_df["Score Lift (pp)"]],
        textposition="outside",
        textfont=dict(color="#ffffff"),
    ))
    fig_lift.add_hline(y=0, line_color="#555555")
    fig_lift.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        yaxis=dict(title="Score lift (pp)", gridcolor="#333333", color="#cccccc"),
        height=500,
        margin=dict(t=20),
    )
    st.plotly_chart(fig_lift, use_container_width=True)

with col_bar_text:
    st.subheader(":material/lightbulb: Key Insights")
    best_feat  = gain_df.loc[gain_df["Score Lift (pp)"].idxmax()]
    worst_feat = gain_df.loc[gain_df["Score Lift (pp)"].idxmin()]
    best_lift  = badge2(f"+{best_feat['Score Lift (pp)']:.1f}pp")
    worst_lift = badge2(
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

# --- Factor interaction heatmap ---
st.header(":material/grid_on: Factor Interaction Heatmap")
st.caption(
    "Synergy (pp): the extra score lift when both features are ON together, "
    "beyond what their individual main effects would predict. "
    "Positive means the pair works better in combination than expected. "
    "Diagonal cells are blank (self-pairs are not meaningful)."
)

feat_cols  = [f[0] for f in FEATURES]
feat_names = [f[1] for f in FEATURES]
n = len(FEATURES)

baseline_mask = (
    (lb_factorial["DOMAIN_PROMPT"] == False) & (lb_factorial["CITATION"] == False) &
    (lb_factorial["AGENTIC"] == False)       & (lb_factorial["SELF_CRITIQUE"] == False)
)
baseline_score = lb_factorial[baseline_mask]["SCORE_PCT"].mean()

# Build n×n matrix: diagonal = NaN (blank), off-diagonal = pairwise synergy
matrix = [[float("nan")] * n for _ in range(n)]
text   = [[""] * n for _ in range(n)]
pairs  = []

for i in range(n):
    for j in range(i + 1, n):
        fi, fj = feat_cols[i], feat_cols[j]
        both        = lb_factorial[(lb_factorial[fi] == True) & (lb_factorial[fj] == True)]["SCORE_PCT"].mean()
        ind_i       = gain_df[gain_df["col"] == fi]["Score Lift (pp)"].values[0]
        ind_j       = gain_df[gain_df["col"] == fj]["Score Lift (pp)"].values[0]
        actual_lift = both - baseline_score
        synergy     = round(actual_lift - (ind_i + ind_j), 1)
        matrix[i][j] = synergy
        matrix[j][i] = synergy
        text[i][j]   = f"{synergy:+.1f}pp"
        text[j][i]   = f"{synergy:+.1f}pp"
        pairs.append({"pair": f"{feat_names[i]} + {feat_names[j]}", "synergy": synergy,
                      "ind_i": ind_i, "ind_j": ind_j, "actual_lift": round(actual_lift, 1)})

pairs_df   = pd.DataFrame(pairs).sort_values("synergy", ascending=False).reset_index(drop=True)
best_pair  = pairs_df.iloc[0]
worst_pair = pairs_df.iloc[-1]

z = np.array(matrix, dtype=float)
abs_max = float(max(abs(np.nanmin(z)), abs(np.nanmax(z))))

# Colorscale matching the Score Lift bar chart: pink (negative) → dark → cyan (positive)
lift_colorscale = [
    [0.0, "#fd3db5"],
    [0.5, "#111827"],
    [1.0, "#22d3ee"],
]

fig_hm = go.Figure(go.Heatmap(
    z=z,
    x=feat_names,
    y=feat_names,
    text=text,
    texttemplate="%{text}",
    colorscale=lift_colorscale,
    zmid=0,
    zmin=-abs_max,
    zmax=abs_max,
    colorbar=dict(title="pp", ticksuffix="pp"),
    hoverongaps=False,
    xgap=2,
    ygap=2,
))

fig_hm.update_layout(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="#000000",
    height=420,
    margin=dict(t=20, b=20, l=120, r=20),
    xaxis=dict(side="bottom", showgrid=False),
    yaxis=dict(showgrid=False),
    font=dict(size=13),
)

col_hm, col_hm_text = st.columns([2, 1])

with col_hm:
    st.plotly_chart(fig_hm, use_container_width=True)

with col_hm_text:
    st.subheader(":material/lightbulb: Key Insights")

    def badge3(val, positive=True):
        bg = "#15803d" if positive else "#9d174d"
        return (
            f'<span style="background:{bg};color:#ffffff;padding:1px 7px;'
            f'border-radius:9999px;font-size:0.85em;font-weight:600;">{val}</span>'
        )

    best_expected  = round(best_pair["ind_i"] + best_pair["ind_j"], 1)
    worst_expected = round(worst_pair["ind_i"] + worst_pair["ind_j"], 1)

    st.markdown(
        f"""
        <p><strong>Strongest synergy: {best_pair['pair']}.</strong>
        Their individual effects predict {badge3(f"{best_expected:+.1f}pp", best_expected >= 0)},
        but together they deliver {badge3(f"{best_pair['actual_lift']:+.1f}pp", best_pair['actual_lift'] >= 0)},
        a synergy of {badge3(f"{best_pair['synergy']:+.1f}pp", best_pair['synergy'] >= 0)}.
        They amplify each other beyond what either contributes alone.</p>

        <p><strong>Weakest synergy: {worst_pair['pair']}.</strong>
        Expected {badge3(f"{worst_expected:+.1f}pp", worst_expected >= 0)},
        actual {badge3(f"{worst_pair['actual_lift']:+.1f}pp", worst_pair['actual_lift'] >= 0)},
        synergy {badge3(f"{worst_pair['synergy']:+.1f}pp", worst_pair['synergy'] >= 0)}.
        Each feature largely delivers its benefit independently with little extra from pairing.</p>

        <p>A high synergy value does not mean either feature is individually strong.
        It means the combination produces more than a naive sum would predict.</p>
        """,
        unsafe_allow_html=True,
    )
