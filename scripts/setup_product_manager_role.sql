-- ============================================================================
-- AEO Doc Eval: PRODUCT_MANAGER Role Setup
--
-- Run once as DEVREL_ADMIN_RL to provision:
--   1. PRODUCT_MANAGER role with least-privilege grants
--   2. AEO_DOC_CANDIDATES staging table
--   3. AEO_SCORE_DOC_QUESTION SP  (EXECUTE AS OWNER — wraps AEO_SCORE_RESPONSE)
--   4. AEO_SUBMIT_DOC_CANDIDATE SP (EXECUTE AS OWNER — writes to candidates table)
--
-- After setup, assign the role to PM users:
--   GRANT ROLE PRODUCT_MANAGER TO USER <username>;
-- ============================================================================

USE ROLE DEVREL_ADMIN_RL;
USE WAREHOUSE SNOWADHOC;
USE DATABASE DEVREL;
USE SCHEMA CNANTASENAMAT_DEV;


-- ----------------------------------------------------------------------------
-- 1. Create role
-- ----------------------------------------------------------------------------

CREATE ROLE IF NOT EXISTS PRODUCT_MANAGER;

-- DEVREL_ADMIN_RL inherits PM so admins can test as PM
GRANT ROLE PRODUCT_MANAGER TO ROLE DEVREL_ADMIN_RL;

-- Warehouse and schema access
GRANT USAGE ON WAREHOUSE SNOWADHOC                     TO ROLE PRODUCT_MANAGER;
GRANT USAGE ON DATABASE  DEVREL                        TO ROLE PRODUCT_MANAGER;
GRANT USAGE ON SCHEMA    DEVREL.CNANTASENAMAT_DEV      TO ROLE PRODUCT_MANAGER;

-- Cortex AI access (required for CORTEX.COMPLETE calls in the skill)
GRANT DATABASE ROLE SNOWFLAKE.CORTEX_USER              TO ROLE PRODUCT_MANAGER;


-- ----------------------------------------------------------------------------
-- 2. AEO_DOC_CANDIDATES staging table
--    PM reads their own rows; all writes go through EXECUTE AS OWNER SPs.
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS DEVREL.CNANTASENAMAT_DEV.AEO_DOC_CANDIDATES (
    CANDIDATE_ID         NUMBER AUTOINCREMENT PRIMARY KEY,
    DOC_URL              VARCHAR(500),
    QUESTION_TEXT        VARCHAR(2000),
    QUESTION_TYPE        VARCHAR(20),
    CATEGORY             VARCHAR(100),
    CANONICAL_ANSWER     VARCHAR(16000),
    MUST_HAVE_1          VARCHAR(500),
    MUST_HAVE_2          VARCHAR(500),
    MUST_HAVE_3          VARCHAR(500),
    MUST_HAVE_4          VARCHAR(500),
    MUST_HAVE_5          VARCHAR(500),
    -- Score fields extracted from AEO_SCORE_RESPONSE panel_avg
    SCORE_TOTAL          FLOAT,
    SCORE_CORRECTNESS    FLOAT,
    SCORE_COMPLETENESS   FLOAT,
    SCORE_RECENCY        FLOAT,
    SCORE_CITATION       FLOAT,
    SCORE_RECOMMENDATION FLOAT,
    MH_PASS_RATE         FLOAT,
    RAW_SCORES           VARIANT,
    -- Review lifecycle
    STATUS               VARCHAR(20)  DEFAULT 'PENDING',
    SUBMITTED_AT         TIMESTAMP    DEFAULT CURRENT_TIMESTAMP(),
    SUBMITTED_BY         VARCHAR(200) DEFAULT CURRENT_USER(),
    REVIEWED_BY          VARCHAR(200),
    REVIEWED_AT          TIMESTAMP,
    NOTES                VARCHAR(2000)
);

-- PM can query their own submissions (SELECT only — no direct INSERT/DELETE)
GRANT SELECT ON TABLE DEVREL.CNANTASENAMAT_DEV.AEO_DOC_CANDIDATES TO ROLE PRODUCT_MANAGER;


