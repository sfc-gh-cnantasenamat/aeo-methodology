"""Page — Factors Influence: main effects, score lift, interactions, and dimension breakdown."""
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from utils.db import run_query, config_label, ENV, v3_leaderboard_sql, v3_per_question_sql
from utils.ui import model_selector

st.title("Factors Influence")
st.caption("Marginal effect of each configuration flag on score % and must-have compliance — computed across all 8 paired contrasts in the 2⁴ factorial design.")

# ---------------------------------------------------------------------------
# Shared constants and utilities
# ---------------------------------------------------------------------------
FEATURES = [
    ("DOMAIN_PROMPT", "Domain Prompt"),
    ("CITATION",      "Citation"),
    ("AGENTIC",       "Agentic"),
    ("SELF_CRITIQUE", "Self-Critique"),
]
ALL_FACTOR_COLS = [col for col, _ in FEATURES]


def compute_effect_se(df, factor_col, metric_col):
    """SE via 8 paired contrasts in a 2^4 factorial design."""
    other_cols = [c for c in ALL_FACTOR_COLS if c != factor_col]
    diffs = []
    for _, grp in df.groupby(other_cols):
        on_val  = grp[grp[factor_col] == True][metric_col]
        off_val = grp[grp[factor_col] == False][metric_col]
        if len(on_val) >= 1 and len(off_val) >= 1:
            diffs.append(float(on_val.mean()) - float(off_val.mean()))
    arr = np.array(diffs)
    if len(arr) < 2:
        return 0.0
    return float(np.std(arr, ddof=1) / np.sqrt(len(arr)))


def load_lb_for_model(model: str) -> pd.DataFrame:
    """Load and pre-process leaderboard rows for one V3 model."""
    df = run_query(v3_leaderboard_sql(model) + " ORDER BY SCORE_PCT DESC")
    df["Config"] = df.apply(
        lambda r: config_label(r.DOMAIN_PROMPT, r.CITATION, r.AGENTIC, r.SELF_CRITIQUE), axis=1
    )
    return df


def compute_gains(lb_factorial: pd.DataFrame) -> pd.DataFrame:
    """Compute marginal score lift per feature from a factorial leaderboard slice."""
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
    return pd.DataFrame(gains)


def bar_color(vals):
    return ["#4dac26" if v >= 0 else "#d01c8b" for v in vals]


def badge(val, positive, bg_pos="#15803d", bg_neg="#9d174d"):
    bg = bg_pos if positive else bg_neg
    return (
        f'<span style="background:{bg};color:#ffffff;padding:1px 7px;'
        f'border-radius:9999px;font-size:0.85em;font-weight:600;">{val}</span>'
    )


# ---------------------------------------------------------------------------
# For Snowhouse: load all shared data once up front
# ---------------------------------------------------------------------------
if ENV != "devrel":
    _lb_snow = run_query("SELECT * FROM V_AEO_LEADERBOARD ORDER BY SCORE_PCT DESC")
    _lb_snow["Config"] = _lb_snow.apply(
        lambda r: config_label(r.DOMAIN_PROMPT, r.CITATION, r.AGENTIC, r.SELF_CRITIQUE), axis=1
    )
    _lb_factorial_snow = _lb_snow[_lb_snow["MODEL"] == "claude-opus-4-6"].copy()
    _gain_df_snow = compute_gains(_lb_factorial_snow)
    _effects_snow = run_query("SELECT * FROM V_AEO_FACTORIAL_EFFECTS")

    _dim_df_snow = run_query("""
        SELECT q.QUESTION_ID, q.QUESTION_TEXT, q.CATEGORY, q.QUESTION_TYPE,
               h.RUN_ID, h.DOMAIN_PROMPT, h.CITATION, h.AGENTIC, h.SELF_CRITIQUE,
               rc.MODEL,
               h.TOTAL_SCORE, h.MUST_HAVE_PASS,
               h.CORRECTNESS, h.COMPLETENESS, h.RECENCY, h.CITATION_SCORE, h.RECOMMENDATION
        FROM V_AEO_PER_QUESTION_HEATMAP h
        JOIN AEO_QUESTIONS q   ON h.QUESTION_ID = q.QUESTION_ID
        JOIN (SELECT DISTINCT RUN_ID, MODEL FROM AEO_RUN_CONFIG) rc ON h.RUN_ID = rc.RUN_ID
        ORDER BY h.RUN_ID, q.QUESTION_ID
    """)
    _dim_df_snow["Config"]  = _dim_df_snow.apply(
        lambda r: config_label(r.DOMAIN_PROMPT, r.CITATION, r.AGENTIC, r.SELF_CRITIQUE), axis=1
    )
    _dim_df_snow["Score %"] = (_dim_df_snow["TOTAL_SCORE"] / 50.0 * 100).round(1)


