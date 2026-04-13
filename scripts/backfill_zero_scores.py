"""
Backfill zero-score questions caused by the $$ delimiter bug.

Two passes:
  A) Generation errors: response starts with "Error" -> re-generate + re-score
  B) Scoring errors: valid response but zero scores -> re-score only

For each affected (run_id, question_id):
  1. DELETE existing zero-score rows from AEO_SCORES
  2. Re-generate response if needed (and UPDATE AEO_RESPONSES)
  3. Re-score with 3-judge panel
  4. INSERT new scores into AEO_SCORES
"""

import json
import sys

sys.path.insert(0, "/Users/cnantasenamat/Documents/Coco/aeo/observability")

from aeo_run_orchestrator import get_connection, _call_cortex_complete
from aeo_data import (
    QUESTIONS, CANONICAL_SUMMARIES, MUST_HAVES, FACTORIAL_RUNS,
    GENERIC_DOMAIN_PROMPT,
)
from aeo_feedback_functions import (
    score_with_panel_and_trulens, clear_score_cache, JUDGE_PANEL,
)


def backfill(profile="devrel"):
    conn = get_connection(profile=profile)
    cur = conn.cursor()

    # Find all zero-score (run_id, question_id) combos with their response status
    cur.execute("""
        SELECT DISTINCT s.RUN_ID, s.QUESTION_ID,
               CASE WHEN r.RESPONSE_TEXT LIKE 'Error%%' THEN TRUE ELSE FALSE END as is_error
        FROM AEO_SCORES s
        JOIN AEO_RESPONSES r ON s.RUN_ID = r.RUN_ID AND s.QUESTION_ID = r.QUESTION_ID
        JOIN AEO_RUNS rm ON s.RUN_ID = rm.RUN_ID
        WHERE s.TOTAL_SCORE = 0
        AND rm.DESCRIPTION LIKE '2^4 factorial%%'
        ORDER BY s.RUN_ID, s.QUESTION_ID
    """)
    zero_combos = cur.fetchall()
    print(f"Found {len(zero_combos)} zero-score (run, question) combos to backfill")

    gen_errors = [(r, q) for r, q, is_err in zero_combos if is_err]
    score_errors = [(r, q) for r, q, is_err in zero_combos if not is_err]
    print(f"  Generation errors (need re-gen + re-score): {len(gen_errors)}")
    print(f"  Scoring errors (need re-score only): {len(score_errors)}")
    print()

    success_count = 0
    fail_count = 0

    # Pass A: Re-generate + re-score for generation errors
    if gen_errors:
        print("=== Pass A: Re-generating failed responses ===")
        for run_id, qid in gen_errors:
            dp, cite_flag, ag, sc = FACTORIAL_RUNS[run_id]
            question = QUESTIONS[qid]

            # Build the same prompt as the original run
            if cite_flag:
                question_text = question + (
                    "\n\nIMPORTANT: Include specific references to official "
                    "Snowflake documentation (docs.snowflake.com) in your answer."
                )
            else:
                question_text = question

            if ag and qid in CANONICAL_SUMMARIES:
                context = CANONICAL_SUMMARIES[qid]
                user_content = (
                    f"Use the following reference material to inform your answer:\n\n"
                    f"---\n{context}\n---\n\n"
                    f"Question: {question_text}"
                )
            else:
                user_content = question_text

            messages = []
            if dp:
                messages.append({"role": "system", "content": GENERIC_DOMAIN_PROMPT})
            messages.append({"role": "user", "content": user_content})

            try:
                text = _call_cortex_complete(cur, "claude-opus-4-6", messages, 8192)

                # Self-critique if enabled
                if sc and text and not text.startswith("Error"):
                    critique_messages = [{
                        "role": "user",
                        "content": (
                            f"You are a Snowflake documentation expert. Review the following "
                            f"answer to the question and improve it. Fix any inaccuracies, "
                            f"add missing details, and ensure it uses current Snowflake syntax.\n\n"
                            f"Question: {question_text}\n\n"
                            f"Current Answer:\n{text}\n\n"
                            f"Provide an improved, complete answer:"
                        ),
                    }]
                    try:
                        refined = _call_cortex_complete(cur, "claude-opus-4-6", critique_messages, 8192)
                        if refined and not refined.startswith("Error"):
                            text = refined
                    except Exception:
                        pass  # Keep original on SC failure

                if text and not text.startswith("Error"):
                    # Update the response
                    cur.execute(
                        "UPDATE AEO_RESPONSES SET RESPONSE_TEXT = %s WHERE RUN_ID = %s AND QUESTION_ID = %s",
                        (text, run_id, qid),
                    )
                    print(f"  Run {run_id} {qid}: re-generated {len(text)} chars")
                else:
                    print(f"  Run {run_id} {qid}: generation still failed, skipping")
                    fail_count += 1
                    continue
            except Exception as e:
                print(f"  Run {run_id} {qid}: generation error: {str(e)[:80]}")
                fail_count += 1
                continue

            # Now score it
            try:
                _rescore_one(conn, cur, run_id, qid, text)
                success_count += 1
            except Exception as e:
                print(f"  Run {run_id} {qid}: scoring error: {str(e)[:80]}")
                fail_count += 1

        print()

    # Pass B: Re-score only for scoring errors
    if score_errors:
        print("=== Pass B: Re-scoring valid responses ===")
        for run_id, qid in score_errors:
            # Load existing response
            cur.execute(
                "SELECT RESPONSE_TEXT FROM AEO_RESPONSES WHERE RUN_ID = %s AND QUESTION_ID = %s",
                (run_id, qid),
            )
            row = cur.fetchone()
            if not row:
                print(f"  Run {run_id} {qid}: no response found, skipping")
                fail_count += 1
                continue

            response_text = row[0]

            try:
                _rescore_one(conn, cur, run_id, qid, response_text)
                success_count += 1
            except Exception as e:
                print(f"  Run {run_id} {qid}: scoring error: {str(e)[:80]}")
                fail_count += 1

    print(f"\n=== Backfill Complete ===")
    print(f"  Success: {success_count}")
    print(f"  Failed: {fail_count}")
    print(f"  Total: {success_count + fail_count}")

    cur.close()
    conn.close()


