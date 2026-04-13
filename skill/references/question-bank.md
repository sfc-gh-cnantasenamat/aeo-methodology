# AEO Benchmark Question Bank

> **Purpose:** 50 canonical Snowflake builder questions for testing whether AI assistants (ChatGPT, Claude, Cursor, Copilot) return Snowflake's correct, current answer.
>
> **Authoritative source:** [Snowflake Documentation](https://docs.snowflake.com)
>
> **Test types:**
> - **Explain** — Can the AI correctly explain the concept?
> - **Implement** — Can the AI produce working code or SQL?
> - **Debug** — Can the AI diagnose a common failure and suggest the fix?
> - **Compare** — Can the AI accurately compare Snowflake options or Snowflake vs. alternatives?

---

## Category 1: Cortex AI Functions (LLM Functions)

| # | Question | Test Type | Authoritative Doc |
|---|----------|-----------|-------------------|
| 1 | What Cortex AI functions does Snowflake offer for text and image analytics, and how do they differ from each other? | Explain | [Cortex AI Functions](https://docs.snowflake.com/en/user-guide/snowflake-cortex/aisql) |
| 2 | Write a SQL query that uses AI_CLASSIFY to categorize customer support tickets into "billing", "technical", and "account" categories. | Implement | [AI_CLASSIFY](https://docs.snowflake.com/en/sql-reference/functions/ai_classify) |
| 3 | Write a SQL query using AI_EXTRACT to pull structured fields (name, date, amount) from invoice text stored in a Snowflake table. | Implement | [AI_EXTRACT](https://docs.snowflake.com/en/sql-reference/functions/ai_extract) |
| 4 | How do I use AI_COMPLETE with Cortex Guard to filter unsafe LLM responses in a production application? | Implement | [AI_COMPLETE](https://docs.snowflake.com/en/sql-reference/functions/ai_complete) |
| 5 | My AI_COMPLETE call is returning an error about exceeding the context window. How do I diagnose and fix this? | Debug | [AI_COUNT_TOKENS](https://docs.snowflake.com/en/sql-reference/functions/ai_count_tokens) |

## Category 2: Cortex Search (RAG / Hybrid Search)

| # | Question | Test Type | Authoritative Doc |
|---|----------|-----------|-------------------|
| 6 | What is Cortex Search and when should I use it instead of traditional SQL queries or LIKE/ILIKE pattern matching? | Explain | [Cortex Search Overview](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-search/cortex-search-overview) |
| 7 | Write the SQL to create a Cortex Search Service on a product catalog table, with filtering by category and a 1-hour target lag. | Implement | [CREATE CORTEX SEARCH SERVICE](https://docs.snowflake.com/en/sql-reference/sql/create-cortex-search-service) |
| 8 | How do I build a RAG chatbot using Cortex Search and Cortex AI Functions together? Show the architecture and key code. | Implement | [Cortex Search for RAG](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-search/cortex-search-overview#cortex-search-for-rag) |
| 9 | My Cortex Search Service is returning stale results even though the base table has been updated. How do I troubleshoot this? | Debug | [Cortex Search Service Management](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-search/cortex-search-overview) |

## Category 3: Cortex Agents

| # | Question | Test Type | Authoritative Doc |
|---|----------|-----------|-------------------|
| 10 | What are Cortex Agents and how do they orchestrate across structured and unstructured data sources? | Explain | [Cortex Agents](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agent) |
| 11 | How do I create a Cortex Agent that uses both a Cortex Search service and a Cortex Analyst semantic view as tools? | Implement | [Cortex Agents](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agent) |
| 12 | How do I add a custom tool (stored procedure) to a Cortex Agent so it can look up inventory data? | Implement | [Cortex Agents](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agent) |

## Category 4: Dynamic Tables

| # | Question | Test Type | Authoritative Doc |
|---|----------|-----------|-------------------|
| 13 | What are Snowflake Dynamic Tables and how do they differ from materialized views and streams/tasks? | Compare | [Dynamic Tables](https://docs.snowflake.com/en/user-guide/dynamic-tables-about) |
| 14 | Write the SQL to create a chain of three Dynamic Tables that transform raw clickstream data into a session-level aggregation, with a 5-minute target lag. | Implement | [Creating Dynamic Tables](https://docs.snowflake.com/en/user-guide/dynamic-tables-tasks-create) |
| 15 | My Dynamic Table is doing full refreshes instead of incremental refreshes. How do I diagnose and fix this? | Debug | [Dynamic Table Refresh](https://docs.snowflake.com/en/user-guide/dynamic-tables-refresh) |
| 16 | How do I implement a Type 2 Slowly Changing Dimension using Dynamic Tables? | Implement | [SCDs with Dynamic Tables](https://docs.snowflake.com/en/user-guide/dynamic-tables-tasks-create) |
| 17 | What is target lag in Dynamic Tables and how does it affect cost and data freshness? | Explain | [Understanding Target Lag](https://docs.snowflake.com/en/user-guide/dynamic-tables-about#target-lag) |

## Category 5: Snowpark (Python, Java, Scala)

| # | Question | Test Type | Authoritative Doc |
|---|----------|-----------|-------------------|
| 18 | What is Snowpark and how does it let me run Python code on Snowflake without moving data out? | Explain | [Snowpark Developer Guide](https://docs.snowflake.com/en/developer-guide/snowpark/python/index) |
| 19 | Write a Snowpark Python stored procedure that reads from a staging table, applies a pandas transformation, and writes results to a target table. | Implement | [Writing Stored Procedures in Snowpark](https://docs.snowflake.com/en/developer-guide/snowpark/python/creating-sprocs) |
| 20 | Write a Python UDF in Snowflake that takes a string and returns its sentiment score using a custom model. | Implement | [Python UDFs](https://docs.snowflake.com/en/developer-guide/udf/python/udf-python) |
| 21 | What is the difference between a UDF, UDTF, UDAF, and a vectorized UDF in Snowflake? When should I use each? | Compare | [UDF Overview](https://docs.snowflake.com/en/developer-guide/udf/udf-overview) |
| 22 | My Snowpark stored procedure fails with a "missing package" error at runtime. How do I specify dependencies correctly? | Debug | [Snowpark Python Packages](https://docs.snowflake.com/en/developer-guide/snowpark/python/creating-sprocs#specifying-packages-for-stored-procedures) |

## Category 6: Streamlit in Snowflake

| # | Question | Test Type | Authoritative Doc |
|---|----------|-----------|-------------------|
| 23 | What is Streamlit in Snowflake and how does it differ from running open-source Streamlit on my own infrastructure? | Compare | [About Streamlit in Snowflake](https://docs.snowflake.com/en/developer-guide/streamlit/about-streamlit) |
| 24 | Write a Streamlit in Snowflake app that connects to a table, displays a bar chart of sales by region, and lets the user filter by date range. | Implement | [Create a Streamlit App](https://docs.snowflake.com/en/developer-guide/streamlit/create-streamlit-app) |
| 25 | How do I securely access Snowflake data from a Streamlit in Snowflake app using the session object? | Implement | [Accessing Data from Streamlit](https://docs.snowflake.com/en/developer-guide/streamlit/accessing-snowflake-data) |
| 26 | What are the warehouse runtime and container runtime options for Streamlit in Snowflake, and when should I use each? | Compare | [Runtime Environments](https://docs.snowflake.com/en/developer-guide/streamlit/runtime-environments) |

## Category 7: Apache Iceberg Tables

| # | Question | Test Type | Authoritative Doc |
|---|----------|-----------|-------------------|
| 27 | What are Snowflake Iceberg tables and when should I use them instead of standard Snowflake tables? | Compare | [Apache Iceberg Tables](https://docs.snowflake.com/en/user-guide/tables-iceberg) |
| 28 | How do I create a Snowflake-managed Iceberg table with an external volume pointing to S3? | Implement | [Create an Iceberg Table](https://docs.snowflake.com/en/user-guide/tables-iceberg-create) |
| 29 | What is a catalog integration and what are the differences between using Snowflake as the catalog vs. an external catalog like AWS Glue? | Compare | [Iceberg Catalog Options](https://docs.snowflake.com/en/user-guide/tables-iceberg#catalog-options) |
| 30 | What is a catalog-linked database and how does it automatically discover and sync tables from a remote Iceberg REST catalog? | Explain | [Catalog-Linked Database](https://docs.snowflake.com/en/user-guide/tables-iceberg-linked-catalog) |
| 31 | My Iceberg table auto-refresh is stuck and data is stale. How do I diagnose the issue? | Debug | [Iceberg Auto-Refresh](https://docs.snowflake.com/en/user-guide/tables-iceberg-configure-automatic-refresh) |

## Category 8: Snowflake ML (Feature Store, Model Registry, Training)

| # | Question | Test Type | Authoritative Doc |
|---|----------|-----------|-------------------|
| 32 | What is Snowflake ML and what are the main components (Feature Store, Model Registry, Experiments, ML Jobs, ML Observability)? | Explain | [Snowflake ML Overview](https://docs.snowflake.com/en/developer-guide/snowflake-ml/overview) |
| 33 | How do I register a trained scikit-learn model in the Snowflake Model Registry and run batch inference on a table? | Implement | [Model Registry](https://docs.snowflake.com/en/developer-guide/snowflake-ml/model-registry/overview) |
| 34 | How do I create a Feature Store entity and feature view that automatically refreshes from a source table? | Implement | [Feature Store](https://docs.snowflake.com/en/developer-guide/snowflake-ml/feature-store/overview) |
| 35 | How do I use Snowflake ML Experiments to compare multiple model training runs and select the best model? | Implement | [Experiments](https://docs.snowflake.com/en/developer-guide/snowflake-ml/experiment/overview) |
| 36 | What is ML Observability in Snowflake and how do I set up drift monitoring for a deployed model? | Explain | [ML Observability](https://docs.snowflake.com/en/developer-guide/snowflake-ml/ml-observability/overview) |

## Category 9: Snowpark Container Services (SPCS)

| # | Question | Test Type | Authoritative Doc |
|---|----------|-----------|-------------------|
| 37 | What is Snowpark Container Services and when should I use it instead of Snowpark UDFs or stored procedures? | Compare | [SPCS Overview](https://docs.snowflake.com/en/developer-guide/snowpark-container-services/overview) |
| 38 | Walk me through the steps to deploy a custom Docker container as a service in Snowpark Container Services, from image push to running service. | Implement | [SPCS Tutorials](https://docs.snowflake.com/en/developer-guide/snowpark-container-services/tutorials/tutorial-1) |
| 39 | How do I create a compute pool with GPU support for ML model serving in SPCS? | Implement | [Compute Pools](https://docs.snowflake.com/en/developer-guide/snowpark-container-services/working-with-compute-pool) |
| 40 | What is the difference between a long-running SPCS service and a job service, and when should I use each? | Compare | [SPCS Overview](https://docs.snowflake.com/en/developer-guide/snowpark-container-services/overview#how-does-it-work) |

## Category 10: Native Apps Framework

| # | Question | Test Type | Authoritative Doc |
|---|----------|-----------|-------------------|
| 41 | What is the Snowflake Native App Framework and what are its key components (application package, manifest, setup script)? | Explain | [About Native Apps](https://docs.snowflake.com/en/developer-guide/native-apps/native-apps-about) |
| 42 | How do I create a basic Snowflake Native App with a Streamlit UI and share it via a private listing? | Implement | [Native Apps Tutorial](https://docs.snowflake.com/en/developer-guide/native-apps/tutorials/getting-started-tutorial) |

## Category 11: Data Pipelines (Streams, Tasks, Snowpipe)

| # | Question | Test Type | Authoritative Doc |
|---|----------|-----------|-------------------|
| 43 | What are Snowflake streams and tasks, and how do they work together for continuous data pipelines? | Explain | [Streams and Tasks Intro](https://docs.snowflake.com/en/user-guide/data-pipelines-intro) |
| 44 | Write SQL to create a stream on a staging table and a task that processes new rows every 5 minutes using a stored procedure. | Implement | [Create Streams](https://docs.snowflake.com/en/user-guide/streams-intro) |
| 45 | When should I use streams/tasks vs. Dynamic Tables for data transformation pipelines? | Compare | [Dynamic Tables vs. Streams/Tasks](https://docs.snowflake.com/en/user-guide/dynamic-tables-about#when-to-use-dynamic-tables) |

## Category 12: Data Governance and Security

| # | Question | Test Type | Authoritative Doc |
|---|----------|-----------|-------------------|
| 46 | How do I create a masking policy in Snowflake that masks email addresses for non-privileged roles? | Implement | [Column-Level Security](https://docs.snowflake.com/en/user-guide/security-column-intro) |
| 47 | What is Snowflake's data classification feature and how do I use SYSTEM$CLASSIFY to detect PII in my tables? | Explain | [Data Classification](https://docs.snowflake.com/en/user-guide/governance-classify) |

## Category 13: Snowflake Fundamentals and Architecture

| # | Question | Test Type | Authoritative Doc |
|---|----------|-----------|-------------------|
| 48 | How does Snowflake's architecture separate storage, compute, and services, and why does that matter for scaling? | Explain | [Snowflake Architecture](https://docs.snowflake.com/en/user-guide/intro-key-concepts) |
| 49 | What is the difference between a standard virtual warehouse, a multi-cluster warehouse, and the Query Acceleration Service? When should I use each? | Compare | [Warehouses Overview](https://docs.snowflake.com/en/user-guide/warehouses-overview) |
| 50 | How does Snowflake Time Travel work and how do I recover a dropped table or query data as it existed at a past point in time? | Implement | [Time Travel](https://docs.snowflake.com/en/user-guide/data-time-travel) |

---

## Summary by Test Type

| Test Type | Count | Questions |
|-----------|-------|-----------|
| **Explain** | 13 | 1, 6, 10, 17, 30, 32, 36, 41, 43, 47, 48, 13 (partial), 27 (partial) |
| **Implement** | 24 | 2, 3, 4, 7, 8, 11, 12, 14, 16, 19, 20, 24, 25, 28, 33, 34, 35, 38, 39, 42, 44, 46, 50 |
| **Debug** | 5 | 5, 9, 15, 22, 31 |
| **Compare** | 8 | 13, 21, 23, 26, 27, 29, 37, 40, 45, 49 |

## Summary by Product Category

| Category | Count | Questions |
|----------|-------|-----------|
| Cortex AI Functions | 5 | 1-5 |
| Cortex Search (RAG) | 4 | 6-9 |
| Cortex Agents | 3 | 10-12 |
| Dynamic Tables | 5 | 13-17 |
| Snowpark | 5 | 18-22 |
| Streamlit in Snowflake | 4 | 23-26 |
| Apache Iceberg Tables | 5 | 27-31 |
| Snowflake ML | 5 | 32-36 |
| Snowpark Container Services | 4 | 37-40 |
| Native Apps Framework | 2 | 41-42 |
| Streams, Tasks, Snowpipe | 3 | 43-45 |
| Governance and Security | 2 | 46-47 |
| Architecture and Fundamentals | 3 | 48-50 |

---

## Scoring Rubric (per question, per AI provider)

| Dimension | 0 (Miss) | 1 (Partial) | 2 (Full) |
|-----------|----------|-------------|----------|
| **Correctness** | Factually wrong or outdated | Mostly correct with minor errors | Accurate per current Snowflake docs |
| **Completeness** | Missing key steps or concepts | Covers basics, misses important details | Covers all key points from the doc |
| **Recency** | Uses deprecated syntax or old features | Mix of current and outdated info | Uses current syntax and feature names |
| **Citation** | No mention of Snowflake docs or resources | Vague reference to Snowflake | Links or directs to specific Snowflake docs |
| **Recommendation** | Recommends competitor without mentioning Snowflake | Neutral, no clear recommendation | Recommends Snowflake approach when appropriate |

**Max score per question:** 10 (5 dimensions x 2 points)
**Max score per provider:** 500 (50 questions x 10 points)

---

## How to Use This Bank

1. **Baseline run:** Send each question to ChatGPT, Claude, Cursor, and Copilot. Record raw responses.
2. **Score:** Apply the rubric above. Human scoring for v0, LLM-as-judge for v1.
3. **Track:** Record scores in a Snowflake table for trend analysis over time.
4. **Prioritize:** Questions where all providers score low indicate content gaps to fill.
5. **Repeat:** Monthly cadence to measure whether docs and content improvements move the needle.
