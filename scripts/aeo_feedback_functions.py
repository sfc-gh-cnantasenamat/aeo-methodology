"""
AEO Custom Feedback Functions for TruLens.

These implement the 5 AEO-specific scoring dimensions as TruLens-compatible
feedback functions, plus the must-have coverage metric.

Each function follows the TruLens feedback function pattern:
  - Takes relevant text inputs (question, response, canonical, etc.)
  - Returns a score between 0.0 and 1.0
  - Optionally returns chain-of-thought reasoning

Scoring scale: 1-10 per dimension (max 50 per question).
Must-haves: up to 5 per question, binary PASS/FAIL each.

Two usage modes:
  1. TruLens compute_metrics(): Each feedback function independently calls the
     judge LLM via CORTEX.COMPLETE and returns a 0.0-1.0 score.
  2. Direct scoring: score_with_panel() calls score_full_rubric() per judge and
     returns raw 1-10 scores for AEO_SCORES table insertion.
"""

import json
import re
from typing import Dict, List, Optional, Tuple

import snowflake.connector


# ---------------------------------------------------------------------------
# Judge prompt template (matches existing AEO scoring rubric, 1-10 scale)
# ---------------------------------------------------------------------------

JUDGE_PROMPT_TEMPLATE = """You are an expert evaluator for Snowflake technical content. Score the RESPONSE against the CANONICAL ANSWER using these criteria:

QUESTION: {question}

CANONICAL ANSWER (ground truth):
{canonical_answer}

MUST-HAVE ELEMENTS:
{must_have_list}

RESPONSE TO EVALUATE:
{response}

DIMENSIONS (each 1-10):
- correctness: Are the technical facts accurate?
- completeness: Does it cover all key aspects from the canonical answer?
- recency: Does it use current Snowflake features and syntax?
- citation: Does it reference official docs or authoritative sources?
- recommendation: Does it suggest Snowflake-native best practices?

For each must-have element, mark PASS (true) or FAIL (false).

Return ONLY valid JSON (no markdown, no explanation):
{{"correctness":N,"completeness":N,"recency":N,"citation":N,"recommendation":N,"mh1_pass":BOOL,"mh2_pass":BOOL,"mh3_pass":BOOL,"mh4_pass":BOOL,"mh5_pass":BOOL}}"""


# ---------------------------------------------------------------------------
# Internal LLM call helper
# ---------------------------------------------------------------------------

def _call_judge(
    session_or_conn,
    judge_model: str,
    prompt: str,
) -> str:
    """Call a Snowflake LLM to act as judge. Works with both connector and session."""
    messages = [{"role": "user", "content": prompt}]
    messages_json = json.dumps(messages)
    options_json = json.dumps({"max_tokens": 1024, "temperature": 0.0})

    try:
        if hasattr(session_or_conn, 'sql'):
            # Snowpark session (qmark binding)
            sql = """
                SELECT SNOWFLAKE.CORTEX.COMPLETE(
                    ?,
                    PARSE_JSON(?),
                    PARSE_JSON(?)
                ) AS response
            """
            result = session_or_conn.sql(sql, params=[judge_model, messages_json, options_json]).collect()
            raw = result[0]["RESPONSE"] if result else ""
        else:
            # snowflake.connector cursor (pyformat binding)
            sql = """
                SELECT SNOWFLAKE.CORTEX.COMPLETE(
                    %s,
                    PARSE_JSON(%s),
                    PARSE_JSON(%s)
                ) AS response
            """
            cur = session_or_conn.cursor()
            cur.execute(sql, (judge_model, messages_json, options_json))
            row = cur.fetchone()
            raw = row[0] if row else ""
            cur.close()

        if isinstance(raw, str):
            resp = json.loads(raw)
        else:
            resp = raw

        # Extract text from COMPLETE response format
        if isinstance(resp, dict):
            if "choices" in resp:
                return resp["choices"][0].get("messages", str(resp))
            if "messages" in resp:
                return resp["messages"]
        return str(resp)
    except Exception as e:
        return f"Error: {str(e)}"