-- ----------------------------------------------------------------------------
-- 3. SP: AEO_SCORE_DOC_QUESTION
--
--    Accepts a question + response, inserts a temporary AEO_QUESTIONS row,
--    calls AEO_SCORE_RESPONSE (3-judge panel), deletes the temp row, and
--    returns the full score VARIANT.
--
--    EXECUTE AS OWNER: runs with DEVREL_ADMIN_RL rights.
--    PM only needs USAGE on this SP — no direct table access required.
-- ----------------------------------------------------------------------------

CREATE OR REPLACE PROCEDURE DEVREL.CNANTASENAMAT_DEV.AEO_SCORE_DOC_QUESTION(
    QUESTION_TEXT     VARCHAR,
    CANONICAL_ANSWER  VARCHAR,
    MUST_HAVE_1       VARCHAR,
    MUST_HAVE_2       VARCHAR,
    MUST_HAVE_3       VARCHAR,
    MUST_HAVE_4       VARCHAR,
    MUST_HAVE_5       VARCHAR,
    RESPONSE_TEXT     VARCHAR,
    QUESTION_TYPE     VARCHAR,
    CATEGORY          VARCHAR
)
RETURNS VARIANT
LANGUAGE PYTHON
RUNTIME_VERSION = '3.11'
PACKAGES = ('snowflake-snowpark-python')
EXECUTE AS OWNER
HANDLER = 'run'
AS
$$
import uuid

