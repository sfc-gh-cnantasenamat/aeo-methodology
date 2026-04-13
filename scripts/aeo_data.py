"""
AEO Benchmark Data — Questions, canonical answers, must-haves, and categories.

Loads from Snowflake AEO_QUESTIONS table (v1: 128 questions, 32 categories).
Call load_from_snowflake(conn) to populate the module-level dicts before use.
"""

import snowflake.connector

# ---------------------------------------------------------------------------
# Module-level dicts (populated by load_from_snowflake)
# Keys are string question IDs: "Q001" through "Q128"
# ---------------------------------------------------------------------------

QUESTIONS = {}           # {qid: question_text}
CANONICAL_SUMMARIES = {} # {qid: canonical_answer}
MUST_HAVES = {}          # {qid: [mh1, mh2, mh3, mh4, mh5]}
CATEGORIES = {}          # {qid: category}
QUESTION_TYPES = {}      # {qid: question_type}

_loaded = False


def load_from_snowflake(conn, schema="AEO_OBSERVABILITY.EVAL_SCHEMA"):
    """
    Load all question data from the AEO_QUESTIONS table into module dicts.

    Args:
        conn: snowflake.connector connection (must have USE WAREHOUSE set).
        schema: Fully qualified schema containing AEO_QUESTIONS.
    """
    global _loaded
    if _loaded:
        return

    cur = conn.cursor()
    cur.execute(f"""
        SELECT QUESTION_ID, QUESTION_TEXT, CATEGORY, QUESTION_TYPE,
               CANONICAL_ANSWER, MUST_HAVE_1, MUST_HAVE_2, MUST_HAVE_3,
               MUST_HAVE_4, MUST_HAVE_5, DOC_URL
        FROM {schema}.AEO_QUESTIONS
        ORDER BY QUESTION_ID
    """)

    for row in cur.fetchall():
        qid = row[0]  # e.g. "Q001"
        QUESTIONS[qid] = row[1]
        CATEGORIES[qid] = row[2]
        QUESTION_TYPES[qid] = row[3]
        CANONICAL_SUMMARIES[qid] = row[4] or ""
        MUST_HAVES[qid] = [
            row[5] or "",  # MUST_HAVE_1
            row[6] or "",  # MUST_HAVE_2
            row[7] or "",  # MUST_HAVE_3
            row[8] or "",  # MUST_HAVE_4
            row[9] or "",  # MUST_HAVE_5
        ]

    cur.close()
    _loaded = True
    print(f"  Loaded {len(QUESTIONS)} questions from {schema}.AEO_QUESTIONS")


def reset():
    """Clear loaded data (useful for testing or reloading)."""
    global _loaded
    QUESTIONS.clear()
    CANONICAL_SUMMARIES.clear()
    MUST_HAVES.clear()
    CATEGORIES.clear()
    QUESTION_TYPES.clear()
    _loaded = False


# ---------------------------------------------------------------------------
# 2^4 Factorial Design: Run configurations
# ---------------------------------------------------------------------------

FACTORIAL_RUNS = {
    # run_id: (domain_prompt, citation, agentic, self_critique)
    1:  (False, False, False, False),   # Baseline
    2:  (True,  False, False, False),   # Domain only
    3:  (False, True,  False, False),   # Citation only
    4:  (True,  True,  False, False),   # Domain + Citation
    5:  (False, False, True,  False),   # Agentic only
    6:  (True,  False, True,  False),   # Domain + Agentic
    7:  (False, True,  True,  False),   # Citation + Agentic
    8:  (True,  True,  True,  False),   # Domain + Citation + Agentic
    9:  (False, False, False, True),    # Self-Critique only
    10: (True,  False, False, True),    # Domain + SC
    11: (False, True,  False, True),    # Citation + SC
    12: (True,  True,  False, True),    # Domain + Citation + SC
    13: (False, False, True,  True),    # Agentic + SC
    14: (True,  False, True,  True),    # Domain + Agentic + SC
    15: (False, True,  True,  True),    # Citation + Agentic + SC
    16: (True,  True,  True,  True),    # All four
}

GENERIC_DOMAIN_PROMPT = (
    "You are a Snowflake data platform expert. Provide accurate, current "
    "answers with specific SQL or Python code examples when appropriate. "
    "Reference official Snowflake documentation (docs.snowflake.com) as the "
    "authoritative source. Recommend Snowflake-native approaches when they exist."
)