def _parse_judge_response(raw: str, must_have_count: int) -> Dict:
    """Parse the JSON response from a judge LLM into a structured dict."""
    try:
        json_match = re.search(r'\{[^{}]*\}', raw, re.DOTALL)
        if json_match:
            scores = json.loads(json_match.group())
        else:
            scores = json.loads(raw)

        # Extract dimension scores
        correctness = float(scores.get("correctness", 1))
        completeness = float(scores.get("completeness", 1))
        recency = float(scores.get("recency", 1))
        citation = float(scores.get("citation", 1))
        recommendation = float(scores.get("recommendation", 1))

        # Extract must-have passes
        mh1_pass = bool(scores.get("mh1_pass", False))
        mh2_pass = bool(scores.get("mh2_pass", False))
        mh3_pass = bool(scores.get("mh3_pass", False))
        mh4_pass = bool(scores.get("mh4_pass", False))
        mh5_pass = bool(scores.get("mh5_pass", False))
        mh_bools = [mh1_pass, mh2_pass, mh3_pass, mh4_pass, mh5_pass]

        total = correctness + completeness + recency + citation + recommendation
        mh_pass_count = sum(1 for b in mh_bools[:must_have_count] if b)
        mh_pass_ratio = mh_pass_count / max(must_have_count, 1)

        return {
            "correctness": correctness,
            "completeness": completeness,
            "recency": recency,
            "citation": citation,
            "recommendation": recommendation,
            "must_have": mh_bools,
            "total": total,
            "must_have_pass": mh_pass_ratio,
            "raw_response": raw,
        }
    except (json.JSONDecodeError, KeyError, TypeError):
        return {
            "correctness": 0,
            "completeness": 0,
            "recency": 0,
            "citation": 0,
            "recommendation": 0,
            "must_have": [False, False, False, False, False],
            "total": 0,
            "must_have_pass": 0.0,
            "raw_response": raw,
            "parse_error": True,
        }


# ---------------------------------------------------------------------------
# Full rubric scorer (used by both TruLens and direct pipeline)
# ---------------------------------------------------------------------------

def score_full_rubric(
    session_or_conn,
    judge_model: str,
    question: str,
    response: str,
    canonical_answer: str,
    must_haves: List[str],
) -> Dict:
    """
    Run the full AEO 5-dimension + must-have scoring rubric using an LLM judge.

    Returns a dict with:
      - correctness, completeness, recency, citation, recommendation (1-10 each)
      - must_have: list of up to 5 booleans
      - total: sum of 5 dimensions (5-50)
      - must_have_pass: ratio of passed must-haves (0.0-1.0)
      - raw_response: the judge's raw output
    """
    mh = [m for m in must_haves if m]
    mh_count = len(mh)
    must_have_list = "\n".join(f"{i+1}. {m}" for i, m in enumerate(mh))
    if not must_have_list:
        must_have_list = "N/A"

    prompt = JUDGE_PROMPT_TEMPLATE.format(
        question=question,
        canonical_answer=canonical_answer[:3000],
        must_have_list=must_have_list,
        response=response[:3000],
    )

    raw = _call_judge(session_or_conn, judge_model, prompt)
    return _parse_judge_response(raw, mh_count)


# ---------------------------------------------------------------------------
# TruLens-compatible feedback functions (self-contained, call judges directly)
#
# Each function:
#   1. Accepts a connection/session via the _conn kwarg (set at registration time)
#   2. Calls the judge LLM independently
#   3. Returns a float in [0.0, 1.0]
#
# The _conn and _judge_model kwargs are injected by the TruLens scoring wrapper.
# If _precomputed_scores is provided (from score_full_rubric), uses those
# instead of making a new judge call — this avoids redundant LLM calls when
# computing multiple dimensions from the same judge response.
# ---------------------------------------------------------------------------

