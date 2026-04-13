---
name: aeo-benchmark
description: "Deploy and run the AEO benchmark entirely inside Snowflake using parallel Task DAGs or SPCS containers. Dataset-agnostic (reads from AEO_QUESTIONS table). 2^4 factorial experiment design (domain_prompt, citation, agentic, self_critique) with 3-judge panel scoring via CORTEX.COMPLETE. Two execution modes: Task DAG (parallel stored procedures) or SPCS (containerized job services). Supports: deploy schema, run benchmarks (runs 1-16), monitor progress, backfill gaps, view results. Triggers: aeo, aeo benchmark, run benchmark, deploy aeo, aeo results, benchmark progress, aeo score, aeo leaderboard, spcs benchmark, run via spcs, spcs run, container benchmark, factorial, run 2, next run."
---

# AEO Benchmark (Snowflake-Native Parallel)

Run the AI Engine Optimization benchmark entirely inside Snowflake. Dataset-agnostic: reads whatever questions are loaded in `AEO_QUESTIONS` (query `SELECT COUNT(*) FROM AEO_QUESTIONS` to discover the dataset size). Scored by a 3-judge panel using CORTEX.COMPLETE. Two execution modes available:

- **Task DAG**: 32-way parallel Snowflake Tasks calling stored procedures. Zero container overhead, best for repeated runs.
- **SPCS Containers**: 8 parallel SPCS job services (16 questions each). Containerized Python runner, best for isolated/reproducible runs or writing to a separate schema.

## Execution Mode Selection

**Ask the user before Deploy or Run intents:**

> Which execution mode would you like to use?
> 1. **Task DAG** (default) — Snowflake Tasks with 32-way parallelism, stored procedures, zero container overhead
> 2. **SPCS Containers** — 8 parallel SPCS job services, containerized Python runner, requires Docker + image push

| Choice | Deploy section | Run section | Monitor section |
|--------|---------------|-------------|-----------------|
| Task DAG | "Deploy Intent" | "Run Intent" | "Monitor Intent" |
| SPCS | "SPCS Deploy" | "SPCS Run" | "SPCS Monitor" |

If the user mentions "SPCS", "container", "docker", or "job service", route directly to SPCS mode without asking.

---

## Intent Detection

| Intent | Triggers | Action |
|--------|----------|--------|
| **Deploy** | "deploy aeo", "create aeo schema", "set up benchmark" | Create all Snowflake objects from scratch |
| **Run** | "run benchmark", "start run", "run aeo" | Configure and trigger a new benchmark run |
| **Monitor** | "check progress", "how's the run", "benchmark status" | Check response/scoring progress |
| **Backfill** | "backfill", "fill gaps", "retry missing" | Retry failed questions |
| **Results** | "show results", "leaderboard", "scores", "aeo results" | Query and display benchmark results |
| **Cleanup** | "clean up", "dedup scores", "fix duplicates" | Deduplicate scores from multiple DAG cycles |

---

## Architecture Overview

```
AEO_RUN_CONFIG (parameter store)
        │
        ▼
TASK_AEO_ROOT ── SP_AEO_INIT_RUN()
        │
        ├── TASK_AEO_GEN_01 ── SP_AEO_GENERATE_MISSING(1)  [Q001-Q004]
        ├── TASK_AEO_GEN_02 ── SP_AEO_GENERATE_MISSING(2)  [Q005-Q008]
        ├── ...
        └── TASK_AEO_GEN_32 ── SP_AEO_GENERATE_MISSING(32) [Q125-Q128]
                │ (all 32 gen tasks complete)
                ▼
        ├── TASK_AEO_SCORE_01 ── SP_AEO_SCORE(1)
        ├── TASK_AEO_SCORE_02 ── SP_AEO_SCORE(2)
        ├── ...
        └── TASK_AEO_SCORE_32 ── SP_AEO_SCORE(32)
```

- **Phase 1**: 32 parallel gen tasks call CORTEX.COMPLETE for inference
- **Phase 2**: 32 parallel score tasks call 3 judge models (one row per judge per question)
- **Batch mapping**: Batch N = Q((N-1)*4+1) through Q(N*4), zero-padded (Q001-Q128)
- **Estimated clean runtime**: ~6 min inference + ~2 min scoring = ~8 min total (32-way parallel)

---

## Deploy Intent

Create all Snowflake objects from scratch. Run these in order.

### Prerequisites

```sql
USE WAREHOUSE COMPUTE_WH;
CREATE DATABASE IF NOT EXISTS AEO_OBSERVABILITY;
CREATE SCHEMA IF NOT EXISTS AEO_OBSERVABILITY.EVAL_SCHEMA;
USE DATABASE AEO_OBSERVABILITY;
USE SCHEMA EVAL_SCHEMA;
```

### Step 1: Create Tables

**CRITICAL**: Use `VARCHAR(65000)` for RESPONSE_TEXT and RAW_JUDGE_RESPONSE. `VARCHAR(16000)` will silently fail on complex questions that generate 15K-33K char responses.

```sql
CREATE TABLE IF NOT EXISTS AEO_QUESTIONS (
    QUESTION_ID VARCHAR(10),
    QUESTION_TEXT VARCHAR(2000),
    CATEGORY VARCHAR(100),
    QUESTION_TYPE VARCHAR(20),
    CANONICAL_ANSWER VARCHAR(16000),
    MUST_HAVE_1 VARCHAR(500),
    MUST_HAVE_2 VARCHAR(500),
    MUST_HAVE_3 VARCHAR(500),
    MUST_HAVE_4 VARCHAR(500),
    MUST_HAVE_5 VARCHAR(500),
    DOC_URL VARCHAR(500)
);

CREATE TABLE IF NOT EXISTS AEO_RUN_CONFIG (
    RUN_ID NUMBER NOT NULL PRIMARY KEY,
    MODEL VARCHAR(100) NOT NULL,
    DOMAIN_PROMPT BOOLEAN DEFAULT FALSE,
    CITE BOOLEAN DEFAULT FALSE,
    JUDGE_MODELS VARCHAR(500) DEFAULT 'openai-gpt-5.4,claude-opus-4-6,llama4-maverick',
    MAX_TOKENS NUMBER DEFAULT 8192,
    STATUS VARCHAR(20) DEFAULT 'PENDING',
    CREATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);

CREATE TABLE IF NOT EXISTS AEO_RUNS (
    RUN_ID NUMBER,
    RUN_DATE TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
    DESCRIPTION VARCHAR(1000),
    DOMAIN_PROMPT BOOLEAN,
    CITATION BOOLEAN,
    AGENTIC BOOLEAN,
    SELF_CRITIQUE BOOLEAN,
    MODEL VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS AEO_RESPONSES (
    RUN_ID NUMBER,
    QUESTION_ID VARCHAR(10),
    RESPONSE_TEXT VARCHAR(65000),
    GENERATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);

CREATE TABLE IF NOT EXISTS AEO_SCORES (
    RUN_ID NUMBER,
    QUESTION_ID VARCHAR(10),
    JUDGE_MODEL VARCHAR(100),
    CORRECTNESS FLOAT,
    COMPLETENESS FLOAT,
    RECENCY FLOAT,
    CITATION FLOAT,
    RECOMMENDATION FLOAT,
    TOTAL_SCORE FLOAT,
    MUST_HAVE_1 BOOLEAN DEFAULT FALSE,
    MUST_HAVE_2 BOOLEAN DEFAULT FALSE,
    MUST_HAVE_3 BOOLEAN DEFAULT FALSE,
    MUST_HAVE_4 BOOLEAN DEFAULT FALSE,
    MUST_HAVE_5 BOOLEAN DEFAULT FALSE,
    MUST_HAVE_PASS FLOAT,
    RAW_JUDGE_RESPONSE VARCHAR(65000),
    SCORED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);
```

### Step 2: Load Questions

Parse the canonical answers file (or use the Python loader at `~/Documents/Coco/aeo/v1_loader/load_to_snowflake.py`) to INSERT questions into AEO_QUESTIONS. Each question has: QUESTION_ID (e.g., Q001-Q128), QUESTION_TEXT, CATEGORY, QUESTION_TYPE, CANONICAL_ANSWER, DOC_URL, MUST_HAVE_1 through MUST_HAVE_5. The number of questions depends on the dataset loaded.

### Step 3: Create Stored Procedures

Create these 6 SPs using `$$` delimiters. See the "Stored Procedure Reference" section below for full DDL.

1. **SP_AEO_INIT_RUN()** — Reads config, creates run row, idempotent on re-triggers
2. **SP_AEO_GENERATE(P_BATCH, P_QUESTION_FILTER)** — Inference via CORTEX.COMPLETE
3. **SP_AEO_GENERATE_MISSING(P_BATCH)** — Same but skips questions with existing responses (LEFT JOIN pattern)
4. **SP_AEO_SCORE(P_RUN_ID, P_BATCH, P_QUESTION_FILTER, P_BATCH_SIZE)** — 3-judge scoring (1-10 scale, no panel_avg)
5. **SP_AEO_GENERATE_ONE(P_QUESTION_ID)** — Single-question generation for targeted backfill
6. **SP_AEO_SCORE_BACKFILL(P_RUN_ID)** — Iterates all questions, scores only missing (question_id, judge_model) pairs

### Step 4: Create Views

