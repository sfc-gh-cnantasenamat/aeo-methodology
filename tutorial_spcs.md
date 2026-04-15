# AEO Benchmark: SPCS Tutorial

Run the AEO benchmark as 8 parallel SPCS job services — one per batch of 16 questions. Best for isolated, reproducible runs or writing results to a separate schema.

---

## Architecture

```
Docker image (aeo-benchmark:v2)
        │
        ▼
Snowflake Image Registry (AEO_DB.PUBLIC.AEO_REPO)
        │
        ▼
Compute Pool (AEO_BENCHMARK_POOL, MAX_NODES=8)
        │
  ┌─────┴──────────────────────────────┐
  │ 8 parallel EXECUTE JOB SERVICE calls│
  │  Batch 1: Q001–Q016                │
  │  Batch 2: Q017–Q032                │
  │  ...                               │
  │  Batch 8: Q113–Q128                │
  └─────────────────────────────────────┘
        │
        ▼
AEO_RESPONSES + AEO_SCORES (written from container via snowflake-connector-python)
```

---

## Step 1: Prerequisites

```sql
USE WAREHOUSE COMPUTE_WH;
CREATE DATABASE IF NOT EXISTS AEO_DB;
USE DATABASE AEO_DB;
CREATE SCHEMA IF NOT EXISTS PUBLIC;
```

Ensure the same AEO tables exist in your target schema (see `tutorial_task_dag.md` Step 2). The SPCS runner writes to whatever schema you pass via `RUN_SCHEMA`.

---

## Step 2: Create Infrastructure

```sql
-- Image repository (one-time)
CREATE IMAGE REPOSITORY IF NOT EXISTS AEO_DB.PUBLIC.AEO_REPO;

-- Internal stage for data exchange
CREATE STAGE IF NOT EXISTS AEO_DB.PUBLIC.AEO_STAGE
  DIRECTORY = (ENABLE = TRUE);

-- Compute pool: CPU_X64_XS is the smallest and cheapest
-- MAX_NODES = 8 allows all batches to run in parallel
CREATE COMPUTE POOL IF NOT EXISTS AEO_BENCHMARK_POOL
  MIN_NODES = 1
  MAX_NODES = 8
  INSTANCE_FAMILY = CPU_X64_XS
  AUTO_SUSPEND_SECS = 300
  AUTO_RESUME = TRUE;

-- Get the image repository URL (needed for docker push)
SHOW IMAGE REPOSITORIES LIKE 'AEO_REPO' IN SCHEMA AEO_DB.PUBLIC;
-- Copy the value in the "repository_url" column
```

---

## Step 3: Build and Push the Docker Image

The `Dockerfile` is at `scripts/spcs/Dockerfile`:

```dockerfile
FROM python:3.11-slim
RUN pip install --no-cache-dir snowflake-connector-python[secure-local-storage]
COPY aeo_spcs_runner.py /app/aeo_spcs_runner.py
WORKDIR /app
CMD ["python", "-u", "aeo_spcs_runner.py"]
```

Build and push:

```bash
# Replace <repo_url> with the value from SHOW IMAGE REPOSITORIES above
REPO_URL="<org>-<account>.registry.snowflakecomputing.com/aeo_db/public/aeo_repo"

# Authenticate Docker with Snowflake registry
docker login $REPO_URL

# Build image (run from scripts/spcs/)
docker build -t aeo-benchmark:v2 .

# Tag and push
docker tag aeo-benchmark:v2 $REPO_URL/aeo-benchmark:v2
docker push $REPO_URL/aeo-benchmark:v2
```

Verify the image is available:

```sql
SHOW IMAGES IN IMAGE REPOSITORY AEO_DB.PUBLIC.AEO_REPO;
```

---

## Step 4: Verify Compute Pool Is Ready

```sql
SHOW COMPUTE POOLS LIKE 'AEO_BENCHMARK_POOL';
-- STATE should be IDLE or ACTIVE, not STARTING
-- If STARTING, wait ~2 minutes before launching jobs
```

Resume if suspended:

```sql
ALTER COMPUTE POOL AEO_BENCHMARK_POOL RESUME;
```

---

## Step 5: Launch 8 Parallel Job Services

Each job service is independent. Launch all 8 in the same session — they run in parallel on separate nodes.

Substitute your values for `RUN_SCHEMA` and `RUN_ID` before executing.