# Thread-local cache to avoid calling the judge 7 times for 7 feedback functions
# on the same (question, response, judge) tuple. The cache key is
# (question[:50], response[:50], judge_model).
_score_cache: Dict[tuple, Dict] = {}


def _get_or_compute_scores(
    session_or_conn,
    judge_model: str,
    question: str,
    response: str,
    canonical_answer: str,
    must_haves: List[str],
    precomputed: Optional[Dict] = None,
) -> Dict:
    """Get cached scores or compute them. Avoids redundant judge calls."""
    if precomputed:
        return precomputed

    cache_key = (question[:50], response[:50], judge_model)
    if cache_key in _score_cache:
        return _score_cache[cache_key]

    scores = score_full_rubric(
        session_or_conn, judge_model, question, response,
        canonical_answer, must_haves,
    )
    _score_cache[cache_key] = scores
    return scores


def clear_score_cache():
    """Clear the score cache between runs or questions."""
    _score_cache.clear()


def aeo_correctness(
    question: str, response: str, canonical: str,
    must_haves: Optional[List[str]] = None,
    _conn=None, _judge_model: str = "claude-opus-4-6",
    _precomputed_scores: Optional[Dict] = None, **kwargs
) -> float:
    """Score correctness (0.0 to 1.0). Maps AEO 1-10 scale to 0.0-1.0."""
    scores = _get_or_compute_scores(
        _conn, _judge_model, question, response, canonical,
        must_haves or [], _precomputed_scores,
    )
    return scores["correctness"] / 10.0


def aeo_completeness(
    question: str, response: str, canonical: str,
    must_haves: Optional[List[str]] = None,
    _conn=None, _judge_model: str = "claude-opus-4-6",
    _precomputed_scores: Optional[Dict] = None, **kwargs
) -> float:
    """Score completeness (0.0 to 1.0)."""
    scores = _get_or_compute_scores(
        _conn, _judge_model, question, response, canonical,
        must_haves or [], _precomputed_scores,
    )
    return scores["completeness"] / 10.0


def aeo_recency(
    question: str, response: str, canonical: str,
    must_haves: Optional[List[str]] = None,
    _conn=None, _judge_model: str = "claude-opus-4-6",
    _precomputed_scores: Optional[Dict] = None, **kwargs
) -> float:
    """Score recency of syntax and feature names (0.0 to 1.0)."""
    scores = _get_or_compute_scores(
        _conn, _judge_model, question, response, canonical,
        must_haves or [], _precomputed_scores,
    )
    return scores["recency"] / 10.0


def aeo_citation_quality(
    question: str, response: str, canonical: str,
    must_haves: Optional[List[str]] = None,
    _conn=None, _judge_model: str = "claude-opus-4-6",
    _precomputed_scores: Optional[Dict] = None, **kwargs
) -> float:
    """Score citation/reference quality (0.0 to 1.0)."""
    scores = _get_or_compute_scores(
        _conn, _judge_model, question, response, canonical,
        must_haves or [], _precomputed_scores,
    )
    return scores["citation"] / 10.0


def aeo_recommendation(
    question: str, response: str, canonical: str,
    must_haves: Optional[List[str]] = None,
    _conn=None, _judge_model: str = "claude-opus-4-6",
    _precomputed_scores: Optional[Dict] = None, **kwargs
) -> float:
    """Score whether Snowflake approach is recommended (0.0 to 1.0)."""
    scores = _get_or_compute_scores(
        _conn, _judge_model, question, response, canonical,
        must_haves or [], _precomputed_scores,
    )
    return scores["recommendation"] / 10.0


def aeo_must_have_coverage(
    question: str, response: str, canonical: str,
    must_haves: Optional[List[str]] = None,
    _conn=None, _judge_model: str = "claude-opus-4-6",
    _precomputed_scores: Optional[Dict] = None, **kwargs
) -> float:
    """Score must-have element coverage (0.0 to 1.0)."""
    scores = _get_or_compute_scores(
        _conn, _judge_model, question, response, canonical,
        must_haves or [], _precomputed_scores,
    )
    return float(scores["must_have_pass"])