```sql
-- Leaderboard (averages across all 3 judges per question)
CREATE OR REPLACE VIEW V_AEO_LEADERBOARD AS
WITH judge_avg AS (
    SELECT RUN_ID, QUESTION_ID,
           AVG(TOTAL_SCORE) AS TOTAL_SCORE,
           AVG(MUST_HAVE_PASS) AS MUST_HAVE_PASS,
           AVG(CORRECTNESS) AS CORRECTNESS,
           AVG(COMPLETENESS) AS COMPLETENESS,
           AVG(RECENCY) AS RECENCY,
           AVG(CITATION) AS CITATION_SCORE,
           AVG(RECOMMENDATION) AS RECOMMENDATION
    FROM AEO_SCORES
    GROUP BY RUN_ID, QUESTION_ID
)
SELECT r.RUN_ID, r.DESCRIPTION, r.DOMAIN_PROMPT, r.CITATION,
       r.AGENTIC, r.SELF_CRITIQUE, r.MODEL,
       ROUND(SUM(ja.TOTAL_SCORE), 1) AS TOTAL_SCORE,
       ROUND(SUM(ja.TOTAL_SCORE) / (COUNT(DISTINCT ja.QUESTION_ID) * 50.0) * 100, 1) AS SCORE_PCT,
       ROUND(SUM(ja.MUST_HAVE_PASS), 1) AS TOTAL_MH_PASS,
       ROUND(SUM(ja.MUST_HAVE_PASS) / COUNT(DISTINCT ja.QUESTION_ID) * 100, 1) AS MH_PCT,
       COUNT(DISTINCT ja.QUESTION_ID) AS QUESTIONS_SCORED,
       COUNT(DISTINCT ja.QUESTION_ID) * 50.0 AS MAX_SCORE
FROM AEO_RUNS r
JOIN judge_avg ja ON r.RUN_ID = ja.RUN_ID
GROUP BY r.RUN_ID, r.DESCRIPTION, r.DOMAIN_PROMPT, r.CITATION,
         r.AGENTIC, r.SELF_CRITIQUE, r.MODEL
ORDER BY SCORE_PCT DESC;

-- Per-question heatmap (averages across judges)
CREATE OR REPLACE VIEW V_AEO_PER_QUESTION_HEATMAP AS
WITH judge_avg AS (
    SELECT RUN_ID, QUESTION_ID,
           AVG(TOTAL_SCORE) AS TOTAL_SCORE,
           AVG(MUST_HAVE_PASS) AS MUST_HAVE_PASS,
           AVG(CORRECTNESS) AS CORRECTNESS,
           AVG(COMPLETENESS) AS COMPLETENESS,
           AVG(RECENCY) AS RECENCY,
           AVG(CITATION) AS CITATION_SCORE,
           AVG(RECOMMENDATION) AS RECOMMENDATION
    FROM AEO_SCORES
    GROUP BY RUN_ID, QUESTION_ID
)
SELECT ja.QUESTION_ID, q.CATEGORY, q.QUESTION_TYPE, ja.RUN_ID,
       r.DOMAIN_PROMPT, r.CITATION, r.AGENTIC, r.SELF_CRITIQUE,
       ja.TOTAL_SCORE, ja.MUST_HAVE_PASS,
       ja.CORRECTNESS, ja.COMPLETENESS, ja.RECENCY,
       ja.CITATION_SCORE, ja.RECOMMENDATION
FROM judge_avg ja
JOIN AEO_QUESTIONS q ON ja.QUESTION_ID = q.QUESTION_ID
JOIN AEO_RUNS r ON ja.RUN_ID = r.RUN_ID
ORDER BY ja.QUESTION_ID, ja.RUN_ID;

-- Judge agreement
CREATE OR REPLACE VIEW V_AEO_JUDGE_AGREEMENT AS
WITH per_judge AS (
    SELECT RUN_ID, QUESTION_ID, JUDGE_MODEL, TOTAL_SCORE, MUST_HAVE_PASS
    FROM AEO_SCORES
),
judge_pairs AS (
    SELECT a.RUN_ID, a.QUESTION_ID,
           a.JUDGE_MODEL AS JUDGE_A, b.JUDGE_MODEL AS JUDGE_B,
           a.TOTAL_SCORE AS SCORE_A, b.TOTAL_SCORE AS SCORE_B,
           ABS(a.TOTAL_SCORE - b.TOTAL_SCORE) AS SCORE_DIFF
    FROM per_judge a
    JOIN per_judge b ON a.RUN_ID = b.RUN_ID AND a.QUESTION_ID = b.QUESTION_ID
         AND a.JUDGE_MODEL < b.JUDGE_MODEL
)
SELECT RUN_ID, JUDGE_A, JUDGE_B, COUNT(*) AS N_QUESTIONS,
       ROUND(AVG(SCORE_DIFF), 2) AS AVG_SCORE_DIFF,
       ROUND(CORR(SCORE_A, SCORE_B), 3) AS PEARSON_CORRELATION,
       SUM(CASE WHEN SCORE_DIFF <= 1 THEN 1 ELSE 0 END) AS AGREE_WITHIN_1PT,
       SUM(CASE WHEN SCORE_DIFF = 0 THEN 1 ELSE 0 END) AS EXACT_AGREE
FROM judge_pairs
GROUP BY RUN_ID, JUDGE_A, JUDGE_B;

-- Factorial effects (for multi-run analysis)
CREATE OR REPLACE VIEW V_AEO_FACTORIAL_EFFECTS AS
WITH judge_avg AS (
    SELECT RUN_ID, QUESTION_ID,
           AVG(TOTAL_SCORE) AS TOTAL_SCORE,
           AVG(MUST_HAVE_PASS) AS MUST_HAVE_PASS
    FROM AEO_SCORES
    GROUP BY RUN_ID, QUESTION_ID
),
run_totals AS (
    SELECT r.RUN_ID, r.DOMAIN_PROMPT, r.CITATION, r.AGENTIC, r.SELF_CRITIQUE,
           ROUND(SUM(ja.TOTAL_SCORE) / (COUNT(DISTINCT ja.QUESTION_ID) * 50.0) * 100, 1) AS SCORE_PCT,
           ROUND(SUM(ja.MUST_HAVE_PASS) / COUNT(DISTINCT ja.QUESTION_ID) * 100, 1) AS MH_PCT
    FROM AEO_RUNS r
    JOIN judge_avg ja ON r.RUN_ID = ja.RUN_ID
    GROUP BY r.RUN_ID, r.DOMAIN_PROMPT, r.CITATION, r.AGENTIC, r.SELF_CRITIQUE
)
SELECT 'Domain Prompt' AS FACTOR,
       ROUND(AVG(CASE WHEN DOMAIN_PROMPT THEN SCORE_PCT END)
           - AVG(CASE WHEN NOT DOMAIN_PROMPT THEN SCORE_PCT END), 1) AS SCORE_EFFECT_PP,
       ROUND(AVG(CASE WHEN DOMAIN_PROMPT THEN MH_PCT END)
           - AVG(CASE WHEN NOT DOMAIN_PROMPT THEN MH_PCT END), 1) AS MH_EFFECT_PP
FROM run_totals
UNION ALL
SELECT 'Citation',
       ROUND(AVG(CASE WHEN CITATION THEN SCORE_PCT END)
           - AVG(CASE WHEN NOT CITATION THEN SCORE_PCT END), 1),
       ROUND(AVG(CASE WHEN CITATION THEN MH_PCT END)
           - AVG(CASE WHEN NOT CITATION THEN MH_PCT END), 1)
FROM run_totals
UNION ALL
SELECT 'Agentic',
       ROUND(AVG(CASE WHEN AGENTIC THEN SCORE_PCT END)
           - AVG(CASE WHEN NOT AGENTIC THEN SCORE_PCT END), 1),
       ROUND(AVG(CASE WHEN AGENTIC THEN MH_PCT END)
           - AVG(CASE WHEN NOT AGENTIC THEN MH_PCT END), 1)
FROM run_totals
UNION ALL
SELECT 'Self-Critique',
       ROUND(AVG(CASE WHEN SELF_CRITIQUE THEN SCORE_PCT END)
           - AVG(CASE WHEN NOT SELF_CRITIQUE THEN SCORE_PCT END), 1),
       ROUND(AVG(CASE WHEN SELF_CRITIQUE THEN MH_PCT END)
           - AVG(CASE WHEN NOT SELF_CRITIQUE THEN MH_PCT END), 1)
FROM run_totals;
```

### Step 5: Create Task DAG (64 child tasks + 1 root = 65 total)

**IMPORTANT**: Resume ALL child tasks BEFORE the root task. Root task must be resumed last.

```sql
-- Root task (manual trigger only, max schedule = 11520 min)
CREATE OR REPLACE TASK TASK_AEO_ROOT
  WAREHOUSE = COMPUTE_WH
  SCHEDULE = '11520 MINUTE'
  ALLOW_OVERLAPPING_EXECUTION = FALSE
AS CALL SP_AEO_INIT_RUN();

-- 32 parallel gen tasks (Phase 1), 4 questions each
CREATE TASK TASK_AEO_GEN_01 WAREHOUSE=COMPUTE_WH
  AFTER TASK_AEO_ROOT AS CALL SP_AEO_GENERATE_MISSING(1);
CREATE TASK TASK_AEO_GEN_02 WAREHOUSE=COMPUTE_WH
  AFTER TASK_AEO_ROOT AS CALL SP_AEO_GENERATE_MISSING(2);
-- ... repeat for GEN_03 through GEN_32 ...
CREATE TASK TASK_AEO_GEN_32 WAREHOUSE=COMPUTE_WH
  AFTER TASK_AEO_ROOT AS CALL SP_AEO_GENERATE_MISSING(32);

-- 32 parallel score tasks (Phase 2, AFTER all 32 gen tasks)
CREATE TASK TASK_AEO_SCORE_01 WAREHOUSE=COMPUTE_WH
  AFTER TASK_AEO_GEN_01, TASK_AEO_GEN_02, ..., TASK_AEO_GEN_32
  AS CALL SP_AEO_SCORE(1);
-- ... repeat for SCORE_02 through SCORE_32 ...

-- Resume order: children first, root last
ALTER TASK TASK_AEO_GEN_01 RESUME;
-- ... resume all 64 gen and score tasks ...
ALTER TASK TASK_AEO_ROOT RESUME;
```

