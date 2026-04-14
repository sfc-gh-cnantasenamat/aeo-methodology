"""Page 1 — Leaderboard: 16-run rankings table."""
import streamlit as st
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
display["Engine"] = display["Engine"].apply(lambda x: [x])
display["Config"] = display["Config"].apply(lambda x: [x])

st.dataframe(
    display,
    column_config={
        "Config": st.column_config.MultiselectColumn(
            "Config",
            options=sorted(df.apply(
                lambda r: config_label(r.DOMAIN_PROMPT, r.CITATION, r.AGENTIC, r.SELF_CRITIQUE), axis=1
            ).unique().tolist()),
            color="#fef08a",
        ),
        "Engine": st.column_config.MultiselectColumn(
            "Engine",
            options=["Agentic", "Non-Agentic"],
            color=["#c084fc", "#f87171"],  # pastel purple, pastel red
        ),
        "Score %": st.column_config.ProgressColumn(
            "Score %",
            format="%.1f%%",
            min_value=0,
            max_value=100,
            color="auto",
        ),
        "MH %": st.column_config.ProgressColumn(
            "MH %",
            format="%.1f%%",
            min_value=0,
            max_value=100,
            color="auto",
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