# ===========================================================================
# Section 1 — Main Effects
# ===========================================================================
st.header(":material/insights: Main Effects")
st.caption(
    "Average marginal effect of each factor across all 8 paired comparisons "
    "(ON minus OFF), in percentage points. Error bars = ±1 SE (8 paired contrasts)."
)

if ENV == "devrel":
    _label_me, _model_me = model_selector("fi_main_effects")
    lb_factorial_me = load_lb_for_model(_model_me)
    effects_me = []
    for col, lbl in FEATURES:
        on_score  = lb_factorial_me[lb_factorial_me[col] == True]["SCORE_PCT"].mean()
        off_score = lb_factorial_me[lb_factorial_me[col] == False]["SCORE_PCT"].mean()
        on_mh     = lb_factorial_me[lb_factorial_me[col] == True]["MH_PCT"].mean()
        off_mh    = lb_factorial_me[lb_factorial_me[col] == False]["MH_PCT"].mean()
        effects_me.append({
            "FACTOR":          lbl,
            "SCORE_EFFECT_PP": round(on_score - off_score, 1),
            "MH_EFFECT_PP":    round(on_mh - off_mh, 1),
        })
    df_me = pd.DataFrame(effects_me)
else:
    lb_factorial_me = _lb_factorial_snow
    df_me = _effects_snow.copy()

df_me = df_me.sort_values("SCORE_EFFECT_PP", ascending=False).reset_index(drop=True)
label_to_col = {lbl: col for col, lbl in FEATURES}
score_se_me = [compute_effect_se(lb_factorial_me, label_to_col[f], "SCORE_PCT") for f in df_me["FACTOR"]]
mh_se_me    = [compute_effect_se(lb_factorial_me, label_to_col[f], "MH_PCT")    for f in df_me["FACTOR"]]

fig_me = go.Figure()
fig_me.add_trace(go.Bar(
    name="Score effect (pp)",
    y=df_me["FACTOR"],
    x=df_me["SCORE_EFFECT_PP"],
    orientation="h",
    marker_color=bar_color(df_me["SCORE_EFFECT_PP"]),
    text=df_me["SCORE_EFFECT_PP"].map(lambda v: f"{v:+.1f}pp"),
    textposition="outside",
    width=0.35,
    offset=-0.2,
    error_x=dict(type="data", array=score_se_me, visible=True,
                 color="rgba(0,0,0,0.55)", thickness=1.5, width=5),
))
fig_me.add_trace(go.Bar(
    name="Must-Have effect (pp)",
    y=df_me["FACTOR"],
    x=df_me["MH_EFFECT_PP"],
    orientation="h",
    marker_color=bar_color(df_me["MH_EFFECT_PP"]),
    opacity=0.5,
    text=df_me["MH_EFFECT_PP"].map(lambda v: f"{v:+.1f}pp"),
    textposition="outside",
    width=0.35,
    offset=0.2,
    error_x=dict(type="data", array=mh_se_me, visible=True,
                 color="rgba(0,0,0,0.55)", thickness=1.5, width=5),
))
x_lim_me = max(
    abs(df_me["SCORE_EFFECT_PP"].max()), abs(df_me["MH_EFFECT_PP"].max()),
    abs(df_me["SCORE_EFFECT_PP"].min()), abs(df_me["MH_EFFECT_PP"].min()),
) + 3
fig_me.add_vline(x=0, line_color="black", line_width=1)
fig_me.update_layout(
    barmode="overlay",
    xaxis_title="Effect (percentage points)",
    yaxis_title="",
    xaxis_range=[-x_lim_me, x_lim_me],
    height=500,
    margin=dict(t=20, b=60),
    template="plotly_white",
    legend=dict(orientation="h", y=-0.18, x=0.5, xanchor="center"),
)

col_me, col_me_text = st.columns([2, 1])
with col_me:
    st.plotly_chart(fig_me, use_container_width=True)

