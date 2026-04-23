-- AEO Benchmark SPCS v5: Snowhouse Infrastructure Setup
-- Run in order: image repo → compute pool → build/push image → execute jobs
--
-- Prerequisites:
--   docker build --platform linux/amd64 -t <registry_url>/aeo-benchmark:v5 spcs/
--   docker login <registry_url>
--   docker push <registry_url>/aeo-benchmark:v5

USE ROLE DEVREL_INGEST_RL;
USE WAREHOUSE SNOWADHOC;

-- 1. Image repository (stores the Docker image)
CREATE IMAGE REPOSITORY IF NOT EXISTS DEVREL.CNANTASENAMAT_DEV.AEO_REPO;

-- Get the registry URL for docker push (copy repository_url from output)
SHOW IMAGE REPOSITORIES IN SCHEMA DEVREL.CNANTASENAMAT_DEV;

-- 2. Compute pool (8 nodes = run all 8 batches in parallel)
CREATE COMPUTE POOL IF NOT EXISTS AEO_BENCHMARK_POOL
  MIN_NODES = 1
  MAX_NODES = 8
  INSTANCE_FAMILY = CPU_X64_XS
  AUTO_SUSPEND_SECS = 300
  AUTO_RESUME = TRUE
  COMMENT = 'AEO Benchmark SPCS job pool';

-- Check pool status
SHOW COMPUTE POOLS LIKE 'AEO_BENCHMARK_POOL';

-- 3. After building and pushing the image, execute 8 parallel job services
--    (one per 16-question batch). Replace RUN_ID value as needed.

-- Batch 1 (Q001-Q016)
EXECUTE JOB SERVICE
  IN COMPUTE POOL AEO_BENCHMARK_POOL
  FROM SPECIFICATION $$
    spec:
      containers:
      - name: aeo-runner
        image: /DEVREL/CNANTASENAMAT_DEV/AEO_REPO/aeo-benchmark:v5
        env:
          BATCH_NUM: "1"
          MODEL: "claude-opus-4-6"
          WAREHOUSE: "SNOWADHOC"
          RUN_SCHEMA: "DEVREL.CNANTASENAMAT_DEV"
          RUN_ID: "20"
          GENERATION_MODE: "cortex_cli"
          ROLE: "DEVREL_INGEST_RL"
          REQUIRE_SPCS: "true"
  $$
  NAME = DEVREL.CNANTASENAMAT_DEV.AEO_RUN20_BATCH1
  QUERY_WAREHOUSE = SNOWADHOC;

-- Batch 2 (Q017-Q032)
EXECUTE JOB SERVICE
  IN COMPUTE POOL AEO_BENCHMARK_POOL
  FROM SPECIFICATION $$
    spec:
      containers:
      - name: aeo-runner
        image: /DEVREL/CNANTASENAMAT_DEV/AEO_REPO/aeo-benchmark:v5
        env:
          BATCH_NUM: "2"
          MODEL: "claude-opus-4-6"
          WAREHOUSE: "SNOWADHOC"
          RUN_SCHEMA: "DEVREL.CNANTASENAMAT_DEV"
          RUN_ID: "20"
          GENERATION_MODE: "cortex_cli"
          ROLE: "DEVREL_INGEST_RL"
          REQUIRE_SPCS: "true"
  $$
  NAME = DEVREL.CNANTASENAMAT_DEV.AEO_RUN20_BATCH2
  QUERY_WAREHOUSE = SNOWADHOC;

-- Batch 3 (Q033-Q048)
EXECUTE JOB SERVICE
  IN COMPUTE POOL AEO_BENCHMARK_POOL
  FROM SPECIFICATION $$
    spec:
      containers:
      - name: aeo-runner
        image: /DEVREL/CNANTASENAMAT_DEV/AEO_REPO/aeo-benchmark:v5
        env:
          BATCH_NUM: "3"
          MODEL: "claude-opus-4-6"
          WAREHOUSE: "SNOWADHOC"
          RUN_SCHEMA: "DEVREL.CNANTASENAMAT_DEV"
          RUN_ID: "20"
          GENERATION_MODE: "cortex_cli"
          ROLE: "DEVREL_INGEST_RL"
          REQUIRE_SPCS: "true"
  $$
  NAME = DEVREL.CNANTASENAMAT_DEV.AEO_RUN20_BATCH3
  QUERY_WAREHOUSE = SNOWADHOC;

-- Batch 4 (Q049-Q064)
EXECUTE JOB SERVICE
  IN COMPUTE POOL AEO_BENCHMARK_POOL
  FROM SPECIFICATION $$
    spec:
      containers:
      - name: aeo-runner
        image: /DEVREL/CNANTASENAMAT_DEV/AEO_REPO/aeo-benchmark:v5
        env:
          BATCH_NUM: "4"
          MODEL: "claude-opus-4-6"
          WAREHOUSE: "SNOWADHOC"
          RUN_SCHEMA: "DEVREL.CNANTASENAMAT_DEV"
          RUN_ID: "20"
          GENERATION_MODE: "cortex_cli"
          ROLE: "DEVREL_INGEST_RL"
          REQUIRE_SPCS: "true"
  $$
  NAME = DEVREL.CNANTASENAMAT_DEV.AEO_RUN20_BATCH4
  QUERY_WAREHOUSE = SNOWADHOC;