---

## Run Intent

The benchmark uses a **2^4 factorial experiment design** with 4 binary factors, yielding 16 runs per model:

| Run | Domain Prompt | Citation | Agentic | Self-Critique |
|-----|:---:|:---:|:---:|:---:|
| 1 | | | | |
| 2 | x | | | |
| 3 | | x | | |
| 4 | x | x | | |
| 5 | | | x | |
| 6 | x | | x | |
| 7 | | x | x | |
| 8 | x | x | x | |
| 9 | | | | x |
| 10 | x | | | x |
| 11 | | x | | x |
| 12 | x | x | | x |
| 13 | | | x | x |
| 14 | x | | x | x |
| 15 | | x | x | x |
| 16 | x | x | x | x |

Use this matrix to determine the config for each run. When the user says "run N", look up the factors above.

### Factor Definitions

| Factor | FALSE | TRUE |
|--------|-------|------|
| **Domain Prompt** | No system prompt (raw question only) | Prepend a Snowflake domain expert system prompt to guide the model |
| **Citation** | No citation instructions | Instruct the model to cite official Snowflake documentation URLs |
| **Agentic** | Direct CORTEX.COMPLETE call (single LLM inference) | Use native Cortex Code as the inference tool. Instead of calling CORTEX.COMPLETE directly, send the question to a Cortex Code session that can use tools (search docs, run SQL, explore code) to compose a grounded answer |
| **Self-Critique** | Single-pass generation | Two-pass: generate an initial response, then ask the model to critique and improve it |

**Agentic mode implementation**: When `agentic=TRUE`, the generation phase replaces the standard CORTEX.COMPLETE call with a Cortex Code session invocation. This allows the model to use built-in tools (Cortex Search, SQL execution, documentation lookup) to produce a more grounded response. The scoring phase remains identical (3-judge panel via CORTEX.COMPLETE).

### Step 1: Insert Run Config

```sql
INSERT INTO AEO_RUN_CONFIG (RUN_ID, MODEL, DOMAIN_PROMPT, CITE, JUDGE_MODELS, MAX_TOKENS, STATUS)
VALUES (
    {run_id},           -- 1-16 per the factorial matrix above
    '{model}',          -- e.g., 'claude-opus-4-6'
    {domain_prompt},    -- TRUE/FALSE per matrix
    {cite},             -- TRUE/FALSE per matrix
    'openai-gpt-5.4,claude-opus-4-6,llama4-maverick',
    8192,
    'PENDING'
);

-- Also insert into AEO_RUNS for the leaderboard view
INSERT INTO AEO_RUNS (RUN_ID, DESCRIPTION, DOMAIN_PROMPT, CITATION, AGENTIC, SELF_CRITIQUE, MODEL)
VALUES (
    {run_id},
    'Run {run_id}: model={model}, domain={domain_prompt}, cite={cite}, agentic={agentic}, self_critique={self_critique}',
    {domain_prompt},
    {cite},
    {agentic},          -- TRUE/FALSE per matrix
    {self_critique},    -- TRUE/FALSE per matrix
    '{model}'
);
```

### Step 2: Trigger the DAG

```sql
EXECUTE TASK TASK_AEO_ROOT;
```

This fires the root task immediately, which:
1. Reads PENDING config, creates AEO_RUNS row, sets status to RUNNING
2. Triggers 8 parallel gen tasks (Phase 1)
3. After all gen tasks complete, triggers 8 parallel score tasks (Phase 2)

### Step 3: Monitor Progress

See "Monitor Intent" section below.

---

## Monitor Intent

### Quick Status Check

```sql
SELECT 'responses' AS phase, COUNT(*) AS total, 128 - COUNT(*) AS remaining
FROM AEO_RESPONSES WHERE RUN_ID = {run_id}
UNION ALL
SELECT 'scores', COUNT(DISTINCT QUESTION_ID), 128 - COUNT(DISTINCT QUESTION_ID)
FROM AEO_SCORES WHERE RUN_ID = {run_id};
```

### Per-Batch Progress

```sql
SELECT
  CEIL(CAST(REPLACE(QUESTION_ID, 'Q', '') AS INT) / 4.0) AS batch,
  COUNT(*) AS done, 4 - COUNT(*) AS missing
FROM AEO_RESPONSES WHERE RUN_ID = {run_id}
GROUP BY batch ORDER BY batch;
```

### Missing Questions

```sql
SELECT q.QUESTION_ID, q.CATEGORY, q.QUESTION_TYPE
FROM AEO_QUESTIONS q
LEFT JOIN AEO_RESPONSES r ON q.QUESTION_ID = r.QUESTION_ID AND r.RUN_ID = {run_id}
WHERE r.QUESTION_ID IS NULL
ORDER BY q.QUESTION_ID;
```

### Task History (use ACCOUNT_USAGE, not INFORMATION_SCHEMA)

**IMPORTANT**: `INFORMATION_SCHEMA.TASK_HISTORY` often returns 0 rows for user-created tasks. Use `SNOWFLAKE.ACCOUNT_USAGE.TASK_HISTORY` instead (has up to 45-min lag).

```sql
SELECT NAME, STATE, SCHEDULED_TIME, COMPLETED_TIME, RETURN_VALUE, ERROR_MESSAGE
FROM SNOWFLAKE.ACCOUNT_USAGE.TASK_HISTORY
WHERE NAME LIKE 'TASK_AEO%'
  AND SCHEDULED_TIME > DATEADD('HOUR', -2, CURRENT_TIMESTAMP())
ORDER BY SCHEDULED_TIME DESC;
```

---

## Backfill Intent

When responses are stuck (some questions consistently failing), use these strategies in order:

### Strategy 1: Re-trigger the DAG

Gen tasks use `SP_AEO_GENERATE_MISSING` which automatically skips questions with existing responses. Just re-trigger:

```sql
EXECUTE TASK TASK_AEO_ROOT;
```

Each cycle picks off a few more questions. The init SP is idempotent (detects RUNNING status and skips).

### Strategy 2: Dedicated Backfill DAG

For stubborn failures, create a lightweight backfill DAG targeting only the batches with missing questions:

```sql
CREATE OR REPLACE TASK TASK_AEO_BACKFILL_ROOT
  WAREHOUSE = COMPUTE_WH SCHEDULE = '11520 MINUTE'
  ALLOW_OVERLAPPING_EXECUTION = FALSE
AS SELECT 'backfill' AS status;

-- Create gen tasks only for batches with gaps (check which batches need it first)
CREATE OR REPLACE TASK TASK_AEO_BF_GEN_{NN} WAREHOUSE = COMPUTE_WH
  AFTER TASK_AEO_BACKFILL_ROOT AS CALL SP_AEO_GENERATE_MISSING({NN});

-- Score tasks AFTER all gen tasks
CREATE OR REPLACE TASK TASK_AEO_BF_SCORE_{NN} WAREHOUSE = COMPUTE_WH
  AFTER TASK_AEO_BF_GEN_02, TASK_AEO_BF_GEN_03, ...
  AS CALL SP_AEO_SCORE({NN});

-- Resume children first, then root, then trigger
ALTER TASK TASK_AEO_BF_GEN_{NN} RESUME;
-- ...
ALTER TASK TASK_AEO_BACKFILL_ROOT RESUME;
EXECUTE TASK TASK_AEO_BACKFILL_ROOT;
```

### Strategy 3: Single-Question Generation

For the last few stubborn questions, use `SP_AEO_GENERATE_ONE` which calls CORTEX.COMPLETE for a single question and surfaces the actual error:

```sql
CALL SP_AEO_GENERATE_ONE('Q018');
-- Returns: 'OK: Q018 generated (22236 chars)' or the actual error
```

Then score individually:
```sql
CALL SP_AEO_SCORE(NULL, 'Q018');
```

---

## Score-Only DAG (Rescoring Without Regeneration)

When you need to rescore existing responses (e.g., after fixing the scoring SP or changing the rubric), use a lightweight score-only DAG that skips the generation phase entirely.

### Create Score-Only DAG

```sql
-- Suspend any existing score-only root first
ALTER TASK TASK_SCORE_ROOT SUSPEND;

-- Root task (manual trigger only)
CREATE OR REPLACE TASK TASK_SCORE_ROOT
  WAREHOUSE = COMPUTE_WH
  SCHEDULE = '11520 MINUTE'
  ALLOW_OVERLAPPING_EXECUTION = FALSE
AS SELECT 1;

-- 32 parallel score tasks, one per batch
-- Replace {run_id} with the target run number
CREATE OR REPLACE TASK TASK_SCORE_R3_01 WAREHOUSE = AEO_WH
  AFTER TASK_SCORE_ROOT AS CALL SP_AEO_SCORE({run_id}, 1, NULL, 4);
CREATE OR REPLACE TASK TASK_SCORE_R3_02 WAREHOUSE = AEO_WH
  AFTER TASK_SCORE_ROOT AS CALL SP_AEO_SCORE({run_id}, 2, NULL, 4);
-- ... repeat for 03 through 32 ...
CREATE OR REPLACE TASK TASK_SCORE_R3_32 WAREHOUSE = AEO_WH
  AFTER TASK_SCORE_ROOT AS CALL SP_AEO_SCORE({run_id}, 32, NULL, 4);

-- Resume children first, then root
ALTER TASK TASK_SCORE_R3_01 RESUME;
-- ... resume all 32 ...
ALTER TASK TASK_SCORE_R3_32 RESUME;
ALTER TASK TASK_SCORE_ROOT RESUME;

-- Trigger
EXECUTE TASK TASK_SCORE_ROOT;
```

