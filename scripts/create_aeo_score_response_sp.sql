-- ============================================================================
-- AEO_SCORE_RESPONSE  —  Snowpark stored procedure
--
-- Scores a response against AEO_QUESTIONS using the multi-judge panel.
-- Self-contained: all scoring logic is inlined so no external imports
-- are needed inside Snowflake.
--
-- Usage:
--   CALL DEVREL.CNANTASENAMAT_DEV.AEO_SCORE_RESPONSE(
--       'Q001',             -- QUESTION_ID  (must exist in AEO_QUESTIONS)
--       '<response text>',  -- RESPONSE_TEXT to evaluate
--       NULL,               -- SYSTEM_PROMPT (stored for reference, not used in scoring)
--       NULL                -- JUDGES array, NULL = default 4-judge panel
--   );
--
-- Custom judge subset example:
--   CALL DEVREL.CNANTASENAMAT_DEV.AEO_SCORE_RESPONSE(
--       'Q001', '<response>', NULL,
--       ARRAY_CONSTRUCT('claude-opus-4-6', 'gemini-3.1-pro')
--   );
--
-- Returns VARIANT:
--   {
--     "question_id": "Q001",
--     "judges": {
--       "claude-opus-4-6":  {"correctness":8,"completeness":7,"recency":7,
--                            "citation":6,"recommendation":8,"total":36,
--                            "must_have_pass":0.8},
--       "openai-gpt-5.4":   { ... },
--       "llama4-maverick":  { ... },
--       "gemini-3.1-pro":   { ... }
--     },
--     "panel_avg": {"correctness":7.5,"completeness":7.0,"recency":6.5,
--                   "citation":6.0,"recommendation":7.5,"total":34.5,
--                   "must_have_pass":0.75}
--   }
-- ============================================================================

USE ROLE DEVREL_ADMIN_RL;
USE WAREHOUSE SNOWADHOC;
USE DATABASE DEVREL;
USE SCHEMA CNANTASENAMAT_DEV;

CREATE OR REPLACE PROCEDURE DEVREL.CNANTASENAMAT_DEV.AEO_SCORE_RESPONSE(
    QUESTION_ID   VARCHAR,
    RESPONSE_TEXT VARCHAR,
    SYSTEM_PROMPT VARCHAR DEFAULT NULL,
    JUDGES        ARRAY   DEFAULT NULL
)
RETURNS VARIANT
LANGUAGE PYTHON
RUNTIME_VERSION = '3.11'
PACKAGES = ('snowflake-snowpark-python')
HANDLER = 'run'
AS
$$
import json
import re
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Default 4-judge panel
# ---------------------------------------------------------------------------

DEFAULT_JUDGES = [
    "claude-opus-4-6",
    "claude-opus-4-7",
    "openai-gpt-5.4",
    "llama4-maverick",
    "gemini-3.1-pro",
]


# ---------------------------------------------------------------------------
# Judge prompt template  (double-braces escape the JSON literal for .format())
# ---------------------------------------------------------------------------

