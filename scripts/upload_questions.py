"""
Upload AEO benchmark questions to Snowflake.
Reads from aeo_data.py and inserts into AEO_OBSERVABILITY.EVAL_SCHEMA.AEO_QUESTIONS.
"""
import sys
sys.path.insert(0, "/Users/cnantasenamat/Documents/Coco/aeo/observability")

import snowflake.connector
import json
from aeo_data import QUESTIONS, CANONICAL_SUMMARIES, MUST_HAVES, CATEGORIES, QUESTION_TYPES

# Connect to Snowflake
conn = snowflake.connector.connect(
    connection_name="devrel",
)
cur = conn.cursor()
cur.execute("USE WAREHOUSE COMPUTE_WH")
cur.execute("USE DATABASE AEO_OBSERVABILITY")
cur.execute("USE SCHEMA EVAL_SCHEMA")

# Insert each question
inserted = 0
for q_id in sorted(QUESTIONS.keys()):
    q_text = QUESTIONS[q_id]
    category = CATEGORIES.get(q_id, "Unknown")
    q_type = QUESTION_TYPES.get(q_id, "Unknown")
    canonical = CANONICAL_SUMMARIES.get(q_id, "")
    mh = MUST_HAVES.get(q_id, ["", "", "", ""])
    # Pad to 4 must-haves
    while len(mh) < 4:
        mh.append("")

    cur.execute(
        """
        INSERT INTO AEO_QUESTIONS (QUESTION_ID, QUESTION_TEXT, CATEGORY, QUESTION_TYPE,
                                   CANONICAL_ANSWER, MUST_HAVE_1, MUST_HAVE_2, MUST_HAVE_3, MUST_HAVE_4)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            f"Q{q_id:02d}",
            q_text,
            category,
            q_type,
            canonical,
            mh[0],
            mh[1],
            mh[2],
            mh[3],
        ),
    )
    inserted += 1

print(f"Inserted {inserted} questions into AEO_OBSERVABILITY.EVAL_SCHEMA.AEO_QUESTIONS")

# Verify
cur.execute("SELECT COUNT(*) FROM AEO_QUESTIONS")
count = cur.fetchone()[0]
print(f"Verification: {count} rows in AEO_QUESTIONS")

cur.close()
conn.close()