### Reusing for Another Run

The same task names can be repurposed for a different run by suspending the root, then `CREATE OR REPLACE` the child tasks with the new run_id:

```sql
ALTER TASK TASK_SCORE_ROOT SUSPEND;
-- Recreate children with new run_id
CREATE OR REPLACE TASK TASK_SCORE_R3_01 WAREHOUSE = AEO_WH
  AFTER TASK_SCORE_ROOT AS CALL SP_AEO_SCORE({new_run_id}, 1, NULL, 4);
-- ... repeat ...
-- Resume and trigger
```

### Two-Pass Scoring Pattern

The DAG pass typically covers 50-70% of questions. Follow up with the backfill SP:

```sql
-- After DAG completes, backfill remaining gaps
USE SCHEMA AEO_OBSERVABILITY.EVAL_SCHEMA;
CALL SP_AEO_SCORE_BACKFILL({run_id});
```

### When to Delete Old Scores Before Rescoring

If rescoring with a different rubric/scale (e.g., changing from 0-2 to 1-10), delete old scores first:

```sql
DELETE FROM AEO_SCORES WHERE RUN_ID = {run_id};
-- Then run the score-only DAG + backfill
```

---

## Results Intent

### Leaderboard

```sql
SELECT * FROM V_AEO_LEADERBOARD ORDER BY SCORE_PCT DESC;
```

### Per-Dimension Breakdown (averaged across judges)

```sql
SELECT
  ROUND(AVG(CORRECTNESS), 2) AS correctness,
  ROUND(AVG(COMPLETENESS), 2) AS completeness,
  ROUND(AVG(RECENCY), 2) AS recency,
  ROUND(AVG(CITATION), 2) AS citation,
  ROUND(AVG(RECOMMENDATION), 2) AS recommendation,
  ROUND(AVG(TOTAL_SCORE), 2) AS avg_total,
  ROUND(AVG(MUST_HAVE_PASS), 2) AS avg_mh
FROM AEO_SCORES
WHERE RUN_ID = {run_id};
```

### Per-Judge Breakdown

```sql
SELECT JUDGE_MODEL, COUNT(*) AS questions,
       ROUND(AVG(TOTAL_SCORE), 2) AS avg_score,
       ROUND(AVG(MUST_HAVE_PASS), 2) AS avg_mh
FROM AEO_SCORES
WHERE RUN_ID = {run_id}
GROUP BY JUDGE_MODEL ORDER BY avg_score DESC;
```

### Per-Question Type

```sql
SELECT q.QUESTION_TYPE, COUNT(*) AS questions,
       ROUND(AVG(s.TOTAL_SCORE), 2) AS avg_score,
       ROUND(AVG(s.MUST_HAVE_PASS), 2) AS avg_mh
FROM AEO_SCORES s
JOIN AEO_QUESTIONS q ON s.QUESTION_ID = q.QUESTION_ID
WHERE s.RUN_ID = {run_id}
GROUP BY q.QUESTION_TYPE ORDER BY avg_score DESC;
```

### Per-Category Breakdown

```sql
SELECT q.CATEGORY, COUNT(*) AS questions,
       ROUND(AVG(s.TOTAL_SCORE), 2) AS avg_score,
       ROUND(AVG(s.MUST_HAVE_PASS), 2) AS avg_mh
FROM AEO_SCORES s
JOIN AEO_QUESTIONS q ON s.QUESTION_ID = q.QUESTION_ID
WHERE s.RUN_ID = {run_id}
GROUP BY q.CATEGORY ORDER BY avg_score DESC;
```

### Response Timing Stats

```sql
SELECT
  MIN(GENERATED_AT) AS first_response,
  MAX(GENERATED_AT) AS last_response,
  ROUND(AVG(LENGTH(RESPONSE_TEXT)), 0) AS avg_chars,
  MIN(LENGTH(RESPONSE_TEXT)) AS min_chars,
  MAX(LENGTH(RESPONSE_TEXT)) AS max_chars
FROM AEO_RESPONSES WHERE RUN_ID = {run_id};
```

---

## Cleanup Intent: Deduplicate Scores

Multiple DAG re-triggers create duplicate score rows. Always dedup after a run completes:

### Check for Duplicates

```sql
SELECT QUESTION_ID, JUDGE_MODEL, COUNT(*) AS cnt
FROM AEO_SCORES WHERE RUN_ID = {run_id}
GROUP BY QUESTION_ID, JUDGE_MODEL HAVING COUNT(*) > 1;
```

### Dedup (keep latest score per question+judge)

```sql
DELETE FROM AEO_SCORES s1
WHERE RUN_ID = {run_id}
  AND SCORED_AT < (
    SELECT MAX(s2.SCORED_AT)
    FROM AEO_SCORES s2
    WHERE s2.RUN_ID = s1.RUN_ID
      AND s2.QUESTION_ID = s1.QUESTION_ID
      AND s2.JUDGE_MODEL = s1.JUDGE_MODEL
  );
```

### Verify: Check for expected row count (N questions x 3 judges)

```sql
SELECT COUNT(*) AS total_rows, COUNT(DISTINCT QUESTION_ID) AS questions
FROM AEO_SCORES WHERE RUN_ID = {run_id};
-- Expected: total_rows = N * 3 (3 judges, no panel_avg), questions = N
```

---

## Known Issues and Fixes

### `$$` Delimiter Bug (CRITICAL)

**Problem**: CORTEX.COMPLETE calls using `$$`-quoted strings break when content contains literal `$$` (common in stored procedure examples). This caused 489 zero-score rows across the 2^4 factorial experiment.

**Fix**: Always use bind parameters, never `$$` interpolation:
- **Python Connector** (cursor): `%s` (pyformat) — `cur.execute(sql, (model, json, opts))`
- **Snowpark Session**: `?` (qmark) — `session.sql(sql, params=[model, json, opts])`

These are NOT interchangeable. Using `?` with the connector causes `not all arguments converted during string formatting`. Using `%s` with Snowpark causes errors.

**Applies to**: `_call_cortex_complete` in orchestrator, `_call_judge` in feedback functions, `generate_response` and `self_critique_refine` in trulens app. Any new CORTEX.COMPLETE call MUST use bind params.

### Backfill Duplicate Row Bug

**Problem**: `backfill_zero_scores.py` deletes only `WHERE TOTAL_SCORE = 0` before reinserting 3 judge rows. If only 1 of 3 judges had a zero, the other 2 get duplicated.

**Fix**: Delete ALL rows for a (run, question) combo before reinserting:
```python
cur.execute("DELETE FROM AEO_SCORES WHERE RUN_ID = %s AND QUESTION_ID = %s", (run_id, qid))
```

After any backfill, always run the dedup check:
```sql
SELECT RUN_ID, QUESTION_ID, JUDGE_MODEL, COUNT(*) as cnt
FROM AEO_SCORES GROUP BY ALL HAVING cnt > 1;
```

### AEO_SCORES Column Order Gotcha

`MUST_HAVE_5` is column 17 (added after SCORED_AT), not column 15 where expected. Always use explicit column names in INSERT statements, never positional:
```sql
INSERT INTO AEO_SCORES (RUN_ID, ..., MUST_HAVE_PASS, RAW_JUDGE_RESPONSE, SCORED_AT, MUST_HAVE_5) ...
```

### llama4-maverick Zero-Score Behavior

Maverick gives all-zero dimension scores for ~0.2% of entries (5/2048). This is intentional judge behavior, not a bug. Maverick also gives citation=0 on 41% of entries (binary treatment). Retrying with temperature=0.3 produces the same zeros. Accept as legitimate or consider replacing maverick with a different third judge.

### AEO_RUNS Column Structure

AEO_RUNS has direct boolean columns (`DOMAIN_PROMPT`, `CITATION`, `AGENTIC`, `SELF_CRITIQUE`), NOT a VARIANT/JSON `FACTORS` column. Use `r.DOMAIN_PROMPT` directly, not `r.FACTORS:domain_prompt::BOOLEAN`.

---

## SPCS Execution Mode

Alternative to the Task DAG approach. Runs the same benchmark using containerized Python runners deployed as SPCS job services. Each container processes a batch of questions (generate + score with 3 judges), reading from and writing to Snowflake tables.

### SPCS Architecture Overview

```
                    EXECUTE JOB SERVICE (x8, parallel)
                    ┌──────────────────────────────────┐
                    │  AEO_SPCS_BATCH_01 (Q001-Q016)   │
                    │  AEO_SPCS_BATCH_02 (Q017-Q032)   │
AEO_BENCHMARK_POOL  │  AEO_SPCS_BATCH_03 (Q033-Q048)   │  ──▶  AEO_OBSERVABILITY.SPCS_EVAL
(CPU_X64_XS, 8 nodes)│  AEO_SPCS_BATCH_04 (Q049-Q064)   │       ├── AEO_RESPONSES
                    │  AEO_SPCS_BATCH_05 (Q065-Q080)   │       └── AEO_SCORES
                    │  AEO_SPCS_BATCH_06 (Q081-Q096)   │
                    │  AEO_SPCS_BATCH_07 (Q097-Q112)   │
                    │  AEO_SPCS_BATCH_08 (Q113-Q128)   │
                    └──────────────────────────────────┘
```

