# AEO Benchmark: Task DAG Tutorial

Run the AEO benchmark entirely inside Snowflake using a 65-task DAG (1 root + 64 parallel children). No containers required. Estimated runtime: ~8 minutes per run.

---

## Architecture

```
AEO_RUN_CONFIG  ──►  TASK_AEO_ROOT (SP_AEO_INIT_RUN)
                              │
          ┌───────────────────┼───────────────────┐
  TASK_AEO_GEN_01         GEN_02 … GEN_32       (32 parallel)
  SP_AEO_GENERATE_MISSING(1)                    Q001–Q004 each
          └───────────────────┼───────────────────┘
                   (all gen tasks complete)
          ┌───────────────────┼───────────────────┐
  TASK_AEO_SCORE_01       SCORE_02 … SCORE_32    (32 parallel)
  SP_AEO_SCORE(1)                                3 judges each
          └───────────────────┴───────────────────┘
```

---

## Step 1: Prerequisites

```sql
USE WAREHOUSE COMPUTE_WH;
CREATE DATABASE IF NOT EXISTS AEO_OBSERVABILITY;
CREATE SCHEMA  IF NOT EXISTS AEO_OBSERVABILITY.EVAL_SCHEMA;
USE DATABASE AEO_OBSERVABILITY;
USE SCHEMA   EVAL_SCHEMA;
```

---

## Step 2: Create Tables

> Use `VARCHAR(65000)` for response and judge columns. `VARCHAR(16000)` silently truncates long answers.

```sql
CREATE TABLE IF NOT EXISTS AEO_QUESTIONS (
    QUESTION_ID       VARCHAR(10),
    QUESTION_TEXT     VARCHAR(2000),
    CATEGORY          VARCHAR(100),
    QUESTION_TYPE     VARCHAR(20),
    CANONICAL_ANSWER  VARCHAR(16000),
    MUST_HAVE_1       VARCHAR(500),
    MUST_HAVE_2       VARCHAR(500),
    MUST_HAVE_3       VARCHAR(500),
    MUST_HAVE_4       VARCHAR(500),
    MUST_HAVE_5       VARCHAR(500),
    DOC_URL           VARCHAR(500)
);

CREATE TABLE IF NOT EXISTS AEO_RUN_CONFIG (
    RUN_ID        NUMBER NOT NULL PRIMARY KEY,
    MODEL         VARCHAR(100) NOT NULL,
    DOMAIN_PROMPT BOOLEAN DEFAULT FALSE,
    CITE          BOOLEAN DEFAULT FALSE,
    JUDGE_MODELS  VARCHAR(500) DEFAULT 'openai-gpt-5.4,claude-opus-4-6,llama4-maverick',
    MAX_TOKENS    NUMBER  DEFAULT 8192,
    STATUS        VARCHAR(20) DEFAULT 'PENDING',
    CREATED_AT    TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);

CREATE TABLE IF NOT EXISTS AEO_RUNS (
    RUN_ID        NUMBER,
    RUN_DATE      TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
    DESCRIPTION   VARCHAR(1000),
    DOMAIN_PROMPT BOOLEAN,
    CITATION      BOOLEAN,
    AGENTIC       BOOLEAN,
    SELF_CRITIQUE BOOLEAN,
    MODEL         VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS AEO_RESPONSES (
    RUN_ID        NUMBER,
    QUESTION_ID   VARCHAR(10),
    RESPONSE_TEXT VARCHAR(65000),
    GENERATED_AT  TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);

CREATE TABLE IF NOT EXISTS AEO_SCORES (
    RUN_ID             NUMBER,
    QUESTION_ID        VARCHAR(10),
    JUDGE_MODEL        VARCHAR(100),
    CORRECTNESS        FLOAT,
    COMPLETENESS       FLOAT,
    RECENCY            FLOAT,
    CITATION           FLOAT,
    RECOMMENDATION     FLOAT,
    TOTAL_SCORE        FLOAT,
    MUST_HAVE_1        BOOLEAN DEFAULT FALSE,
    MUST_HAVE_2        BOOLEAN DEFAULT FALSE,
    MUST_HAVE_3        BOOLEAN DEFAULT FALSE,
    MUST_HAVE_4        BOOLEAN DEFAULT FALSE,
    MUST_HAVE_5        BOOLEAN DEFAULT FALSE,
    MUST_HAVE_PASS     FLOAT,
    RAW_JUDGE_RESPONSE VARCHAR(65000),
    SCORED_AT          TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);
```

---

## Step 3: Load Questions

Use the Python loader script to insert rows into `AEO_QUESTIONS`:

```bash
python3 scripts/upload_questions.py --connection my-snowflake
```

Verify:

```sql
SELECT COUNT(*), COUNT(DISTINCT CATEGORY) FROM AEO_QUESTIONS;
-- Expected: 128 questions, 32 categories
```

---

## Step 4: Create Stored Procedures

Six stored procedures are required. The key ones:

| SP | Purpose |
|---|---|
| `SP_AEO_INIT_RUN()` | Reads `AEO_RUN_CONFIG`, inserts row into `AEO_RUNS`, idempotent |
| `SP_AEO_GENERATE_MISSING(P_BATCH)` | Generates responses for batch N (4 questions), skips existing |
| `SP_AEO_SCORE(P_BATCH)` | Scores batch N with 3 judges via `SNOWFLAKE.CORTEX.COMPLETE` |
| `SP_AEO_SCORE_BACKFILL(P_RUN_ID)` | Re-scores only missing (question, judge) pairs |