with col_me_text:
    st.subheader(":material/lightbulb: Key Insights")
    _row_me = {r["FACTOR"]: r for _, r in df_me.iterrows()}
    _g = lambda f, k: _row_me[f][k] if f in _row_me else 0.0

    _ag_score = _g("Agentic",      "SCORE_EFFECT_PP")
    _ag_mh    = _g("Agentic",      "MH_EFFECT_PP")
    _ci_score = _g("Citation",     "SCORE_EFFECT_PP")
    _ci_mh    = _g("Citation",     "MH_EFFECT_PP")
    _dp_score = _g("Domain Prompt","SCORE_EFFECT_PP")
    _dp_mh    = _g("Domain Prompt","MH_EFFECT_PP")
    _sc_score = _g("Self-Critique","SCORE_EFFECT_PP")
    _sc_mh    = _g("Self-Critique","MH_EFFECT_PP")

    st.markdown(
        f"""
        <p><strong>Agentic tools.</strong> Enabling tool access lifts Score by
        {badge(f"{_ag_score:+.1f}pp", _ag_score >= 0)} and Must-Have compliance by
        {badge(f"{_ag_mh:+.1f}pp", _ag_mh >= 0)}.</p>

        <p><strong>Citation.</strong> Score lift is
        {badge(f"{_ci_score:+.1f}pp", _ci_score >= 0)}, Must-Have lift is
        {badge(f"{_ci_mh:+.1f}pp", _ci_mh >= 0)}.</p>

        <p><strong>Domain Prompt.</strong> Score lift is
        {badge(f"{_dp_score:+.1f}pp", _dp_score >= 0)}, Must-Have lift is
        {badge(f"{_dp_mh:+.1f}pp", _dp_mh >= 0)}.</p>

        <p><strong>Self-Critique.</strong> Score lift is
        {badge(f"{_sc_score:+.1f}pp", _sc_score >= 0)}, Must-Have lift is
        {badge(f"{_sc_mh:+.1f}pp", _sc_mh >= 0)}.</p>
        """,
        unsafe_allow_html=True,
    )


# ===========================================================================
# Section 2 — Score Lift by Feature
# ===========================================================================
st.divider()
st.header(":material/show_chart: Score Lift by Feature")
st.caption("Marginal score lift from each configuration feature and their interactions.")

if ENV == "devrel":
    _label_sl, _model_sl = model_selector("fi_score_lift")
    lb_factorial_sl = load_lb_for_model(_model_sl)
else:
    lb_factorial_sl = _lb_factorial_snow

gain_df_sl = compute_gains(lb_factorial_sl)

col_sl, col_sl_text = st.columns([2, 1])
with col_sl:
    colors_sl = ["#22d3ee" if g >= 0 else "#fd3db5" for g in gain_df_sl["Score Lift (pp)"]]
    fig_sl = go.Figure(go.Bar(
        x=gain_df_sl["Feature"],
        y=gain_df_sl["Score Lift (pp)"],
        marker_color=colors_sl,
        text=[f"{v:+.1f}pp" for v in gain_df_sl["Score Lift (pp)"]],
        textposition="outside",
        textfont=dict(color="#ffffff"),
    ))
    fig_sl.add_hline(y=0, line_color="#555555")
    fig_sl.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        yaxis=dict(title="Score lift (pp)", gridcolor="#333333", color="#cccccc"),
        height=500,
        margin=dict(t=20),
    )
    st.plotly_chart(fig_sl, use_container_width=True)

with col_sl_text:
    st.subheader(":material/lightbulb: Key Insights")
    best_feat  = gain_df_sl.loc[gain_df_sl["Score Lift (pp)"].idxmax()]
    worst_feat = gain_df_sl.loc[gain_df_sl["Score Lift (pp)"].idxmin()]
    st.markdown(
        f"""
        <p><strong>{best_feat['Feature']}</strong> delivers the highest marginal
        score lift at {badge(f"+{best_feat['Score Lift (pp)']:.1f}pp", True)} on average across all 16 configurations.</p>

        <p><strong>{worst_feat['Feature']}</strong> shows the smallest lift at
        {badge(f"{worst_feat['Score Lift (pp)']:+.1f}pp", worst_feat['Score Lift (pp)'] >= 0)},
        suggesting diminishing returns or interference with other features.</p>

        <p>Positive bars mean the feature consistently improves scores when
        enabled. Negative bars indicate it may hurt performance in certain
        configuration combinations.</p>
        """,
        unsafe_allow_html=True,
    )


# ===========================================================================
# Section 3 — Factor Interaction Heatmap
# ===========================================================================
st.divider()
st.header(":material/grid_on: Factor Interaction Heatmap")
st.caption(
    "Synergy (pp): the extra score lift when both features are ON together, "
    "beyond what their individual main effects would predict. "
    "Positive means the pair works better in combination than expected. "
    "Diagonal cells are blank (self-pairs are not meaningful)."
)

if ENV == "devrel":
    _label_fi, _model_fi = model_selector("fi_interaction")
    lb_factorial_fi = load_lb_for_model(_model_fi)
else:
    lb_factorial_fi = _lb_factorial_snow

