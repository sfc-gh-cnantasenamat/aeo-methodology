"""AEO Benchmark — Home page."""
import streamlit as st
from utils.db import run_query

st.title(":material/query_stats: AEO Benchmark")
st.markdown("*Building an AI Engine Optimization (AEO) system for measuring how well LLMs answer Snowflake developer questions*")

st.divider()

# ── Live stats ────────────────────────────────────────────────────────────────
stats = run_query("""
    SELECT
        (SELECT COUNT(*)          FROM AEO_RUNS)                    AS total_runs,
        (SELECT COUNT(*)          FROM AEO_QUESTIONS)               AS total_questions,
        (SELECT COUNT(DISTINCT CATEGORY) FROM AEO_QUESTIONS)        AS total_categories,
        (SELECT COUNT(*)          FROM AEO_RESPONSES)               AS total_responses,
        (SELECT COUNT(*)          FROM AEO_SCORES)                  AS total_scores,
        (SELECT REPLACE(MIN(MODEL), 'claude-', '') FROM AEO_RUNS)    AS model_name,
        (SELECT TO_CHAR(MIN(RUN_DATE), 'Mon DD, YYYY') FROM AEO_RUNS) AS first_run,
        (SELECT TO_CHAR(MAX(RUN_DATE), 'Mon DD, YYYY') FROM AEO_RUNS) AS last_run
""")
s = stats.iloc[0]

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Runs",        int(s["TOTAL_RUNS"]))
c2.metric("Questions",   int(s["TOTAL_QUESTIONS"]))
c3.metric("Categories",  int(s["TOTAL_CATEGORIES"]))
c4.metric("Responses",   f'{int(s["TOTAL_RESPONSES"]):,}')
c5.metric("Judge Scores",f'{int(s["TOTAL_SCORES"]):,}')
c6.metric("Model",       s["MODEL_NAME"])

st.divider()

# ── 5W + H ────────────────────────────────────────────────────────────────────
col_left, col_right = st.columns(2, gap="large")

with col_left:
    st.subheader(":orange[:material/group:] Who")
    st.markdown(
        "The **Snowflake Developer Relations** team built AEO to evaluate "
        "AI-powered answer quality across Snowflake's product surface. "
        "A panel of **3 LLM judges** scores every response, removing "
        "single-model bias."
    )

    st.subheader(":orange[:material/science:] What")
    st.markdown(
        "AEO is a **2⁴ factorial benchmark** that tests every combination "
        "of four binary configuration flags:\n\n"
        "| Flag | Meaning |\n"
        "|---|---|\n"
        "| **D** — Domain Prompt | Inject a Snowflake-specific system prompt |\n"
        "| **C** — Citation | Require the agent to cite documentation |\n"
        "| **A** — Agentic | Use **Cortex Code** for multi-step agentic retrieval |\n"
        "| **S** — Self-Critique | Add a self-critique refinement pass |\n\n"
        f"This yields **16 configurations** tested against "
        f"**{int(s['TOTAL_QUESTIONS'])} expert-curated questions** "
        f"across **{int(s['TOTAL_CATEGORIES'])} Snowflake topic categories**. "
        "Half the runs (A=TRUE) invoke **native Cortex Code** for retrieval; "
        "the other half call `SNOWFLAKE.CORTEX.COMPLETE` directly."
    )

    st.subheader(":orange[:material/lightbulb:] Why")
    st.markdown(
        "Improving answer quality matters for developer trust. "
        "AEO quantifies the **marginal gain** of each configuration feature "
        "so teams can make evidence-based decisions about which LLM prompting "
        "strategies are worth the added latency and cost."
    )

with col_right:
    st.subheader(":orange[:material/calendar_today:] When")
    st.markdown(
        f"Benchmark runs were collected between "
        f"**{s['FIRST_RUN']}** and **{s['LAST_RUN']}**. "
        f"Each of the **{int(s['TOTAL_RUNS'])} runs** corresponds to one "
        f"unique configuration, run in full against all questions."
    )

    st.subheader(":orange[:material/location_on:] Where")
    st.markdown(
        "Everything runs natively inside **Snowflake**:\n\n"
        "- Questions, responses, and scores are stored in `DEVREL.CNANTASENAMAT_DEV`\n"
        "- Benchmark execution uses **Snowflake Task DAGs** and stored procedures\n"
        "- Scoring uses **Cortex LLM functions** (`SNOWFLAKE.CORTEX.COMPLETE`)\n"
        "- This dashboard is a **Streamlit in Snowflake** app"
    )

    st.subheader(":orange[:material/engineering:] How")
    st.markdown(
        "For each configuration:\n\n"
        f"1. Send all **{int(s['TOTAL_QUESTIONS'])} questions** to the agent\n"
        "2. Collect the raw text response — via **native Cortex Code** (agentic runs) "
        "or direct `SNOWFLAKE.CORTEX.COMPLETE` API (non-agentic runs)\n"
        "3. Score each response with **3 independent LLM judges** "
        f"→ {int(s['TOTAL_SCORES']):,} scores total\n"
        "4. Average judge scores to get a per-question, per-run score\n"
        "5. Aggregate across questions to compare configurations\n\n"
        "Use the **Leaderboard** and **Main Effects** pages to explore results."
    )