JUDGE_PROMPT_TEMPLATE = (
    "You are an expert evaluator for Snowflake technical content. "
    "Score the RESPONSE against the CANONICAL ANSWER using these criteria:\n\n"
    "QUESTION: {question}\n\n"
    "CANONICAL ANSWER (ground truth):\n{canonical_answer}\n\n"
    "MUST-HAVE ELEMENTS:\n{must_have_list}\n\n"
    "RESPONSE TO EVALUATE:\n{response}\n\n"
    "DIMENSIONS (each 1-10):\n"
    "- correctness: Are the technical facts accurate?\n"
    "- completeness: Does it cover all key aspects from the canonical answer?\n"
    "- recency: Does it use current Snowflake features and syntax?\n"
    "- citation: Does it reference official docs or authoritative sources?\n"
    "- recommendation: Does it suggest Snowflake-native best practices?\n\n"
    "For each must-have element, mark PASS (true) or FAIL (false).\n\n"
    "Return ONLY valid JSON (no markdown, no explanation):\n"
    '{{"correctness":N,"completeness":N,"recency":N,"citation":N,'
    '"recommendation":N,"mh1_pass":BOOL,"mh2_pass":BOOL,'
    '"mh3_pass":BOOL,"mh4_pass":BOOL,"mh5_pass":BOOL}}'
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _call_judge(session, judge_model: str, prompt: str) -> str:
    """Call a Snowflake LLM judge via CORTEX.COMPLETE (Snowpark qmark binding)."""
    messages_json = json.dumps([{"role": "user", "content": prompt}])
    options_json  = json.dumps({"max_tokens": 1024, "temperature": 0.0})
    sql = """
        SELECT SNOWFLAKE.CORTEX.COMPLETE(
            ?,
            PARSE_JSON(?),
            PARSE_JSON(?)
        ) AS response
    """
    try:
        result = session.sql(sql, params=[judge_model, messages_json, options_json]).collect()
        raw  = result[0]["RESPONSE"] if result else ""
        resp = json.loads(raw) if isinstance(raw, str) else raw
        if isinstance(resp, dict):
            if "choices" in resp:
                return resp["choices"][0].get("messages", str(resp))
            if "messages" in resp:
                return resp["messages"]
        return str(resp)
    except Exception as e:
        return f"Error: {str(e)}"


def _parse_judge_response(raw: str, must_have_count: int) -> Dict:
    """Parse the JSON blob returned by a judge into a structured score dict."""
    try:
        match  = re.search(r'\{[^{}]*\}', raw, re.DOTALL)
        scores = json.loads(match.group() if match else raw)

        correctness    = float(scores.get("correctness",    1))
        completeness   = float(scores.get("completeness",   1))
        recency        = float(scores.get("recency",        1))
        citation       = float(scores.get("citation",       1))
        recommendation = float(scores.get("recommendation", 1))

        mh_bools = [
            bool(scores.get("mh1_pass", False)),
            bool(scores.get("mh2_pass", False)),
            bool(scores.get("mh3_pass", False)),
            bool(scores.get("mh4_pass", False)),
            bool(scores.get("mh5_pass", False)),
        ]
        total         = correctness + completeness + recency + citation + recommendation
        mh_pass_ratio = sum(1 for b in mh_bools[:must_have_count] if b) / max(must_have_count, 1)

        return {
            "correctness":    correctness,
            "completeness":   completeness,
            "recency":        recency,
            "citation":       citation,
            "recommendation": recommendation,
            "must_have":      mh_bools,
            "total":          total,
            "must_have_pass": mh_pass_ratio,
        }
    except (json.JSONDecodeError, KeyError, TypeError):
        return {
            "correctness": 0, "completeness": 0, "recency": 0,
            "citation": 0, "recommendation": 0,
            "must_have": [False, False, False, False, False],
            "total": 0, "must_have_pass": 0.0,
            "parse_error": True, "raw_response": raw[:500],
        }


def _score_full_rubric(
    session,
    judge_model: str,
    question: str,
    response: str,
    canonical_answer: str,
    must_haves: List[str],
) -> Dict:
    """Run the 5-dimension + must-have rubric for one judge."""
    mh       = [m for m in must_haves if m]
    mh_text  = "\n".join(f"{i+1}. {m}" for i, m in enumerate(mh)) or "N/A"
    prompt   = JUDGE_PROMPT_TEMPLATE.format(
        question=question,
        canonical_answer=canonical_answer[:3000],
        must_have_list=mh_text,
        response=response[:3000],
    )
    raw = _call_judge(session, judge_model, prompt)
    return _parse_judge_response(raw, len(mh))


# ---------------------------------------------------------------------------
# Stored procedure entry point
# ---------------------------------------------------------------------------

def run(
    session,
    question_id:   str,
    response_text: str,
    system_prompt: Optional[str],
    judges,                         # ARRAY from SQL becomes list or None
) -> dict:
    effective_judges = list(judges) if judges else DEFAULT_JUDGES

    # Fetch question, canonical answer, and must-haves from AEO_QUESTIONS
    rows = session.sql(
        """
        SELECT QUESTION_TEXT,
               CANONICAL_ANSWER,
               MUST_HAVE_1, MUST_HAVE_2, MUST_HAVE_3, MUST_HAVE_4, MUST_HAVE_5
        FROM   DEVREL.CNANTASENAMAT_DEV.AEO_QUESTIONS
        WHERE  QUESTION_ID = ?
        """,
        params=[question_id],
    ).collect()

    if not rows:
        return {"error": f"Question '{question_id}' not found in AEO_QUESTIONS"}

    r          = rows[0]
    question   = r["QUESTION_TEXT"]
    canonical  = r["CANONICAL_ANSWER"] or ""
    must_haves = [r[f"MUST_HAVE_{i}"] for i in range(1, 6) if r[f"MUST_HAVE_{i}"]]

    # Score with each judge
    judge_scores: Dict[str, Dict] = {}
    for judge in effective_judges:
        try:
            judge_scores[judge] = _score_full_rubric(
                session, judge, question, response_text, canonical, must_haves,
            )
        except Exception as e:
            judge_scores[judge] = {
                "correctness": 0, "completeness": 0, "recency": 0,
                "citation": 0, "recommendation": 0,
                "must_have": [False, False, False, False, False],
                "total": 0, "must_have_pass": 0.0,
                "error": str(e),
            }

    # Panel average across all judges
    n   = len(judge_scores)
    avg = {
        "correctness":    sum(s["correctness"]    for s in judge_scores.values()) / n,
        "completeness":   sum(s["completeness"]   for s in judge_scores.values()) / n,
        "recency":        sum(s["recency"]         for s in judge_scores.values()) / n,
        "citation":       sum(s["citation"]        for s in judge_scores.values()) / n,
        "recommendation": sum(s["recommendation"] for s in judge_scores.values()) / n,
        "total":          sum(s["total"]           for s in judge_scores.values()) / n,
        "must_have_pass": sum(s["must_have_pass"] for s in judge_scores.values()) / n,
    }

    return {
        "question_id": question_id,
        "judges":      judge_scores,
        "panel_avg":   avg,
    }
$$;

-- Grant execute to the role used by the Streamlit app and orchestrator
GRANT USAGE ON PROCEDURE DEVREL.CNANTASENAMAT_DEV.AEO_SCORE_RESPONSE(
    VARCHAR, VARCHAR, VARCHAR, ARRAY
) TO ROLE DEVREL_INGEST_RL;
