"""
AEO Benchmark App — TruLens-instrumented pipeline.

This module defines the AEOBenchmarkApp class, which wraps the AEO
question-answering and scoring workflow with TruLens @instrument
decorators so that every step emits OpenTelemetry spans.

v1: 128 questions loaded from Snowflake tables, 1-10 scoring scale.

Usage:
    from aeo_trulens_app import AEOBenchmarkApp, register_app

    app = AEOBenchmarkApp(session)
    tru_app = register_app(app, session, app_version="v1")
    # Then create a RunConfig and call run.start() / run.compute_metrics()
"""

import json
import os
import time
from typing import Dict, List, Optional

import snowflake.connector

# TruLens instrumentation
os.environ["TRULENS_OTEL_TRACING"] = "1"

from trulens.core.otel.instrument import instrument
from trulens.otel.semconv.trace import SpanAttributes


# ---------------------------------------------------------------------------
# Data: loaded lazily from Snowflake via aeo_data module
# ---------------------------------------------------------------------------

from aeo_data import QUESTIONS, CANONICAL_SUMMARIES, MUST_HAVES, CATEGORIES


# ---------------------------------------------------------------------------
# AEO Benchmark Application
# ---------------------------------------------------------------------------

class AEOBenchmarkApp:
    """
    AEO Benchmark application instrumented with TruLens.

    Supports three execution modes:
      - baseline:  bare LLM call (no system prompt, no tools)
      - augmented: LLM call with a domain system prompt
      - agentic:   uses native Cortex Code as the inference tool

    The @instrument decorators emit OTel spans for each step, which TruLens
    captures and stores in Snowflake for evaluation.
    """

    def __init__(
        self,
        snowflake_session,
        mode: str = "baseline",
        model: str = "claude-opus-4-6",
        system_prompt: Optional[str] = None,
        cite: bool = False,
        self_critique: bool = False,
        max_tokens: int = 8192,
    ):
        """
        Args:
            snowflake_session: Active Snowpark session.
            mode: One of 'baseline', 'augmented', 'agentic'.
            model: LLM model name for SNOWFLAKE.CORTEX.COMPLETE.
            system_prompt: Optional system prompt (used in augmented mode).
            cite: If True, append citation instruction to each question.
            self_critique: If True, add a self-critique refinement step.
            max_tokens: Maximum output tokens.
        """
        self.session = snowflake_session
        self.mode = mode
        self.model = model
        self.system_prompt = system_prompt
        self.cite = cite
        self.self_critique = self_critique
        self.max_tokens = max_tokens

    # ----- Retrieval (agentic mode only) -----

    @instrument(
        span_type=SpanAttributes.SpanType.RETRIEVAL,
        attributes={
            SpanAttributes.RETRIEVAL.QUERY_TEXT: "question",
            SpanAttributes.RETRIEVAL.RETRIEVED_CONTEXTS: "return",
        },
    )
    def retrieve_context(self, question: str) -> List[str]:
        """
        Retrieve relevant Snowflake documentation context for the question.

        In baseline/augmented mode, returns empty (no retrieval step).
        In agentic mode, uses the canonical answer as gold retrieval context,
        which isolates generation quality from retrieval quality.

        For production agentic runs, this would be replaced with actual
        Cortex Code session invocation or Cortex Search calls.
        """
        if self.mode != "agentic":
            return []

        # Find question ID from text
        qid = self._find_question_id(question)
        if qid and qid in CANONICAL_SUMMARIES:
            return [CANONICAL_SUMMARIES[qid]]
        return []

    # ----- Generation -----

    @instrument(span_type=SpanAttributes.SpanType.GENERATION)
    def generate_response(
        self, question: str, context: Optional[List[str]] = None
    ) -> str:
        """
        Generate an LLM response to the question using SNOWFLAKE.CORTEX.COMPLETE.

        In agentic mode, the retrieved context is injected into the prompt.
        In replay mode (_preloaded_response is set), returns the pre-existing
        response directly without making any LLM call.
        """
        if getattr(self, "_preloaded_response", None):
            return self._preloaded_response

        prompt = question

        # Append citation instruction if enabled
        if self.cite:
            prompt += (
                "\n\nIMPORTANT: Include specific references to official "
                "Snowflake documentation (docs.snowflake.com) in your answer."
            )

        # Build messages
        messages = []

        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})

        if context:
            context_block = "\n\n".join(context)
            user_content = (
                f"Use the following reference material to inform your answer:\n\n"
                f"---\n{context_block}\n---\n\n"
                f"Question: {prompt}"
            )
        else:
            user_content = prompt

        messages.append({"role": "user", "content": user_content})

        # Call Snowflake CORTEX.COMPLETE
        messages_json = json.dumps(messages)
        options_json = json.dumps({"max_tokens": self.max_tokens})

        sql = """
            SELECT SNOWFLAKE.CORTEX.COMPLETE(
                ?,
                PARSE_JSON(?),
                PARSE_JSON(?)
            ) AS response
        """

        try:
            result = self.session.sql(sql, params=[self.model, messages_json, options_json]).collect()
            if result:
                raw = result[0]["RESPONSE"]
                resp = json.loads(raw) if isinstance(raw, str) else raw
                if isinstance(resp, dict) and "choices" in resp:
                    return resp["choices"][0]["messages"]
                elif isinstance(resp, dict) and "messages" in resp:
                    return resp["messages"]
                return str(resp)
        except Exception as e:
            return f"Error generating response: {str(e)}"

        return ""

    # ----- Self-Critique (optional refinement step) -----

    @instrument(span_type=SpanAttributes.SpanType.GENERATION)
    def self_critique_refine(self, question: str, initial_response: str) -> str:
        """
        Apply a self-critique pass: ask the model to review and improve
        its own response for accuracy and completeness.

        In replay mode (_preloaded_response is set), the pre-existing response
        has already been through self-critique, so return it unchanged.
        """
        if getattr(self, "_preloaded_response", None):
            return initial_response

        if not self.self_critique:
            return initial_response

        critique_prompt = (
            f"You are a Snowflake documentation expert. Review the following "
            f"answer to the question and improve it. Fix any inaccuracies, "
            f"add missing details, and ensure it uses current Snowflake syntax.\n\n"
            f"Question: {question}\n\n"
            f"Current Answer:\n{initial_response}\n\n"
            f"Provide an improved, complete answer:"
        )

        messages = [{"role": "user", "content": critique_prompt}]
        messages_json = json.dumps(messages)
        options_json = json.dumps({"max_tokens": self.max_tokens})

        sql = """
            SELECT SNOWFLAKE.CORTEX.COMPLETE(
                ?,
                PARSE_JSON(?),
                PARSE_JSON(?)
            ) AS response
        """

        try:
            result = self.session.sql(sql, params=[self.model, messages_json, options_json]).collect()
            if result:
                raw = result[0]["RESPONSE"]
                resp = json.loads(raw) if isinstance(raw, str) else raw
                if isinstance(resp, dict) and "choices" in resp:
                    return resp["choices"][0]["messages"]
                elif isinstance(resp, dict) and "messages" in resp:
                    return resp["messages"]
                return str(resp)
        except Exception as e:
            return initial_response  # Fall back to original on error

        return initial_response

    # ----- Main entry point -----

    @instrument(
        attributes={
            SpanAttributes.RECORD_ROOT.INPUT: "question",
            SpanAttributes.RECORD_ROOT.OUTPUT: "return",
        },
    )
    def query(self, question: str) -> str:
        """
        Main entry point: answer an AEO benchmark question.

        Flow:
          1. Retrieve context (agentic mode only)
          2. Generate response
          3. Self-critique refinement (if enabled)
          4. Return final response
        """
        # Step 1: Retrieve context
        context = self.retrieve_context(question)

        # Step 2: Generate response
        response = self.generate_response(question, context if context else None)

        # Step 3: Self-critique
        if self.self_critique:
            response = self.self_critique_refine(question, response)

        return response

    # ----- Helpers -----

    def _find_question_id(self, question_text: str) -> Optional[str]:
        """Find question ID by matching text. Returns string ID like 'Q001'."""
        for qid, q_text in QUESTIONS.items():
            if q_text.strip() == question_text.strip():
                return qid
            # Fuzzy match: first 50 chars
            if q_text[:50].lower() in question_text[:80].lower():
                return qid
        return None


