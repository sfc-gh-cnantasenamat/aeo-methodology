"""
Re-score the 5 remaining maverick zero-score entries with temperature=0.3.

These are cases where llama4-maverick gave all-zero scores while the other
judges gave low-but-nonzero scores. With temperature=0.0, maverick is
deterministic and will produce the same result. A small temperature gives
it a chance to produce a more nuanced score.

If maverick still returns 0 after retry, we accept it as genuine.
"""

import json
import re
import sys

sys.path.insert(0, "/Users/cnantasenamat/Documents/Coco/aeo/observability")

from aeo_run_orchestrator import get_connection
from aeo_data import QUESTIONS, CANONICAL_SUMMARIES, MUST_HAVES
from aeo_feedback_functions import JUDGE_PROMPT_TEMPLATE, _parse_judge_response

# The 5 zero-score (run_id, question_id) combos
TARGETS = [
    (1, "Q054"),
    (1, "Q071"),
    (1, "Q102"),
    (9, "Q102"),
    (14, "Q066"),
]

JUDGE_MODEL = "llama4-maverick"


def _call_judge_with_temp(cur, judge_model, prompt, temperature=0.3):
    """Call judge with configurable temperature."""
    messages = [{"role": "user", "content": prompt}]
    messages_json = json.dumps(messages)
    options_json = json.dumps({"max_tokens": 1024, "temperature": temperature})

    sql = """
        SELECT SNOWFLAKE.CORTEX.COMPLETE(
            %s,
            PARSE_JSON(%s),
            PARSE_JSON(%s)
        ) AS response
    """
    cur.execute(sql, (judge_model, messages_json, options_json))
    row = cur.fetchone()
    raw = row[0] if row else ""

    if isinstance(raw, str):
        resp = json.loads(raw)
    else:
        resp = raw

    if isinstance(resp, dict):
        if "choices" in resp:
            return resp["choices"][0].get("messages", str(resp))
        if "messages" in resp:
            return resp["messages"]
    return str(resp)


def main():
    conn = get_connection(profile="devrel")
    cur = conn.cursor()

    for run_id, qid in TARGETS:
        # Load the response text
        cur.execute(
            "SELECT RESPONSE_TEXT FROM AEO_OBSERVABILITY.EVAL_SCHEMA.AEO_RESPONSES WHERE RUN_ID = %s AND QUESTION_ID = %s",
            (run_id, qid),
        )
        row = cur.fetchone()
        if not row:
            print(f"  Run {run_id} {qid}: no response, skipping")
            continue

        response_text = row[0]
        question = QUESTIONS.get(qid, "")
        canonical = CANONICAL_SUMMARIES.get(qid, "")
        must_haves_list = MUST_HAVES.get(qid, [])
        mh = [m for m in must_haves_list if m]
        mh_count = len(mh)
        must_have_list_str = "\n".join(f"{i+1}. {m}" for i, m in enumerate(mh)) or "N/A"

        prompt = JUDGE_PROMPT_TEMPLATE.format(
            question=question,
            canonical_answer=canonical[:3000],
            must_have_list=must_have_list_str,
            response=response_text[:3000],
        )

        # Call maverick with temperature=0.3
        raw = _call_judge_with_temp(cur, JUDGE_MODEL, prompt, temperature=0.3)
        scores = _parse_judge_response(raw, mh_count)

        new_total = scores["total"]
        new_mh = scores["must_have_pass"]
        parse_error = scores.get("parse_error", False)

        print(f"  Run {run_id} {qid}: new_score={new_total:.1f}/50  mh={new_mh:.2f}  parse_error={parse_error}")

        if new_total > 0 or not parse_error:
            # Delete old zero row
            cur.execute(
                "DELETE FROM AEO_OBSERVABILITY.EVAL_SCHEMA.AEO_SCORES WHERE RUN_ID = %s AND QUESTION_ID = %s AND JUDGE_MODEL = %s",
                (run_id, qid, JUDGE_MODEL),
            )
            # Insert new score
            mh_bools = scores.get("must_have", [False]*5)
            cur.execute(
                """
                INSERT INTO AEO_OBSERVABILITY.EVAL_SCHEMA.AEO_SCORES (
                    RUN_ID, QUESTION_ID, JUDGE_MODEL,
                    CORRECTNESS, COMPLETENESS, RECENCY, CITATION, RECOMMENDATION,
                    TOTAL_SCORE,
                    MUST_HAVE_1, MUST_HAVE_2, MUST_HAVE_3, MUST_HAVE_4, MUST_HAVE_5,
                    MUST_HAVE_PASS, RAW_JUDGE_RESPONSE
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    run_id, qid, JUDGE_MODEL,
                    scores["correctness"], scores["completeness"],
                    scores["recency"], scores["citation"], scores["recommendation"],
                    new_total,
                    mh_bools[0] if len(mh_bools) > 0 else False,
                    mh_bools[1] if len(mh_bools) > 1 else False,
                    mh_bools[2] if len(mh_bools) > 2 else False,
                    mh_bools[3] if len(mh_bools) > 3 else False,
                    mh_bools[4] if len(mh_bools) > 4 else False,
                    new_mh,
                    scores.get("raw_response", "")[:8000],
                ),
            )
            status = "UPDATED" if new_total > 0 else "still zero (kept new)"
        else:
            status = "still zero (kept old)"

        print(f"           -> {status}")

    cur.close()
    conn.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