- **Runner**: Python script (`aeo_spcs_runner.py`) using `snowflake-connector-python`
- **Auth**: SPCS OAuth token at `/snowflake/session/token` (automatic inside containers)
- **Idempotent**: Checks existing responses/scores before processing; safe to re-run for backfill
- **Batch size**: 16 questions per container (128 / 8 batches)
- **Per-question work**: 1 CORTEX.COMPLETE call (inference) + 3 judge calls = 4 LLM calls per question
- **Source files**: `~/Documents/Coco/aeo/spcs-v2/` (runner, Dockerfile, launch.sql)

### SPCS Deploy

#### Prerequisites

- Docker Desktop running locally
- Snowflake account with ACCOUNTADMIN (for compute pool and image repo creation)

#### Step 1: Create Snowflake Infrastructure

```sql
USE ROLE ACCOUNTADMIN;

-- Compute pool (CPU_X64_XS is sufficient; LLM calls are the bottleneck, not container CPU)
CREATE COMPUTE POOL IF NOT EXISTS AEO_BENCHMARK_POOL
  MIN_NODES = 1 MAX_NODES = 8
  INSTANCE_FAMILY = CPU_X64_XS
  AUTO_SUSPEND_SECS = 600
  AUTO_RESUME = TRUE;

-- Image repository
CREATE DATABASE IF NOT EXISTS AEO_DB;
CREATE SCHEMA IF NOT EXISTS AEO_DB.PUBLIC;
CREATE IMAGE REPOSITORY IF NOT EXISTS AEO_DB.PUBLIC.AEO_REPO;

-- External access (needed for CORTEX.COMPLETE calls from inside the container)
CREATE OR REPLACE EXTERNAL ACCESS INTEGRATION AEO_CORTEX_ACCESS
  ALLOWED_NETWORK_RULES = ()
  ENABLED = TRUE;

-- Get the registry URL for docker push
SHOW IMAGE REPOSITORIES IN SCHEMA AEO_DB.PUBLIC;
-- Note the repository_url column, e.g.: sfdevrel-sfdevrel-enterprise.registry.snowflakecomputing.com/aeo_db/public/aeo_repo
```

#### Step 2: Create Target Schema and Tables

Use a separate schema (e.g., `SPCS_EVAL`) to keep results distinct from Task DAG runs:

```sql
CREATE DATABASE IF NOT EXISTS AEO_OBSERVABILITY;
CREATE SCHEMA IF NOT EXISTS AEO_OBSERVABILITY.SPCS_EVAL;
USE SCHEMA AEO_OBSERVABILITY.SPCS_EVAL;

-- Same table DDL as Task DAG, but with VARCHAR(100000) for RESPONSE_TEXT
-- CRITICAL: VARCHAR(16000) is too small for claude-opus-4-6 responses (see Pitfall #14)
CREATE TABLE IF NOT EXISTS AEO_QUESTIONS (
    QUESTION_ID VARCHAR(10),
    QUESTION_TEXT VARCHAR(2000),
    CATEGORY VARCHAR(100),
    QUESTION_TYPE VARCHAR(20),
    CANONICAL_ANSWER VARCHAR(16000),
    MUST_HAVE_1 VARCHAR(500),
    MUST_HAVE_2 VARCHAR(500),
    MUST_HAVE_3 VARCHAR(500),
    MUST_HAVE_4 VARCHAR(500),
    MUST_HAVE_5 VARCHAR(500),
    DOC_URL VARCHAR(500)
);

CREATE TABLE IF NOT EXISTS AEO_RUN_CONFIG (
    RUN_ID NUMBER NOT NULL PRIMARY KEY,
    MODEL VARCHAR(100) NOT NULL,
    DOMAIN_PROMPT BOOLEAN DEFAULT FALSE,
    CITE BOOLEAN DEFAULT FALSE,
    JUDGE_MODELS VARCHAR(500) DEFAULT 'openai-gpt-5.4,claude-opus-4-6,llama4-maverick',
    MAX_TOKENS NUMBER DEFAULT 8192,
    STATUS VARCHAR(20) DEFAULT 'PENDING',
    CREATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);

CREATE TABLE IF NOT EXISTS AEO_RUNS (
    RUN_ID NUMBER, RUN_DATE TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
    DESCRIPTION VARCHAR(1000), DOMAIN_PROMPT BOOLEAN, CITATION BOOLEAN,
    AGENTIC BOOLEAN, SELF_CRITIQUE BOOLEAN, MODEL VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS AEO_RESPONSES (
    RUN_ID NUMBER,
    QUESTION_ID VARCHAR(10),
    RESPONSE_TEXT VARCHAR(100000),
    GENERATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);

CREATE TABLE IF NOT EXISTS AEO_SCORES (
    RUN_ID NUMBER, QUESTION_ID VARCHAR(10), JUDGE_MODEL VARCHAR(100),
    CORRECTNESS FLOAT, COMPLETENESS FLOAT, RECENCY FLOAT,
    CITATION FLOAT, RECOMMENDATION FLOAT, TOTAL_SCORE FLOAT,
    MUST_HAVE_1 BOOLEAN DEFAULT FALSE, MUST_HAVE_2 BOOLEAN DEFAULT FALSE,
    MUST_HAVE_3 BOOLEAN DEFAULT FALSE, MUST_HAVE_4 BOOLEAN DEFAULT FALSE,
    MUST_HAVE_5 BOOLEAN DEFAULT FALSE, MUST_HAVE_PASS FLOAT,
    RAW_JUDGE_RESPONSE VARCHAR(65000),
    SCORED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);
```

Copy questions from the existing schema (or load fresh):
```sql
INSERT INTO AEO_OBSERVABILITY.SPCS_EVAL.AEO_QUESTIONS
SELECT * FROM AEO_OBSERVABILITY.EVAL_SCHEMA.AEO_QUESTIONS;
```

#### Step 3: Build and Push Docker Image

The runner script and Dockerfile are at `~/Documents/Coco/aeo/spcs-v2/`.

**Dockerfile:**
```dockerfile
FROM python:3.11-slim
RUN pip install --no-cache-dir snowflake-connector-python[secure-local-storage]
COPY aeo_spcs_runner.py /app/aeo_spcs_runner.py
WORKDIR /app
CMD ["python", "-u", "aeo_spcs_runner.py"]
```

**Build and push:**
```bash
cd ~/Documents/Coco/aeo/spcs-v2

# Get registry URL from SHOW IMAGE REPOSITORIES output
REGISTRY="<account>.registry.snowflakecomputing.com"
REPO="$REGISTRY/aeo_db/public/aeo_repo"

# Login to Snowflake registry
# Use the password from ~/.snowflake/connections.toml for your connection
docker login "$REGISTRY" -u <username>

# Build and push
docker build --platform linux/amd64 -t aeo-benchmark:v2 .
docker tag aeo-benchmark:v2 "$REPO/aeo-benchmark:v2"
docker push "$REPO/aeo-benchmark:v2"
```

**IMPORTANT**: Always build with `--platform linux/amd64` even on Apple Silicon Macs. SPCS runs on x86_64.

#### Step 4: Scale and Resume Compute Pool

```sql
ALTER COMPUTE POOL AEO_BENCHMARK_POOL SET MAX_NODES = 8;
ALTER COMPUTE POOL AEO_BENCHMARK_POOL RESUME;
```

### SPCS Run

#### Step 1: Insert Run Config

```sql
INSERT INTO AEO_OBSERVABILITY.SPCS_EVAL.AEO_RUN_CONFIG
  (RUN_ID, MODEL, DOMAIN_PROMPT, CITE, JUDGE_MODELS, MAX_TOKENS, STATUS)
VALUES ({run_id}, '{model}', {domain_prompt}, {cite},
        'openai-gpt-5.4,claude-opus-4-6,llama4-maverick', 8192, 'PENDING');

INSERT INTO AEO_OBSERVABILITY.SPCS_EVAL.AEO_RUNS
  (RUN_ID, DESCRIPTION, DOMAIN_PROMPT, CITATION, AGENTIC, SELF_CRITIQUE, MODEL)
VALUES ({run_id}, '{description}', {domain_prompt}, {cite}, FALSE, FALSE, '{model}');
```

#### Step 2: Launch 8 Parallel Jobs

**IMPORTANT**: Do NOT use `QUERY_WAREHOUSE` clause with inline `FROM SPECIFICATION $$...$$`. It causes a syntax error. The runner script handles `USE WAREHOUSE` internally.

For each batch (1-8), execute:

```sql
DROP SERVICE IF EXISTS AEO_DB.PUBLIC.AEO_SPCS_BATCH_{NN};

EXECUTE JOB SERVICE
  IN COMPUTE POOL AEO_BENCHMARK_POOL
  NAME = AEO_DB.PUBLIC.AEO_SPCS_BATCH_{NN}
  FROM SPECIFICATION $$
spec:
  containers:
  - name: aeo-runner
    image: /AEO_DB/PUBLIC/AEO_REPO/aeo-benchmark:v2
    env:
      BATCH_NUM: "{NN}"
      MODEL: "{model}"
      JUDGE_MODELS: "openai-gpt-5.4,claude-opus-4-6,llama4-maverick"
      WAREHOUSE: "COMPUTE_WH"
      RUN_SCHEMA: "AEO_OBSERVABILITY.SPCS_EVAL"
      RUN_ID: "{run_id}"
      MAX_TOKENS: "8192"
$$;
```

Where `{NN}` is 1 through 8 (or `01` through `08` in the service name).