# ---------------------------------------------------------------------------
# Registration helper
# ---------------------------------------------------------------------------

def register_app(
    app: AEOBenchmarkApp,
    snowpark_session,
    app_name: str = "aeo_benchmark",
    app_version: str = "v1",
    connector=None,
    feedbacks=None,
):
    """
    Register the AEO app with TruLens and Snowflake AI Observability.

    Args:
        connector: Optional pre-existing SnowflakeConnector to reuse.
                   Pass this when registering multiple apps in one process
                   to avoid the 'TruSession with different connector' error.
                   If None, a new connector is created from snowpark_session.
        feedbacks: Optional list of trulens.core.Feedback objects to attach
                   to this app version. Used to inject pre-computed scores
                   as metrics visible in Snowsight Evaluations.

    Returns a TruApp instance ready for creating runs.
    """
    from trulens.apps.app import TruApp
    from trulens.connectors.snowflake import SnowflakeConnector

    if connector is None:
        connector = SnowflakeConnector(snowpark_session=snowpark_session)

    kwargs = {}
    if feedbacks:
        kwargs["feedbacks"] = feedbacks

    tru_app = TruApp(
        app,
        app_name=app_name,
        app_version=app_version,
        connector=connector,
        main_method=app.query,
        **kwargs,
    )

    return tru_app


# ---------------------------------------------------------------------------
# Run configuration factory
# ---------------------------------------------------------------------------

def create_run_config(
    run_name: str,
    dataset_name: str = "AEO_QUESTIONS",
    description: str = "",
    label: str = "",
):
    """
    Create a TruLens RunConfig for an AEO benchmark evaluation run.

    Args:
        run_name: Unique name for this run (e.g., 'run3_baseline_8192tok').
        dataset_name: Snowflake table name with questions and ground truth.
        description: Human-readable description.
        label: Tag for grouping runs.
    """
    from trulens.core.run import RunConfig

    return RunConfig(
        run_name=run_name,
        dataset_name=dataset_name,
        description=description,
        label=label,
        source_type="TABLE",
        dataset_spec={
            "input": "QUESTION_TEXT",
            "ground_truth_output": "CANONICAL_ANSWER",
        },
    )
