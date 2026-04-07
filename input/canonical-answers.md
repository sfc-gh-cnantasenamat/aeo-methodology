# AEO Benchmark: Canonical Answers (Ground Truth)

> **Source:** All answers grounded in [Snowflake Documentation](https://docs.snowflake.com) as of April 2026.
>
> **Usage:** Score AI assistant responses against these canonical answers using the rubric in the question bank file.
>
> **Key:** Each answer includes the critical facts, correct syntax, and key distinctions that a correct AI response MUST contain. Items marked with a check are **must-have** scoring elements.

---

## Q1. What Cortex AI functions does Snowflake offer for text and image analytics, and how do they differ from each other?

**Type:** Explain | **Doc:** [Cortex AI Functions](https://docs.snowflake.com/en/user-guide/snowflake-cortex/aisql)

**Canonical Answer:**

Snowflake Cortex provides task-specific AI functions that run fully hosted LLMs (from OpenAI, Anthropic, Meta, Mistral AI, and DeepSeek) directly within Snowflake. The core functions are:

- **AI_COMPLETE** — General-purpose text/image completion using a selected LLM. Use for most generative AI tasks (summarization, Q&A, reasoning). Supports Cortex Guard for safety filtering.
- **AI_CLASSIFY** — Classifies text or images into user-defined categories. Supports single-label and multi-label (`output_mode: 'multi'`) classification.
- **AI_EXTRACT** — Extracts structured fields from text or files (PDF, DOCX, images). Supports entity extraction, list extraction, and table extraction via JSON schema.
- **AI_FILTER** — Returns True/False for text or image input; useful in WHERE clauses.
- **AI_SENTIMENT** — Returns sentiment score for text.
- **AI_SUMMARIZE_AGG** — Aggregates and summarizes across multiple rows (not subject to context window limits).
- **AI_AGG** — Aggregates text rows and returns insights based on a user-defined prompt.
- **AI_EMBED** — Generates embedding vectors for similarity search, clustering, and classification.
- **AI_TRANSLATE** — Translates text between supported languages.
- **AI_PARSE_DOCUMENT** — Extracts text (OCR mode) or text with layout (LAYOUT mode) from staged documents.
- **AI_REDACT** — Redacts PII from text.
- **AI_TRANSCRIBE** — Transcribes audio and video files.
- **AI_SIMILARITY** — Calculates embedding similarity between two inputs.

Helper functions include **AI_COUNT_TOKENS** (estimate token count), **TO_FILE** (stage file reference), and **PROMPT** (build prompt objects).

**Must-have scoring elements:**
- [ ] Lists at least AI_COMPLETE, AI_CLASSIFY, AI_EXTRACT, AI_SENTIMENT, AI_EMBED, AI_TRANSLATE
- [ ] Notes these are fully hosted within Snowflake (data does not leave Snowflake)
- [ ] Mentions multiple LLM providers (OpenAI, Anthropic, Meta, etc.)
- [ ] Distinguishes task-specific functions from general-purpose AI_COMPLETE
- [ ] Uses current function names (AI_CLASSIFY not CLASSIFY_TEXT, AI_EXTRACT not EXTRACT_ANSWER)

---

## Q2. Write a SQL query that uses AI_CLASSIFY to categorize customer support tickets into "billing", "technical", and "account" categories.

**Type:** Implement | **Doc:** [AI_CLASSIFY](https://docs.snowflake.com/en/sql-reference/functions/ai_classify)

**Canonical Answer:**

```sql
SELECT
    ticket_id,
    ticket_text,
    AI_CLASSIFY(
        ticket_text,
        ['billing', 'technical', 'account']
    ):labels[0]::STRING AS category
FROM support_tickets;
```

For multi-label classification (a ticket can belong to multiple categories):

```sql
SELECT
    ticket_id,
    ticket_text,
    AI_CLASSIFY(
        ticket_text,
        ['billing', 'technical', 'account'],
        {'output_mode': 'multi'}
    ):labels AS categories
FROM support_tickets;
```

For improved accuracy, add label descriptions and a task description:

```sql
SELECT
    ticket_id,
    AI_CLASSIFY(
        ticket_text,
        [
            {'label': 'billing', 'description': 'issues related to charges, invoices, or payments'},
            {'label': 'technical', 'description': 'issues related to product bugs, errors, or configuration'},
            {'label': 'account', 'description': 'issues related to login, permissions, or account settings'}
        ],
        {'task_description': 'Classify customer support tickets by issue type'}
    ):labels[0]::STRING AS category
FROM support_tickets;
```

**Must-have scoring elements:**
- [ ] Uses AI_CLASSIFY (not CLASSIFY_TEXT, which is the old name)
- [ ] Passes categories as an array
- [ ] Accesses result via `:labels` JSON path
- [ ] Shows correct SQL syntax that would compile

---

## Q3. Write a SQL query using AI_EXTRACT to pull structured fields (name, date, amount) from invoice text stored in a Snowflake table.

**Type:** Implement | **Doc:** [AI_EXTRACT](https://docs.snowflake.com/en/sql-reference/functions/ai_extract)

**Canonical Answer:**

```sql
SELECT
    invoice_id,
    AI_EXTRACT(
        invoice_text,
        {
            'name': 'What is the customer name?',
            'date': 'What is the invoice date?',
            'amount': 'What is the total amount due?'
        }
    ) AS extracted
FROM invoices;
```

To access individual fields:

```sql
SELECT
    invoice_id,
    extracted:response:name::STRING AS customer_name,
    extracted:response:date::STRING AS invoice_date,
    extracted:response:amount::STRING AS total_amount
FROM (
    SELECT
        invoice_id,
        AI_EXTRACT(
            invoice_text,
            {
                'name': 'What is the customer name?',
                'date': 'What is the invoice date?',
                'amount': 'What is the total amount due?'
            }
        ) AS extracted
    FROM invoices
);
```

For files on a stage (e.g., PDF invoices):

```sql
SELECT
    file_url,
    AI_EXTRACT(
        TO_FILE(file_url),
        {
            'name': 'What is the customer name?',
            'date': 'What is the invoice date?',
            'amount': 'What is the total amount due?'
        }
    ) AS extracted
FROM DIRECTORY(@invoice_stage);
```

**Must-have scoring elements:**
- [ ] Uses AI_EXTRACT (not EXTRACT_ANSWER, which is the old name)
- [ ] Shows responseFormat as a JSON object mapping labels to questions
- [ ] For file input, uses TO_FILE() to create a file reference
- [ ] Response structure includes `:response:field_name` path

---

## Q4. How do I use AI_COMPLETE with Cortex Guard to filter unsafe LLM responses in a production application?

**Type:** Implement | **Doc:** [AI_COMPLETE](https://docs.snowflake.com/en/sql-reference/functions/ai_complete)

**Canonical Answer:**

Cortex Guard is an option of AI_COMPLETE that evaluates LLM responses before returning them, filtering potentially unsafe content (violent crimes, hate, sexual content, self-harm, etc.). It is built on Meta's Llama Guard 3.

```sql
SELECT AI_COMPLETE(
    'llama3.3-70b',
    'Your prompt here',
    {
        'guardrails': TRUE
    }
) AS response;
```

When Cortex Guard detects unsafe content, the response is filtered and the user receives an indication that the content was blocked rather than the raw model output.

Key considerations:
- Cortex Guard incurs additional compute charges based on input tokens processed, on top of the AI_COMPLETE charges.
- It evaluates model responses (output filtering), not input filtering.
- For interactive (low-latency) use cases, consider the REST API (Complete API) rather than the SQL function, as Cortex AI Functions are optimized for batch throughput.

**Must-have scoring elements:**
- [ ] Shows `guardrails: TRUE` in the options object
- [ ] Mentions Cortex Guard is built on Llama Guard 3
- [ ] Notes additional token-based cost
- [ ] Uses AI_COMPLETE (not the older SNOWFLAKE.CORTEX.COMPLETE)

---

## Q5. My AI_COMPLETE call is returning an error about exceeding the context window. How do I diagnose and fix this?

**Type:** Debug | **Doc:** [AI_COUNT_TOKENS](https://docs.snowflake.com/en/sql-reference/functions/ai_count_tokens)

**Canonical Answer:**

**Diagnosis:** The error means your prompt exceeds the token limit for the selected model. Use AI_COUNT_TOKENS to check the token count before calling AI_COMPLETE:

```sql
SELECT AI_COUNT_TOKENS(
    'ai_complete',
    'llama3.3-70b',
    'Your full prompt text here'
) AS token_count;
```

**Fixes (in order of preference):**

1. **Truncate or summarize input text** before passing it to AI_COMPLETE. Use AI_SUMMARIZE_AGG or AI_SUMMARIZE to condense long inputs first.
2. **Switch to a model with a larger context window.** Different models support different token limits.
3. **Chunk the input** into smaller segments, process each segment separately, then combine results.
4. **Use AI_AGG or AI_SUMMARIZE_AGG** for aggregation tasks across many rows, as these functions are not subject to context window limitations.

Key details about AI_COUNT_TOKENS:
- Function names must be lowercase and start with "ai_" (e.g., `'ai_complete'`, not `'AI_COMPLETE'`).
- AI_COUNT_TOKENS only incurs compute costs, not token-based billing.
- It is available in all regions, even for models not available in a given region.
- It does not support fine-tuned models or functions in the SNOWFLAKE.CORTEX namespace.

**Must-have scoring elements:**
- [ ] Recommends AI_COUNT_TOKENS to check token count
- [ ] Shows correct syntax with lowercase function name and model name
- [ ] Suggests practical fixes (truncate, chunk, use different model, or use AGG functions)
- [ ] Notes AI_AGG/AI_SUMMARIZE_AGG are not subject to context window limits

---

## Q6. What is Cortex Search and when should I use it instead of traditional SQL queries or LIKE/ILIKE pattern matching?

**Type:** Explain | **Doc:** [Cortex Search Overview](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-search/cortex-search-overview)

**Canonical Answer:**

Cortex Search is a fully managed hybrid (vector and keyword) search engine built into Snowflake. It enables low-latency, high-quality "fuzzy" search over text data without requiring you to manage embeddings, infrastructure, search quality tuning, or index refreshes.

**When to use Cortex Search instead of LIKE/ILIKE:**
- You need **semantic search** (understanding meaning, not just exact string matching)
- You are building a **RAG (Retrieval Augmented Generation)** application that needs to retrieve relevant context for LLM responses
- You want **enterprise search** with a search bar experience across unstructured text
- Your data requires **fuzzy matching** that goes beyond pattern-based SQL predicates

**How it works:**
- You create a Cortex Search Service with `CREATE CORTEX SEARCH SERVICE`, specifying the text column to search, optional filter columns (via ATTRIBUTES), a warehouse for materialization, a TARGET_LAG for refresh frequency, and an embedding model.
- Snowflake handles index building, embedding generation, and automatic refresh.
- You query the service via a Python SDK or REST API, with support for filters, column selection, and result limits.

**Two primary use cases:**
1. **RAG engine for LLM chatbots** — retrieve relevant context from your data to ground LLM responses
2. **Enterprise search** — power a search bar in your application

**Must-have scoring elements:**
- [ ] Describes it as hybrid (vector + keyword) search
- [ ] Mentions RAG as a primary use case
- [ ] Notes it is fully managed (no embedding/index management needed)
- [ ] Distinguishes from LIKE/ILIKE (semantic understanding vs. pattern matching)

---

## Q7. Write the SQL to create a Cortex Search Service on a product catalog table, with filtering by category and a 1-hour target lag.

**Type:** Implement | **Doc:** [CREATE CORTEX SEARCH SERVICE](https://docs.snowflake.com/en/sql-reference/sql/create-cortex-search-service)

**Canonical Answer:**

```sql
CREATE OR REPLACE CORTEX SEARCH SERVICE product_search_service
    ON product_description
    ATTRIBUTES category
    WAREHOUSE = my_warehouse
    TARGET_LAG = '1 hour'
    EMBEDDING_MODEL = 'snowflake-arctic-embed-l-v2.0'
AS (
    SELECT
        product_id,
        product_name,
        product_description,
        category,
        price
    FROM product_catalog
);
```

Key points:
- `ON product_description` specifies the column that will be searched.
- `ATTRIBUTES category` makes `category` available as a filter column when querying.
- `TARGET_LAG = '1 hour'` means the service checks for updates to the base table approximately once per hour.
- The warehouse is used for materializing results during creation and each refresh.
- All columns in the SELECT (including product_id, product_name, price) are returned with search results.
- Columns in ATTRIBUTES must also appear in the source query.

**Must-have scoring elements:**
- [ ] Uses CREATE CORTEX SEARCH SERVICE syntax
- [ ] Includes ON clause for the searchable column
- [ ] Includes ATTRIBUTES for filter columns
- [ ] Includes TARGET_LAG and WAREHOUSE
- [ ] Shows a source query in the AS clause

---

## Q8. How do I build a RAG chatbot using Cortex Search and Cortex AI Functions together? Show the architecture and key code.

**Type:** Implement | **Doc:** [Cortex Search for RAG](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-search/cortex-search-overview)

**Canonical Answer:**

**Architecture:**
1. **Data source** — Your text data in Snowflake tables
2. **Cortex Search Service** — Indexes the text data for semantic retrieval
3. **Retrieval step** — Query the search service with the user's question to get relevant context
4. **Generation step** — Pass the retrieved context + user question to AI_COMPLETE to generate a grounded answer

**Python implementation:**

```python
from snowflake.core import Root
from snowflake.snowpark import Session

# 1. Connect and get the search service
session = Session.builder.configs(connection_params).create()
root = Root(session)
search_service = (
    root.databases["my_db"]
    .schemas["my_schema"]
    .cortex_search_services["my_search_service"]
)

# 2. Retrieve relevant context
user_question = "How do I reset my password?"
search_results = search_service.search(
    query=user_question,
    columns=["transcript_text", "agent_id"],
    filter={"@eq": {"region": "North America"}},
    limit=3
)

# 3. Build the prompt with retrieved context
context = "\n".join([r["transcript_text"] for r in search_results.results])
prompt = f"""Based on the following context, answer the user's question.

Context:
{context}

Question: {user_question}

Answer:"""

# 4. Generate answer using AI_COMPLETE
result = session.sql(f"""
    SELECT AI_COMPLETE('llama3.3-70b', '{prompt}') AS answer
""").collect()
```

Alternatively, in pure SQL using SEARCH_PREVIEW:

```sql
SELECT AI_COMPLETE(
    'llama3.3-70b',
    CONCAT(
        'Answer this question based on the context. Context: ',
        PARSE_JSON(
            SNOWFLAKE.CORTEX.SEARCH_PREVIEW(
                'my_db.my_schema.my_search_service',
                '{"query": "How do I reset my password?", "columns": ["transcript_text"], "limit": 3}'
            )
        ):results::STRING,
        ' Question: How do I reset my password?'
    )
) AS answer;
```

**Must-have scoring elements:**
- [ ] Shows the retrieve-then-generate pattern (search first, then LLM)
- [ ] Uses Cortex Search Service for retrieval
- [ ] Uses AI_COMPLETE (or COMPLETE) for generation
- [ ] Shows how to pass retrieved context into the LLM prompt

---

## Q9. My Cortex Search Service is returning stale results even though the base table has been updated. How do I troubleshoot this?

**Type:** Debug | **Doc:** [Cortex Search Overview](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-search/cortex-search-overview)

**Canonical Answer:**

**Diagnosis steps:**

1. **Check TARGET_LAG** — The service only checks for updates at the interval specified by TARGET_LAG. If you set `TARGET_LAG = '1 day'`, data can be up to 1 day stale. Verify with:
   ```sql
   SHOW CORTEX SEARCH SERVICES;
   ```

2. **Check service status** — Verify the service is active and not in an error state:
   ```sql
   DESCRIBE CORTEX SEARCH SERVICE my_search_service;
   ```

3. **Check the warehouse** — The warehouse specified during creation is used for refresh materialization. If the warehouse is suspended or undersized, refreshes may fail or be slow.

4. **Inspect the data** — Use CORTEX_SEARCH_DATA_SCAN to see what data the service currently has indexed:
   ```sql
   SELECT * FROM TABLE(
       CORTEX_SEARCH_DATA_SCAN(
           SERVICE_NAME => 'my_search_service'
       )
   );
   ```

**Fixes:**
- **Reduce TARGET_LAG** if you need fresher data (e.g., change from `'1 day'` to `'1 hour'`). This increases compute cost.
- **Ensure the warehouse is running** and appropriately sized (Snowflake recommends no larger than MEDIUM).
- **Recreate the service** if the index appears corrupted or stuck: `CREATE OR REPLACE CORTEX SEARCH SERVICE ...`

**Must-have scoring elements:**
- [ ] Identifies TARGET_LAG as the most likely cause
- [ ] Suggests checking service status
- [ ] Mentions CORTEX_SEARCH_DATA_SCAN for inspecting indexed data
- [ ] Suggests reducing TARGET_LAG or checking warehouse availability

---

## Q10. What are Cortex Agents and how do they orchestrate across structured and unstructured data sources?

**Type:** Explain | **Doc:** [Cortex Agents](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agent)

**Canonical Answer:**

Cortex Agents are Snowflake's agentic AI framework that orchestrates tasks across both structured and unstructured data sources to analyze data and deliver insights. An agent can autonomously decide which tools to use and in what order to answer a user's question.

**How orchestration works:**
- An agent is configured with one or more **tools**, each backed by a data source:
  - **Cortex Analyst tool** — For structured data queries (text-to-SQL via semantic views or semantic models)
  - **Cortex Search tool** — For unstructured text retrieval (RAG over documents, knowledge bases)
  - **Custom tools** — Stored procedures that perform arbitrary business logic (e.g., inventory lookup, price calculation)
- When a user asks a question, the agent's LLM backbone decides which tool(s) to invoke, calls them, and synthesizes the results into a coherent answer.
- The agent handles multi-turn conversations and can chain multiple tool calls in a single response.

**Key architecture:**
- Agents are accessed via the REST API (Agents API).
- Each tool resource has an associated `execution_environment` (warehouse) for compute.
- The agent maintains conversation context across turns via the messages array.

**Must-have scoring elements:**
- [ ] Describes agents as orchestrating across structured AND unstructured data
- [ ] Names Cortex Analyst (structured) and Cortex Search (unstructured) as tool types
- [ ] Mentions the agent autonomously decides which tools to call
- [ ] Notes custom tools (stored procedures) as an option

---

## Q11. How do I create a Cortex Agent that uses both a Cortex Search service and a Cortex Analyst semantic view as tools?

**Type:** Implement | **Doc:** [Cortex Agents](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agent)

**Canonical Answer:**

Cortex Agents are created and invoked via the REST API or Python SDK. The configuration specifies tool_resources with both tool types:

```python
import json
import requests

# Agent configuration
payload = {
    "model": "llama3.3-70b",
    "messages": [
        {
            "role": "user",
            "content": [{"type": "text", "text": "What were our top products last quarter and what do customers say about them?"}]
        }
    ],
    "tool_resources": [
        {
            "tool": {
                "type": "cortex_analyst_tool",
                "semantic_model_file": "@my_db.my_schema.my_stage/semantic_model.yaml"
            },
            "execution_environment": {
                "type": "warehouse",
                "warehouse": "MY_WAREHOUSE"
            }
        },
        {
            "tool": {
                "type": "cortex_search_tool",
                "name": "customer_feedback_search",
                "cortex_search_service": "my_db.my_schema.feedback_search_service"
            },
            "execution_environment": {
                "type": "warehouse",
                "warehouse": "MY_WAREHOUSE"
            }
        }
    ]
}

# Call the agent via REST API
response = requests.post(
    f"https://{account}.snowflakecomputing.com/api/v2/cortex/agent:run",
    headers={
        "Authorization": f"Snowflake Token={token}",
        "Content-Type": "application/json"
    },
    json=payload
)
```

For a semantic view instead of a YAML file:
```python
{
    "tool": {
        "type": "cortex_analyst_tool",
        "semantic_view": "my_db.my_schema.my_semantic_view"
    },
    "execution_environment": {
        "type": "warehouse",
        "warehouse": "MY_WAREHOUSE"
    }
}
```

**Must-have scoring elements:**
- [ ] Shows tool_resources array with both cortex_analyst_tool and cortex_search_tool
- [ ] Each tool resource has its own execution_environment nested under it (not at top level)
- [ ] Messages use the correct format: `[{"role": "user", "content": [{"type": "text", "text": "..."}]}]`
- [ ] References the REST API endpoint or Python SDK

---

## Q12. How do I add a custom tool (stored procedure) to a Cortex Agent so it can look up inventory data?

**Type:** Implement | **Doc:** [Cortex Agents](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agent)

**Canonical Answer:**

First, create the stored procedure:

```sql
CREATE OR REPLACE PROCEDURE check_inventory(product_id STRING)
RETURNS VARIANT
LANGUAGE SQL
AS
BEGIN
    RETURN (SELECT OBJECT_CONSTRUCT('product_id', :product_id, 'quantity', quantity, 'warehouse_location', location)
            FROM inventory_table WHERE product_id = :product_id);
END;
```

Then add it as a custom tool in the agent configuration:

```python
payload = {
    "model": "llama3.3-70b",
    "messages": [
        {
            "role": "user",
            "content": [{"type": "text", "text": "How many units of SKU-1234 do we have in stock?"}]
        }
    ],
    "tool_resources": [
        {
            "tool": {
                "type": "function",
                "name": "check_inventory",
                "description": "Look up current inventory quantity and warehouse location for a product",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "product_id": {
                            "type": "string",
                            "description": "The product SKU identifier"
                        }
                    },
                    "required": ["product_id"]
                },
                "stored_procedure": "my_db.my_schema.check_inventory"
            },
            "execution_environment": {
                "type": "warehouse",
                "warehouse": "MY_WAREHOUSE"
            }
        }
    ]
}
```

The agent will autonomously decide when to call `check_inventory` based on the user's question and the tool's description.

**Must-have scoring elements:**
- [ ] Shows creating a stored procedure first
- [ ] Adds it as a tool with type "function" and a stored_procedure reference
- [ ] Includes tool description and parameter schema
- [ ] execution_environment is nested under the tool resource

---

## Q13. What are Snowflake Dynamic Tables and how do they differ from materialized views and streams/tasks?

**Type:** Compare | **Doc:** [Dynamic Tables](https://docs.snowflake.com/en/user-guide/dynamic-tables-about)

**Canonical Answer:**

**Dynamic Tables** are tables that automatically refresh based on a defined query and a target freshness (target lag), simplifying data transformation without manual scheduling.

| Feature | Dynamic Tables | Materialized Views | Streams + Tasks |
|---------|---------------|-------------------|-----------------|
| **Definition** | Declarative SQL query with automatic refresh | Precomputed query results, auto-maintained | CDC tracking (streams) + scheduled SQL (tasks) |
| **Refresh control** | Target lag (e.g., "5 minutes") | Automatic, transparent | Cron schedule or trigger-based |
| **Chaining** | Can chain multiple DTs into a pipeline (DAG) | Cannot chain MVs | Can chain tasks into DAGs |
| **Incremental processing** | Supported (AUTO, incremental, or full refresh modes) | Always incremental | Manual CDC logic via stream metadata |
| **Complexity** | Low: declare the desired outcome | Low for simple queries | High: must write CDC processing logic |
| **Use case** | Data transformation pipelines | Accelerating repeated queries | Fine-grained control over when/how processing occurs |

**When to use Dynamic Tables:**
- You want to materialize query results without writing custom refresh logic
- You want to chain multiple transformations declaratively
- You do not need fine-grained control over exact refresh schedules
- You only need to specify a target freshness, and Snowflake handles orchestration

**When to use Streams/Tasks instead:**
- You need precise control over refresh schedules (e.g., exact cron timing)
- You need to execute arbitrary procedural logic (not just SQL transformations)
- You need fine-grained control over what happens at each step

**Must-have scoring elements:**
- [ ] Explains Dynamic Tables as declarative, query-based with automatic refresh
- [ ] Contrasts with materialized views (simpler but not chainable)
- [ ] Contrasts with streams/tasks (more control but more complex)
- [ ] Mentions target lag as the key control mechanism

---

## Q14. Write the SQL to create a chain of three Dynamic Tables that transform raw clickstream data into a session-level aggregation, with a 5-minute target lag.

**Type:** Implement | **Doc:** [Creating Dynamic Tables](https://docs.snowflake.com/en/user-guide/dynamic-tables-tasks-create)

**Canonical Answer:**

```sql
-- DT1: Clean and deduplicate raw events
CREATE OR REPLACE DYNAMIC TABLE clickstream_cleaned
    TARGET_LAG = '5 minutes'
    WAREHOUSE = transform_wh
AS
SELECT DISTINCT
    event_id,
    user_id,
    page_url,
    event_type,
    event_timestamp
FROM raw_clickstream
WHERE event_timestamp > DATEADD(day, -30, CURRENT_TIMESTAMP());

-- DT2: Sessionize events (group clicks within 30-minute windows)
CREATE OR REPLACE DYNAMIC TABLE clickstream_sessions
    TARGET_LAG = '5 minutes'
    WAREHOUSE = transform_wh
AS
SELECT
    user_id,
    session_id,
    MIN(event_timestamp) AS session_start,
    MAX(event_timestamp) AS session_end,
    COUNT(*) AS event_count,
    ARRAY_AGG(DISTINCT page_url) AS pages_visited
FROM (
    SELECT *,
        SUM(CASE WHEN DATEDIFF(minute, prev_ts, event_timestamp) > 30
                 THEN 1 ELSE 0 END) OVER (PARTITION BY user_id ORDER BY event_timestamp) AS session_id
    FROM (
        SELECT *,
            LAG(event_timestamp) OVER (PARTITION BY user_id ORDER BY event_timestamp) AS prev_ts
        FROM clickstream_cleaned
    )
)
GROUP BY user_id, session_id;

-- DT3: Session-level aggregation
CREATE OR REPLACE DYNAMIC TABLE session_summary
    TARGET_LAG = '5 minutes'
    WAREHOUSE = transform_wh
AS
SELECT
    DATE_TRUNC('hour', session_start) AS hour,
    COUNT(DISTINCT user_id) AS unique_users,
    COUNT(*) AS total_sessions,
    AVG(event_count) AS avg_events_per_session,
    AVG(DATEDIFF(second, session_start, session_end)) AS avg_session_duration_seconds
FROM clickstream_sessions
GROUP BY DATE_TRUNC('hour', session_start);
```

Key points:
- Each DT uses `TARGET_LAG = '5 minutes'`, meaning data freshness is within 5 minutes of the base table.
- Snowflake automatically manages the DAG and refreshes upstream DTs before downstream ones.
- The target lag of a downstream DT cannot be shorter than its upstream DTs.

**Must-have scoring elements:**
- [ ] Uses CREATE DYNAMIC TABLE with TARGET_LAG and WAREHOUSE
- [ ] Shows a chain where each DT references the previous one
- [ ] Includes the AS clause with the transformation query
- [ ] TARGET_LAG is set on each table

---

## Q15. My Dynamic Table is doing full refreshes instead of incremental refreshes. How do I diagnose and fix this?

**Type:** Debug | **Doc:** [Dynamic Table Refresh](https://docs.snowflake.com/en/user-guide/dynamic-tables-refresh)

**Canonical Answer:**

**Diagnosis:**

1. **Check the current refresh mode:**
   ```sql
   SHOW DYNAMIC TABLES LIKE 'my_table';
   -- Look at the "refresh_mode" column
   ```

2. **Understand why full refresh was chosen.** When refresh mode is AUTO (default), Snowflake selects the mode at creation time. If incremental refresh is unsupported or deemed inefficient, it chooses full refresh. Common reasons:
   - The query uses constructs not supported for incremental refresh
   - The DT is downstream from a DT with full refresh mode (incremental DTs cannot be downstream from full-refresh DTs)
   - An upstream view definition changed after the DT was created

3. **Check for the specific error:** If the original decision was incremental but an upstream view changed, you will see: `"Dynamic table can no longer be refreshed incrementally because an upstream view changed."`

**Fixes:**

1. **Simplify the query** to use constructs supported by incremental refresh. Break complex queries into smaller, focused Dynamic Tables.
2. **Ensure upstream DTs are also incremental.** Incremental DTs cannot be downstream from full-refresh DTs.
3. **Recreate the DT** with `CREATE OR REPLACE DYNAMIC TABLE` after fixing the query. The refresh mode decision is made only once at creation time.
4. **Explicitly set the refresh mode** to force incremental:
   ```sql
   CREATE OR REPLACE DYNAMIC TABLE my_table
       TARGET_LAG = '5 minutes'
       WAREHOUSE = my_wh
       REFRESH_MODE = INCREMENTAL
   AS ...
   ```
   Note: This will fail at creation if the query does not support incremental refresh.

**Must-have scoring elements:**
- [ ] Notes AUTO mode decides at creation time and does not change later
- [ ] Identifies unsupported query constructs as a common cause
- [ ] Mentions that incremental DTs cannot be downstream of full-refresh DTs
- [ ] Recommends recreating the DT (since mode is set at creation)

---

## Q16. How do I implement a Type 2 Slowly Changing Dimension using Dynamic Tables?

**Type:** Implement | **Doc:** [SCDs with Dynamic Tables](https://docs.snowflake.com/en/user-guide/dynamic-tables-about)

**Canonical Answer:**

Dynamic Tables can implement Type 2 SCDs by reading from a change stream and using window functions over per-record keys ordered by a change timestamp. This handles insertions, deletions, and updates that occur out of order.

```sql
CREATE OR REPLACE DYNAMIC TABLE customer_dim_scd2
    TARGET_LAG = '10 minutes'
    WAREHOUSE = transform_wh
AS
SELECT
    customer_id,
    customer_name,
    email,
    city,
    updated_at AS valid_from,
    LEAD(updated_at) OVER (
        PARTITION BY customer_id
        ORDER BY updated_at
    ) AS valid_to,
    CASE
        WHEN LEAD(updated_at) OVER (
            PARTITION BY customer_id
            ORDER BY updated_at
        ) IS NULL THEN TRUE
        ELSE FALSE
    END AS is_current
FROM customer_changes;
```

Key points:
- The source table (`customer_changes`) contains all versions of each record with a timestamp.
- `LEAD()` window function computes `valid_to` as the next change timestamp for the same key.
- `is_current = TRUE` marks the latest version of each record.
- Dynamic Tables handle the refresh automatically; no manual CDC logic needed.

**Must-have scoring elements:**
- [ ] Uses window functions (LEAD) partitioned by the business key
- [ ] Produces valid_from, valid_to, and is_current columns
- [ ] Notes that DTs simplify SCD2 by handling refresh automatically
- [ ] Source data contains all historical versions with timestamps

---

## Q17. What is target lag in Dynamic Tables and how does it affect cost and data freshness?

**Type:** Explain | **Doc:** [Understanding Target Lag](https://docs.snowflake.com/en/user-guide/dynamic-tables-about#target-lag)

**Canonical Answer:**

**Target lag** is the maximum acceptable staleness for a Dynamic Table's data relative to its base tables. It controls how often Snowflake refreshes the Dynamic Table.

**How it works:**
- If you set `TARGET_LAG = '5 minutes'`, the data in the Dynamic Table should be no more than 5 minutes behind the base table data.
- Snowflake does not refresh at exactly this interval. Instead, it picks a refresh cadence to attempt to keep the lag under the target value. For example, a 4-hour target lag might result in refreshes every ~3.5 hours.
- Setting `TARGET_LAG = DOWNSTREAM` means the DT only refreshes when a downstream DT with a time-based target lag triggers it.

**Cost vs. freshness tradeoff:**
- **Shorter target lag** = more frequent refreshes = higher compute cost but fresher data
- **Longer target lag** = fewer refreshes = lower compute cost but staler data
- Setting the entire DAG's target lag to DOWNSTREAM effectively disables scheduled refreshes (only manual refreshes occur)

**In a DAG of Dynamic Tables:**
- The target lag of a downstream DT cannot be shorter than the target lag of its upstream DTs.
- Snowflake coordinates refreshes so that upstream DTs refresh before downstream ones, and less frequent refreshes coincide with more frequent ones.
- Snapshot isolation is preserved: a DT sees a consistent snapshot of all its upstream dependencies.

**Must-have scoring elements:**
- [ ] Defines target lag as maximum allowed staleness
- [ ] Explains the cost vs. freshness tradeoff
- [ ] Mentions DOWNSTREAM as an option
- [ ] Notes that Snowflake coordinates refresh timing across the DAG

---

## Q18. What is Snowpark and how does it let me run Python code on Snowflake without moving data out?

**Type:** Explain | **Doc:** [Snowpark Developer Guide](https://docs.snowflake.com/en/developer-guide/snowpark/python/index)

**Canonical Answer:**

Snowpark is the set of libraries and code execution environments that let you run Python, Java, and Scala code directly within Snowflake, next to your data. Instead of extracting data to an external system for processing, your code runs inside Snowflake's secure execution environment.

**Key capabilities:**
- **DataFrame API** — Write data transformations in Python (similar to pandas or PySpark) that are translated to optimized SQL and executed on Snowflake warehouses.
- **Stored procedures** — Write Python logic that executes server-side in Snowflake. Useful for multi-step data processing, ML model training, and orchestration.
- **User-Defined Functions (UDFs)** — Write Python functions callable from SQL. Runs on every row without moving data out.
- **Third-party packages** — Use packages from Anaconda (e.g., pandas, scikit-learn, xgboost) that are installed and cached automatically on the virtual warehouse.

**Why data stays in Snowflake:**
- Snowpark code is pushed down to Snowflake's compute layer. The DataFrame API generates SQL that runs on warehouses.
- Stored procedures and UDFs execute in a secure Python sandbox within Snowflake.
- No data egress is required. This preserves security, governance, and avoids data movement overhead.

**Must-have scoring elements:**
- [ ] Describes Snowpark as running code next to data inside Snowflake
- [ ] Mentions Python, Java, and Scala support
- [ ] Explains DataFrame API, stored procedures, and UDFs
- [ ] Notes data does not leave Snowflake

---

## Q19. Write a Snowpark Python stored procedure that reads from a staging table, applies a pandas transformation, and writes results to a target table.

**Type:** Implement | **Doc:** [Writing Stored Procedures in Snowpark](https://docs.snowflake.com/en/developer-guide/snowpark/python/creating-sprocs)

**Canonical Answer:**

```python
from snowflake.snowpark import Session
from snowflake.snowpark.functions import sproc
from snowflake.snowpark.types import StringType
import snowflake.snowpark

@sproc(
    name="transform_staging_data",
    is_permanent=True,
    stage_location="@my_stage",
    replace=True,
    packages=["snowflake-snowpark-python", "pandas"]
)
def transform_staging_data(session: snowflake.snowpark.Session) -> str:
    # Read from staging table into a pandas DataFrame
    df = session.table("staging_table").to_pandas()

    # Apply pandas transformation
    df['full_name'] = df['FIRST_NAME'] + ' ' + df['LAST_NAME']
    df['email_domain'] = df['EMAIL'].str.split('@').str[1]
    df['created_date'] = pd.to_datetime(df['CREATED_AT']).dt.date

    # Write results back to Snowflake
    result_df = session.create_dataframe(df)
    result_df.write.mode("overwrite").save_as_table("transformed_data")

    return f"Successfully transformed {len(df)} rows"
```

Alternatively, using SQL `CREATE PROCEDURE`:

```sql
CREATE OR REPLACE PROCEDURE transform_staging_data()
RETURNS STRING
LANGUAGE PYTHON
RUNTIME_VERSION = '3.12'
PACKAGES = ('snowflake-snowpark-python', 'pandas')
HANDLER = 'run'
AS
$$
import pandas as pd

def run(session):
    df = session.table("staging_table").to_pandas()

    df['full_name'] = df['FIRST_NAME'] + ' ' + df['LAST_NAME']
    df['email_domain'] = df['EMAIL'].str.split('@').str[1]

    result_df = session.create_dataframe(df)
    result_df.write.mode("overwrite").save_as_table("transformed_data")

    return f"Transformed {len(df)} rows"
$$;

CALL transform_staging_data();
```

**Must-have scoring elements:**
- [ ] Shows reading a Snowflake table into pandas (`.to_pandas()`)
- [ ] Applies a pandas transformation
- [ ] Writes results back to a Snowflake table (`.save_as_table()` or `write`)
- [ ] Specifies packages (at minimum `snowflake-snowpark-python` and `pandas`)

---

## Q20. Write a Python UDF in Snowflake that takes a string and returns its sentiment score using a custom model.

**Type:** Implement | **Doc:** [Python UDFs](https://docs.snowflake.com/en/developer-guide/udf/python/udf-python-introduction)

**Canonical Answer:**

```sql
CREATE OR REPLACE FUNCTION custom_sentiment(text STRING)
RETURNS FLOAT
LANGUAGE PYTHON
RUNTIME_VERSION = '3.12'
PACKAGES = ('textblob')
HANDLER = 'analyze_sentiment'
AS
$$
from textblob import TextBlob

def analyze_sentiment(text):
    if text is None:
        return 0.0
    blob = TextBlob(text)
    return blob.sentiment.polarity
$$;

-- Usage
SELECT
    review_text,
    custom_sentiment(review_text) AS sentiment_score
FROM customer_reviews;
```

For a model loaded from a stage:

```sql
CREATE OR REPLACE FUNCTION predict_sentiment(text STRING)
RETURNS FLOAT
LANGUAGE PYTHON
RUNTIME_VERSION = '3.12'
PACKAGES = ('snowflake-snowpark-python', 'joblib', 'scikit-learn')
IMPORTS = ('@my_stage/sentiment_model.pkl')
HANDLER = 'predict'
AS
$$
import joblib
import sys
import os

model = None

def predict(text):
    global model
    if model is None:
        import_dir = sys._xoptions["snowflake_import_directory"]
        model = joblib.load(os.path.join(import_dir, 'sentiment_model.pkl'))
    return float(model.predict([text])[0])
$$;
```

Key points:
- Supported Python versions: 3.9 (deprecated), 3.10, 3.11, 3.12, 3.13
- HANDLER specifies the Python function name
- Use IMPORTS to load model files from a stage
- Global state (like model loading) persists across rows for performance

**Must-have scoring elements:**
- [ ] Uses CREATE FUNCTION with LANGUAGE PYTHON
- [ ] Specifies RUNTIME_VERSION, HANDLER, and PACKAGES
- [ ] Shows the handler function matching the HANDLER name
- [ ] For staged models, uses IMPORTS and `sys._xoptions["snowflake_import_directory"]`

---

## Q21. What is the difference between a UDF, UDTF, UDAF, and a vectorized UDF in Snowflake? When should I use each?

**Type:** Compare | **Doc:** [UDF Overview](https://docs.snowflake.com/en/developer-guide/udf/udf-overview)

**Canonical Answer:**

| Type | Input | Output | Use Case |
|------|-------|--------|----------|
| **UDF (Scalar)** | One row | One scalar value | Row-level transformations (e.g., format a string, calculate a score) |
| **UDTF (Table Function)** | One row | Multiple rows (tabular) | Exploding/expanding data (e.g., parse a JSON array into rows) |
| **UDAF (Aggregate Function)** | Multiple rows | One scalar value | Custom aggregations (e.g., custom statistical measures). Python only. |
| **Vectorized UDF** | Batch of rows (pandas DataFrame) | Batch of results (pandas Series) | High-throughput row-level transforms with pandas. More efficient for large datasets. |
| **Vectorized UDTF** | Batch of rows (pandas DataFrame) | Tabular results | High-throughput table-valued transforms with pandas batching. |

**When to use each:**
- **UDF** — Default choice for any row-level calculation. Supported in Python, Java, JavaScript, Scala, SQL.
- **UDTF** — When you need to return multiple rows per input row. Supported in Python, Java, JavaScript, Scala, SQL.
- **UDAF** — When you need a custom aggregate function (like SUM or AVG but custom logic). Python only.
- **Vectorized UDF** — When processing large tables and you want the performance benefit of pandas batch processing. Python only.

**Must-have scoring elements:**
- [ ] Correctly distinguishes scalar (UDF), table (UDTF), and aggregate (UDAF)
- [ ] Describes vectorized UDFs as using pandas for batch processing
- [ ] Notes UDAF is Python-only
- [ ] Gives practical guidance on when to use each

---

## Q22. My Snowpark stored procedure fails with a "missing package" error at runtime. How do I specify dependencies correctly?

**Type:** Debug | **Doc:** [Snowpark Python Packages](https://docs.snowflake.com/en/developer-guide/snowpark/python/creating-sprocs)

**Canonical Answer:**

**Diagnosis:** The error means a required Python package is not available in the execution environment. Snowflake uses Anaconda for package management.

**Fixes:**

1. **Specify packages explicitly** when creating the stored procedure:

   Using the `@sproc` decorator:
   ```python
   @sproc(packages=["snowflake-snowpark-python", "pandas", "xgboost==1.5.0"])
   def my_proc(session):
       ...
   ```

   Using SQL:
   ```sql
   CREATE OR REPLACE PROCEDURE my_proc()
   RETURNS STRING
   LANGUAGE PYTHON
   RUNTIME_VERSION = '3.12'
   PACKAGES = ('snowflake-snowpark-python', 'pandas', 'xgboost==1.5.0')
   HANDLER = 'run'
   AS $$ ... $$;
   ```

2. **Pin package versions** for production. If you do not specify a version, Snowflake uses the latest version, which may change:
   ```python
   packages=["pandas==2.1.0", "scikit-learn==1.3.0"]
   ```

3. **Use session-level packages** for development:
   ```python
   session.add_packages("snowflake-snowpark-python", "pandas", "xgboost==1.5.0")
   # Or from a requirements file:
   session.add_requirements("mydir/requirements.txt")
   ```

4. **Procedure-level packages override session-level packages.** If you specify packages in the `@sproc` decorator, those take precedence.

5. **Check package availability.** Not all PyPI packages are available in Snowflake's Anaconda channel. Check the [Anaconda Snowflake channel](https://repo.anaconda.com/pkgs/snowflake/) for available packages.

**Must-have scoring elements:**
- [ ] Shows how to specify packages (PACKAGES clause or `packages=` argument)
- [ ] Recommends pinning versions for production
- [ ] Mentions session.add_packages for development
- [ ] Notes that Snowflake uses Anaconda (not all PyPI packages are available)

---

## Q23. What is Streamlit in Snowflake and how does it differ from running open-source Streamlit on my own infrastructure?

**Type:** Compare | **Doc:** [About Streamlit in Snowflake](https://docs.snowflake.com/en/developer-guide/streamlit/about-streamlit)

**Canonical Answer:**

| Aspect | Streamlit in Snowflake | Open-source Streamlit (self-hosted) |
|--------|----------------------|-------------------------------------|
| **Hosting** | Fully managed by Snowflake | You manage servers, containers, etc. |
| **Data access** | Direct, secure access to Snowflake data via session object (no credentials in code) | Requires connection strings, credentials management |
| **Security** | Uses Snowflake RBAC; access controlled via roles | You manage authentication and authorization |
| **Deployment** | Deploy from Snowsight, SQL, or Snowflake CLI | Deploy to your own infrastructure (Docker, cloud VMs, Streamlit Cloud) |
| **Compute** | Choose warehouse runtime or container runtime | You provision compute |
| **Packages** | Anaconda channel + container runtime for custom packages | Full pip/conda access |
| **Sharing** | Share via Snowflake roles and grants | Share via URL with your own auth |

**Key features of Streamlit in Snowflake:**
- Snowflake manages compute and storage for the app
- Source code stored as a Snowflake object with RBAC
- Seamless integration with Snowpark, UDFs, stored procedures, and Native Apps
- Side-by-side editor and preview in Snowsight

**Must-have scoring elements:**
- [ ] Notes Streamlit in Snowflake is fully managed by Snowflake
- [ ] Highlights direct, secure data access without credential management
- [ ] Mentions RBAC-based access control
- [ ] Notes warehouse and container runtime options

---

## Q24. Write a Streamlit in Snowflake app that connects to a table, displays a bar chart of sales by region, and lets the user filter by date range.

**Type:** Implement | **Doc:** [Create a Streamlit App](https://docs.snowflake.com/en/developer-guide/streamlit/create-streamlit-app)

**Canonical Answer:**

```python
import streamlit as st
from snowflake.snowpark.context import get_active_session

session = get_active_session()

st.title("Sales by Region")

# Date range filter
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("Start date", value=pd.Timestamp("2024-01-01"))
with col2:
    end_date = st.date_input("End date", value=pd.Timestamp.today())

# Query data with filter
df = session.sql(f"""
    SELECT region, SUM(amount) AS total_sales
    FROM sales_table
    WHERE sale_date BETWEEN '{start_date}' AND '{end_date}'
    GROUP BY region
    ORDER BY total_sales DESC
""").to_pandas()

# Display bar chart
st.bar_chart(df.set_index("REGION")["TOTAL_SALES"])

# Show raw data
st.dataframe(df)
```

Key points:
- Use `get_active_session()` to get the Snowflake session (no credentials needed)
- The session is pre-authenticated with the current user's role
- `to_pandas()` converts the Snowpark DataFrame for Streamlit visualization
- Deploy via Snowsight (Create > Streamlit App) or SQL (`CREATE STREAMLIT`)

**Must-have scoring elements:**
- [ ] Uses `get_active_session()` for the Snowflake connection
- [ ] Queries a Snowflake table via `session.sql()` or `session.table()`
- [ ] Shows a bar chart with `st.bar_chart()` or similar
- [ ] Includes a date filter using Streamlit widgets

---

## Q25. How do I securely access Snowflake data from a Streamlit in Snowflake app using the session object?

**Type:** Implement | **Doc:** [Accessing Data from Streamlit](https://docs.snowflake.com/en/developer-guide/streamlit/accessing-snowflake-data)

**Canonical Answer:**

```python
from snowflake.snowpark.context import get_active_session

session = get_active_session()

# Option 1: Use session.sql() for SQL queries
df = session.sql("SELECT * FROM my_table WHERE status = 'active'").to_pandas()

# Option 2: Use session.table() for DataFrame API
df = session.table("my_table").filter(col("status") == "active").to_pandas()

# Option 3: Call stored procedures
result = session.call("my_stored_procedure", arg1, arg2)

# Option 4: Use Snowpark DataFrame operations
snowpark_df = session.table("sales")
grouped = snowpark_df.group_by("region").agg(sum("amount").alias("total"))
pandas_df = grouped.to_pandas()
```

**Security model:**
- The session is automatically authenticated using the **current user's role** (the role of the user viewing the app).
- No credentials, connection strings, or tokens are needed in the code.
- Data access is governed by Snowflake RBAC. The user sees only data their role can access.
- The app runs within Snowflake, so data never leaves the platform.

**Must-have scoring elements:**
- [ ] Uses `get_active_session()` (not connection parameters)
- [ ] Explains that the session inherits the viewer's role and RBAC
- [ ] Shows at least one method of querying data (session.sql or session.table)
- [ ] Notes no credentials are stored in code

---

## Q26. What are the warehouse runtime and container runtime options for Streamlit in Snowflake, and when should I use each?

**Type:** Compare | **Doc:** [Runtime Environments](https://docs.snowflake.com/en/developer-guide/streamlit/runtime-environments)

**Canonical Answer:**

| Aspect | Warehouse Runtime | Container Runtime |
|--------|------------------|-------------------|
| **Compute** | Runs on a virtual warehouse | Runs in a container (Snowpark Container Services) |
| **Packages** | Limited to Anaconda Snowflake channel | Full pip/conda access, custom packages |
| **Startup** | Fast, uses existing warehouse | Slower cold start (container provisioning) |
| **Use case** | Standard data apps, dashboards | Apps needing custom libraries, ML models, or GPU |
| **Cost model** | Warehouse credits | Container compute credits |

**Use warehouse runtime when:**
- Your app uses standard packages available in the Anaconda Snowflake channel
- You want fast startup times
- Your app primarily queries data and displays visualizations

**Use container runtime when:**
- You need packages not available in the Anaconda channel
- You need to run custom ML models or heavy computation
- You need GPU support
- You want more control over the execution environment

**Must-have scoring elements:**
- [ ] Distinguishes warehouse runtime from container runtime
- [ ] Notes package availability difference (Anaconda vs. full pip)
- [ ] Gives guidance on when to choose each
- [ ] Mentions container runtime is based on Snowpark Container Services

---

## Q27. What are Snowflake Iceberg tables and when should I use them instead of standard Snowflake tables?

**Type:** Compare | **Doc:** [Apache Iceberg Tables](https://docs.snowflake.com/en/user-guide/tables-iceberg)

**Canonical Answer:**

**Iceberg tables** combine Snowflake's query performance with external cloud storage (S3, GCS, Azure Storage) that you manage, using the open Apache Iceberg table format.

| Aspect | Standard Snowflake Tables | Iceberg Tables |
|--------|--------------------------|----------------|
| **Storage** | Snowflake-managed (internal, compressed, columnar) | External cloud storage you manage |
| **Storage cost** | Billed by Snowflake | Billed by your cloud provider |
| **Format** | Snowflake proprietary | Open (Apache Parquet + Iceberg metadata) |
| **Interoperability** | Snowflake only | Queryable by Spark, Trino, Flink, and other engines |
| **Fail-safe** | Yes | No (you manage data protection) |
| **Performance** | Optimized for Snowflake | Near-native performance in Snowflake |
| **Write support** | Full | Full (Snowflake-managed) or varies (external catalog) |

**Use Iceberg tables when:**
- You have an existing data lake you cannot or choose not to move into Snowflake
- You need open format interoperability with other compute engines (Spark, Trino, etc.)
- You want to avoid Snowflake storage costs while still using Snowflake for compute
- You need cross-cloud or cross-region data access

**Use standard Snowflake tables when:**
- You want maximum performance with zero storage management
- You need Fail-safe for data recovery
- You do not need to share data with non-Snowflake compute engines

**Must-have scoring elements:**
- [ ] Explains Iceberg tables use external cloud storage with open format
- [ ] Notes interoperability with other engines
- [ ] Mentions no Fail-safe for Iceberg tables
- [ ] Gives clear guidance on when to choose each

---

## Q28. How do I create a Snowflake-managed Iceberg table with an external volume pointing to S3?

**Type:** Implement | **Doc:** [Create an Iceberg Table](https://docs.snowflake.com/en/user-guide/tables-iceberg-create)

**Canonical Answer:**

**Step 1: Create an external volume:**

```sql
CREATE OR REPLACE EXTERNAL VOLUME my_s3_volume
    STORAGE_LOCATIONS = (
        (
            NAME = 'my-s3-location'
            STORAGE_BASE_URL = 's3://my-bucket/iceberg-data/'
            STORAGE_PROVIDER = 'S3'
            STORAGE_AWS_ROLE_ARN = 'arn:aws:iam::123456789012:role/my-iceberg-role'
        )
    );
```

**Step 2: Configure the IAM trust policy** (set up in AWS to allow the Snowflake account to assume the role). Use `DESCRIBE EXTERNAL VOLUME my_s3_volume` to get the Snowflake IAM user ARN and external ID for the trust policy.

**Step 3: Create the Iceberg table:**

```sql
CREATE OR REPLACE ICEBERG TABLE my_iceberg_table (
    id INT,
    name STRING,
    amount DECIMAL(10,2),
    created_at TIMESTAMP
)
    CATALOG = 'SNOWFLAKE'
    EXTERNAL_VOLUME = 'my_s3_volume'
    BASE_LOCATION = 'my_table_data/';
```

**Step 4: Insert data:**

```sql
INSERT INTO my_iceberg_table VALUES
    (1, 'Alice', 100.50, CURRENT_TIMESTAMP()),
    (2, 'Bob', 200.75, CURRENT_TIMESTAMP());
```

Key points:
- `CATALOG = 'SNOWFLAKE'` means Snowflake manages the Iceberg catalog (full read/write, compaction, etc.)
- `BASE_LOCATION` is the subdirectory within the external volume where this table's data files are stored
- Snowflake handles lifecycle maintenance (compaction) automatically
- Data files are stored in Parquet format

**Must-have scoring elements:**
- [ ] Shows creating an external volume with S3 storage location
- [ ] Shows CREATE ICEBERG TABLE with CATALOG = 'SNOWFLAKE' and EXTERNAL_VOLUME
- [ ] Includes BASE_LOCATION
- [ ] Mentions IAM trust policy setup

---

## Q29. What is a catalog integration and what are the differences between using Snowflake as the catalog vs. an external catalog like AWS Glue?

**Type:** Compare | **Doc:** [Iceberg Catalog Options](https://docs.snowflake.com/en/user-guide/tables-iceberg#catalog-options)

**Canonical Answer:**

A **catalog integration** is a named, account-level Snowflake object that stores information about how your Iceberg table metadata is organized when using an external catalog. It connects Snowflake to an external Iceberg catalog (e.g., AWS Glue, Snowflake Open Catalog, Unity Catalog).

| Feature | Snowflake as Catalog | External Catalog (e.g., AWS Glue) |
|---------|---------------------|-----------------------------------|
| **Read access** | Yes | Yes |
| **Write access** | Yes | Yes (via Iceberg REST catalog) |
| **Lifecycle management** | Snowflake handles compaction, etc. | You manage externally |
| **Setup** | External volume only | External volume + catalog integration |
| **Replication** | Supported | Not supported for all types |
| **Catalog-vended credentials** | Yes | Yes |
| **Integration with Open Catalog** | Can sync to Open Catalog | Can query from Open Catalog |

**Use Snowflake as catalog when:**
- You want full Snowflake platform support with minimal management
- You need Snowflake to handle compaction and lifecycle
- Your primary query engine is Snowflake

**Use an external catalog when:**
- Your tables are already managed by another system (AWS Glue, Databricks Unity Catalog, Open Catalog)
- You need multiple compute engines to access the same tables
- You want to use a catalog-linked database to automatically discover and sync tables

A **catalog-linked database** can automatically discover and stay in sync with namespaces and tables in your remote catalog, providing read and write access from Snowflake.

**Must-have scoring elements:**
- [ ] Defines catalog integration as connecting Snowflake to an external catalog
- [ ] Compares Snowflake-managed vs. external catalog options
- [ ] Notes lifecycle management difference
- [ ] Mentions catalog-linked database for automatic discovery

---

## Q30. What is a catalog-linked database and how does it automatically discover and sync tables from a remote Iceberg REST catalog?

**Type:** Explain | **Doc:** [Catalog-Linked Database](https://docs.snowflake.com/en/user-guide/tables-iceberg-linked-catalog)

**Canonical Answer:**

A **catalog-linked database** is a Snowflake database that automatically discovers and stays in sync with the namespaces and tables in a remote Iceberg REST catalog. Instead of manually creating individual Iceberg tables in Snowflake, the catalog-linked database mirrors the structure of your external catalog.

**How it works:**
- You create a catalog integration pointing to a remote Iceberg REST catalog (e.g., AWS Glue, Snowflake Open Catalog, Databricks Unity Catalog)
- You create a catalog-linked database using that integration
- Snowflake automatically discovers all namespaces and tables from the remote catalog
- As tables are added or removed in the remote catalog, the linked database stays in sync
- You can read and write to these tables from Snowflake while maintaining full interoperability with your existing Iceberg ecosystem

**Key benefits:**
- No manual table creation needed
- Automatic sync with the external catalog
- Preserves interoperability (other engines can still access the same tables)
- Read and write access from Snowflake

**Must-have scoring elements:**
- [ ] Defines it as a database that auto-syncs with a remote Iceberg REST catalog
- [ ] Explains automatic discovery of namespaces and tables
- [ ] Notes it requires a catalog integration
- [ ] Mentions both read and write access

---

## Q31. My Iceberg table auto-refresh is stuck and data is stale. How do I diagnose the issue?

**Type:** Debug | **Doc:** [Iceberg Auto-Refresh](https://docs.snowflake.com/en/user-guide/tables-iceberg-configure-automatic-refresh)

**Canonical Answer:**

**Diagnosis steps:**

1. **Check auto-refresh status:**
   ```sql
   SELECT SYSTEM$GET_ICEBERG_TABLE_INFORMATION('my_db.my_schema.my_iceberg_table');
   ```

2. **Check refresh history:**
   ```sql
   SELECT *
   FROM TABLE(INFORMATION_SCHEMA.ICEBERG_TABLE_REFRESH_HISTORY(
       TABLE_NAME => 'my_iceberg_table'
   ))
   ORDER BY REFRESH_START_TIME DESC;
   ```

3. **Common causes:**
   - **External volume permissions:** Snowflake cannot access the storage location. Verify the IAM role trust policy allows Snowflake to read metadata files.
   - **Notification setup missing:** For automatic refresh, event notifications (SNS for S3, Event Grid for Azure) must be configured to notify Snowflake when metadata files change.
   - **Metadata file changes not detected:** If the external catalog updates metadata without triggering notifications, auto-refresh will not fire.

4. **Manual refresh as a workaround:**
   ```sql
   ALTER ICEBERG TABLE my_iceberg_table REFRESH;
   ```

**Fixes:**
- Verify and fix IAM role trust policy (use `DESCRIBE EXTERNAL VOLUME` to get the required Snowflake IAM user ARN)
- Verify event notification configuration is correctly pointing to Snowflake
- Check that the external catalog is writing metadata files to the expected location
- If using Snowflake as catalog, check that compaction is not disabled

**Must-have scoring elements:**
- [ ] Suggests checking refresh history
- [ ] Identifies IAM/permissions as a common cause
- [ ] Mentions event notification setup for auto-refresh
- [ ] Shows manual refresh as a workaround

---

## Q32. What is Snowflake ML and what are the main components?

**Type:** Explain | **Doc:** [Snowflake ML Overview](https://docs.snowflake.com/en/developer-guide/snowflake-ml/overview)

**Canonical Answer:**

Snowflake ML is an integrated set of capabilities for end-to-end machine learning on top of governed data within Snowflake. The main components are:

1. **Snowflake Notebooks on Container Runtime** — Jupyter-like environment for training and fine-tuning models with preinstalled packages (PyTorch, XGBoost, scikit-learn) and GPU support.

2. **Feature Store** — Defines, manages, stores, and discovers ML features. Supports automated incremental refresh from batch and streaming sources. Features are defined once and continuously updated.

3. **ML Jobs** — Develop and automate ML pipelines. Lets teams working from external IDEs (VS Code, PyCharm) dispatch functions or modules to Snowflake's Container Runtime.

4. **Experiments** — Record model training results and evaluate collections of models. Compare metrics, select the best model, and view results in Snowsight.

5. **Model Registry and Model Serving** — Log and manage models (regardless of where they were trained). Deploy models for inference at scale via Snowpark Container Services.

6. **ML Observability** — Monitor model performance metrics in production. Track drift, set alerts for performance thresholds. Includes ML Explainability (Shapley values).

7. **ML Lineage** — Trace end-to-end lineage from source data to features, datasets, and models for reproducibility and compliance.

8. **Datasets** — Immutable, versioned snapshots of data suitable for ML framework ingestion.

**Must-have scoring elements:**
- [ ] Lists Feature Store, Model Registry, Experiments, ML Jobs, ML Observability
- [ ] Notes it is integrated within Snowflake (no data movement)
- [ ] Mentions GPU support via Container Runtime
- [ ] Describes the registry as supporting models trained anywhere

---

## Q33. How do I register a trained scikit-learn model in the Snowflake Model Registry and run batch inference on a table?

**Type:** Implement | **Doc:** [Model Registry](https://docs.snowflake.com/en/developer-guide/snowflake-ml/model-registry/overview)

**Canonical Answer:**

```python
from snowflake.ml.registry import Registry
from snowflake.snowpark import Session
from sklearn.ensemble import RandomForestClassifier

session = Session.builder.configs(connection_params).create()

# 1. Train your model
model = RandomForestClassifier(n_estimators=100)
model.fit(X_train, y_train)

# 2. Connect to the Model Registry
registry = Registry(session=session, database_name="ML_DB", schema_name="ML_SCHEMA")

# 3. Log the model
model_version = registry.log_model(
    model_name="churn_classifier",
    version_name="v1",
    model=model,
    sample_input_data=X_train[:5]  # for schema inference
)

# 4. Run batch inference
# Option A: Using the model version object
predictions = model_version.run(
    session.table("INFERENCE_INPUT_TABLE"),
    function_name="predict"
)
predictions.write.save_as_table("PREDICTIONS_OUTPUT")

# Option B: Using SQL after deployment
# CALL ML_DB.ML_SCHEMA.CHURN_CLASSIFIER!PREDICT(...)
```

**Must-have scoring elements:**
- [ ] Uses `Registry` from `snowflake.ml.registry`
- [ ] Shows `registry.log_model()` with model_name and version_name
- [ ] Shows running inference via `model_version.run()`
- [ ] Mentions sample_input_data for schema inference

---

## Q34. How do I create a Feature Store entity and feature view that automatically refreshes from a source table?

**Type:** Implement | **Doc:** [Feature Store](https://docs.snowflake.com/en/developer-guide/snowflake-ml/feature-store/overview)

**Canonical Answer:**

```python
from snowflake.ml.feature_store import FeatureStore, Entity, FeatureView
from snowflake.snowpark import Session

session = Session.builder.configs(connection_params).create()

# 1. Create the Feature Store
fs = FeatureStore(
    session=session,
    database="ML_DB",
    name="ML_SCHEMA",
    default_warehouse="ML_WH"
)

# 2. Define an entity (the join key)
customer_entity = Entity(
    name="CUSTOMER",
    join_keys=["CUSTOMER_ID"]
)
fs.register_entity(customer_entity)

# 3. Create a feature view from a source query
customer_features_df = session.sql("""
    SELECT
        customer_id,
        AVG(order_amount) AS avg_order_amount,
        COUNT(*) AS total_orders,
        MAX(order_date) AS last_order_date
    FROM orders
    GROUP BY customer_id
""")

feature_view = FeatureView(
    name="CUSTOMER_ORDER_FEATURES",
    entities=[customer_entity],
    feature_df=customer_features_df,
    refresh_freq="1 hour"  # Automatically refresh every hour
)

# 4. Register the feature view
registered_fv = fs.register_feature_view(
    feature_view=feature_view,
    version="v1"
)
```

Key points:
- Entities define the join keys for features
- Feature views are backed by Dynamic Tables for automatic refresh
- `refresh_freq` controls how often features are recomputed
- Features defined once are continuously updated with new data

**Must-have scoring elements:**
- [ ] Creates an Entity with join keys
- [ ] Creates a FeatureView from a DataFrame/query
- [ ] Shows register_entity and register_feature_view
- [ ] Includes refresh_freq for automatic refresh

---

## Q35. How do I use Snowflake ML Experiments to compare multiple model training runs and select the best model?

**Type:** Implement | **Doc:** [Experiments](https://docs.snowflake.com/en/developer-guide/snowflake-ml/experiment/overview)

**Canonical Answer:**

```python
from snowflake.ml.experiment import Experiment
from snowflake.snowpark import Session

session = Session.builder.configs(connection_params).create()

# 1. Create an experiment
experiment = Experiment(
    session=session,
    database="ML_DB",
    schema="ML_SCHEMA",
    name="churn_prediction_experiment"
)

# 2. Log multiple training runs
for n_est in [50, 100, 200]:
    for max_depth in [5, 10, 15]:
        run = experiment.create_run(f"rf_{n_est}_{max_depth}")

        model = RandomForestClassifier(n_estimators=n_est, max_depth=max_depth)
        model.fit(X_train, y_train)
        accuracy = model.score(X_test, y_test)

        run.log_param("n_estimators", n_est)
        run.log_param("max_depth", max_depth)
        run.log_metric("accuracy", accuracy)
        run.log_metric("f1_score", f1_score(y_test, model.predict(X_test)))

# 3. View results in Snowsight or query programmatically
# Navigate to Snowsight > ML > Experiments to compare runs visually
```

Key points:
- Experiments group related model training runs
- Each run logs parameters and metrics
- Results are viewable in Snowsight for visual comparison
- You can also upload metadata and artifacts from prior training done outside Snowflake

**Must-have scoring elements:**
- [ ] Creates an Experiment object
- [ ] Logs parameters and metrics per run
- [ ] Shows multiple runs for comparison
- [ ] Mentions Snowsight for viewing results

---

## Q36. What is ML Observability in Snowflake and how do I set up drift monitoring for a deployed model?

**Type:** Explain | **Doc:** [ML Observability](https://docs.snowflake.com/en/developer-guide/snowflake-ml/ml-observability/overview)

**Canonical Answer:**

ML Observability provides tools to monitor production model performance within Snowflake. Key capabilities:

- **Performance monitoring** — Track prediction metrics (accuracy, F1, AUC) over time
- **Data drift detection** — Monitor whether input feature distributions shift from training data
- **Prediction drift detection** — Monitor whether model output distributions change
- **Alerting** — Set thresholds and receive alerts when performance degrades
- **ML Explainability** — Compute Shapley values for models in the Model Registry to understand feature importance

**How drift monitoring works:**
- You register a model in the Model Registry
- You configure a monitor that compares current inference data against a reference dataset (typically training data)
- The monitor runs on a schedule, computing drift statistics
- If drift exceeds a threshold, alerts fire

**ML Explainability:**
- Computes Shapley values for models regardless of where they were trained
- Helps identify which features drive predictions

**Must-have scoring elements:**
- [ ] Describes monitoring for production model performance
- [ ] Mentions data drift and prediction drift
- [ ] Notes alerting capabilities
- [ ] Mentions ML Explainability (Shapley values)

---

## Q37. What is Snowpark Container Services and when should I use it instead of Snowpark UDFs or stored procedures?

**Type:** Compare | **Doc:** [SPCS Overview](https://docs.snowflake.com/en/developer-guide/snowpark-container-services/overview)

**Canonical Answer:**

Snowpark Container Services (SPCS) is a managed container orchestration platform within Snowflake. You package applications as OCI container images and run them on Snowflake-managed compute.

| Aspect | Snowpark UDFs/Stored Procedures | SPCS |
|--------|-------------------------------|------|
| **Runtime** | Python/Java/Scala sandbox | Any OCI container (any language, framework) |
| **Use case** | SQL-callable functions, data transforms | Full applications, APIs, web UIs, ML serving |
| **GPU support** | No | Yes |
| **Networking** | Limited (external access integration) | Full networking (ingress, egress, service-to-service) |
| **Persistence** | Stateless | Can maintain state, run long-lived services |
| **Packages** | Anaconda channel | Any package (Docker image) |
| **Invocation** | SQL (SELECT, CALL) | HTTP endpoints, service functions, job services |

**Use SPCS when:**
- You need custom runtimes, specialized libraries, or specific software configurations
- You need GPU for ML training or inference
- You want to deploy a web application or REST API over Snowflake data
- You need long-running services (not just request/response)
- You need service-to-service communication

**Use Snowpark UDFs/stored procedures when:**
- You need SQL-callable row-level or batch processing
- Your logic fits standard Python/Java/Scala with available Anaconda packages
- You want the simplest deployment model

**Must-have scoring elements:**
- [ ] Describes SPCS as a managed container platform
- [ ] Contrasts with UDFs/stored procs (any language vs. Python/Java/Scala)
- [ ] Notes GPU support as a key differentiator
- [ ] Mentions web applications, APIs, and long-running services as SPCS use cases

---

## Q38. Walk me through the steps to deploy a custom Docker container as a service in Snowpark Container Services.

**Type:** Implement | **Doc:** [SPCS Tutorials](https://docs.snowflake.com/en/developer-guide/snowpark-container-services/tutorials/tutorial-1)

**Canonical Answer:**

**Step 1: Create an image repository:**
```sql
CREATE IMAGE REPOSITORY my_db.my_schema.my_repo;
```

**Step 2: Build and push your Docker image:**
```bash
# Tag for Snowflake registry
docker tag my-app:latest <org>-<account>.registry.snowflakecomputing.com/my_db/my_schema/my_repo/my-app:latest

# Login to Snowflake registry
docker login <org>-<account>.registry.snowflakecomputing.com

# Push
docker push <org>-<account>.registry.snowflakecomputing.com/my_db/my_schema/my_repo/my-app:latest
```

**Step 3: Create a compute pool:**
```sql
CREATE COMPUTE POOL my_pool
    MIN_NODES = 1
    MAX_NODES = 3
    INSTANCE_FAMILY = CPU_X64_S;
```

**Step 4: Create a service specification (YAML):**
```yaml
spec:
  containers:
    - name: my-app
      image: /my_db/my_schema/my_repo/my-app:latest
      ports:
        - name: http
          port: 8080
  endpoints:
    - name: http-endpoint
      port: 8080
      public: true
```

**Step 5: Create the service:**
```sql
CREATE SERVICE my_service
    IN COMPUTE POOL my_pool
    FROM @my_stage
    SPECIFICATION_FILE = 'my_spec.yaml';
```

**Step 6: Check service status:**
```sql
SELECT SYSTEM$GET_SERVICE_STATUS('my_service');
SELECT SYSTEM$GET_SERVICE_LOGS('my_service', 0, 'my-app');
```

**Must-have scoring elements:**
- [ ] Shows creating an image repository
- [ ] Shows pushing a Docker image to the Snowflake registry
- [ ] Shows creating a compute pool
- [ ] Shows CREATE SERVICE with a specification file

---

## Q39. How do I create a compute pool with GPU support for ML model serving in SPCS?

**Type:** Implement | **Doc:** [Compute Pools](https://docs.snowflake.com/en/developer-guide/snowpark-container-services/working-with-compute-pool)

**Canonical Answer:**

```sql
CREATE COMPUTE POOL gpu_inference_pool
    MIN_NODES = 1
    MAX_NODES = 5
    INSTANCE_FAMILY = GPU_NV_S;
```

Available GPU instance families include:
- `GPU_NV_S` — Small GPU (e.g., single NVIDIA GPU)
- `GPU_NV_M` — Medium GPU
- `GPU_NV_L` — Large GPU

Key points:
- `MIN_NODES` is the minimum number of VM nodes (the pool starts with this many)
- `MAX_NODES` is the maximum the pool can scale to
- The compute pool auto-suspends when idle and auto-resumes when services need it
- Specify the compute pool when creating a service: `CREATE SERVICE ... IN COMPUTE POOL gpu_inference_pool`

**Must-have scoring elements:**
- [ ] Uses CREATE COMPUTE POOL with a GPU instance family
- [ ] Shows MIN_NODES and MAX_NODES
- [ ] Lists at least one GPU instance family name
- [ ] Mentions auto-suspend/resume behavior

---

## Q40. What is the difference between a long-running SPCS service and a job service, and when should I use each?

**Type:** Compare | **Doc:** [SPCS Overview](https://docs.snowflake.com/en/developer-guide/snowpark-container-services/overview)

**Canonical Answer:**

| Aspect | Service (Long-running) | Job Service (Finite) |
|--------|----------------------|---------------------|
| **Lifecycle** | Runs until you explicitly stop it | Exits when all containers complete |
| **Restart behavior** | Snowflake restarts crashed containers | No restart on exit |
| **Creation** | `CREATE SERVICE` | `EXECUTE JOB SERVICE` |
| **Use case** | Web apps, APIs, model serving endpoints | ML training, batch processing, ETL jobs |
| **Analogy** | Like a web service or daemon | Like a stored procedure |

**Use a long-running service when:**
- You are deploying a web application or REST API
- You need a persistent endpoint (e.g., model serving)
- The application should run continuously until explicitly stopped

**Use a job service when:**
- You are running a one-time or periodic computation (ML training, data processing)
- The workload has a defined start and end
- You want behavior similar to a stored procedure but with container flexibility and GPU support

**Must-have scoring elements:**
- [ ] Distinguishes lifecycle (persistent vs. finite)
- [ ] Notes CREATE SERVICE vs. EXECUTE JOB SERVICE
- [ ] Explains restart behavior difference
- [ ] Gives clear use case guidance

---

## Q41. What is the Snowflake Native App Framework and what are its key components?

**Type:** Explain | **Doc:** [About Native Apps](https://docs.snowflake.com/en/developer-guide/native-apps/native-apps-about)

**Canonical Answer:**

The Snowflake Native App Framework lets you build data applications that share both data and business logic with other Snowflake accounts. Key components:

1. **Application Package** — Encapsulates all data content, application logic, metadata, and setup script. Contains version and patch information.

2. **Manifest File** — Defines configuration and setup properties (location of setup script, versions, etc.).

3. **Setup Script** — SQL statements that run when a consumer installs or upgrades the application. Creates the required objects within the app.

4. **Snowflake Native App** — The database object installed in the consumer account. Created when a consumer installs from a listing.

5. **Listings** — Distribution mechanism: Snowflake Marketplace listings (public, free or paid) or private listings (direct to specific accounts).

**Capabilities:**
- Include Streamlit apps for rich visualizations
- Include stored procedures and UDFs (Snowpark, JavaScript, SQL)
- Support versioning and patching for incremental updates
- Support logging and event sharing for troubleshooting
- Support apps with containers (Snowpark Container Services) for custom runtime workloads

**Must-have scoring elements:**
- [ ] Names application package, manifest file, and setup script as key components
- [ ] Explains the provider/consumer model
- [ ] Mentions distribution via Marketplace or private listings
- [ ] Notes support for Streamlit, stored procedures, and versioning

---

## Q42. How do I create a basic Snowflake Native App with a Streamlit UI and share it via a private listing?

**Type:** Implement | **Doc:** [Native Apps Tutorial](https://docs.snowflake.com/en/developer-guide/native-apps/tutorials/getting-started-tutorial)

**Canonical Answer:**

**Step 1: Create the application package:**
```sql
CREATE APPLICATION PACKAGE my_app_package;
```

**Step 2: Create the manifest file** (`manifest.yml`):
```yaml
manifest_version: 1
artifacts:
  setup_script: setup.sql
  default_streamlit: app_schema.my_streamlit_app
```

**Step 3: Create the setup script** (`setup.sql`):
```sql
CREATE OR ALTER VERSIONED SCHEMA app_schema;

CREATE OR REPLACE STREAMLIT app_schema.my_streamlit_app
    FROM '/streamlit'
    MAIN_FILE = 'app.py';

CREATE OR REPLACE PROCEDURE app_schema.get_data()
    RETURNS TABLE()
    LANGUAGE SQL
    AS 'SELECT * FROM shared_data.my_table';
```

**Step 4: Create the Streamlit app** (`streamlit/app.py`):
```python
import streamlit as st
from snowflake.snowpark.context import get_active_session

session = get_active_session()
st.title("My Native App")
df = session.sql("CALL app_schema.get_data()").to_pandas()
st.dataframe(df)
```

**Step 5: Upload files and create a version:**
```sql
PUT file://manifest.yml @my_app_package.my_stage/v1 OVERWRITE=TRUE AUTO_COMPRESS=FALSE;
PUT file://setup.sql @my_app_package.my_stage/v1 OVERWRITE=TRUE AUTO_COMPRESS=FALSE;
PUT file://streamlit/app.py @my_app_package.my_stage/v1/streamlit OVERWRITE=TRUE AUTO_COMPRESS=FALSE;

ALTER APPLICATION PACKAGE my_app_package ADD VERSION v1 USING '@my_app_package.my_stage/v1';
```

**Step 6: Test locally:**
```sql
CREATE APPLICATION my_test_app FROM APPLICATION PACKAGE my_app_package USING VERSION v1;
```

**Step 7: Share via private listing** (in Snowsight: Data Products > Listings > Create Listing > select "Private" > add the application package as the data product > specify the target account).

**Must-have scoring elements:**
- [ ] Shows creating an application package
- [ ] Includes a manifest file and setup script
- [ ] Shows the Streamlit app code
- [ ] Mentions private listing for sharing

---

## Q43. What are Snowflake streams and tasks, and how do they work together for continuous data pipelines?

**Type:** Explain | **Doc:** [Streams and Tasks Intro](https://docs.snowflake.com/en/user-guide/data-pipelines-intro)

**Canonical Answer:**

**Streams** record DML changes (inserts, updates, deletes) made to tables, providing change data capture (CDC) at the row level. A stream tracks an offset in the table's version history and returns the changes between that offset and the current version.

**Tasks** run SQL statements (including stored procedure calls) on a schedule or based on a trigger. Tasks can be chained into directed acyclic graphs (DAGs) for complex processing.

**How they work together:**
1. Data is loaded into a staging table (via Snowpipe, COPY INTO, etc.)
2. A stream on the staging table captures new/changed rows
3. A task checks `SYSTEM$STREAM_HAS_DATA` and, if there is new data, processes the changes
4. The task's DML statement consumes the stream (advancing its offset)

**Stream metadata columns:**
- `METADATA$ACTION` — INSERT or DELETE
- `METADATA$ISUPDATE` — TRUE if the change is part of an UPDATE (represented as DELETE + INSERT pair)
- `METADATA$ROW_ID` — Unique, immutable row identifier

**Key behaviors:**
- Querying a stream does not advance the offset; only DML consumption does
- Streams support repeatable read isolation within a transaction
- A stream provides the minimal set of net changes (not every intermediate state)

**Must-have scoring elements:**
- [ ] Defines streams as CDC (change data capture) mechanism
- [ ] Defines tasks as scheduled SQL execution
- [ ] Explains the combined pattern (stream captures changes, task processes them)
- [ ] Mentions SYSTEM$STREAM_HAS_DATA for conditional execution

---

## Q44. Write SQL to create a stream on a staging table and a task that processes new rows every 5 minutes using a stored procedure.

**Type:** Implement | **Doc:** [Create Streams](https://docs.snowflake.com/en/user-guide/streams-intro)

**Canonical Answer:**

```sql
-- Create the stream on the staging table
CREATE OR REPLACE STREAM staging_stream ON TABLE staging_table;

-- Create the task that runs every 5 minutes
CREATE OR REPLACE TASK process_staging_task
    WAREHOUSE = transform_wh
    SCHEDULE = '5 MINUTE'
    WHEN SYSTEM$STREAM_HAS_DATA('staging_stream')
AS
    CALL process_new_data();

-- The stored procedure consumes the stream
CREATE OR REPLACE PROCEDURE process_new_data()
RETURNS STRING
LANGUAGE SQL
AS
BEGIN
    INSERT INTO target_table (id, name, amount, loaded_at)
    SELECT id, name, amount, CURRENT_TIMESTAMP()
    FROM staging_stream
    WHERE METADATA$ACTION = 'INSERT';

    RETURN 'Processed new rows';
END;

-- Resume the task (tasks are created in suspended state)
ALTER TASK process_staging_task RESUME;
```

Key points:
- `WHEN SYSTEM$STREAM_HAS_DATA('staging_stream')` ensures the task only runs when there are new changes (saving compute cost)
- Tasks are created in a **suspended** state; you must `ALTER TASK ... RESUME` to activate
- The stream offset advances when the DML in the stored procedure commits
- For task DAGs, use `AFTER` clause: `CREATE TASK child_task ... AFTER parent_task AS ...`

**Must-have scoring elements:**
- [ ] Shows CREATE STREAM on a table
- [ ] Shows CREATE TASK with SCHEDULE and WHEN clause
- [ ] Uses SYSTEM$STREAM_HAS_DATA for conditional execution
- [ ] Shows ALTER TASK RESUME (tasks start suspended)

---

## Q45. When should I use streams/tasks vs. Dynamic Tables for data transformation pipelines?

**Type:** Compare | **Doc:** [Dynamic Tables vs. Streams/Tasks](https://docs.snowflake.com/en/user-guide/dynamic-tables-about#when-to-use-dynamic-tables)

**Canonical Answer:**

| Aspect | Dynamic Tables | Streams + Tasks |
|--------|---------------|-----------------|
| **Paradigm** | Declarative (define the query, Snowflake manages refresh) | Imperative (you write the CDC logic and scheduling) |
| **Scheduling** | Target lag (Snowflake decides timing) | Explicit cron/interval schedules |
| **Pipeline complexity** | Chain DTs; Snowflake manages DAG ordering | Build task DAGs manually with AFTER clauses |
| **Incremental logic** | Automatic (when supported) | Manual via stream metadata columns |
| **Procedural logic** | SQL queries only | Can call stored procedures (any logic) |
| **Fine-grained control** | Limited (target lag only) | Full control (exact timing, conditional logic) |

**Use Dynamic Tables when:**
- You want to materialize query results without custom code
- You do not need fine-grained control over refresh schedules
- You want to chain multiple transformations declaratively
- Your transformations can be expressed as SQL queries

**Use Streams/Tasks when:**
- You need precise scheduling (exact cron times)
- You need procedural logic (stored procedures, conditionals)
- You need to execute arbitrary actions on change events
- You need fine-grained control over what happens at each step

**Must-have scoring elements:**
- [ ] Frames DTs as declarative vs. streams/tasks as imperative
- [ ] Notes DTs use target lag while tasks use explicit schedules
- [ ] Highlights that DTs manage incremental logic automatically
- [ ] Notes tasks can call stored procedures (arbitrary logic)

---

## Q46. How do I create a masking policy in Snowflake that masks email addresses for non-privileged roles?

**Type:** Implement | **Doc:** [Column-Level Security](https://docs.snowflake.com/en/user-guide/security-column-intro)

**Canonical Answer:**

```sql
-- Step 1: Create the masking policy
CREATE OR REPLACE MASKING POLICY email_mask AS (val STRING)
RETURNS STRING ->
    CASE
        WHEN CURRENT_ROLE() IN ('DATA_ADMIN', 'SUPPORT')
            THEN val
        ELSE REGEXP_REPLACE(val, '.+@', '***@')
    END;

-- Step 2: Apply the policy to a column
ALTER TABLE customers MODIFY COLUMN email SET MASKING POLICY email_mask;

-- Step 3: Verify
-- As DATA_ADMIN role: sees full email
-- As ANALYST role: sees ***@domain.com
```

Key points:
- A masking policy is a **schema-level object** that evaluates at **query time** (dynamic masking, not static)
- The policy does not modify underlying data; it transforms output based on conditions
- Supports **segregation of duties**: policy admins can restrict access even from object owners
- Policies can use context functions: `CURRENT_ROLE()`, `INVOKER_ROLE()`, `IS_ROLE_IN_SESSION()`
- One policy can be applied to many columns (any column with matching data type)
- **Conditional masking** can reference other columns: `CREATE MASKING POLICY ... AS (email VARCHAR, visibility STRING) RETURNS VARCHAR -> ...`

To update a policy without unassigning it:
```sql
ALTER MASKING POLICY email_mask SET BODY ->
    CASE
        WHEN CURRENT_ROLE() IN ('DATA_ADMIN') THEN val
        ELSE '***REDACTED***'
    END;
```

**Must-have scoring elements:**
- [ ] Uses CREATE MASKING POLICY with correct AS/RETURNS syntax
- [ ] Shows CASE expression with CURRENT_ROLE() check
- [ ] Shows ALTER TABLE to apply the policy to a column
- [ ] Notes policies evaluate at query time (dynamic, not static)

---

## Q47. What is Snowflake's data classification feature and how do I use it to detect PII in my tables?

**Type:** Explain | **Doc:** [Data Classification](https://docs.snowflake.com/en/user-guide/classify-intro)

**Canonical Answer:**

Snowflake's sensitive data classification automatically discovers columns containing sensitive data and assigns two categories:

1. **Semantic category** — Identifies the type of personal attribute (e.g., NAME, EMAIL, PHONE_NUMBER, US_SSN). Snowflake provides native categories; you can also create custom categories.

2. **Privacy category** — Identifies sensitivity level: IDENTIFIER, QUASI_IDENTIFIER, or SENSITIVE.

**How it works:**
- Classification uses system-defined tags: `SNOWFLAKE.CORE.SEMANTIC_CATEGORY` and `SNOWFLAKE.CORE.PRIVACY_CATEGORY`
- You set up classification via the Trust Center in Snowsight or via SQL
- Settings are saved as a **classification profile** that controls which databases are monitored
- Classification runs automatically on a schedule using serverless compute

**Setting up via SQL:**
```sql
-- Classify a specific table manually
SELECT SYSTEM$CLASSIFY('my_db.my_schema.my_table');

-- View classification results
SELECT *
FROM TABLE(
    my_db.INFORMATION_SCHEMA.TAG_REFERENCES(
        'my_db.my_schema.my_table',
        'TABLE'
    )
)
WHERE TAG_NAME IN ('SEMANTIC_CATEGORY', 'PRIVACY_CATEGORY');
```

**Protecting classified data:**
- Assign masking policies to columns classified as sensitive
- Use **tag-based masking** to automatically mask columns when classification tags are applied
- As new data arrives, tag-based masking policies are automatically applied to newly classified columns

**Supported objects:** Snowflake tables, external tables, Iceberg tables, dynamic tables, event tables, views, materialized views, secure views.

**Must-have scoring elements:**
- [ ] Explains semantic category and privacy category distinction
- [ ] Mentions SYSTEM$CLASSIFY or Trust Center for running classification
- [ ] Describes automatic discovery (not manual column-by-column)
- [ ] Notes tag-based masking as a way to automatically protect classified data

---

## Q48. How does Snowflake's architecture separate storage, compute, and services, and why does that matter for scaling?

**Type:** Explain | **Doc:** [Snowflake Architecture](https://docs.snowflake.com/en/user-guide/intro-key-concepts)

**Canonical Answer:**

Snowflake's architecture is a hybrid of shared-disk and shared-nothing designs with three independent layers:

**1. Database Storage Layer**
- Stores all data in a central repository accessible from all compute nodes
- Data is reorganized into an internally optimized, compressed, columnar format (micro-partitions)
- Snowflake manages organization, file size, structure, compression, metadata, and statistics
- Supports structured data (tables), semi-structured (JSON, Avro, Parquet), and unstructured data (via FILE type)
- Also supports Iceberg tables (external storage) and hybrid tables (low-latency OLTP)

**2. Compute Layer (Virtual Warehouses)**
- Independent compute clusters that process queries using MPP (massively parallel processing)
- Each warehouse is a separate cluster that does not share resources with other warehouses
- Warehouses can be started, stopped, and resized independently, even while running
- No impact between warehouses (workload isolation)

**3. Cloud Services Layer**
- Coordinates all activities: authentication, access control, query parsing and optimization, metadata management, infrastructure management
- Runs on Snowflake-provisioned compute instances
- Includes the Snowflake Horizon Catalog and Information Schema

**Why separation matters for scaling:**
- **Independent scaling** — Scale compute without affecting storage (and vice versa). Add warehouses for more concurrency without duplicating data.
- **Workload isolation** — Different teams/workloads use separate warehouses with no resource contention.
- **Pay-per-use** — Compute charges only when warehouses are running. Storage charges based on data stored. No idle compute cost when warehouses are suspended.
- **Instant elasticity** — Resize a warehouse or add clusters in seconds, no data redistribution needed.

**Must-have scoring elements:**
- [ ] Names all three layers: storage, compute, cloud services
- [ ] Explains independent scaling of compute and storage
- [ ] Mentions workload isolation between warehouses
- [ ] Notes pay-per-use / no idle compute cost

---

## Q49. What is the difference between a standard virtual warehouse, a multi-cluster warehouse, and the Query Acceleration Service?

**Type:** Compare | **Doc:** [Warehouses Overview](https://docs.snowflake.com/en/user-guide/warehouses-overview)

**Canonical Answer:**

| Feature | Standard Warehouse | Multi-cluster Warehouse | Query Acceleration Service (QAS) |
|---------|-------------------|------------------------|----------------------------------|
| **What it is** | Single compute cluster | Auto-scaling group of clusters | Offloads portions of queries to shared compute |
| **Scaling** | Manual resize (XS to 6XL) | Auto-adds/removes clusters based on concurrency | Automatic, no config needed (enable per warehouse) |
| **Solves** | General query processing | Concurrency scaling (many users/queries) | Large scan-heavy queries with selective filters |
| **Billing** | Credits based on size and runtime | Credits x number of active clusters | Separate QAS credit consumption |
| **Edition** | All editions | Enterprise Edition+ | Enterprise Edition+ |

**Standard warehouse:**
- Sizes range from X-Small (1 credit/hr) to 6X-Large (512 credits/hr), with doubling at each tier
- Per-second billing with 60-second minimum
- Auto-suspend (stop when idle) and auto-resume (start when queried)
- Default for most workloads

**Multi-cluster warehouse:**
- Scales out by adding identical clusters (not scaling up the cluster size)
- Set MIN_CLUSTERS and MAX_CLUSTERS; Snowflake auto-manages within the range
- Ideal for high concurrency (many users submitting queries simultaneously)
- Auto-suspend applies only when minimum clusters are running and idle

**Query Acceleration Service:**
- Offloads portions of eligible queries to shared Snowflake-managed compute
- Best for queries that scan large amounts of data but filter down to small results
- Does not require resizing the warehouse
- Controlled by a scale factor parameter

**Must-have scoring elements:**
- [ ] Distinguishes standard (single cluster) from multi-cluster (auto-scaling clusters)
- [ ] Explains QAS as offloading to shared compute
- [ ] Notes multi-cluster and QAS require Enterprise Edition
- [ ] Gives guidance on when to use each

---

## Q50. How does Snowflake Time Travel work and how do I recover a dropped table or query data as it existed at a past point in time?

**Type:** Implement | **Doc:** [Time Travel](https://docs.snowflake.com/en/user-guide/data-time-travel)

**Canonical Answer:**

Time Travel lets you access historical data (changed or deleted) within a configurable retention period.

**Query historical data:**

```sql
-- By timestamp
SELECT * FROM my_table AT(TIMESTAMP => '2026-04-01 12:00:00'::TIMESTAMP);

-- By time offset (300 seconds ago)
SELECT * FROM my_table AT(OFFSET => -300);

-- By query ID (see data as it was before a specific query ran)
SELECT * FROM my_table BEFORE(STATEMENT => '01abc123-0000-0000-0000-000000000001');
```

**Recover a dropped table:**

```sql
-- Drop a table (accidentally)
DROP TABLE important_data;

-- Recover it
UNDROP TABLE important_data;
```

**Clone data from a past point:**

```sql
CREATE TABLE my_table_backup CLONE my_table AT(TIMESTAMP => '2026-04-01 12:00:00'::TIMESTAMP);
```

**UNDROP** also works for schemas, databases, accounts, external volumes, and tags.

**Retention period:**
- Default: 1 day (24 hours) for all editions
- Enterprise Edition+: configurable up to 90 days for permanent objects via `DATA_RETENTION_TIME_IN_DAYS`
- Transient and temporary tables: 0 or 1 day only
- After retention expires, data moves to Fail-safe (7 days, Snowflake-managed recovery only)

```sql
-- Set retention to 90 days
ALTER TABLE my_table SET DATA_RETENTION_TIME_IN_DAYS = 90;

-- Set account-level minimum
ALTER ACCOUNT SET MIN_DATA_RETENTION_TIME_IN_DAYS = 7;
```

**Must-have scoring elements:**
- [ ] Shows AT/BEFORE clause syntax for querying historical data
- [ ] Shows UNDROP TABLE for recovery
- [ ] Shows CLONE with AT for point-in-time backup
- [ ] Explains retention period (default 1 day, up to 90 on Enterprise)