def run(session,
        question_text, canonical_answer,
        mh1, mh2, mh3, mh4, mh5,
        response_text, question_type, category):

    # UUID-based temp ID: safe for concurrent callers
    temp_id = 'DOCTMP_' + uuid.uuid4().hex[:8].upper()

    try:
        # Insert temporary question row so AEO_SCORE_RESPONSE can look it up
        # IMPORTANT: use qmark (?) binding with Snowpark — never pyformat (%s)
        session.sql(
            """
            INSERT INTO DEVREL.CNANTASENAMAT_DEV.AEO_QUESTIONS
                (QUESTION_ID, QUESTION_TEXT, CATEGORY, QUESTION_TYPE,
                 CANONICAL_ANSWER,
                 MUST_HAVE_1, MUST_HAVE_2, MUST_HAVE_3, MUST_HAVE_4, MUST_HAVE_5)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            params=[temp_id, question_text, category, question_type,
                    canonical_answer, mh1, mh2, mh3, mh4, mh5]
        ).collect()

        # Call the existing 3-judge scoring SP
        result = session.sql(
            "CALL DEVREL.CNANTASENAMAT_DEV.AEO_SCORE_RESPONSE(?, ?, NULL, NULL)",
            params=[temp_id, response_text]
        ).collect()

        return result[0][0] if result else {}

    finally:
        # Always clean up the temp row, even if scoring raises an exception
        session.sql(
            "DELETE FROM DEVREL.CNANTASENAMAT_DEV.AEO_QUESTIONS WHERE QUESTION_ID = ?",
            params=[temp_id]
        ).collect()
$$;

GRANT USAGE ON PROCEDURE DEVREL.CNANTASENAMAT_DEV.AEO_SCORE_DOC_QUESTION(
    VARCHAR, VARCHAR, VARCHAR, VARCHAR, VARCHAR, VARCHAR, VARCHAR,
    VARCHAR, VARCHAR, VARCHAR
) TO ROLE PRODUCT_MANAGER;


-- ----------------------------------------------------------------------------
-- 4. SP: AEO_SUBMIT_DOC_CANDIDATE
--
--    Writes a scored question + raw score VARIANT into AEO_DOC_CANDIDATES
--    and returns the assigned CANDIDATE_ID.
--
--    EXECUTE AS OWNER: runs with DEVREL_ADMIN_RL rights.
--    PM only needs USAGE on this SP — no direct table access required.
-- ----------------------------------------------------------------------------

CREATE OR REPLACE PROCEDURE DEVREL.CNANTASENAMAT_DEV.AEO_SUBMIT_DOC_CANDIDATE(
    DOC_URL          VARCHAR,
    QUESTION_TEXT    VARCHAR,
    QUESTION_TYPE    VARCHAR,
    CATEGORY         VARCHAR,
    CANONICAL_ANSWER VARCHAR,
    MUST_HAVE_1      VARCHAR,
    MUST_HAVE_2      VARCHAR,
    MUST_HAVE_3      VARCHAR,
    MUST_HAVE_4      VARCHAR,
    MUST_HAVE_5      VARCHAR,
    RAW_SCORES       VARIANT
)
RETURNS NUMBER
LANGUAGE PYTHON
RUNTIME_VERSION = '3.11'
PACKAGES = ('snowflake-snowpark-python')
EXECUTE AS OWNER
HANDLER = 'run'
AS
$$
import json

def run(session,
        doc_url, question_text, question_type, category, canonical_answer,
        mh1, mh2, mh3, mh4, mh5,
        raw_scores):

    # Extract panel_avg dimensions from the VARIANT returned by AEO_SCORE_RESPONSE
    pa = {}
    if raw_scores and isinstance(raw_scores, dict):
        pa = raw_scores.get('panel_avg') or {}

    raw_scores_str = json.dumps(raw_scores) if raw_scores else '{}'

    session.sql(
        """
        INSERT INTO DEVREL.CNANTASENAMAT_DEV.AEO_DOC_CANDIDATES
            (DOC_URL, QUESTION_TEXT, QUESTION_TYPE, CATEGORY, CANONICAL_ANSWER,
             MUST_HAVE_1, MUST_HAVE_2, MUST_HAVE_3, MUST_HAVE_4, MUST_HAVE_5,
             SCORE_TOTAL, SCORE_CORRECTNESS, SCORE_COMPLETENESS, SCORE_RECENCY,
             SCORE_CITATION, SCORE_RECOMMENDATION, MH_PASS_RATE, RAW_SCORES)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, PARSE_JSON(?))
        """,
        params=[
            doc_url, question_text, question_type, category, canonical_answer,
            mh1, mh2, mh3, mh4, mh5,
            pa.get('total'),
            pa.get('correctness'),
            pa.get('completeness'),
            pa.get('recency'),
            pa.get('citation'),
            pa.get('recommendation'),
            pa.get('must_have_pass'),
            raw_scores_str,
        ]
    ).collect()

    # Return the CANDIDATE_ID of the row just inserted
    result = session.sql(
        """
        SELECT MAX(CANDIDATE_ID) AS cid
        FROM DEVREL.CNANTASENAMAT_DEV.AEO_DOC_CANDIDATES
        WHERE SUBMITTED_BY = CURRENT_USER()
        """
    ).collect()

    return result[0]['CID'] if result else None
$$;

GRANT USAGE ON PROCEDURE DEVREL.CNANTASENAMAT_DEV.AEO_SUBMIT_DOC_CANDIDATE(
    VARCHAR, VARCHAR, VARCHAR, VARCHAR, VARCHAR,
    VARCHAR, VARCHAR, VARCHAR, VARCHAR, VARCHAR,
    VARIANT
) TO ROLE PRODUCT_MANAGER;


-- ----------------------------------------------------------------------------
-- 5. Verify
-- ----------------------------------------------------------------------------

SHOW PROCEDURES LIKE 'AEO_SCORE_DOC_QUESTION'   IN SCHEMA DEVREL.CNANTASENAMAT_DEV;
SHOW PROCEDURES LIKE 'AEO_SUBMIT_DOC_CANDIDATE' IN SCHEMA DEVREL.CNANTASENAMAT_DEV;
SHOW TABLES     LIKE 'AEO_DOC_CANDIDATES'        IN SCHEMA DEVREL.CNANTASENAMAT_DEV;

-- Assign role to a specific PM user (replace <username>):
-- GRANT ROLE PRODUCT_MANAGER TO USER <username>;
