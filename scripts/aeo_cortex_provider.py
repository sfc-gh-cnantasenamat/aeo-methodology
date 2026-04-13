"""
AEO-equivalent TruLens native evaluation provider.

Implements all 5 AEO scoring dimensions as TruLens-compatible metric
functions using direct SNOWFLAKE.CORTEX.COMPLETE SQL calls. This avoids
the JSON-mode parsing failures in the TruLens Cortex Python provider
(trulens.providers.cortex.provider.Cortex).

Dimensions mirror the AEO benchmark rubric:
  - correctness:      Factual accuracy of Snowflake claims (0-1)
  - completeness:     Coverage of all question aspects (0-1)
  - recency:          Uses current vs deprecated Snowflake APIs (0-1)
  - citation_quality: Quality of docs.snowflake.com references (0-1)
  - recommendation:   Actionability of next steps provided (0-1)
  - must_have_pass:   Heuristic: docs.snowflake.com URL present (0 or 1)

Multi-judge design: scores from all judge models are averaged, mirroring
the AEO benchmark's 3-judge consensus approach.

Note on recency: judge models have training cutoffs around early 2025 and
cannot reliably identify post-cutoff content. The recency rubric therefore
focuses on deprecated vs current API patterns that the judges do know, rather
than anchoring to a specific calendar year.

Each method signature follows the TruLens Metric convention:
    fn(prompt: str, response: str) -> float

Usage (future live runs):
    from aeo_cortex_provider import AEOCortexProvider, build_native_metrics

    provider = AEOCortexProvider(snowpark_session=session)
    metrics = build_native_metrics(provider)
    run.compute_metrics(metrics=metrics)

Usage (replay with native scoring):
    python3 replay_runs_to_trulens.py --profile snowhouse --native --run-ids 1 7
"""

import re
from typing import List, Optional


# Default judge panel mirrors AEO's multi-model approach.
# All three are available in Snowflake Cortex on Snowhouse.
DEFAULT_JUDGE_MODELS = [
    "claude-opus-4-6",
    "llama4-maverick",
    "openai-gpt-5.4",
]


