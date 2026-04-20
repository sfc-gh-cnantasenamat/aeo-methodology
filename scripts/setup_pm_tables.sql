-- ============================================================================
-- AEO PM Tools: Tables and Stage for Prompt/Skill Eval Loops
-- Run once on Snowhouse (connection: my-snowflake)
-- ============================================================================

USE ROLE DEVREL_ADMIN_RL;
USE WAREHOUSE SNOWADHOC;
USE DATABASE DEVREL;
USE SCHEMA CNANTASENAMAT_DEV;

-- ---------------------------------------------------------------------------
-- Table: AEO_PM_PROMPTS — stores PM prompt experiments and eval results
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS AEO_PM_PROMPTS (
    EXPERIMENT_ID    VARCHAR        NOT NULL,
    CREATED_AT       TIMESTAMP_NTZ  DEFAULT CURRENT_TIMESTAMP(),
    USER_NAME        VARCHAR        DEFAULT 'local',
    SYSTEM_PROMPT    VARCHAR,                          -- PM's custom system prompt
    QUESTION_ID      VARCHAR,                          -- FK to AEO_QUESTIONS (NULL if custom)
    CUSTOM_QUESTION  VARCHAR,                          -- free-text question (NULL if from bank)
    CATEGORY         VARCHAR,                          -- category for baseline comparison
    MODEL            VARCHAR        DEFAULT 'claude-opus-4-6',
    RESPONSE_TEXT    VARCHAR,                          -- generated response
    CORRECTNESS      FLOAT,
    COMPLETENESS     FLOAT,
    RECENCY          FLOAT,
    CITATION_SCORE   FLOAT,
    RECOMMENDATION   FLOAT,
    TOTAL_SCORE      FLOAT,
    MUST_HAVE_PASS   FLOAT,
    JUDGE_DETAILS    VARIANT,                          -- per-judge raw JSON
    PRIMARY KEY (EXPERIMENT_ID)
);

-- ---------------------------------------------------------------------------
-- Table: AEO_SKILL_TESTS — stores skill eval results
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS AEO_SKILL_TESTS (
    TEST_ID          VARCHAR        NOT NULL,
    CREATED_AT       TIMESTAMP_NTZ  DEFAULT CURRENT_TIMESTAMP(),
    USER_NAME        VARCHAR        DEFAULT 'local',
    SKILL_NAME       VARCHAR        NOT NULL,
    SKILL_VERSION    VARCHAR,
    QUESTION_ID      VARCHAR        NOT NULL,          -- FK to AEO_QUESTIONS
    CATEGORY         VARCHAR,
    MODEL            VARCHAR        DEFAULT 'claude-opus-4-6',
    RESPONSE_TEXT    VARCHAR,
    CORRECTNESS      FLOAT,
    COMPLETENESS     FLOAT,
    RECENCY          FLOAT,
    CITATION_SCORE   FLOAT,
    RECOMMENDATION   FLOAT,
    TOTAL_SCORE      FLOAT,
    MUST_HAVE_PASS   FLOAT,
    JUDGE_DETAILS    VARIANT,
    PRIMARY KEY (TEST_ID)
);

-- ---------------------------------------------------------------------------
-- Stage: AEO_SKILL_STAGE — stores uploaded SKILL.md files
-- ---------------------------------------------------------------------------
CREATE STAGE IF NOT EXISTS AEO_SKILL_STAGE
    ENCRYPTION = (TYPE = 'SNOWFLAKE_SSE')
    COMMENT = 'Internal stage for AEO skill evaluation SKILL.md files';
