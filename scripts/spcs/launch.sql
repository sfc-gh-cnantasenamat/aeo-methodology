-- AEO SPCS v2: Launch 8 parallel batch jobs
-- Each job processes 16 questions (generate + score) against SPCS_EVAL schema.
-- Prerequisites:
--   1. Docker image aeo-benchmark:v2 pushed to AEO_DB.PUBLIC.AEO_REPO
--   2. Compute pool AEO_BENCHMARK_POOL with MAX_NODES >= 8, resumed
--   3. AEO_OBSERVABILITY.SPCS_EVAL schema populated with questions + run config

-- Upload the job spec first:
-- PUT file:///Users/cnantasenamat/Documents/Coco/aeo/spcs-v2/aeo-job-spec-batch.yaml @AEO_DB.PUBLIC.AEO_STAGE/specs-v2/ AUTO_COMPRESS=FALSE OVERWRITE=TRUE;

-- Batch 1: Q001-Q016
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

-- Batch 2: Q017-Q032
EXECUTE JOB SERVICE
  IN COMPUTE POOL AEO_BENCHMARK_POOL
  NAME = AEO_DB.PUBLIC.AEO_SPCS_BATCH_02
  FROM SPECIFICATION $$
spec:
  containers:
  - name: aeo-runner
    image: /AEO_DB/PUBLIC/AEO_REPO/aeo-benchmark:v2
    env:
      BATCH_NUM: "2"
      MODEL: "claude-opus-4-6"
      JUDGE_MODELS: "openai-gpt-5.4,claude-opus-4-6,llama4-maverick"
      WAREHOUSE: "COMPUTE_WH"
      RUN_SCHEMA: "AEO_OBSERVABILITY.SPCS_EVAL"
      RUN_ID: "1"
      MAX_TOKENS: "8192"
$$
  QUERY_WAREHOUSE = COMPUTE_WH;

-- Batch 3: Q033-Q048
EXECUTE JOB SERVICE
  IN COMPUTE POOL AEO_BENCHMARK_POOL
  NAME = AEO_DB.PUBLIC.AEO_SPCS_BATCH_03
  FROM SPECIFICATION $$
spec:
  containers:
  - name: aeo-runner
    image: /AEO_DB/PUBLIC/AEO_REPO/aeo-benchmark:v2
    env:
      BATCH_NUM: "3"
      MODEL: "claude-opus-4-6"
      JUDGE_MODELS: "openai-gpt-5.4,claude-opus-4-6,llama4-maverick"
      WAREHOUSE: "COMPUTE_WH"
      RUN_SCHEMA: "AEO_OBSERVABILITY.SPCS_EVAL"
      RUN_ID: "1"
      MAX_TOKENS: "8192"
$$
  QUERY_WAREHOUSE = COMPUTE_WH;

-- Batch 4: Q049-Q064
EXECUTE JOB SERVICE
  IN COMPUTE POOL AEO_BENCHMARK_POOL
  NAME = AEO_DB.PUBLIC.AEO_SPCS_BATCH_04
  FROM SPECIFICATION $$
spec:
  containers:
  - name: aeo-runner
    image: /AEO_DB/PUBLIC/AEO_REPO/aeo-benchmark:v2
    env:
      BATCH_NUM: "4"
      MODEL: "claude-opus-4-6"
      JUDGE_MODELS: "openai-gpt-5.4,claude-opus-4-6,llama4-maverick"
      WAREHOUSE: "COMPUTE_WH"
      RUN_SCHEMA: "AEO_OBSERVABILITY.SPCS_EVAL"
      RUN_ID: "1"
      MAX_TOKENS: "8192"
$$
  QUERY_WAREHOUSE = COMPUTE_WH;

-- Batch 5: Q065-Q080
EXECUTE JOB SERVICE
  IN COMPUTE POOL AEO_BENCHMARK_POOL
  NAME = AEO_DB.PUBLIC.AEO_SPCS_BATCH_05
  FROM SPECIFICATION $$