Full DDL is in `skill/SKILL.md` under "Stored Procedure Reference".

---

## Step 5: Create Analysis Views

```sql
-- Leaderboard: ranked configs by average score
CREATE OR REPLACE VIEW V_AEO_LEADERBOARD AS ...;

-- Per-question heatmap: scores by question × run
CREATE OR REPLACE VIEW V_AEO_PER_QUESTION_HEATMAP AS ...;

-- Factorial effects: marginal gain per flag (D/C/A/S)
CREATE OR REPLACE VIEW V_AEO_FACTORIAL_EFFECTS AS ...;

-- Judge agreement: cross-judge correlation per run
CREATE OR REPLACE VIEW V_AEO_JUDGE_AGREEMENT AS ...;
```

Full view DDL is in `skill/SKILL.md` under "Step 4: Create Views".

---

## Step 6: Create Task DAG

> **Critical order**: resume all 64 child tasks BEFORE the root task. Resuming root first triggers an immediate execution.

```sql
-- Root task (manual-trigger only via EXECUTE TASK)
CREATE OR REPLACE TASK TASK_AEO_ROOT
  WAREHOUSE = COMPUTE_WH
  SCHEDULE  = '11520 MINUTE'   -- effectively never auto-fires
AS
  CALL SP_AEO_INIT_RUN();

-- 32 parallel generation tasks (repeat for 02–32, adjusting batch number)
CREATE OR REPLACE TASK TASK_AEO_GEN_01
  WAREHOUSE = COMPUTE_WH
  AFTER TASK_AEO_ROOT
AS
  CALL SP_AEO_GENERATE_MISSING(1);

-- 32 parallel scoring tasks (depend on ALL gen tasks completing)
CREATE OR REPLACE TASK TASK_AEO_SCORE_01
  WAREHOUSE = COMPUTE_WH
  AFTER TASK_AEO_GEN_01, TASK_AEO_GEN_02, /* ... */ TASK_AEO_GEN_32
AS
  CALL SP_AEO_SCORE(1);

-- Resume children first, then root
ALTER TASK TASK_AEO_GEN_01   RESUME;
-- ... (all 32 gen tasks)
ALTER TASK TASK_AEO_SCORE_01 RESUME;
-- ... (all 32 score tasks)
ALTER TASK TASK_AEO_ROOT     RESUME;  -- resume root LAST
```

---

## Step 7: Configure a Run

Insert one row into `AEO_RUN_CONFIG` before each run. The DAG reads this on startup.

```sql
-- Example: Run 5 — agentic only (Cortex Code retrieval enabled)
INSERT INTO AEO_RUN_CONFIG
    (RUN_ID, MODEL, DOMAIN_PROMPT, CITE, STATUS)
VALUES
    (5, 'claude-opus-4-6', FALSE, FALSE, 'PENDING');
```

The 16 factorial configurations map to runs 1–16:

| Run | D | C | A | S |
|-----|---|---|---|---|
| 1 | F | F | F | F | (baseline)
| 5 | F | F | T | F | (agentic only — uses Cortex Code)
| 16 | T | T | T | T | (all flags)

---

## Step 8: Trigger the Run

```sql
EXECUTE TASK TASK_AEO_ROOT;
```

The root task calls `SP_AEO_INIT_RUN()`, which fans out to 32 parallel gen tasks, then 32 parallel score tasks.

---

## Step 9: Monitor Progress

```sql
-- Check task graph execution status
SELECT *
FROM TABLE(INFORMATION_SCHEMA.TASK_HISTORY(
    SCHEDULED_TIME_RANGE_START => DATEADD('hour', -1, CURRENT_TIMESTAMP()),
    RESULT_LIMIT => 100
))
ORDER BY SCHEDULED_TIME DESC;

-- Check how many responses have been generated
SELECT COUNT(*) AS responses_so_far
FROM AEO_RESPONSES
WHERE RUN_ID = 5;  -- 128 expected when complete

-- Check scoring progress (3 judges × 128 questions = 384 expected)
SELECT COUNT(*) AS scores_so_far
FROM AEO_SCORES
WHERE RUN_ID = 5;
```

---

## Step 10: View Results

```sql
-- Overall leaderboard
SELECT RUN_ID, SCORE_PCT, MH_PCT, DOMAIN_PROMPT, CITATION, AGENTIC, SELF_CRITIQUE
FROM V_AEO_LEADERBOARD
ORDER BY SCORE_PCT DESC;

-- Marginal effect of each flag
SELECT FACTOR, SCORE_EFFECT_PP, MH_EFFECT_PP
FROM V_AEO_FACTORIAL_EFFECTS
ORDER BY SCORE_EFFECT_PP DESC;
```

---

## Backfill Missing Scores

If some tasks fail or score rows are missing, run the backfill SP without re-running generation:

```sql
CALL SP_AEO_SCORE_BACKFILL(5);  -- only scores missing (question, judge) pairs
```

---

## Cleanup

```sql
-- Suspend DAG when not in use (avoids credits from accidental triggers)
ALTER TASK TASK_AEO_ROOT SUSPEND;
```