class AEOCortexProvider:
    """
    TruLens-compatible provider implementing AEO's 5-dimension rubric.

    Uses direct SNOWFLAKE.CORTEX.COMPLETE SQL calls so it is unaffected by
    the JSON-mode parsing failures in trulens.providers.cortex.provider.Cortex.

    Scoring uses a panel of judge models whose scores are averaged, mirroring
    the 3-judge consensus in the AEO benchmark. Full response text is always
    passed to the judges (no truncation) so citations at the end of long
    responses are not missed.

    Each scoring method takes (prompt: str, response: str) and returns a
    float in [0, 1]. The must_have_pass method is a heuristic (no LLM call).
    """

    def __init__(
        self,
        snowpark_session,
        judge_models: Optional[List[str]] = None,
        question_metadata: Optional[dict] = None,
    ):
        """
        Args:
            snowpark_session: Active Snowpark Session. Must have a warehouse set.
            judge_models: List of Cortex model names used as the judge panel.
                          Defaults to [claude-opus-4-6, llama4-maverick, openai-gpt-5.4].
                          Pass a single-element list to use one judge only.
            question_metadata: Optional dict mapping question text to per-question
                               metadata. Format: {question_text: {"canonical_answer": str,
                               "must_haves": [str]}}. When provided, correctness(),
                               completeness(), and must_have_pass() automatically inject
                               the reference answer and criteria without needing explicit
                               arguments, making the methods fully TruLens-compatible
                               while still using ground truth for evaluation.
        """
        self._session = snowpark_session
        self._models = judge_models if judge_models is not None else DEFAULT_JUDGE_MODELS
        self._question_metadata = question_metadata or {}

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _call(self, model: str, prompt: str) -> str:
        """Call CORTEX.COMPLETE with the given model and return raw text."""
        rows = self._session.sql(
            "SELECT SNOWFLAKE.CORTEX.COMPLETE(?, ?)",
            params=[model, prompt],
        ).collect()
        return str(rows[0][0]).strip() if rows else ""

    def _parse_score(self, raw: str, scale: int) -> Optional[float]:
        """Extract first numeric token from raw text and normalize to [0, 1]."""
        m = re.search(r"\b(\d+(?:\.\d+)?)\b", raw)
        if not m:
            return None
        val = float(m.group(1))
        if scale > 1:
            val = val / scale
        return round(min(max(val, 0.0), 1.0), 4)

    def _get_canonical(self, prompt: str) -> Optional[str]:
        """Look up canonical answer for a question prompt from question_metadata."""
        meta = self._question_metadata.get(prompt)
        return meta.get("canonical_answer") if meta else None

    def _get_must_haves(self, prompt: str) -> list:
        """Look up must-have criteria for a question prompt from question_metadata."""
        meta = self._question_metadata.get(prompt)
        return meta.get("must_haves", []) if meta else []

    def _score(
        self,
        question: str,
        response: str,
        system: str,
        scale: int = 10,
        extra_context: str = None,
    ) -> float:
        """
        Score with every judge model and return the average.

        Full response text is passed without truncation. If a judge call fails
        or returns unparseable output it is excluded from the average. Returns
        0.0 only if every judge fails.

        extra_context: optional text (e.g. a reference answer) injected between
        the system instructions and the QUESTION block.
        """
        context_block = f"\n{extra_context}\n" if extra_context else ""
        prompt = (
            f"{system}\n"
            f"{context_block}\n"
            f"QUESTION: {question}\n\n"
            f"RESPONSE: {response}\n\n"
            f"Reply with ONLY a single integer from 0 to {scale}. No explanation."
        )
        scores = []
        for model in self._models:
            try:
                raw = self._call(model, prompt)
                val = self._parse_score(raw, scale)
                if val is not None:
                    scores.append(val)
            except Exception:
                pass  # exclude failed judge from average
        if not scores:
            return 0.0
        return round(sum(scores) / len(scores), 4)

    # ------------------------------------------------------------------ #
    # AEO dimensions
    # ------------------------------------------------------------------ #

    def correctness(self, prompt: str, response: str, canonical_answer: str = None) -> float:
        """
        Factual accuracy of Snowflake-specific claims.

        When canonical_answer is provided, judges compare the response directly
        against the reference answer, matching the AEO benchmark approach.
        When absent, falls back to rubric-only evaluation (TruLens-compatible).
        Scale: 0-10 normalized to 0-1. Averaged across all judge models.
        """
        if canonical_answer is None:
            canonical_answer = self._get_canonical(prompt)
        if canonical_answer:
            system = (
                "You are a Snowflake technical evaluator assessing factual accuracy. "
                "A REFERENCE ANSWER is provided below. Compare the RESPONSE against "
                "the REFERENCE ANSWER to assess correctness. "
                "Use this scale: "
                "0-2=contradicts the reference answer or contains broken SQL; "
                "3-4=mostly incorrect relative to the reference with few accurate details; "
                "5-6=partially correct but misses or contradicts key elements from the reference; "
                "7-8=mostly accurate and consistent with the reference; "
                "minor phrasing differences or omitted details are acceptable at this level; "
                "9-10=fully accurate and consistent with all key facts in the reference answer."
            )
            extra_context = f"REFERENCE ANSWER:\n{canonical_answer}"
        else:
            system = (
                "You are a Snowflake technical evaluator assessing factual accuracy. "
                "Rate the FACTUAL CORRECTNESS of the response to the Snowflake question. "
                "Use this scale: "
                "0-2=contains clearly wrong statements, broken SQL that would fail to execute, "
                "or function names that do not exist in Snowflake; "
                "3-4=mostly incorrect with only a few accurate details; "
                "5-6=partially correct but contains notable errors in SQL syntax, API names, "
                "or parameter descriptions that would mislead a practitioner; "
                "7-8=mostly accurate with working SQL and correct Snowflake function names "
                "(e.g. SNOWFLAKE.CORTEX.COMPLETE, CORTEX_ANALYST, CORTEX_SEARCH); "
                "minor phrasing imprecision or omitted edge cases are acceptable at this level; "
                "9-10=fully accurate, all function names, SQL syntax, parameter names, and "
                "behavioral descriptions exactly match current Snowflake documentation. "
                "Calibration: a response that provides working, runnable Snowflake SQL with "
                "correct function names and accurate behavioral descriptions should score 7-8 "
                "even if minor caveats are omitted. "
                "Only score 5 or below if the SQL would actually fail or a stated behavior "
                "is factually wrong."
            )
            extra_context = None
        return self._score(prompt, response, system, scale=10, extra_context=extra_context)

    def completeness(self, prompt: str, response: str, canonical_answer: str = None) -> float:
        """
        Coverage of all relevant aspects of the question.

        When canonical_answer is provided, judges compare coverage against the
        reference answer's scope. When absent, falls back to rubric-only
        evaluation (TruLens-compatible).
        Scale: 0-10 normalized to 0-1. Averaged across all judge models.
        """
        if canonical_answer is None:
            canonical_answer = self._get_canonical(prompt)
        if canonical_answer:
            system = (
                "You are a Snowflake technical evaluator assessing completeness. "
                "A REFERENCE ANSWER is provided below. Compare the RESPONSE against "
                "the REFERENCE ANSWER to assess how completely the response covers "
                "the question. "
                "Use this scale: "
                "0-2=addresses almost nothing from the reference answer; "
                "3-4=covers the topic at surface level only; if the reference includes SQL or "
                "step-by-step instructions, the response merely mentions the concept without code; "
                "5-6=covers the main topic but omits significant technical portions from the "
                "reference (e.g. has partial SQL but is missing key clauses or configuration steps); "
                "7-8=covers most technical aspects from the reference with only minor gaps; "
                "9-10=covers all key aspects including technical detail present in the reference answer. "
                "HARD RULE: if the response covers less than half the technical content present "
                "in the reference answer, it MUST score 5 or below."
            )
            extra_context = f"REFERENCE ANSWER:\n{canonical_answer}"
        else:
            system = (
                "You are a strict Snowflake technical evaluator. "
                "Rate the COMPLETENESS of the response to the Snowflake question. "
                "Use this scale strictly: "
                "0-2=does not address the question at all; "
                "3-4=addresses only a small part of the question; "
                "5-6=addresses the main question but misses important sub-aspects; "
                "7-8=addresses most aspects with minor gaps; "
                "9-10=fully comprehensive, covers all aspects a practitioner would need. "
                "Penalize responses that omit required steps, prerequisites, or caveats."
            )
            extra_context = None
        return self._score(prompt, response, system, scale=10, extra_context=extra_context)

    def recency(self, prompt: str, response: str) -> float:
        """
        Use of current vs deprecated Snowflake APIs and patterns.

        Mirrors AEO RECENCY: does the response use up-to-date Snowflake syntax
        and avoid deprecated functions, old API names, or superseded workflows?

        Note: judge models evaluate based on their training knowledge of which
        Snowflake APIs are current vs deprecated. They do not anchor to a
        specific calendar year, which would exceed their knowledge cutoff.
        Scale: 0-10 normalized to 0-1. Averaged across all judge models.
        """
        system = (
            "You are a strict Snowflake technical evaluator. "
            "Rate the RECENCY of the Snowflake response based on whether it uses "
            "current APIs, syntax, and best practices vs deprecated or superseded ones. "
            "Use this scale strictly: "
            "0-2=references deprecated functions or APIs that have been removed or replaced; "
            "3-4=uses mostly outdated patterns with some current elements; "
            "5-6=mix of current and outdated; uses valid but not recommended approaches; "
            "7-8=mostly current with only minor outdated references; "
            "9-10=fully uses current Snowflake APIs, syntax, and recommended patterns. "
            "Examples of deprecated patterns to penalize: old COMPLETE() syntax without "
            "SNOWFLAKE.CORTEX prefix, deprecated ML function names, removed parameters. "
            "If the response cannot be evaluated for recency, score 5."
        )
        return self._score(prompt, response, system, scale=10)

    def citation_quality(self, prompt: str, response: str) -> float:
        """
        Quality and specificity of official Snowflake documentation references.

        Mirrors AEO CITATION: does the response include specific references to
        docs.snowflake.com, named documentation pages, or specific doc sections?
        Full response text is used (no truncation) so citations at the end of
        long responses are captured.
        Scale: 0-10 normalized to 0-1. Averaged across all judge models.
        """
        system = (
            "You are a strict Snowflake technical evaluator. "
            "Rate the CITATION QUALITY of the response to the Snowflake question. "
            "Use this scale strictly: "
            "0-2=no specific docs.snowflake.com URLs present; vague phrases like "
            "'see the Snowflake documentation' or 'refer to Snowflake docs' without "
            "an actual URL must score 0-2; "
            "3-4=at least one specific docs.snowflake.com URL present but coverage is sparse; "
            "5-6=one or two specific docs.snowflake.com URLs covering the main topic; "
            "7-8=multiple specific docs.snowflake.com URLs covering most major claims; "
            "9-10=comprehensive docs.snowflake.com URLs for every major claim. "
            "HARD RULE: if the response contains no docs.snowflake.com URL, "
            "the score MUST be 2 or below regardless of any generic documentation mentions."
        )
        return self._score(prompt, response, system, scale=10)

    def recommendation(self, prompt: str, response: str, canonical_answer: str = None) -> float:
        """
        Actionability: does the response give clear, concrete next steps?

        When canonical_answer is provided, judges compare the response's
        actionability against the reference, correctly penalising incomplete
        or incorrect SQL relative to the reference. When absent, falls back
        to rubric-only evaluation (TruLens-compatible).
        Scale: 0-10 normalized to 0-1. Averaged across all judge models.
        """
        if canonical_answer is None:
            canonical_answer = self._get_canonical(prompt)
        if canonical_answer:
            system = (
                "You are a Snowflake technical evaluator assessing recommendation quality. "
                "A REFERENCE ANSWER is provided below. Compare the RESPONSE against "
                "the REFERENCE ANSWER to assess how actionable and complete the guidance is. "
                "Use this scale: "
                "0-2=no actionable guidance; purely conceptual with no SQL or steps; "
                "3-4=describes what to do in prose only, without runnable SQL or commands, "
                "when the reference provides them; "
                "5-6=some actionable steps but missing key SQL clauses, parameters, or "
                "configuration details present in the reference; "
                "7-8=actionable guidance with SQL comparable to the reference; minor gaps only; "
                "9-10=as specific and immediately actionable as the reference, with correct "
                "and complete SQL or commands. "
                "HARD RULE: if the reference answer contains runnable SQL and the response "
                "contains no SQL at all, the score MUST be 4 or below. "
                "HARD RULE: a response that is mostly prose when the reference is SQL-focused "
                "MUST score 5 or below."
            )
            extra_context = f"REFERENCE ANSWER:\n{canonical_answer}"
        else:
            system = (
                "You are a strict Snowflake technical evaluator. "
                "Rate the RECOMMENDATION QUALITY of the response to the Snowflake question. "
                "Use this scale: "
                "0-2=no actionable guidance; only describes concepts without next steps; "
                "3-4=vague suggestions without concrete steps or examples; "
                "5-6=describes what to do in general terms but lacks concrete SQL examples "
                "or specific configuration steps the user can copy and run; "
                "7-8=includes at least one concrete SQL snippet or specific command the user "
                "can run directly, covering most of the user's needs; "
                "9-10=highly specific, immediately actionable guidance with concrete SQL, "
                "commands, or configuration covering all aspects of the question. "
                "Calibration: a response that only describes what to do conceptually without "
                "providing specific SQL syntax or runnable commands should not score above 6."
            )
            extra_context = None
        return self._score(prompt, response, system, scale=10, extra_context=extra_context)

    def must_have_pass(self, prompt: str, response: str, must_haves: list = None) -> float:
        """
        Pass/fail check against must-have criteria.

        When must_haves is provided (list of strings from AEO_QUESTIONS.MUST_HAVE_1-5),
        uses the judge panel to count how many criteria the response satisfies,
        returning the fraction satisfied (0.0-1.0) averaged across judges.
        This mirrors the AEO benchmark's semantic must-have evaluation.

        When must_haves is absent or empty, falls back to a regex check for
        docs.snowflake.com references (no LLM call).
        """
        if must_haves is None:
            must_haves = self._get_must_haves(prompt)
        active = [m for m in (must_haves or []) if m]

        if not active:
            patterns = [
                r"docs\.snowflake\.com",
                r"snowflake\.com/en/",
                r"docs\.snowflake\.com/en/",
            ]
            for pattern in patterns:
                if re.search(pattern, response, re.IGNORECASE):
                    return 1.0
            return 0.0

        n = len(active)
        criteria_text = "\n".join(f"{i + 1}. {c}" for i, c in enumerate(active))
        system = (
            f"You are a strict evaluator. Count how many of the following {n} criteria "
            f"are satisfied by the response to the question. "
            f"Each criterion must be clearly met, not just partially addressed.\n\n"
            f"Criteria:\n{criteria_text}"
        )
        return self._score(prompt, response, system, scale=n)


# ------------------------------------------------------------------ #
# Factory
# ------------------------------------------------------------------ #

def build_native_metrics(provider: AEOCortexProvider) -> list:
    """
    Build the full AEO-equivalent Metric list using native Cortex evaluation.

    All 6 metrics follow the TruLens Metric convention:
        fn(prompt: str, response: str) -> float in [0, 1]

    Pass the returned list to run.compute_metrics(metrics=...).

    Args:
        provider: Initialized AEOCortexProvider instance.

    Returns:
        List of trulens.core.Metric objects ready for run.compute_metrics().
    """
    from trulens.core import Metric

    return [
        Metric(
            implementation=provider.correctness,
            name="correctness",
        ).on_input_output(),
        Metric(
            implementation=provider.completeness,
            name="completeness",
        ).on_input_output(),
        Metric(
            implementation=provider.recency,
            name="recency",
        ).on_input_output(),
        Metric(
            implementation=provider.citation_quality,
            name="citation",
        ).on_input_output(),
        Metric(
            implementation=provider.recommendation,
            name="recommendation",
        ).on_input_output(),
        Metric(
            implementation=provider.must_have_pass,
            name="must_have_pass",
        ).on_input_output(),
    ]