gain_df_fi = compute_gains(lb_factorial_fi)

feat_cols  = [f[0] for f in FEATURES]
feat_names = [f[1] for f in FEATURES]
n = len(FEATURES)

baseline_mask = (
    (lb_factorial_fi["DOMAIN_PROMPT"] == False) & (lb_factorial_fi["CITATION"] == False) &
    (lb_factorial_fi["AGENTIC"] == False)        & (lb_factorial_fi["SELF_CRITIQUE"] == False)
)
baseline_score = lb_factorial_fi[baseline_mask]["SCORE_PCT"].mean()

matrix = [[float("nan")] * n for _ in range(n)]
text   = [[""] * n for _ in range(n)]
pairs  = []

for i in range(n):
    for j in range(i + 1, n):
        fi_col, fj_col = feat_cols[i], feat_cols[j]
        both        = lb_factorial_fi[(lb_factorial_fi[fi_col] == True) & (lb_factorial_fi[fj_col] == True)]["SCORE_PCT"].mean()
        ind_i       = gain_df_fi[gain_df_fi["col"] == fi_col]["Score Lift (pp)"].values[0]
        ind_j       = gain_df_fi[gain_df_fi["col"] == fj_col]["Score Lift (pp)"].values[0]
        actual_lift = both - baseline_score
        synergy     = round(actual_lift - (ind_i + ind_j), 1)
        matrix[i][j] = synergy
        matrix[j][i] = synergy
        text[i][j]   = f"{synergy:+.1f}pp"
        text[j][i]   = f"{synergy:+.1f}pp"
        pairs.append({
            "pair": f"{feat_names[i]} + {feat_names[j]}",
            "synergy": synergy,
            "ind_i": ind_i, "ind_j": ind_j,
            "actual_lift": round(actual_lift, 1),
        })

pairs_df   = pd.DataFrame(pairs).sort_values("synergy", ascending=False).reset_index(drop=True)
best_pair  = pairs_df.iloc[0]
worst_pair = pairs_df.iloc[-1]

z = np.array(matrix, dtype=float)
abs_max = float(max(abs(np.nanmin(z)), abs(np.nanmax(z))))