```sql
-- Batch 1: Q001–Q016
EXECUTE JOB SERVICE
  IN COMPUTE POOL AEO_BENCHMARK_POOL
  NAME = AEO_DB.PUBLIC.AEO_SPCS_BATCH_01
  FROM SPECIFICATION $$
spec:
  containers:
  - name: aeo-runner
    image: /AEO_DB/PUBLIC/AEO_REPO/aeo-benchmark:v2
    env:
      BATCH_NUM: "1"
      MODEL: "claude-opus-4-6"
      JUDGE_MODELS: "openai-gpt-5.4,claude-opus-4-6,llama4-maverick"
      WAREHOUSE: "COMPUTE_WH"
      RUN_SCHEMA: "AEO_OBSERVABILITY.SPCS_EVAL"
      RUN_ID: "1"
      MAX_TOKENS: "8192"
$$
  QUERY_WAREHOUSE = COMPUTE_WH;

-- Repeat for BATCH_02 through BATCH_08, incrementing BATCH_NUM each time
-- Batch 2: Q017–Q032  →  BATCH_NUM: "2"
-- Batch 3: Q033–Q048  →  BATCH_NUM: "3"
-- ...
-- Batch 8: Q113–Q128  →  BATCH_NUM: "8"
```

> Each `EXECUTE JOB SERVICE` call returns immediately. The job runs asynchronously on the compute pool.

---

## Step 6: Monitor Job Status

```sql
-- Check all batch job statuses
SELECT SYSTEM$GET_SERVICE_STATUS('AEO_DB.PUBLIC.AEO_SPCS_BATCH_01');
SELECT SYSTEM$GET_SERVICE_STATUS('AEO_DB.PUBLIC.AEO_SPCS_BATCH_02');
-- ... repeat for 03–08

-- Check container logs for a specific batch
SELECT SYSTEM$GET_SERVICE_LOGS('AEO_DB.PUBLIC.AEO_SPCS_BATCH_01', 0, 'aeo-runner');
```

Status values to expect:

| Status | Meaning |
|---|---|
| `PENDING` | Waiting for compute node |
| `RUNNING` | Container executing |
| `SUCCEEDED` | Completed successfully |
| `FAILED` | Error — check logs |

Track data progress:

```sql
-- Response generation progress (128 expected when all batches complete)
SELECT COUNT(*) AS responses FROM AEO_OBSERVABILITY.SPCS_EVAL.AEO_RESPONSES WHERE RUN_ID = 1;

-- Scoring progress (384 expected: 128 questions × 3 judges)
SELECT COUNT(*) AS scores FROM AEO_OBSERVABILITY.SPCS_EVAL.AEO_SCORES WHERE RUN_ID = 1;
```

---

## Step 7: View Results

```sql
USE SCHEMA AEO_OBSERVABILITY.SPCS_EVAL;

-- Leaderboard
SELECT RUN_ID, SCORE_PCT, MH_PCT
FROM V_AEO_LEADERBOARD
ORDER BY SCORE_PCT DESC;

-- Per-batch completion check
SELECT SUBSTRING(QUESTION_ID, 1, 4) AS BATCH_Q_PREFIX, COUNT(*) AS n
FROM AEO_RESPONSES
WHERE RUN_ID = 1
GROUP BY 1
ORDER BY 1;
```

---

## Step 8: Cleanup

Drop completed job services to free resources (SPCS keeps them until explicitly dropped):

```sql
DROP SERVICE IF EXISTS AEO_DB.PUBLIC.AEO_SPCS_BATCH_01;
DROP SERVICE IF EXISTS AEO_DB.PUBLIC.AEO_SPCS_BATCH_02;
-- ... repeat for 03–08

-- Suspend compute pool when done (stops billing for idle nodes)
ALTER COMPUTE POOL AEO_BENCHMARK_POOL SUSPEND;
```

---

## Comparison: SPCS vs Task DAG

| | Task DAG | SPCS |
|---|---|---|
| Setup | SQL only | Docker build + push required |
| Parallelism | 32-way (4 questions/task) | 8-way (16 questions/job) |
| Overhead | Zero container startup | ~2 min cold start per node |
| Target schema | Same schema as DAG | Configurable via `RUN_SCHEMA` env var |
| Best for | Repeated runs, low overhead | Isolated runs, separate schema |
| Est. runtime | ~8 min | ~10–12 min (includes container start) |
