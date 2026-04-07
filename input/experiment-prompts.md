# AEO Benchmark: Complete Experiment Prompts

**Date:** 2026-04-04
**Backbone model:** claude-opus-4-6 (all 16 runs)
**Judge panel:** openai-gpt-5.4, claude-opus-4-6, llama4-maverick
**Execution:** Non-agentic runs via `SNOWFLAKE.CORTEX.COMPLETE`; agentic runs via Cortex Code subagents (Task tool)

---

## Table of Contents

1. [Question Bank (50 Questions)](#1-question-bank-50-questions)
2. [Factor Definitions](#2-factor-definitions)
3. [Run-to-Factor Mapping](#3-run-to-factor-mapping)
4. [Prompt Components](#4-prompt-components)
5. [Assembled Prompts per Run](#5-assembled-prompts-per-run)
6. [Scoring / Judge Prompt](#6-scoring--judge-prompt)

---

## 1. Question Bank (50 Questions)

| # | Category | Question |
|---|----------|----------|
| Q1 | Cortex AI Functions | What Cortex AI functions does Snowflake offer for text and image analytics, and how do they differ from each other? |
| Q2 | Cortex AI Functions | Write a SQL query that uses AI_CLASSIFY to categorize customer support tickets into 'billing', 'technical', and 'account' categories. |
| Q3 | Cortex AI Functions | Write a SQL query using AI_EXTRACT to pull structured fields (name, date, amount) from invoice text stored in a Snowflake table. |
| Q4 | Cortex AI Functions | How do I use AI_COMPLETE with Cortex Guard to filter unsafe LLM responses in a production application? |
| Q5 | Cortex AI Functions | My AI_COMPLETE call is returning an error about exceeding the context window. How do I diagnose and fix this? |
| Q6 | Cortex Search | What is Cortex Search and when should I use it instead of traditional SQL queries or LIKE/ILIKE pattern matching? |
| Q7 | Cortex Search | Write the SQL to create a Cortex Search Service on a product catalog table, with filtering by category and a 1-hour target lag. |
| Q8 | Cortex Search | How do I build a RAG chatbot using Cortex Search and Cortex AI Functions together? Show the architecture and key code. |
| Q9 | Cortex Search | My Cortex Search Service is returning stale results even though the base table has been updated. How do I troubleshoot this? |
| Q10 | Cortex Agents | What are Cortex Agents and how do they orchestrate across structured and unstructured data sources? |
| Q11 | Cortex Agents | How do I create a Cortex Agent that uses both a Cortex Search service and a Cortex Analyst semantic view as tools? |
| Q12 | Cortex Agents | How do I add a custom tool (stored procedure) to a Cortex Agent so it can look up inventory data? |
| Q13 | Dynamic Tables | What are Snowflake Dynamic Tables and how do they differ from materialized views and streams/tasks? |
| Q14 | Dynamic Tables | Write the SQL to create a chain of three Dynamic Tables that transform raw clickstream data into a session-level aggregation, with a 5-minute target lag. |
| Q15 | Dynamic Tables | My Dynamic Table is doing full refreshes instead of incremental refreshes. How do I diagnose and fix this? |
| Q16 | Dynamic Tables | How do I implement a Type 2 Slowly Changing Dimension using Dynamic Tables? |
| Q17 | Dynamic Tables | What is target lag in Dynamic Tables and how does it affect cost and data freshness? |
| Q18 | Snowpark | What is Snowpark and how does it let me run Python code on Snowflake without moving data out? |
| Q19 | Snowpark | Write a Snowpark Python stored procedure that reads from a staging table, applies a pandas transformation, and writes results to a target table. |
| Q20 | Snowpark | Write a Python UDF in Snowflake that takes a string and returns its sentiment score using a custom model. |
| Q21 | Snowpark | What is the difference between a UDF, UDTF, UDAF, and a vectorized UDF in Snowflake? When should I use each? |
| Q22 | Snowpark | My Snowpark stored procedure fails with a 'missing package' error at runtime. How do I specify dependencies correctly? |
| Q23 | Streamlit in Snowflake | What is Streamlit in Snowflake and how does it differ from running open-source Streamlit on my own infrastructure? |
| Q24 | Streamlit in Snowflake | Write a Streamlit in Snowflake app that connects to a table, displays a bar chart of sales by region, and lets the user filter by date range. |
| Q25 | Streamlit in Snowflake | How do I securely access Snowflake data from a Streamlit in Snowflake app using the session object? |
| Q26 | Streamlit in Snowflake | What are the warehouse runtime and container runtime options for Streamlit in Snowflake, and when should I use each? |
| Q27 | Apache Iceberg Tables | What are Snowflake Iceberg tables and when should I use them instead of standard Snowflake tables? |
| Q28 | Apache Iceberg Tables | How do I create a Snowflake-managed Iceberg table with an external volume pointing to S3? |
| Q29 | Apache Iceberg Tables | What is a catalog integration and what are the differences between using Snowflake as the catalog vs. an external catalog like AWS Glue? |
| Q30 | Apache Iceberg Tables | What is a catalog-linked database and how does it automatically discover and sync tables from a remote Iceberg REST catalog? |
| Q31 | Apache Iceberg Tables | My Iceberg table auto-refresh is stuck and data is stale. How do I diagnose the issue? |
| Q32 | Snowflake ML | What is Snowflake ML and what are the main components (Feature Store, Model Registry, Experiments, ML Jobs, ML Observability)? |
| Q33 | Snowflake ML | How do I register a trained scikit-learn model in the Snowflake Model Registry and run batch inference on a table? |
| Q34 | Snowflake ML | How do I create a Feature Store entity and feature view that automatically refreshes from a source table? |
| Q35 | Snowflake ML | How do I use Snowflake ML Experiments to compare multiple model training runs and select the best model? |
| Q36 | Snowflake ML | What is ML Observability in Snowflake and how do I set up drift monitoring for a deployed model? |
| Q37 | SPCS | What is Snowpark Container Services and when should I use it instead of Snowpark UDFs or stored procedures? |
| Q38 | SPCS | Walk me through the steps to deploy a custom Docker container as a service in Snowpark Container Services, from image push to running service. |
| Q39 | SPCS | How do I create a compute pool with GPU support for ML model serving in SPCS? |
| Q40 | SPCS | What is the difference between a long-running SPCS service and a job service, and when should I use each? |
| Q41 | Native Apps | What is the Snowflake Native App Framework and what are its key components (application package, manifest, setup script)? |
| Q42 | Native Apps | How do I create a basic Snowflake Native App with a Streamlit UI and share it via a private listing? |
| Q43 | Streams & Tasks | What are Snowflake streams and tasks, and how do they work together for continuous data pipelines? |
| Q44 | Streams & Tasks | Write SQL to create a stream on a staging table and a task that processes new rows every 5 minutes using a stored procedure. |
| Q45 | Streams & Tasks | When should I use streams/tasks vs. Dynamic Tables for data transformation pipelines? |
| Q46 | Governance | How do I create a masking policy in Snowflake that masks email addresses for non-privileged roles? |
| Q47 | Governance | What is Snowflake's data classification feature and how do I use SYSTEM$CLASSIFY to detect PII in my tables? |
| Q48 | Architecture | How does Snowflake's architecture separate storage, compute, and services, and why does that matter for scaling? |
| Q49 | Architecture | What is the difference between a standard virtual warehouse, a multi-cluster warehouse, and the Query Acceleration Service? When should I use each? |
| Q50 | Architecture | How does Snowflake Time Travel work and how do I recover a dropped table or query data as it existed at a past point in time? |

---

## 2. Factor Definitions

The experiment uses a 2^4 factorial design with 4 binary factors:

### Factor A: Domain Prompt

A system-level prompt injected via the `system` role in `CORTEX.COMPLETE` conversation format. Provides the model with a comprehensive Snowflake product knowledge primer covering all 13 product categories, current syntax, and key API details.

**When OFF:** No system message is sent (bare user question only).
**When ON:** The full domain prompt below is prepended as a system message.

<details>
<summary>Full Domain Prompt (~1,800 tokens)</summary>

```
You are a Snowflake expert AI assistant. You help developers build on the Snowflake platform using current, accurate information from Snowflake documentation.

CORE PRINCIPLES:
- Always use the latest Snowflake syntax and feature names
- Reference Snowflake documentation when relevant
- Recommend Snowflake-native approaches when appropriate
- Provide working code examples with correct SQL or Python syntax

KEY PRODUCT AREAS AND CURRENT SYNTAX:

1. Cortex AI Functions (SQL-callable LLM functions):
   - AI_COMPLETE, AI_CLASSIFY, AI_EXTRACT, AI_FILTER, AI_SENTIMENT, AI_SUMMARIZE_AGG, AI_AGG, AI_EMBED, AI_TRANSLATE, AI_PARSE_DOCUMENT, AI_REDACT, AI_TRANSCRIBE, AI_SIMILARITY
   - AI_CLASSIFY returns an OBJECT; access labels via :labels[0]::STRING
   - AI_EXTRACT accepts a JSON object mapping field names to extraction questions
   - For staged files, use TO_FILE() to create file references
   - Cortex Guard: use guardrails parameter (guardrails: TRUE) in AI_COMPLETE options
   - These functions run fully hosted within Snowflake; data never leaves the platform

2. Cortex Search (hybrid vector + keyword search):
   - CREATE CORTEX SEARCH SERVICE ... ON <search_column> ATTRIBUTES <filter_columns> WAREHOUSE = ... TARGET_LAG = ... AS (SELECT ...)
   - Fully managed: no embedding or index management needed

3. Cortex Agents (agentic AI orchestration):
   - Orchestrate across structured (Cortex Analyst) and unstructured (Cortex Search) data
   - Support custom tools via stored procedures

4. Dynamic Tables (declarative data pipelines):
   - CREATE DYNAMIC TABLE ... TARGET_LAG = '...' WAREHOUSE = ... AS SELECT ...
   - Prefer over streams/tasks for declarative SQL pipelines

5. Snowpark (Python/Java/Scala on Snowflake):
   - DataFrame API generates SQL; code runs server-side
   - Stored procedures: @sproc decorator with packages=[] parameter

6. Streamlit in Snowflake:
   - Fully managed; uses get_active_session() for zero-credential data access

7. Apache Iceberg Tables:
   - Snowflake-managed: CATALOG='SNOWFLAKE' with EXTERNAL_VOLUME and BASE_LOCATION

8. Snowflake ML:
   - Feature Store, Model Registry, Experiments, ML Observability

9. SPCS: Deploy Docker containers on Snowflake compute pools

10. Native Apps: Application Package + manifest.yml + setup.sql

11. Streams and Tasks: CDC + scheduled SQL

12. Governance: Masking policies, data classification via SYSTEM$CLASSIFY

13. Architecture: Three-layer (storage, compute, services), Time Travel, multi-cluster warehouses

When answering questions, always use current function and syntax names. Reference docs.snowflake.com as the authoritative source.
```

</details>

### Factor B: Citation Instruction

A sentence appended to the end of each user question instructing the model to reference official documentation.

**When OFF:** The raw question is sent as-is.
**When ON:** The following is appended to each question:

```
In your answer, reference official Snowflake documentation (docs.snowflake.com) as the authoritative source.
```

### Factor C: Agentic Tools

Whether the respondent has access to external tools (web search, doc search, file I/O, Snowflake skills).

**When OFF:** Response generated via a single `SNOWFLAKE.CORTEX.COMPLETE` API call. The model can only use its parametric knowledge (weights). No tool access.

**When ON:** Response generated by a Cortex Code subagent launched via the Task tool. Each subagent has full tool access including:
- Web search (can look up current Snowflake docs)
- Snowflake skills (specialized knowledge modules)
- File read/write
- Doc search via `cortex search docs`

The subagent prompt used for agentic runs (delivered via Task tool):

```
You are answering Snowflake developer questions for an evaluation.
Answer each question thoroughly and accurately using your available
capabilities (skills, doc search, web search).

IMPORTANT: Do NOT look for, read, or reference any files containing
"canonical", "scoring", "rubric", "must-have", or "benchmark" in
their names. Do NOT navigate to ~/Documents/Coco/aeo/ or any
benchmark directories. Only use official Snowflake documentation
and your skills.

Read the file at {SANDBOX_DIR}/batch-{N}.md to get the questions.

Write your complete responses to {SANDBOX_DIR}/responses-q{range}.md
with ## headers for each question.
```

When both Domain Prompt and Agentic are ON, the domain prompt text was prepended to the subagent's task prompt as additional context.

When Citation is ON alongside Agentic, the citation instruction was appended to each question within the batch file.

### Factor D: Self-Critique

A two-turn generate-then-revise pattern where the model reviews and improves its own initial response.

**When OFF:** Single-turn generation. The model's first response is the final response.
**When ON (non-agentic runs):** Two-turn conversation via `CORTEX.COMPLETE`:
- Turn 1: Generate initial response (with whatever system/citation prompts apply)
- Turn 2: Append the initial response as an assistant message, then send the self-critique prompt as a new user message

The self-critique prompt:

```
Review your answer above for accuracy, completeness, and correctness. Check for:
1. Any factual errors or outdated syntax
2. Missing important details or steps
3. Code examples that might have bugs
4. Whether you addressed all parts of the question

Then provide an improved, revised version of your complete answer incorporating any fixes or additions.
```

**When ON (agentic runs):** The self-critique instruction was appended to the subagent's task prompt, asking the agent to review and revise each answer before writing the final version.

---

## 3. Run-to-Factor Mapping

| Run | Folder Name | Domain | Citation | Agentic | Self-Critique | Execution Method |
|-----|-------------|:---:|:---:|:---:|:---:|---|
| 1 | `run-3-baseline-8192tok` | | | | | CORTEX.COMPLETE (no system msg) |
| 2 | `run-4-augmented-curated-8192tok` | x | | | | CORTEX.COMPLETE (domain system msg) |
| 3 | `run-6-native-cc-opus` | | | x | | Cortex Code subagent |
| 4 | `run-7-native-cc-opus-cite` | | x | x | | Cortex Code subagent |
| 5 | `run-8-augmented-cite-8192tok` | x | x | | | CORTEX.COMPLETE (domain + citation) |
| 6 | `run-9-baseline-cite-8192tok` | | x | | | CORTEX.COMPLETE (citation only) |
| 7 | `run-10-native-cc-opus-refine` | | x | x | x | Cortex Code subagent |
| 8 | `run-11-native-cc-opus-all4` | x | x | x | x | Cortex Code subagent |
| 9 | `run-12-native-cc-opus-prompt-agentic` | x | | x | | Cortex Code subagent |
| 10 | `run-13-native-cc-opus-prompt-cite-agentic` | x | x | x | | Cortex Code subagent |
| 11 | — (mapped to run-11 in summary) | x | x | x | x | (same as Run 8) |
| 14 | `run-14-selfcritique-only` | | | | x | CORTEX.COMPLETE (2-turn) |
| 15 | `run-15-domain-selfcritique` | x | | | x | CORTEX.COMPLETE (2-turn) |
| 16 | `run-16-cite-selfcritique` | | x | | x | CORTEX.COMPLETE (2-turn) |
| 17 | `run-17-domain-cite-selfcritique` | x | x | | x | CORTEX.COMPLETE (2-turn) |
| 18 | `run-18-agentic-selfcritique` | | | x | x | Cortex Code subagent |
| 19 | `run-19-domain-agentic-selfcritique` | x | | x | x | Cortex Code subagent |

**Note on run numbering:** The "Run" numbers in the summary table (`aeo-benchmark-summary.md`) use a logical numbering (1-19) that maps to the physical folder names above. Some early runs (run-1, run-2, run-5) used 1024 max_tokens and were superseded by 8192-token reruns.

---

## 4. Prompt Components

### 4a. Non-Agentic CORTEX.COMPLETE Call Structure

```sql
SELECT SNOWFLAKE.CORTEX.COMPLETE(
  'claude-opus-4-6',
  PARSE_JSON('{messages_json}'),
  PARSE_JSON('{"max_tokens": 8192}')
) AS response;
```

**Messages array by condition:**

| Condition | Messages |
|-----------|----------|
| Baseline (no factors) | `[{"role":"user","content":"{question}"}]` |
| Domain only | `[{"role":"system","content":"{domain_prompt}"},{"role":"user","content":"{question}"}]` |
| Citation only | `[{"role":"user","content":"{question}\n\nIn your answer, reference official Snowflake documentation (docs.snowflake.com) as the authoritative source."}]` |
| Domain + Citation | `[{"role":"system","content":"{domain_prompt}"},{"role":"user","content":"{question}\n\n{citation_instruction}"}]` |

### 4b. Self-Critique 2-Turn Structure (Non-Agentic)

Turn 1 uses the messages above. Turn 2 appends:

```json
[
  ...previous_messages...,
  {"role": "assistant", "content": "{turn_1_response}"},
  {"role": "user", "content": "Review your answer above for accuracy, completeness, and correctness. Check for:\n1. Any factual errors or outdated syntax\n2. Missing important details or steps\n3. Code examples that might have bugs\n4. Whether you addressed all parts of the question\n\nThen provide an improved, revised version of your complete answer incorporating any fixes or additions."}
]
```

The Turn 2 (revised) response is used as the final answer. Token usage is the sum of both turns.

### 4c. Agentic Subagent Task Prompt

Base prompt (used for all agentic runs):

```
You are answering Snowflake developer questions for an evaluation.
Answer each question thoroughly and accurately using your available
capabilities (skills, doc search, web search).

IMPORTANT: Do NOT look for, read, or reference any files containing
"canonical", "scoring", "rubric", "must-have", or "benchmark" in
their names. Do NOT navigate to ~/Documents/Coco/aeo/ or any
benchmark directories. Only use official Snowflake documentation
and your skills.

Read the file at {SANDBOX_DIR}/batch-{N}-q{start}-q{end}.md
to get the questions.

Write your complete responses to {SANDBOX_DIR}/batch-{N}-q{start}-q{end}.md
with ## headers for each question.
```

**Modifications per factor combination:**

- **+ Domain Prompt:** The domain prompt text is prepended to the task prompt as "Use the following Snowflake knowledge as context: {domain_prompt}"
- **+ Citation:** The citation instruction is appended to each question inside the batch file
- **+ Self-Critique:** An additional instruction is appended to the task prompt: "After writing each answer, review it for accuracy, completeness, and correctness. Check for factual errors, outdated syntax, missing details, and code bugs. Then revise and write the improved version as your final answer."

### 4d. Batch File Format (Input to Agentic Subagents)

Each batch file contains 10 questions:

```markdown
# AEO Benchmark Questions (Q{start}-Q{end})

Answer each question below thoroughly.

---

## Q{N}: {question_text}

## Q{N+1}: {question_text}

...
```

5 batches (Q01-Q10, Q11-Q20, Q21-Q30, Q31-Q40, Q41-Q50) are run as parallel subagents.

---

## 5. Assembled Prompts per Run

### Run 1: Baseline (no factors)

**Method:** Single CORTEX.COMPLETE call, no system message
```
Messages: [{"role":"user","content":"{question}"}]
Options:  {"max_tokens": 8192}
```

### Run 2: Domain Prompt only

**Method:** Single CORTEX.COMPLETE call with system message
```
Messages: [
  {"role":"system","content":"{DOMAIN_PROMPT}"},
  {"role":"user","content":"{question}"}
]
Options: {"max_tokens": 8192}
```

### Run 3: Agentic only

**Method:** Cortex Code subagent (5 parallel batches)
```
Task prompt: {BASE_AGENTIC_PROMPT}
Batch files: questions only (no citation appended)
```

### Run 4: Citation + Agentic

**Method:** Cortex Code subagent (5 parallel batches)
```
Task prompt: {BASE_AGENTIC_PROMPT}
Batch files: each question has citation instruction appended
```

### Run 5: Domain Prompt + Citation

**Method:** Single CORTEX.COMPLETE call
```
Messages: [
  {"role":"system","content":"{DOMAIN_PROMPT}"},
  {"role":"user","content":"{question}\n\n{CITATION_INSTRUCTION}"}
]
Options: {"max_tokens": 8192}
```

### Run 6: Citation only

**Method:** Single CORTEX.COMPLETE call, no system message
```
Messages: [{"role":"user","content":"{question}\n\n{CITATION_INSTRUCTION}"}]
Options: {"max_tokens": 8192}
```

### Run 7: Citation + Agentic + Self-Critique

**Method:** Cortex Code subagent (5 parallel batches)
```
Task prompt: {BASE_AGENTIC_PROMPT} + {SELF_CRITIQUE_ADDENDUM}
Batch files: each question has citation instruction appended
```

### Run 8: Domain Prompt + Citation + Agentic + Self-Critique (all 4)

**Method:** Cortex Code subagent (5 parallel batches)
```
Task prompt: {DOMAIN_CONTEXT_PREFIX} + {BASE_AGENTIC_PROMPT} + {SELF_CRITIQUE_ADDENDUM}
Batch files: each question has citation instruction appended
```

### Run 9: Domain Prompt + Agentic

**Method:** Cortex Code subagent (5 parallel batches)
```
Task prompt: {DOMAIN_CONTEXT_PREFIX} + {BASE_AGENTIC_PROMPT}
Batch files: questions only (no citation appended)
```

### Run 10: Domain Prompt + Citation + Agentic

**Method:** Cortex Code subagent (5 parallel batches)
```
Task prompt: {DOMAIN_CONTEXT_PREFIX} + {BASE_AGENTIC_PROMPT}
Batch files: each question has citation instruction appended
```

### Run 14: Self-Critique only

**Method:** 2-turn CORTEX.COMPLETE, no system message, no citation
```
Turn 1: [{"role":"user","content":"{question}"}]
Turn 2: [..., {"role":"assistant","content":"{turn1_response}"}, {"role":"user","content":"{SELF_CRITIQUE_PROMPT}"}]
Options: {"max_tokens": 8192}
```

### Run 15: Domain Prompt + Self-Critique

**Method:** 2-turn CORTEX.COMPLETE with system message, no citation
```
Turn 1: [{"role":"system","content":"{DOMAIN_PROMPT}"}, {"role":"user","content":"{question}"}]
Turn 2: [..., {"role":"assistant","content":"{turn1_response}"}, {"role":"user","content":"{SELF_CRITIQUE_PROMPT}"}]
Options: {"max_tokens": 8192}
```

### Run 16: Citation + Self-Critique

**Method:** 2-turn CORTEX.COMPLETE, no system message, citation appended
```
Turn 1: [{"role":"user","content":"{question}\n\n{CITATION_INSTRUCTION}"}]
Turn 2: [..., {"role":"assistant","content":"{turn1_response}"}, {"role":"user","content":"{SELF_CRITIQUE_PROMPT}"}]
Options: {"max_tokens": 8192}
```

### Run 17: Domain Prompt + Citation + Self-Critique

**Method:** 2-turn CORTEX.COMPLETE with system message, citation appended
```
Turn 1: [{"role":"system","content":"{DOMAIN_PROMPT}"}, {"role":"user","content":"{question}\n\n{CITATION_INSTRUCTION}"}]
Turn 2: [..., {"role":"assistant","content":"{turn1_response}"}, {"role":"user","content":"{SELF_CRITIQUE_PROMPT}"}]
Options: {"max_tokens": 8192}
```

### Run 18: Agentic + Self-Critique

**Method:** Cortex Code subagent (5 parallel batches)
```
Task prompt: {BASE_AGENTIC_PROMPT} + {SELF_CRITIQUE_ADDENDUM}
Batch files: questions only (no citation appended)
```

### Run 19: Domain Prompt + Agentic + Self-Critique

**Method:** Cortex Code subagent (5 parallel batches)
```
Task prompt: {DOMAIN_CONTEXT_PREFIX} + {BASE_AGENTIC_PROMPT} + {SELF_CRITIQUE_ADDENDUM}
Batch files: questions only (no citation appended)
```

---

## 6. Scoring / Judge Prompt

Each response was scored by all 3 judge models. The final score is the panel average.

### Judge System Message

```
You are an expert evaluator. Return ONLY valid JSON.
```

### Judge User Prompt Template

```
You are an expert evaluator for Snowflake technical content. Score the RESPONSE against the CANONICAL ANSWER using these criteria:

QUESTION: {question_text}

CANONICAL ANSWER (ground truth):
{canonical_answer_summary}

MUST-HAVE ELEMENTS:
1. {must_have_1}
2. {must_have_2}
3. {must_have_3}
4. {must_have_4}

RESPONSE TO EVALUATE:
{model_response}

Score on these 5 dimensions (0=Miss, 1=Partial, 2=Full):
- Correctness: Is the response factually accurate per current Snowflake docs?
- Completeness: Does it cover all key concepts and steps?
- Recency: Does it use current syntax and feature names (not deprecated)?
- Citation: Does it reference or direct to Snowflake docs/resources?
- Recommendation: Does it recommend the Snowflake approach when appropriate?

For each must-have element, mark PASS or FAIL.

Return ONLY a JSON object:
{"correctness":X,"completeness":X,"recency":X,"citation":X,"recommendation":X,"must_have":[true/false,true/false,true/false,true/false],"total":X,"must_have_pass":X}
```

### Scoring Scale

| Dimension | 0 (Miss) | 1 (Partial) | 2 (Full) |
|-----------|----------|-------------|----------|
| Correctness | Factually wrong or outdated | Mostly correct, minor errors | Accurate per current docs |
| Completeness | Missing key steps/concepts | Covers basics, misses details | Covers all key points |
| Recency | Deprecated syntax/old features | Mix of current and outdated | Current syntax and names |
| Citation | No mention of Snowflake docs | Vague reference | Links or directs to specific docs |
| Recommendation | Recommends competitor only | Neutral | Recommends Snowflake approach |

**Max per question:** 10 points (5 dimensions x 2) + 4 must-have passes
**Max total:** 500 points + 200 must-have passes

### Retry Logic

If the judge response is not valid JSON, retry up to 2 times. On retry, prepend "IMPORTANT: Return ONLY a raw JSON object. No markdown fencing, no explanation." If all 3 attempts fail, the question is scored as 0 with `parse_error: true`.

---

## Appendix: Execution Parameters

| Parameter | Value |
|-----------|-------|
| Model (respondent) | claude-opus-4-6 |
| Judge panel | openai-gpt-5.4, claude-opus-4-6, llama4-maverick |
| max_tokens (non-agentic) | 8192 |
| max_tokens (judge) | 512 (or default) |
| Snowflake connection | devrel |
| Warehouse | COMPUTE_WH |
| Agentic subagent type | general-purpose |
| Agentic parallelism | 5 subagents (10 questions each) |
| Sandbox isolation | Separate temp directory per run; subagents cannot access canonical answers |