-- Batch 5 (Q065-Q080)
EXECUTE JOB SERVICE
  IN COMPUTE POOL AEO_BENCHMARK_POOL
  FROM SPECIFICATION $$
    spec:
      containers:
      - name: aeo-runner
        image: /DEVREL/CNANTASENAMAT_DEV/AEO_REPO/aeo-benchmark:v5
        env:
          BATCH_NUM: "5"
          MODEL: "claude-opus-4-6"
          WAREHOUSE: "SNOWADHOC"
          RUN_SCHEMA: "DEVREL.CNANTASENAMAT_DEV"
          RUN_ID: "20"
          GENERATION_MODE: "cortex_cli"
          ROLE: "DEVREL_INGEST_RL"
          REQUIRE_SPCS: "true"
  $$
  NAME = DEVREL.CNANTASENAMAT_DEV.AEO_RUN20_BATCH5
  QUERY_WAREHOUSE = SNOWADHOC;

-- Batch 6 (Q081-Q096)
EXECUTE JOB SERVICE
  IN COMPUTE POOL AEO_BENCHMARK_POOL
  FROM SPECIFICATION $$
    spec:
      containers:
      - name: aeo-runner
        image: /DEVREL/CNANTASENAMAT_DEV/AEO_REPO/aeo-benchmark:v5
        env:
          BATCH_NUM: "6"
          MODEL: "claude-opus-4-6"
          WAREHOUSE: "SNOWADHOC"
          RUN_SCHEMA: "DEVREL.CNANTASENAMAT_DEV"
          RUN_ID: "20"
          GENERATION_MODE: "cortex_cli"
          ROLE: "DEVREL_INGEST_RL"
          REQUIRE_SPCS: "true"
  $$
  NAME = DEVREL.CNANTASENAMAT_DEV.AEO_RUN20_BATCH6
  QUERY_WAREHOUSE = SNOWADHOC;

-- Batch 7 (Q097-Q112)
EXECUTE JOB SERVICE
  IN COMPUTE POOL AEO_BENCHMARK_POOL
  FROM SPECIFICATION $$
    spec:
      containers:
      - name: aeo-runner
        image: /DEVREL/CNANTASENAMAT_DEV/AEO_REPO/aeo-benchmark:v5
        env:
          BATCH_NUM: "7"
          MODEL: "claude-opus-4-6"
          WAREHOUSE: "SNOWADHOC"
          RUN_SCHEMA: "DEVREL.CNANTASENAMAT_DEV"
          RUN_ID: "20"
          GENERATION_MODE: "cortex_cli"
          ROLE: "DEVREL_INGEST_RL"
          REQUIRE_SPCS: "true"
  $$
  NAME = DEVREL.CNANTASENAMAT_DEV.AEO_RUN20_BATCH7
  QUERY_WAREHOUSE = SNOWADHOC;

-- Batch 8 (Q113-Q128)
EXECUTE JOB SERVICE
  IN COMPUTE POOL AEO_BENCHMARK_POOL
  FROM SPECIFICATION $$
    spec:
      containers:
      - name: aeo-runner
        image: /DEVREL/CNANTASENAMAT_DEV/AEO_REPO/aeo-benchmark:v5
        env:
          BATCH_NUM: "8"
          MODEL: "claude-opus-4-6"
          WAREHOUSE: "SNOWADHOC"
          RUN_SCHEMA: "DEVREL.CNANTASENAMAT_DEV"
          RUN_ID: "20"
          GENERATION_MODE: "cortex_cli"
          ROLE: "DEVREL_INGEST_RL"
          REQUIRE_SPCS: "true"
  $$
  NAME = DEVREL.CNANTASENAMAT_DEV.AEO_RUN20_BATCH8
  QUERY_WAREHOUSE = SNOWADHOC;

-- 4. Monitor job status
-- SELECT SYSTEM$GET_SERVICE_STATUS('DEVREL.CNANTASENAMAT_DEV.AEO_RUN20_BATCH1');
-- SELECT SYSTEM$GET_SERVICE_STATUS('DEVREL.CNANTASENAMAT_DEV.AEO_RUN20_BATCH2');
-- SELECT SYSTEM$GET_SERVICE_STATUS('DEVREL.CNANTASENAMAT_DEV.AEO_RUN20_BATCH3');
-- SELECT SYSTEM$GET_SERVICE_STATUS('DEVREL.CNANTASENAMAT_DEV.AEO_RUN20_BATCH4');
-- SELECT SYSTEM$GET_SERVICE_STATUS('DEVREL.CNANTASENAMAT_DEV.AEO_RUN20_BATCH5');
-- SELECT SYSTEM$GET_SERVICE_STATUS('DEVREL.CNANTASENAMAT_DEV.AEO_RUN20_BATCH6');
-- SELECT SYSTEM$GET_SERVICE_STATUS('DEVREL.CNANTASENAMAT_DEV.AEO_RUN20_BATCH7');
-- SELECT SYSTEM$GET_SERVICE_STATUS('DEVREL.CNANTASENAMAT_DEV.AEO_RUN20_BATCH8');

-- 5. View logs for a batch
-- SELECT SYSTEM$GET_SERVICE_LOGS('DEVREL.CNANTASENAMAT_DEV.AEO_RUN20_BATCH1', 0, 'aeo-runner');

-- 6. Verify results after all batches complete
-- SELECT COUNT(*) FROM DEVREL.CNANTASENAMAT_DEV.AEO_RESPONSES WHERE RUN_ID = 20;  -- expect 128
-- SELECT COUNT(*) FROM DEVREL.CNANTASENAMAT_DEV.AEO_SCORES    WHERE RUN_ID = 20;  -- expect 512
-- SELECT * FROM DEVREL.CNANTASENAMAT_DEV.V_AEO_LEADERBOARD    WHERE RUN_ID = 20;

-- 7. Cleanup (after run is complete and results verified)
-- ALTER COMPUTE POOL AEO_BENCHMARK_POOL SUSPEND;
