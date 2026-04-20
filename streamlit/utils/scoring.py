"""Scoring helpers for the AEO PM Tools pages.

Wraps CORTEX.COMPLETE for response generation and the 3-judge scoring panel
from aeo_feedback_functions.  All calls go through the Snowpark session
returned by utils.db.get_session().
"""

import json
from typing import Dict, List, Optional

import streamlit as st
import pandas as pd

from utils.db import get_session, run_query  # noqa: E402

# Judge panel — mirrors aeo_feedback_functions.JUDGE_PANEL
JUDGE_PANEL = [
    "claude-opus-4-6",
    "claude-opus-4-7",
    "openai-gpt-5.4",
    "llama4-maverick",
    "gemini-3.1-pro",
]

# ---------------------------------------------------------------------------
# Response generation
# ---------------------------------------------------------------------------

DEFAULT_MODEL = "claude-opus-4-6"


def generate_response(
    session,
    question: str,
    system_prompt: str = "",
    model: str = DEFAULT_MODEL,
    max_tokens: int = 4096,
) -> str:
    """Generate a response via CORTEX.COMPLETE with an optional system prompt.

    Returns the plain-text response.
    """
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": question})

    messages_json = json.dumps(messages)
    options_json = json.dumps({"max_tokens": max_tokens, "temperature": 0.0})

    sql = (
        "SELECT SNOWFLAKE.CORTEX.COMPLETE(?, PARSE_JSON(?), PARSE_JSON(?)) "
        "AS response"
    )
    result = session.sql(sql, params=[model, messages_json, options_json]).collect()
    raw = result[0]["RESPONSE"] if result else ""

    # Parse the COMPLETE response envelope
    if isinstance(raw, str):
        try:
            resp = json.loads(raw)
        except json.JSONDecodeError:
            return raw
    else:
        resp = raw

    if isinstance(resp, dict):
        if "choices" in resp:
            return resp["choices"][0].get("messages", str(resp))
        if "messages" in resp:
            return resp["messages"]
    return str(resp)


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def score_response(
    session,
    question: str,
    response: str,
    canonical_answer: str,
    must_haves: List[str],
    judges: Optional[List[str]] = None,
    progress_callback=None,
    question_id: Optional[str] = None,
) -> Dict:
    """Score a response using the 4-judge panel.

    When *question_id* is provided (bank questions), delegates to the
    AEO_SCORE_RESPONSE stored procedure for a single Snowflake round-trip.
    For custom questions (question_id=None), falls back to the per-judge
    Python loop so progress callbacks still fire after each judge.

    If *progress_callback* is provided it is called after each judge with
    (judge_index, judge_name) so the caller can update a progress bar.

    Returns {judges: {...}, panel_avg: {...}}
    """
    effective_judges = list(judges) if judges else list(JUDGE_PANEL)

    if question_id:
        # SP path: one round-trip, all 4 judges run inside Snowflake
        result = session.sql(
            "CALL DEVREL.CNANTASENAMAT_DEV.AEO_SCORE_RESPONSE(?, ?, NULL, NULL)",
            params=[question_id, response],
        ).collect()
        data = result[0][0] if result else {}
        if isinstance(data, str):
            data = json.loads(data)
        # Fire callbacks post-hoc so the progress bar stays accurate
        for idx, judge in enumerate(effective_judges):
            if progress_callback:
                progress_callback(idx, judge)
        return {
            "judges":    data.get("judges", {}),
            "panel_avg": data.get("panel_avg", {}),
        }

    # Fallback: per-judge loop for custom questions
    from aeo_feedback_functions import score_full_rubric

    all_scores = {}
    for idx, judge in enumerate(effective_judges):
        try:
            scores = score_full_rubric(
                session, judge, question, response,
                canonical_answer, must_haves,
            )
            all_scores[judge] = scores
        except Exception as e:
            all_scores[judge] = {
                "correctness": 0, "completeness": 0, "recency": 0,
                "citation": 0, "recommendation": 0,
                "must_have": [False] * 5,
                "total": 0, "must_have_pass": 0.0,
                "error": str(e),
            }
        if progress_callback:
            progress_callback(idx, judge)

    n = len(all_scores)
    if n == 0:
        return {"judges": {}, "panel_avg": {}}

    avg = {
        dim: sum(s[dim] for s in all_scores.values()) / n
        for dim in [
            "correctness", "completeness", "recency",
            "citation", "recommendation", "total", "must_have_pass",
        ]
    }

    return {"judges": all_scores, "panel_avg": avg}


# ---------------------------------------------------------------------------
# Baseline lookup
# ---------------------------------------------------------------------------


@st.cache_data(ttl=600)
def get_baseline_scores(question_id: str) -> Optional[Dict]:
    """Return baseline (run_id=1) scores for a question from the heatmap view.

    Returns a dict with keys matching panel_avg (correctness, completeness, …)
    or None if no baseline exists.
    """
    df = run_query(f"""
        SELECT CORRECTNESS, COMPLETENESS, RECENCY, CITATION_SCORE,
               RECOMMENDATION, TOTAL_SCORE, MUST_HAVE_PASS
        FROM V_AEO_PER_QUESTION_HEATMAP
        WHERE QUESTION_ID = '{question_id}'
          AND RUN_ID = 1
    """)
    if df.empty:
        return None

    row = df.iloc[0]
    return {
        "correctness": float(row["CORRECTNESS"]),
        "completeness": float(row["COMPLETENESS"]),
        "recency": float(row["RECENCY"]),
        "citation": float(row["CITATION_SCORE"]),
        "recommendation": float(row["RECOMMENDATION"]),
        "total": float(row["TOTAL_SCORE"]),
        "must_have_pass": float(row["MUST_HAVE_PASS"]),
    }


# ---------------------------------------------------------------------------
# Question bank
# ---------------------------------------------------------------------------


@st.cache_data(ttl=600)
def load_question_bank() -> pd.DataFrame:
    """Load all questions with canonical answers and must-haves."""
    return run_query("""
        SELECT QUESTION_ID, QUESTION_TEXT, CATEGORY, QUESTION_TYPE,
               CANONICAL_ANSWER, MUST_HAVE_1, MUST_HAVE_2, MUST_HAVE_3,
               MUST_HAVE_4, MUST_HAVE_5
        FROM AEO_QUESTIONS
        ORDER BY QUESTION_ID
    """)
