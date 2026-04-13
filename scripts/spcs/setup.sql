-- AEO Benchmark SPCS PoC: Setup SQL
-- Run these statements in order to set up the SPCS infrastructure.

-- 1. Database and schema
CREATE DATABASE IF NOT EXISTS AEO_DB;
USE DATABASE AEO_DB;
CREATE SCHEMA IF NOT EXISTS PUBLIC;

-- 2. Image repository
CREATE IMAGE REPOSITORY IF NOT EXISTS AEO_DB.PUBLIC.AEO_REPO;

-- 3. Internal stage for data exchange
CREATE STAGE IF NOT EXISTS AEO_DB.PUBLIC.AEO_STAGE
  DIRECTORY = (ENABLE = TRUE);

-- 4. Compute pool (CPU_X64_XS is the smallest, cheapest option)
CREATE COMPUTE POOL IF NOT EXISTS AEO_BENCHMARK_POOL
  MIN_NODES = 1
  MAX_NODES = 1
  INSTANCE_FAMILY = CPU_X64_XS
  AUTO_SUSPEND_SECS = 300
  AUTO_RESUME = TRUE;

-- 5. Check repo URL (needed for docker push)
SHOW IMAGE REPOSITORIES LIKE 'AEO_REPO' IN SCHEMA AEO_DB.PUBLIC;

-- 6. After building and pushing the Docker image, upload data files:
-- PUT file:///path/to/q1_question.json @AEO_DB.PUBLIC.AEO_STAGE/questions/ AUTO_COMPRESS=FALSE OVERWRITE=TRUE;
-- PUT file:///path/to/q1_canonical.json @AEO_DB.PUBLIC.AEO_STAGE/canonical/ AUTO_COMPRESS=FALSE OVERWRITE=TRUE;
-- PUT file:///path/to/scoring_template.json @AEO_DB.PUBLIC.AEO_STAGE/ AUTO_COMPRESS=FALSE OVERWRITE=TRUE;
-- PUT file:///path/to/aeo-job-spec.yaml @AEO_DB.PUBLIC.AEO_STAGE/specs/ AUTO_COMPRESS=FALSE OVERWRITE=TRUE;

-- 7. Run PoC job (full pipeline mode)
-- EXECUTE JOB SERVICE
--   IN COMPUTE POOL AEO_BENCHMARK_POOL
--   FROM @AEO_DB.PUBLIC.AEO_STAGE/specs
--   SPEC = 'aeo-job-spec.yaml'
--   NAME = AEO_DB.PUBLIC.AEO_POC_FULL
--   QUERY_WAREHOUSE = COMPUTE_WH;

-- 8. Check job status
-- SELECT SYSTEM$GET_SERVICE_STATUS('AEO_DB.PUBLIC.AEO_POC_FULL');

-- 9. Check logs
-- SELECT SYSTEM$GET_SERVICE_LOGS('AEO_DB.PUBLIC.AEO_POC_FULL', 0, 'aeo-runner');

-- 10. Cleanup
-- ALTER COMPUTE POOL AEO_BENCHMARK_POOL SUSPEND;
-- DROP SERVICE IF EXISTS AEO_DB.PUBLIC.AEO_POC_FULL;