def aeo_total_score(
    question: str, response: str, canonical: str,
    must_haves: Optional[List[str]] = None,
    _conn=None, _judge_model: str = "claude-opus-4-6",
    _precomputed_scores: Optional[Dict] = None, **kwargs
) -> float:
    """Overall AEO score (0.0 to 1.0). Maps 5-50 to 0.0-1.0."""
    scores = _get_or_compute_scores(
        _conn, _judge_model, question, response, canonical,
        must_haves or [], _precomputed_scores,
    )
    return scores["total"] / 50.0


# ---------------------------------------------------------------------------
# Multi-judge orchestration
# ---------------------------------------------------------------------------

JUDGE_PANEL = [
    "claude-opus-4-6",
    "openai-gpt-5.4",
    "llama4-maverick",
]


def score_with_panel(
    session_or_conn,
    question: str,
    response: str,
    canonical_answer: str,
    must_haves: List[str],
    judges: Optional[List[str]] = None,
) -> Dict:
    """
    Score a response using a panel of LLM judges and return per-judge results.

    Returns a dict with:
      - per-judge scores under 'judges' key
      - averaged scores under 'panel_avg' key

    Used by both the TruLens pipeline (for dual-write to AEO_SCORES) and
    the direct scoring pipeline.
    """
    if judges is None:
        judges = JUDGE_PANEL

    all_scores = {}
    for judge in judges:
        try:
            scores = score_full_rubric(
                session_or_conn, judge, question, response,
                canonical_answer, must_haves,
            )
            all_scores[judge] = scores
        except Exception as e:
            all_scores[judge] = {
                "correctness": 0, "completeness": 0, "recency": 0,
                "citation": 0, "recommendation": 0,
                "must_have": [False, False, False, False, False],
                "total": 0, "must_have_pass": 0.0,
                "error": str(e),
            }

    # Compute panel averages
    n = len(all_scores)
    if n == 0:
        return {"judges": {}, "panel_avg": {}}

    avg = {
        "correctness": sum(s["correctness"] for s in all_scores.values()) / n,
        "completeness": sum(s["completeness"] for s in all_scores.values()) / n,
        "recency": sum(s["recency"] for s in all_scores.values()) / n,
        "citation": sum(s["citation"] for s in all_scores.values()) / n,
        "recommendation": sum(s["recommendation"] for s in all_scores.values()) / n,
        "total": sum(s["total"] for s in all_scores.values()) / n,
        "must_have_pass": sum(s["must_have_pass"] for s in all_scores.values()) / n,
    }

    return {
        "judges": all_scores,
        "panel_avg": avg,
    }


def score_with_panel_and_trulens(
    session_or_conn,
    question: str,
    response: str,
    canonical_answer: str,
    must_haves: List[str],
    judges: Optional[List[str]] = None,
) -> Dict:
    """
    Score a response and return results in both raw (for AEO_SCORES) and
    TruLens-normalized (0.0-1.0) formats.

    Returns a dict with:
      - 'judges': per-judge raw scores (1-10 scale)
      - 'panel_avg': averaged raw scores
      - 'trulens': dict of normalized 0.0-1.0 scores for TruLens feedback
    """
    result = score_with_panel(
        session_or_conn, question, response, canonical_answer,
        must_haves, judges,
    )

    # Add TruLens-normalized panel averages
    avg = result.get("panel_avg", {})
    result["trulens"] = {
        "aeo_correctness": avg.get("correctness", 0) / 10.0,
        "aeo_completeness": avg.get("completeness", 0) / 10.0,
        "aeo_recency": avg.get("recency", 0) / 10.0,
        "aeo_citation": avg.get("citation", 0) / 10.0,
        "aeo_recommendation": avg.get("recommendation", 0) / 10.0,
        "aeo_must_have_coverage": avg.get("must_have_pass", 0),
        "aeo_total_score": avg.get("total", 0) / 50.0,
    }

    return result