fig_hm = go.Figure(go.Heatmap(
    z=z,
    x=feat_names,
    y=feat_names,
    text=text,
    texttemplate="%{text}",
    colorscale=[[0.0, "#fd3db5"], [0.5, "#111827"], [1.0, "#22d3ee"]],
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
    best_expected  = round(best_pair["ind_i"] + best_pair["ind_j"], 1)
    worst_expected = round(worst_pair["ind_i"] + worst_pair["ind_j"], 1)
    st.markdown(
        f"""
        <p><strong>Strongest synergy: {best_pair['pair']}.</strong>
        Their individual effects predict {badge(f"{best_expected:+.1f}pp", best_expected >= 0)},
        but together they deliver {badge(f"{best_pair['actual_lift']:+.1f}pp", best_pair['actual_lift'] >= 0)},
        a synergy of {badge(f"{best_pair['synergy']:+.1f}pp", best_pair['synergy'] >= 0)}.
        They amplify each other beyond what either contributes alone.</p>

        <p><strong>Weakest synergy: {worst_pair['pair']}.</strong>
        Expected {badge(f"{worst_expected:+.1f}pp", worst_expected >= 0)},
        actual {badge(f"{worst_pair['actual_lift']:+.1f}pp", worst_pair['actual_lift'] >= 0)},
        synergy {badge(f"{worst_pair['synergy']:+.1f}pp", worst_pair['synergy'] >= 0)}.
        Each feature largely delivers its benefit independently with little extra from pairing.</p>

        <p>A high synergy value does not mean either feature is individually strong.
        It means the combination produces more than a naive sum would predict.</p>
        """,
        unsafe_allow_html=True,
    )


# ===========================================================================
# Section 4 — Dimension Breakdown by Question
# ===========================================================================
st.divider()
st.header("Dimension Breakdown by Question")

if ENV == "devrel":
    _label_db, _model_db = model_selector("fi_dim_breakdown")
    dim_df = run_query(v3_per_question_sql(_model_db))
    q_meta = run_query(
        "SELECT QUESTION_ID, QUESTION_TEXT, CATEGORY, QUESTION_TYPE FROM AEO_QUESTIONS"
    )
    dim_df = dim_df.merge(q_meta, on="QUESTION_ID", how="left")
else:
    dim_df = _dim_df_snow.copy()

dim_df["Config"]  = dim_df.apply(
    lambda r: config_label(r.DOMAIN_PROMPT, r.CITATION, r.AGENTIC, r.SELF_CRITIQUE), axis=1
)
dim_df["Score %"] = (dim_df["TOTAL_SCORE"] / 50.0 * 100).round(1)

q_options = sorted(dim_df["QUESTION_ID"].unique())
sel_q = st.selectbox("Select a question to inspect", q_options)

q_df = dim_df[dim_df["QUESTION_ID"] == sel_q]
if not q_df.empty:
    q_text = q_df.iloc[0]["QUESTION_TEXT"]
    st.markdown(f"**{sel_q}**: {q_text}")

    fig_dim = go.Figure()
    dims_radar = ["Correctness", "Completeness", "Recency", "Citation", "Recommendation"]
    dim_cols   = ["CORRECTNESS", "COMPLETENESS", "RECENCY", "CITATION_SCORE", "RECOMMENDATION"]
    for _, row in q_df.iterrows():
        vals = [row[c] for c in dim_cols]
        fig_dim.add_trace(go.Scatterpolar(
            r=vals + [vals[0]],
            theta=dims_radar + [dims_radar[0]],
            fill="toself",
            name=row["Config"],
            opacity=0.7,
        ))
    fig_dim.update_layout(
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

    col_radar, col_radar_text = st.columns([2, 1])

    with col_radar:
        st.plotly_chart(fig_dim, use_container_width=True)

    with col_radar_text:
        st.subheader(":material/lightbulb: Key Insights")

        q_category = q_df.iloc[0]["CATEGORY"]
        q_type     = q_df.iloc[0]["QUESTION_TYPE"]
        n_configs  = len(q_df)

        best_row  = q_df.loc[q_df["Score %"].idxmax()]
        worst_row = q_df.loc[q_df["Score %"].idxmin()]
        score_gap = best_row["Score %"] - worst_row["Score %"]

        dim_means = q_df[dim_cols].mean()
        best_dim  = dims_radar[dim_means.argmax()]
        worst_dim = dims_radar[dim_means.argmin()]

        _best_score_badge  = badge(f"{best_row['Score %']:.1f}%", True)
        _worst_score_badge = badge(f"{worst_row['Score %']:.1f}%", False)
        _gap_badge         = badge(f"+{score_gap:.1f}pp", True)

        if n_configs > 1:
            comparison = (
                f"<p><strong>{best_row['Config']} performs best</strong> on this question "
                f"with a score of {_best_score_badge}, compared to "
                f"{_worst_score_badge} for {worst_row['Config']}, "
                f"a gap of {_gap_badge}.</p>"
            )
        else:
            comparison = (
                f"<p>Only one configuration is selected. "
                f"<strong>{best_row['Config']}</strong> scores "
                f"{_best_score_badge} on this question.</p>"
            )

        st.markdown(
            f"""
            <p>A <strong>{q_type}</strong> question in
            <strong>{q_category}</strong>.</p>

            {comparison}

            <p><strong>{best_dim} is the strongest dimension</strong> on average
            across the selected configurations for this question.</p>

            <p><strong>{worst_dim} is the weakest dimension,</strong> suggesting
            this question challenges the model on that criterion regardless of
            configuration.</p>
            """,
            unsafe_allow_html=True,
        )

    # --- Per-config scores table ---
    table_cols = ["Config"]
    if "MODEL" in q_df.columns:
        table_cols.append("MODEL")
    table_cols += ["Score %"] + dim_cols

    ranked = q_df.sort_values("Score %", ascending=False)[table_cols].rename(columns={
        "MODEL":         "Model",
        "CORRECTNESS":   "Correctness",
        "COMPLETENESS":  "Completeness",
        "RECENCY":       "Recency",
        "CITATION_SCORE":"Citation",
        "RECOMMENDATION":"Recommendation",
    }).reset_index(drop=True)

    st.dataframe(
        ranked,
        column_config={
            "Score %":       st.column_config.ProgressColumn("Score %",       format="%.1f%%", min_value=0, max_value=100),
            "Correctness":   st.column_config.ProgressColumn("Correctness",   format="%.1f",   min_value=0, max_value=10),
            "Completeness":  st.column_config.ProgressColumn("Completeness",  format="%.1f",   min_value=0, max_value=10),
            "Recency":       st.column_config.ProgressColumn("Recency",       format="%.1f",   min_value=0, max_value=10),
            "Citation":      st.column_config.ProgressColumn("Citation",      format="%.1f",   min_value=0, max_value=10),
            "Recommendation":st.column_config.ProgressColumn("Recommendation",format="%.1f",   min_value=0, max_value=10),
        },
        use_container_width=True,
        hide_index=True,
    )