**Timeout**: `EXECUTE JOB SERVICE` blocks synchronously until the job finishes. Each batch takes 15-25 minutes. Set `timeout_seconds=1200` when executing from Cortex Code. If the client times out, the job continues running on the compute pool.

**Launch all 8 in parallel** from Cortex Code using 8 separate `snowflake_sql_execute` calls with `timeout_seconds=1200`. Jobs that time out client-side are still running.

#### Step 3: Monitor

```sql
-- Check job statuses (PENDING, READY, RUNNING, DONE, FAILED)
SHOW SERVICES IN SCHEMA AEO_DB.PUBLIC;

-- Check container logs for a specific batch
SELECT SYSTEM$GET_SERVICE_LOGS('AEO_DB.PUBLIC.AEO_SPCS_BATCH_01', 0, 'aeo-runner');

-- Check data progress
SELECT COUNT(*) AS responses FROM AEO_OBSERVABILITY.SPCS_EVAL.AEO_RESPONSES WHERE RUN_ID = {run_id};
SELECT COUNT(*) AS scores FROM AEO_OBSERVABILITY.SPCS_EVAL.AEO_SCORES WHERE RUN_ID = {run_id};

-- Per-batch progress
SELECT
  CEIL(CAST(REPLACE(QUESTION_ID, 'Q', '') AS INT) / 16.0) AS batch,
  COUNT(*) AS done, 16 - COUNT(*) AS missing
FROM AEO_OBSERVABILITY.SPCS_EVAL.AEO_RESPONSES WHERE RUN_ID = {run_id}
GROUP BY batch ORDER BY batch;
```

**Expected final counts**: N responses, N*3 scores (N questions x 3 judges). Query `SELECT COUNT(*) FROM AEO_QUESTIONS` to get N.

### SPCS Backfill

The runner is idempotent: it skips questions with existing responses and (question_id, judge_model) pairs with existing scores. To backfill gaps:

1. **Drop the old service** (required, or you get "Object already exists"):
   ```sql
   DROP SERVICE IF EXISTS AEO_DB.PUBLIC.AEO_SPCS_BATCH_{NN};
   ```

2. **Re-launch the batch** using the same `EXECUTE JOB SERVICE` command. It will only process missing questions.

