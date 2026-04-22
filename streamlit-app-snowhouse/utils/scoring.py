"""Scoring helpers for the AEO PM Tools pages.

Wraps CORTEX.COMPLETE for response generation and the 3-judge scoring panel
from aeo_feedback_functions.  All calls go through the Snowpark session
returned by utils.db.get_session().

Local vs SiS behaviour
----------------------
  SiS  (Snowhouse / DevRel): bank questions use the AEO_SCORE_RESPONSE stored
         procedure for a single round-trip; custom questions use the
         aeo_feedback_functions UDF package.
  Local: both paths fall back to _score_full_rubric_local, which calls
         SNOWFLAKE.CORTEX.COMPLETE directly through the active Snowpark session.
"""

import json
import re
from typing import Dict, List, Optional

import streamlit as st
import pandas as pd

from utils.db import get_session, run_query, is_sis, DB, SCH  # noqa: E402

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
# Local scoring fallback
# ---------------------------------------------------------------------------


def _score_full_rubric_local(
    session,
    judge: str,
    question: str,
    response: str,
    canonical_answer: str,
    must_haves: List[str],
) -> Dict:
    """Local equivalent of aeo_feedback_functions.score_full_rubric.

    Calls SNOWFLAKE.CORTEX.COMPLETE directly instead of the SiS UDF package.
    Used when running outside SiS (local dev).
    """
    active_mh = [m for m in (must_haves or []) if m and m.strip()]

    mh_section = ""
    if active_mh:
        mh_list = "\n".join(f"{i + 1}. {mh}" for i, mh in enumerate(active_mh))
        mh_section = f"\n\nMust-have criteria to check:\n{mh_list}"

    mh_field = (
        f',\n  "must_have": [<true or false for each of the {len(active_mh)} criteria above, in order>]'
        if active_mh else ""
    )

    scoring_prompt = (
        f"You are an expert evaluator scoring an AI assistant's response to a "
        f"Snowflake developer question.\n\n"
        f"Question: {question}\n\n"
        f"Canonical answer (ground truth): {canonical_answer or 'Not provided'}"
        f"{mh_section}\n\n"
        f"Response to evaluate:\n{response}\n\n"
        f"Score on each dimension from 1 to 10:\n"
        f"  correctness  — factual accuracy vs the canonical answer\n"
        f"  completeness — coverage of all important aspects\n"
        f"  recency      — use of current APIs and up-to-date information\n"
        f"  citation     — references to documentation or sources\n"
        f"  recommendation — actionable and specific guidance\n\n"
        f"Return ONLY valid JSON (no markdown, no commentary):\n"
        f'{{\n'
        f'  "correctness": <1-10>,\n'
        f'  "completeness": <1-10>,\n'
        f'  "recency": <1-10>,\n'
        f'  "citation": <1-10>,\n'
        f'  "recommendation": <1-10>'
        f'{mh_field}\n}}'
    )

    messages_json = json.dumps([{"role": "user", "content": scoring_prompt}])
    options_json = json.dumps({"max_tokens": 512, "temperature": 0.0})

    sql = "SELECT SNOWFLAKE.CORTEX.COMPLETE(?, PARSE_JSON(?), PARSE_JSON(?)) AS response"
    result = session.sql(sql, params=[judge, messages_json, options_json]).collect()
    raw = result[0]["RESPONSE"] if result else ""

    try:
        if isinstance(raw, str):
            resp = json.loads(raw)
        else:
            resp = raw

        if isinstance(resp, dict) and "choices" in resp:
            content = resp["choices"][0].get("messages", "")
        elif isinstance(resp, dict) and "messages" in resp:
            content = resp["messages"]
        else:
            content = str(resp)

        # Extract the first JSON object from the content
        m = re.search(r'\{[^{}]*\}', content, re.DOTALL)
        scores_raw = json.loads(m.group() if m else content)

        dims = ["correctness", "completeness", "recency", "citation", "recommendation"]
        scores = {d: float(scores_raw.get(d, 5)) for d in dims}

        mh_vals = scores_raw.get("must_have", [])
        mh_bools = [bool(v) for v in mh_vals]
        while len(mh_bools) < 5:
            mh_bools.append(False)

        scores["total"] = sum(scores[d] for d in dims)
        scores["must_have"] = mh_bools
        scores["must_have_pass"] = (
            sum(1 for v in mh_vals if v) / len(mh_vals) if mh_vals else 0.0
        )
        return scores

    except Exception as exc:
        return {
            "correctness": 0, "completeness": 0, "recency": 0,
            "citation": 0, "recommendation": 0,
            "must_have": [False] * 5,
            "total": 0, "must_have_pass": 0.0,
            "error": f"Scoring parse error: {exc}",
        }


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
    """Score a response using the judge panel.

    SiS + bank question : delegates to the AEO_SCORE_RESPONSE stored procedure
                          (single Snowflake round-trip).
    SiS + custom question: uses aeo_feedback_functions.score_full_rubric UDF.
    Local (any question) : uses _score_full_rubric_local via CORTEX.COMPLETE.

    If *progress_callback* is provided it is called after each judge with
    (judge_index, judge_name) so the caller can update a progress bar.

    Returns {judges: {...}, panel_avg: {...}}
    """
    effective_judges = list(judges) if judges else list(JUDGE_PANEL)
    in_sis = is_sis()

    if question_id and in_sis:
        # SP path: one round-trip, all judges run inside Snowflake (SiS only)
        result = session.sql(
            f"CALL {DB}.{SCH}.AEO_SCORE_RESPONSE(?, ?, NULL, NULL)",
            params=[question_id, response],
        ).collect()
        data = result[0][0] if result else {}
        if isinstance(data, str):
            data = json.loads(data)
        for idx, judge in enumerate(effective_judges):
            if progress_callback:
                progress_callback(idx, judge)
        return {
            "judges":    data.get("judges", {}),
            "panel_avg": data.get("panel_avg", {}),
        }

    # Per-judge loop — custom questions in SiS, or all questions locally
    if in_sis:
        from aeo_feedback_functions import score_full_rubric as _score_fn
    else:
        _score_fn = None  # use _score_full_rubric_local below

    all_scores = {}
    for idx, judge in enumerate(effective_judges):
        try:
            if in_sis:
                scores = _score_fn(
                    session, judge, question, response,
                    canonical_answer, must_haves,
                )
            else:
                scores = _score_full_rubric_local(
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