def _rescore_one(conn, cur, run_id, qid, response_text):
    """Delete old zero scores for (run_id, qid) and insert new scores."""
    question = QUESTIONS.get(qid, "")
    canonical = CANONICAL_SUMMARIES.get(qid, "")
    must_haves = MUST_HAVES.get(qid, [])

    # Score with the 3-judge panel
    panel_result = score_with_panel_and_trulens(
        conn, question, response_text, canonical, must_haves, JUDGE_PANEL
    )
    clear_score_cache()

    avg_total = panel_result["panel_avg"].get("total", 0)
    avg_mh = panel_result["panel_avg"].get("must_have_pass", 0)

    # Delete old zero-score rows
    cur.execute(
        "DELETE FROM AEO_SCORES WHERE RUN_ID = %s AND QUESTION_ID = %s AND TOTAL_SCORE = 0",
        (run_id, qid),
    )

    # Insert new scores
    for judge_name, scores in panel_result.get("judges", {}).items():
        mh = scores.get("must_have", [False, False, False, False, False])
        cur.execute(
            """
            INSERT INTO AEO_SCORES (
                RUN_ID, QUESTION_ID, JUDGE_MODEL,
                CORRECTNESS, COMPLETENESS, RECENCY, CITATION, RECOMMENDATION,
                TOTAL_SCORE,
                MUST_HAVE_1, MUST_HAVE_2, MUST_HAVE_3, MUST_HAVE_4, MUST_HAVE_5,
                MUST_HAVE_PASS, RAW_JUDGE_RESPONSE
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                run_id,
                qid,
                judge_name,
                scores.get("correctness", 0),
                scores.get("completeness", 0),
                scores.get("recency", 0),
                scores.get("citation", 0),
                scores.get("recommendation", 0),
                scores.get("total", 0),
                mh[0] if len(mh) > 0 else False,
                mh[1] if len(mh) > 1 else False,
                mh[2] if len(mh) > 2 else False,
                mh[3] if len(mh) > 3 else False,
                mh[4] if len(mh) > 4 else False,
                scores.get("must_have_pass", 0.0),
                scores.get("raw_response", "")[:8000],
            ),
        )

    print(f"  Run {run_id} {qid}: score={avg_total:.1f}/50  mh={avg_mh:.2f}")


if __name__ == "__main__":
    backfill()