spec:
  containers:
  - name: aeo-runner
    image: /AEO_DB/PUBLIC/AEO_REPO/aeo-benchmark:v2
    env:
      BATCH_NUM: "5"
      MODEL: "claude-opus-4-6"
      JUDGE_MODELS: "openai-gpt-5.4,claude-opus-4-6,llama4-maverick"
      WAREHOUSE: "COMPUTE_WH"
      RUN_SCHEMA: "AEO_OBSERVABILITY.SPCS_EVAL"
      RUN_ID: "1"
      MAX_TOKENS: "8192"
$$
  QUERY_WAREHOUSE = COMPUTE_WH;

-- Batch 6: Q081-Q096
EXECUTE JOB SERVICE
  IN COMPUTE POOL AEO_BENCHMARK_POOL
  NAME = AEO_DB.PUBLIC.AEO_SPCS_BATCH_06
  FROM SPECIFICATION $$
spec:
  containers:
  - name: aeo-runner
    image: /AEO_DB/PUBLIC/AEO_REPO/aeo-benchmark:v2
    env:
      BATCH_NUM: "6"
      MODEL: "claude-opus-4-6"
      JUDGE_MODELS: "openai-gpt-5.4,claude-opus-4-6,llama4-maverick"
      WAREHOUSE: "COMPUTE_WH"
      RUN_SCHEMA: "AEO_OBSERVABILITY.SPCS_EVAL"
      RUN_ID: "1"
      MAX_TOKENS: "8192"
$$
  QUERY_WAREHOUSE = COMPUTE_WH;

-- Batch 7: Q097-Q112
EXECUTE JOB SERVICE
  IN COMPUTE POOL AEO_BENCHMARK_POOL
  NAME = AEO_DB.PUBLIC.AEO_SPCS_BATCH_07
  FROM SPECIFICATION $$
spec:
  containers:
  - name: aeo-runner
    image: /AEO_DB/PUBLIC/AEO_REPO/aeo-benchmark:v2
    env:
      BATCH_NUM: "7"
      MODEL: "claude-opus-4-6"
      JUDGE_MODELS: "openai-gpt-5.4,claude-opus-4-6,llama4-maverick"
      WAREHOUSE: "COMPUTE_WH"
      RUN_SCHEMA: "AEO_OBSERVABILITY.SPCS_EVAL"
      RUN_ID: "1"
      MAX_TOKENS: "8192"
$$
  QUERY_WAREHOUSE = COMPUTE_WH;

-- Batch 8: Q113-Q128
EXECUTE JOB SERVICE
  IN COMPUTE POOL AEO_BENCHMARK_POOL
  NAME = AEO_DB.PUBLIC.AEO_SPCS_BATCH_08
  FROM SPECIFICATION $$
spec:
  containers:
  - name: aeo-runner
    image: /AEO_DB/PUBLIC/AEO_REPO/aeo-benchmark:v2
    env:
      BATCH_NUM: "8"
      MODEL: "claude-opus-4-6"
      JUDGE_MODELS: "openai-gpt-5.4,claude-opus-4-6,llama4-maverick"
      WAREHOUSE: "COMPUTE_WH"
      RUN_SCHEMA: "AEO_OBSERVABILITY.SPCS_EVAL"
      RUN_ID: "1"
      MAX_TOKENS: "8192"
$$
  QUERY_WAREHOUSE = COMPUTE_WH;

-- Monitor jobs:
-- SELECT SYSTEM$GET_SERVICE_STATUS('AEO_DB.PUBLIC.AEO_SPCS_BATCH_01');
-- SELECT SYSTEM$GET_SERVICE_LOGS('AEO_DB.PUBLIC.AEO_SPCS_BATCH_01', 0, 'aeo-runner');
--
-- Check progress:
-- SELECT COUNT(*) FROM AEO_OBSERVABILITY.SPCS_EVAL.AEO_RESPONSES WHERE RUN_ID = 1;
-- SELECT COUNT(*) FROM AEO_OBSERVABILITY.SPCS_EVAL.AEO_SCORES WHERE RUN_ID = 1;