3. **Check logs if a batch keeps failing**:
   ```sql
   SELECT SYSTEM$GET_SERVICE_LOGS('AEO_DB.PUBLIC.AEO_SPCS_BATCH_{NN}', 0, 'aeo-runner');
   ```
   Common root cause: VARCHAR truncation (see Pitfall #14).

### SPCS Cleanup

After the run completes:

```sql
-- Suspend compute pool to stop billing
ALTER COMPUTE POOL AEO_BENCHMARK_POOL SUSPEND;

-- Optionally drop completed job services
DROP SERVICE IF EXISTS AEO_DB.PUBLIC.AEO_SPCS_BATCH_01;
-- ... repeat for 02-08
```

### SPCS vs Task DAG Comparison

| Aspect | Task DAG | SPCS |
|--------|----------|------|
| Parallelism | 32-way (4 Qs each) | 8-way (16 Qs each) |
| Overhead | Zero (native Tasks) | ~20s container warm start |
| Requires Docker | No | Yes |
| Error visibility | Silent (exception handler) | Full logs via `SYSTEM$GET_SERVICE_LOGS` |
| Schema flexibility | Fixed schema | Configurable via `RUN_SCHEMA` env var |
| Scoring | 3 judges, 1-10 scale, no panel_avg | 3 judges, 1-10 scale, no panel_avg |
| Reproducibility | SP code in Snowflake | Versioned Docker image |
| Clean runtime (128 Qs) | ~8 min | ~25 min |
| Best for | Repeated runs, production | Isolated runs, debugging, separate schemas |

---

## Stored Procedure Reference

### SP_AEO_INIT_RUN()

Reads latest config from AEO_RUN_CONFIG. If STATUS='RUNNING', returns immediately (idempotent re-trigger). If STATUS='PENDING', creates AEO_RUNS row and sets status to RUNNING.

### SP_AEO_GENERATE(P_BATCH NUMBER, P_QUESTION_FILTER VARCHAR)

Inference SP. Reads RUNNING config, loops over questions in batch, calls CORTEX.COMPLETE, writes to AEO_RESPONSES.

**Key implementation details:**
- Uses `OBJECT_CONSTRUCT`/`ARRAY_CONSTRUCT` for JSON messages (NEVER string concatenation)
- Error handler increments counter only (no SQLERRM references)
- Batch N = Q((N-1)*4+1) through Q(N*4) using LPAD zero-padding

### SP_AEO_GENERATE_MISSING(P_BATCH NUMBER)

Same as SP_AEO_GENERATE but uses LEFT JOIN to skip questions that already have responses:

```sql
SELECT q.QUESTION_ID, q.QUESTION_TEXT
FROM AEO_QUESTIONS q
LEFT JOIN AEO_RESPONSES r ON q.QUESTION_ID = r.QUESTION_ID AND r.RUN_ID = :v_run_id
WHERE q.QUESTION_ID >= :v_batch_start AND q.QUESTION_ID <= :v_batch_end
  AND r.QUESTION_ID IS NULL
ORDER BY q.QUESTION_ID
```

This is the preferred SP for DAG gen tasks since it enables safe re-triggers.

### SP_AEO_GENERATE_ONE(P_QUESTION_ID VARCHAR)

Generates a single question. Useful for diagnosing failures (surfaces actual CORTEX.COMPLETE errors instead of silently catching them). Also checks for existing response before calling.

### SP_AEO_SCORE(P_RUN_ID NUMBER, P_BATCH NUMBER, P_QUESTION_FILTER VARCHAR, P_BATCH_SIZE NUMBER DEFAULT 4)

Scoring SP. For each question in batch:
1. Joins AEO_RESPONSES with AEO_QUESTIONS to get response + canonical answer + must-haves
2. Builds judge prompt with 5-dimension rubric (Correctness, Completeness, Recency, Citation, Recommendation) x **1-10 scale**
3. Calls each of 3 judge models via CORTEX.COMPLETE
4. Parses JSON scores, writes to AEO_SCORES (one row per judge, 3 rows per question)
5. Captures RAW_JUDGE_RESPONSE for debugging

**Judge models**: openai-gpt-5.4, claude-opus-4-6, llama4-maverick

**IMPORTANT**: The SP requires schema context to be set before calling:
```sql
USE SCHEMA AEO_OBSERVABILITY.EVAL_SCHEMA;
CALL SP_AEO_SCORE({run_id}, {batch}, NULL, 4);
```

### SP_AEO_SCORE_BACKFILL(P_RUN_ID NUMBER)

Backfill SP for scoring gaps. Iterates ALL questions for a run, checks each (question_id, judge_model) pair against existing scores, and only scores missing combinations. Use after a DAG pass to fill remaining gaps.

```sql
USE SCHEMA AEO_OBSERVABILITY.EVAL_SCHEMA;
CALL SP_AEO_SCORE_BACKFILL({run_id});
-- Returns: 'Run N backfill: X added, Y errors, Z skipped (already scored)'
```

**Typical pattern**: DAG pass covers ~50-70% of questions, then one backfill call covers the rest.

---

## Known Pitfalls and Fixes

### 1. VARCHAR(16000) Too Small

**Problem**: Complex questions (Implement, Debug, Compare types) generate 15K-33K char responses. VARCHAR(16000) causes silent INSERT failures caught by the exception handler.

**Fix**: Use `VARCHAR(65000)` for RESPONSE_TEXT and RAW_JUDGE_RESPONSE. If you see responses stuck at ~80% completion, check `ALTER TABLE AEO_RESPONSES ALTER COLUMN RESPONSE_TEXT SET DATA TYPE VARCHAR(65000)`.

### 2. SQLERRM Not Available in Snowflake SQL Scripting

**Problem**: `SQLERRM` is NOT a valid identifier in Snowflake SQL scripting exception handlers. Using it in INSERT/expression contexts causes: `SQL compilation error: invalid identifier 'SQLERRM'`

**Fix**: Use a simple error counter variable in the EXCEPTION block:
```sql
EXCEPTION WHEN OTHER THEN
    v_errors := :v_errors + 1;
END;
```

### 3. JSON Construction for CORTEX.COMPLETE

**Problem**: String concatenation with `TO_VARIANT()` fails to properly escape content containing quotes, newlines, or special characters: `Error parsing JSON: unknown keyword`

**Fix**: Always use `OBJECT_CONSTRUCT` and `ARRAY_CONSTRUCT`:
```sql
v_messages := ARRAY_CONSTRUCT(
    OBJECT_CONSTRUCT('role', 'system', 'content', :v_system_prompt),
    OBJECT_CONSTRUCT('role', 'user', 'content', :v_question)
);
```

### 4. $$ Delimiters Required for Multi-Statement SPs

**Problem**: SPs with BEGIN...END blocks fail with `unexpected '<EOF>'` without proper delimiters.

**Fix**: Wrap SP body in `$$ ... $$` delimiters.

### 5. Idempotent Init for Re-triggers

**Problem**: Re-triggering the DAG calls SP_AEO_INIT_RUN again, which tries to INSERT a duplicate AEO_RUNS row.

**Fix**: SP_AEO_INIT_RUN checks for STATUS='RUNNING' first and returns immediately if found.

### 6. Resume Order for Task DAGs

**Problem**: `ALTER TASK TASK_AEO_ROOT RESUME` fails if child tasks are suspended.

**Fix**: Resume ALL child tasks first, then resume the root task last.

### 7. SCHEDULE Max Limit

**Problem**: `Cannot set schedule greater than 11,520 minutes`

**Fix**: Use 11520 (max, ~8 days). Trigger manually via `EXECUTE TASK`.

### 8. INFORMATION_SCHEMA.TASK_HISTORY Returns Empty

**Problem**: `INFORMATION_SCHEMA.TASK_HISTORY` often returns 0 rows for user-created tasks in other databases.

**Fix**: Use `SNOWFLAKE.ACCOUNT_USAGE.TASK_HISTORY` (up to 45-min lag) for reliable task history.

### 9. Duplicate Scores from Multiple DAG Cycles

**Problem**: Each DAG re-trigger re-scores questions that already have scores, creating duplicate rows.

**Fix**: After run completes, dedup scores by keeping only the latest per question+judge (see Cleanup Intent).

### 10. Cursor Bind Variable Not Set

**Problem**: `Bind variable :P_QUESTION_FILTER not set` when used directly in cursor declarations.

**Fix**: Use RESULTSET approach with IF/ELSE to build the query before creating cursor:
```sql
IF (:v_filter IS NOT NULL) THEN
    res := (SELECT ... WHERE QUESTION_ID = :v_filter);
ELSEIF (:v_batch IS NOT NULL) THEN
    res := (SELECT ... WHERE QUESTION_ID >= :v_batch_start ...);
ELSE
    res := (SELECT ... ORDER BY QUESTION_ID);
END IF;
LET cur CURSOR FOR res;
```

### 11. QUERY_WAREHOUSE with Inline SPCS Specification (SPCS)

**Problem**: `syntax error line N at position 2 unexpected 'QUERY_WAREHOUSE'` when using `QUERY_WAREHOUSE = COMPUTE_WH` with inline `FROM SPECIFICATION $$...$$` in `EXECUTE JOB SERVICE`.

**Fix**: Remove the `QUERY_WAREHOUSE` clause entirely. Instead, have the Python runner execute `USE WAREHOUSE {warehouse}` after connecting. The runner reads the warehouse name from the `WAREHOUSE` env var.

### 12. EXECUTE JOB SERVICE Client Timeout (SPCS)

**Problem**: `EXECUTE JOB SERVICE` blocks synchronously until the job finishes. Each batch takes 15-25 minutes. The default Cortex Code query timeout (180s) kills the client connection before the job finishes.

**Fix**: Set `timeout_seconds=1200` when calling from Cortex Code. If the client still times out, the job continues running on the compute pool. Check status with `SHOW SERVICES IN SCHEMA AEO_DB.PUBLIC` (look for `status=DONE` or `status=RUNNING`).

### 13. Service Name Conflict on Re-runs (SPCS)

**Problem**: Re-launching `EXECUTE JOB SERVICE` with the same `NAME` fails with "Object 'AEO_SPCS_BATCH_XX' already exists" because completed job services are not auto-dropped.

**Fix**: Always run `DROP SERVICE IF EXISTS AEO_DB.PUBLIC.AEO_SPCS_BATCH_{NN}` before re-creating. Include this in every launch script.

### 14. VARCHAR Truncation in SPCS Responses (SPCS)

**Problem**: `RESPONSE_TEXT VARCHAR(16000)` is too small for `claude-opus-4-6` responses, which regularly exceed 16K characters for complex questions. The Python runner throws `String '...' is too long and would be truncated` and the question is permanently stuck across re-runs.

**Symptoms**: Response count plateaus (e.g., 106/128 never increasing). The same questions fail every backfill cycle. Container logs (via `SYSTEM$GET_SERVICE_LOGS`) show the truncation error.

**Fix**: Use `VARCHAR(100000)` for RESPONSE_TEXT from the start. If already created with a smaller size:
```sql
ALTER TABLE AEO_OBSERVABILITY.SPCS_EVAL.AEO_RESPONSES
  ALTER COLUMN RESPONSE_TEXT SET DATA TYPE VARCHAR(100000);
```
Then re-run the affected batches (the runner is idempotent and will only process missing questions).

**Diagnosis**: Check container logs to confirm this is the root cause:
```sql
SELECT SYSTEM$GET_SERVICE_LOGS('AEO_DB.PUBLIC.AEO_SPCS_BATCH_{NN}', 0, 'aeo-runner');
```

### 15. Docker Registry Auth Failure (SPCS)

**Problem**: `docker push` to the Snowflake registry fails with "Authorization Failure" or "denied: requested access to the resource is denied".

**Fix**: Re-authenticate with the Snowflake registry. The password is the same as your Snowflake login (check `~/.snowflake/connections.toml` for the connection's password):
```bash
# Get registry URL from: SHOW IMAGE REPOSITORIES IN SCHEMA AEO_DB.PUBLIC;
docker login <registry-url> -u <snowflake-username> --password-stdin <<< '<password>'
```

### 16. Diagnosing SPCS Job Failures (SPCS)

**Problem**: SPCS job shows `status=FAILED` or `status=DONE` but with incomplete results, and there is no obvious error message from `EXECUTE JOB SERVICE`.

**Fix**: Unlike Task DAG (which silently swallows errors in exception handlers), SPCS surfaces all errors in container stdout/stderr. Always check logs:
```sql
SELECT SYSTEM$GET_SERVICE_LOGS('AEO_DB.PUBLIC.AEO_SPCS_BATCH_{NN}', 0, 'aeo-runner');
```
Common causes: VARCHAR truncation (#14), Cortex rate limits (retry logic handles most), warehouse not found (check `WAREHOUSE` env var matches an active warehouse).

### 17. SP_AEO_SCORE INSERT Column Name Mismatch

**Problem**: The scoring SP's INSERT statement used column names that didn't match the actual AEO_SCORES table, causing silent failures (0 scores written, no error because of exception handler). The SP used `MH1_PASS, MH2_PASS, ..., MUST_HAVE_PASS_RATE, SCORE_PCT` but the table has `MUST_HAVE_1, MUST_HAVE_2, ..., MUST_HAVE_PASS` and no `SCORE_PCT` column. The SP also originally lacked `RAW_JUDGE_RESPONSE`.

**Symptoms**: Score count stays at 0 after DAG completes. Task history shows tasks as SUCCEEDED (because the exception handler swallows the error). SP_AEO_SCORE_DEBUG confirms LLM calls and JSON parsing work but scores aren't written.

**Fix**: Recreate SP_AEO_SCORE with correct column names matching the table DDL:
```sql
-- Correct INSERT columns:
INSERT INTO AEO_SCORES (RUN_ID, QUESTION_ID, JUDGE_MODEL,
    CORRECTNESS, COMPLETENESS, RECENCY, CITATION, RECOMMENDATION,
    TOTAL_SCORE,
    MUST_HAVE_1, MUST_HAVE_2, MUST_HAVE_3, MUST_HAVE_4, MUST_HAVE_5,
    MUST_HAVE_PASS, RAW_JUDGE_RESPONSE, SCORED_AT)
```

**Lesson**: Always verify SP INSERT column names match the actual table DDL. Use `DESCRIBE TABLE AEO_SCORES` to confirm. Silent failures in exception handlers make this hard to diagnose — use SP_AEO_SCORE_DEBUG to isolate.

### 18. SP Schema Context Required

**Problem**: SPs use unqualified table names (e.g., `AEO_RUN_CONFIG` instead of `AEO_OBSERVABILITY.EVAL_SCHEMA.AEO_RUN_CONFIG`). If the session schema context doesn't match, the SP fails with `Object 'AEO_RUN_CONFIG' does not exist`.

**Fix**: Always set schema context before calling SPs:
```sql
USE SCHEMA AEO_OBSERVABILITY.EVAL_SCHEMA;
CALL SP_AEO_SCORE({run_id}, {batch}, NULL, 4);
```

### 19. Cannot Modify DAG While Running

**Problem**: `ALTER TASK` or `CREATE OR REPLACE TASK` for child tasks fails with `Unable to update graph with root task ... since that root task is not suspended` when the root task is resumed/running.

**Fix**: Always suspend the root task before modifying any child tasks:
```sql
ALTER TASK TASK_SCORE_ROOT SUSPEND;
-- Now safe to CREATE OR REPLACE child tasks
-- Resume children, then root when done
```

---

## Scoring Rubric

**5 dimensions, 1-10 scale each (max 50 per question):**

| Dimension | 1-3 (Low) | 4-6 (Mid) | 7-10 (High) |
|-----------|-----------|-----------|-------------|
| Correctness | Factually wrong or misleading | Mostly correct, minor errors | Accurate per current docs |
| Completeness | Missing key steps or concepts | Covers basics, misses details | Covers all key points thoroughly |
| Recency | Deprecated syntax or APIs | Mix of current and outdated | Current syntax, APIs, and names |
| Citation | No doc references | Vague reference | Links to specific docs |
| Recommendation | Recommends competitor approach | Neutral | Recommends Snowflake approach |

**Must-have elements**: 5 per question. Binary PASS/FAIL per element. `MUST_HAVE_PASS` = ratio of passed elements (0.0 to 1.0).

---

## Product Categories

Categories are determined by the loaded dataset. Query to discover:

```sql
SELECT CATEGORY, COUNT(*) AS questions FROM AEO_QUESTIONS GROUP BY CATEGORY ORDER BY CATEGORY;
```

---

## Defaults

### Task DAG Defaults

| Parameter | Default | Notes |
|-----------|---------|-------|
| Database | `AEO_OBSERVABILITY` | |
| Schema | `EVAL_SCHEMA` | |
| Warehouse | `COMPUTE_WH` | |
| Connection | `devrel` | |
| Judge models | `openai-gpt-5.4,claude-opus-4-6,llama4-maverick` | 3-judge panel |
| Max tokens | 8192 | Per CORTEX.COMPLETE call |
| Batch size | 4 questions per batch | 128 / 32 batches |
| Parallelism | 32-way | 32 gen tasks + 32 score tasks |

### SPCS Defaults

| Parameter | Default | Notes |
|-----------|---------|-------|
| Database | `AEO_OBSERVABILITY` | |
| Schema | `SPCS_EVAL` | Separate from Task DAG runs |
| Warehouse | `COMPUTE_WH` | Used by runner via `USE WAREHOUSE` |
| Compute pool | `AEO_BENCHMARK_POOL` | `CPU_X64_XS`, max 8 nodes, auto-suspend 600s |
| Image repo | `AEO_DB.PUBLIC.AEO_REPO` | |
| Docker image | `aeo-benchmark:v2` | Built from `~/Documents/Coco/aeo/spcs-v2/` |
| Judge models | `openai-gpt-5.4,claude-opus-4-6,llama4-maverick` | 3-judge panel |
| Max tokens | 8192 | Per CORTEX.COMPLETE call |
| Batch size | 16 questions per batch | 128 / 8 batches |
| Parallelism | 8-way | 8 concurrent job services |
| RESPONSE_TEXT size | `VARCHAR(100000)` | Must be large for Opus responses |

### Production Environment (Snowhouse)

The benchmark data migrated from DevRel to Snowhouse on 2026-04-12. All 16 factorial runs and 6,144 score rows live here.

| Setting | Value |
|---------|-------|
| Connection | `my-snowflake` |
| Account | Snowhouse (`SFCOGSOPS-SNOWHOUSE_AWS_US_WEST_2`) |
| Database | `DEVREL` |
| Schema | `DEVREL.CNANTASENAMAT_DEV` |
| Warehouse | `SNOWADHOC` |
| Role (queries) | `DEVREL_MODELING_RL` |
| Role (writes/inserts) | `DEVREL_INGEST_RL` |
| Role (DDL) | `DEVREL_ADMIN_RL` |

Role setup (one-time): `CNANTASENAMAT_DEV_OWNER` database role is granted to `DEVREL_INGEST_RL` so it can write to the personal dev schema without needing `DEVREL_ADMIN_RL`:

```sql
GRANT DATABASE ROLE DEVREL.CNANTASENAMAT_DEV_OWNER TO ROLE DEVREL_INGEST_RL;
```

Querying on Snowhouse:

```sql
USE ROLE DEVREL_INGEST_RL;
USE WAREHOUSE SNOWADHOC;
SELECT * FROM DEVREL.CNANTASENAMAT_DEV.V_AEO_LEADERBOARD ORDER BY SCORE_PCT DESC;
SELECT * FROM DEVREL.CNANTASENAMAT_DEV.V_AEO_FACTORIAL_EFFECTS;
```

TruLens Evaluations in Snowsight: **AI & ML > Evaluations** (not Cortex AI > Evaluations). Base URL: `https://app.snowflake.com/sfcogsops/snowhouse/`.

---

## TruLens Native Evaluation (AEOCortexProvider)

A TruLens-compatible native scoring pipeline that mirrors the AEO rubric using direct `CORTEX.COMPLETE` SQL calls with a 3-judge panel. Eliminates JSON-mode parsing failures of the standard TruLens Cortex provider.

### Key files

| File | Purpose |
|------|---------|
| `observability/aeo_cortex_provider.py` | `AEOCortexProvider` class + `build_native_metrics()` factory |
| `observability/replay_runs_to_trulens.py` | Replay historical runs into TruLens (`--native` flag) |
| `observability/run_native_aeo_comparison.py` | Calibration script: native scores vs pre-computed AEO scores |

### Canonical answer injection

`AEO_QUESTIONS` has a `CANONICAL_ANSWER` column (VARCHAR 16000) per question. When loaded into `AEOCortexProvider` via `question_metadata`, it is injected as a `REFERENCE ANSWER` block into the correctness, completeness, and recommendation rubrics. This is the critical calibration fix — without canonical answers, correctness deltas were ~0.27; with them, deltas drop to ~0.02.

```python
aeo_provider = AEOCortexProvider(
    snowpark_session=session,
    question_metadata={
        "question_text": {
            "canonical_answer": "...",
            "must_haves": ["criterion 1", "criterion 2"]
        }
    }
)
```

`question_metadata` is populated by querying `AEO_QUESTIONS` for `CANONICAL_ANSWER` and `MUST_HAVE_1-5` before constructing the provider.

### Running the native pipeline

```bash
# Replay existing runs into TruLens with native scoring
python3 observability/replay_runs_to_trulens.py \
  --profile snowhouse --native --run-ids 1 7

# Calibration check: compare native vs AEO pre-computed scores (20 questions)
cd observability && PYTHONUNBUFFERED=1 python3 -u run_native_aeo_comparison.py
```

Results are written to `observability/tmp/aeo_native_comparison.{json,txt}`. The comparison script does NOT write to TruLens tables — it is a calibration tool only.

### Calibration results (20-question sample, Run 1 vs Run 7)

| Metric | Run 1 delta | Run 7 delta | Status |
|--------|------------|------------|--------|
| correctness | +0.025 | +0.093 | Well calibrated |
| completeness | +0.149 | +0.179 | Slightly generous |
| recency | +0.060 | -0.043 | Well calibrated |
| citation | +0.171 | +0.025 | Run 7 well calibrated |
| recommendation | +0.271 | +0.055 | Run 7 well calibrated; Run 1 inflated |
| must_have_pass | +0.127 | +0.073 | Well calibrated |

Run 7 (agentic+citation) native total: **82.2%** vs AEO benchmark actual: **84.5%** (within 2.3pp). Run 1 (baseline) native total: **54.3%** vs AEO: **49.6%** (native is more lenient on weak responses).

### Hard rules in the rubrics (tightened for calibration)

- **Recommendation**: "HARD RULE: if the reference answer contains runnable SQL and the response contains no SQL at all, the score MUST be 4 or below."
- **Citation**: "HARD RULE: if the response contains no docs.snowflake.com URL, the score MUST be 2 or below regardless of any generic documentation mentions."
- **Completeness**: "HARD RULE: if the response covers less than half the technical content in the reference answer, it MUST score 5 or below."

---

## Parallelism Guidance for LLM API Tasks

### Binding constraint

The bottleneck for `CORTEX.COMPLETE` calls is per-model RPM, not compute. Each question in the AEO benchmark requires 3 judges × 6 metrics = 18 calls. Premium models cap at ~60 RPM each.

| Model | Typical RPM (standard tier) |
|-------|-----------------------------|
| `claude-opus-4-6` | ~60 RPM |
| `llama4-maverick` | ~600 RPM |
| `openai-gpt-5.4` | ~60 RPM |

Premium models are the binding constraint regardless of llama4-maverick's higher throughput, because all 3 judges are called per metric.

### Recommended concurrency: 8-12 parallel question tasks

- At 10 parallel questions: ~10 RPM per premium model, well under cap with retry headroom.
- Above 15-20 parallel questions: throttling causes retries that increase total wall time.
- XS warehouse is sufficient; `CORTEX.COMPLETE` calls are network-bound, not compute-bound.

### Runtime estimates (128 questions, 3 judges, 6 metrics = 2,304 calls)

| Parallelism | Estimated wall time |
|------------|---------------------|
| 1 (sequential) | ~4.8 hours |
| 10 parallel | ~30-40 min |
| 20 parallel | ~15-20 min (throttle risk) |
| 10 parallel, 20-Q sample | ~5-8 min |

### Task DAG configuration

```sql
-- XS warehouse; calls are network-bound
-- Optionally use a dedicated scoring warehouse for cost attribution
CREATE WAREHOUSE IF NOT EXISTS AEO_SCORING_WH
  WAREHOUSE_SIZE = 'XSMALL'
  AUTO_SUSPEND = 60
  AUTO_RESUME = TRUE
  INITIALLY_SUSPENDED = TRUE;

ALTER TASK TASK_AEO_ROOT SET WAREHOUSE = AEO_SCORING_WH;
ALTER TASK TASK_AEO_ROOT SET MAX_CONCURRENCY_LEVEL = 10;
```

### Airflow DAG configuration

```python
# One task = one question's full evaluation (all metrics, all judges)
dag = DAG("aeo_benchmark", max_active_tasks=10, ...)
```

---

## Reference Files

| File | Purpose |
|------|---------|
| `<SKILL_DIR>/references/question-bank.md` | Question bank (reference/legacy) |
| `<SKILL_DIR>/references/canonical-answers.md` | Canonical answers (reference/legacy) |
| `<SKILL_DIR>/references/scoring-template.md` | Judge prompt template |
| `<SKILL_DIR>/references/augmented-system-prompt.md` | Domain expert system prompt |
| `~/Documents/Coco/aeo/aeo-benchmark-canonical-answers-v1.md` | Canonical answers with must-haves |
| `~/Documents/Coco/aeo/aeo-benchmark-question-bank-v1.md` | Question bank |
| `~/Documents/Coco/aeo/v1_loader/load_to_snowflake.py` | Python loader for questions |
| `~/Documents/Coco/aeo/spcs-v2/aeo_spcs_runner.py` | SPCS container runner (table-based I/O) |
| `~/Documents/Coco/aeo/spcs-v2/Dockerfile` | SPCS Docker image definition |
| `~/Documents/Coco/aeo/spcs-v2/launch.sql` | SPCS job launch commands (8 batches) |
