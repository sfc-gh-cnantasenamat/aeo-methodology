---
# AEO Benchmark: Methodology

---
# The Question

What makes an AI assistant give **better answers** to developer questions?

- More instructions? Bigger system prompts?
- Access to tools and documentation?
- Self-review and revision loops?
- All of the above?

We built a controlled experiment to find out.

---
# What is AEO?

**AI Engine Optimization** — a benchmark for scoring AI assistants on real Snowflake developer questions.

- **50 questions** across 15 product categories
- Categories include Cortex AI, Dynamic Tables, Iceberg, Snowpark, Security, Data Sharing, and more
- Each question has a **canonical answer** with required **facts checklist**
- Questions range from basic SQL to multi-step architecture design

---
# Question Bank Excerpt

```
+-----+-----------+--------------------------------------------------------------------------------+
| Q#  | Type      | Question                                                                       |
+-----+-----------+--------------------------------------------------------------------------------+
| Q1  | Explain   | What Cortex AI functions does Snowflake offer for text and image analytics,    |
|     |           | and how do they differ from each other?                                        |
| Q7  | Implement | Write the SQL to create a Cortex Search Service on a product catalog table,    |
|     |           | with filtering by category and a 1-hour target lag.                            |
| Q15 | Debug     | My Dynamic Table is doing full refreshes instead of incremental. How do I      |
|     |           | diagnose and fix this?                                                         |
| Q21 | Compare   | What is the difference between a UDF, UDTF, UDAF, and a vectorized UDF in      |
|     |           | Snowflake? When should I use each?                                             |
| Q48 | Explain   | How does Snowflake's architecture separate storage, compute, and services,     |
|     |           | and why does that matter for scaling?                                          |
+-----+-----------+--------------------------------------------------------------------------------+
```

50 questions, 15 categories, 4 types: **Explain**, **Implement**, **Debug**, **Compare**

---
# Scoring System

## Five Dimensions (0–2 points each, max 10 points per question)

```
+----------------+------------------------------------------+
| Dimension      | What It Measures                         |
+----------------+------------------------------------------+
| Correctness    | Are the facts and code accurate?         |
| Completeness   | Does it cover the full answer?           |
| Recency        | Does it reflect current features/syntax? |
| Citation       | Does it reference official docs?         |
| Recommendation | Does it suggest Snowflake-native paths?  |
+----------------+------------------------------------------+
```

- Each dimension scored **0** (miss), **1** (partial), or **2** (full)
- **Score:** panel average across all 5 dimensions

---
# Must-Have Facts

Beyond the 5 dimensions, each question defines **4 must-have facts** in the canonical answer:

- **Binary pass/fail** per fact: present or absent in the response
- **200 total** fact checks across 50 questions
- Tests critical technical details: correct function names, required syntax, key caveats, important distinctions
- Defined **before** any model is evaluated
- Scored independently from the 5 rubric dimensions

> Example: "Lists at least AI_COMPLETE, AI_CLASSIFY, AI_EXTRACT, AI_SENTIMENT, AI_EMBED, AI_TRANSLATE"

---
# The Judge Panel

Three independent LLM judges score every answer:

```
+-------------------+---------+
| Judge             | Role    |
+-------------------+---------+
| claude-opus-4-6   | Judge 1 |
| openai-gpt-5.4    | Judge 2 |
| llama4-maverick   | Judge 3 |
+-------------------+---------+
```

- Each judge scores independently using the same rubric
- Final score = **average of all three judges**
- Cross-model judging reduces single-model bias
- Judges never see each other's scores

---
# The Judge Prompt

Each judge receives this template, filled per question:

```
You are an expert evaluator for Snowflake technical content.
Score the RESPONSE against the CANONICAL ANSWER.

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

5 dimensions (0=Miss, 1=Partial, 2=Full):
Correctness, Completeness, Recency, Citation, Recommendation

For each must-have element, mark PASS or FAIL.
Return ONLY a JSON object.
```

- Judges return structured JSON (no prose)
- Same prompt for all 3 judges, retry up to 3x on parse failure

---
# The 4 Levers

We identified four interventions commonly used to improve AI answers:

```
+---------------+-----------------------------------------------+
| Lever         | What It Does                                  |
+---------------+-----------------------------------------------+
| Domain Prompt | ~1,800-token Snowflake expert persona         |
| Citation      | 'Reference official Snowflake docs' sentence  |
| Agentic Tools | Web search, bash, SQL, file I/O               |
| Self-Critique | Multi-turn review and revision loop           |
+---------------+-----------------------------------------------+
```

Each lever is either **ON** or **OFF** — giving us binary factors for a controlled experiment.

---
# Lever 1: Domain Prompt

A ~1,800-token system prompt that frames the model as a Snowflake expert:

> "You are a Snowflake data platform expert. Provide accurate, current answers with specific SQL or Python code examples when appropriate. Reference official Snowflake documentation as the authoritative source. Recommend Snowflake-native approaches when they exist."

- Generic, non-proprietary — no curated product knowledge
- Tests whether **role framing** alone improves answers
- Standard practice in most AI deployments

---
# Lever 2: Citation Instruction

A single sentence appended to each question:

> "In your answer, reference official Snowflake documentation (docs.snowflake.com) as the authoritative source."

- Not a system prompt, appended directly to the user question
- Creates a **retrieval objective**: look up docs before answering
- Minimal intervention, maximum signal
- Tests whether a nudge outperforms a detailed persona

---
# Lever 3: Agentic Tools

When ON, the model runs inside **Cortex Code** with access to:

- **Web search** — query docs.snowflake.com and the wider web
- **Bash shell** — run commands, install packages
- **SQL execution** — query Snowflake directly
- **File I/O** — read and write local files

When OFF, the model is a **single-turn CORTEX.COMPLETE call** with no tools, no memory, and a fixed 8192-token output limit.

This is the biggest architectural difference in the experiment.

---
# Lever 4: Self-Critique

A two-turn generate-then-revise protocol:

```
+------+----------------------------------------------+
| Turn | What Happens                                 |
+------+----------------------------------------------+
| 1    | Model answers the question normally          |
| 2    | Model is told: "Review your answer above     |
|      | for factual accuracy, completeness, and      |
|      | correctness against current Snowflake docs.  |
|      | Revise any answers that need improvement."   |
+------+----------------------------------------------+
```

- Questions are batched in groups of 10 for the review pass
- Tests whether **multi-turn self-reflection** catches errors
- Applied to both agentic and non-agentic conditions

---
# Two Execution Engines

All runs use **claude-opus-4-6** as the backbone model, but through two different engines:

```
+--------------+---------------------+--------+---------+
| Engine       | Method              | Tokens | Tools   |
+--------------+---------------------+--------+---------+
| Claude Opus  | CORTEX.COMPLETE     | 8192   | None    |
|              | (single-turn API)   |        |         |
+--------------+---------------------+--------+---------+
| Cortex Code  | Agentic multi-step  | No     | Web,    |
|              | (with tool use)     | limit  | bash,   |
|              |                     |        | SQL, IO |
+--------------+---------------------+--------+---------+
```

- Same underlying LLM isolates the effect of tooling
- **Non-agentic** = Claude Opus direct; **Agentic** = Cortex Code

---
# Non-Agentic Prompt Structure

Each non-agentic run is a single SQL call:

```
SELECT CORTEX.COMPLETE(
  'claude-opus-4-6',
  [system_msg, user_msg],
  {max_tokens: 8192}
);
```

- **Baseline:** user question only, no system message
- **+ Domain:** system message with expert persona
- **+ Citation:** instruction appended to user question
- **+ Self-Critique:** second turn reviews and revises
- All combinations assembled from these 4 components

---
# Agentic Prompt Structure

Each agentic run launches a **Cortex Code subagent** with this task prompt:

> "Answer each question thoroughly and accurately using your available capabilities (skills, doc search, web search)."

- 5 parallel subagents, 10 questions each
- **+ Domain:** expert persona prepended to task prompt
- **+ Citation:** instruction appended to each question in batch file
- **+ Self-Critique:** "Review and revise each answer before writing the final version"
- Subagents had **no access** to canonical answers or scoring rubric

---
# The 2⁴ Factorial Design

4 binary factors = **16 unique combinations**.

- A factorial design tests **every combination**, not just one-at-a-time
- This reveals **interaction effects** (when two factors together behave differently than expected)
  - Example: Domain Prompt might help alone but hurt when combined with Agentic Tools
- Without the full factorial, you would miss these interactions
- Each combination is a separate, independent run of all 50 questions

---
# All 16 Conditions

```
+----+--------+----------+---------+-------+
| #  | Domain | Citation | Agentic | SC    |
+----+--------+----------+---------+-------+
|  1 |        |          |         |       |
|  2 |   x    |          |         |       |
|  3 |        |    x     |         |       |
|  4 |        |          |    x    |       |
|  5 |        |          |         |   x   |
|  6 |   x    |    x     |         |       |
|  7 |   x    |          |    x    |       |
|  8 |   x    |          |         |   x   |
|  9 |        |    x     |    x    |       |
| 10 |        |    x     |         |   x   |
| 11 |        |          |    x    |   x   |
| 12 |   x    |    x     |    x    |       |
| 13 |   x    |    x     |         |   x   |
| 14 |   x    |          |    x    |   x   |
| 15 |        |    x     |    x    |   x   |
| 16 |   x    |    x     |    x    |   x   |
+----+--------+----------+---------+-------+
```

0 levers, then 1, 2, 3, and all 4 active.

---
# Cross-Model Baselines

To confirm lever effects generalize beyond one model, we also ran three LLMs in non-agentic conditions:

```
+-------------------+------+--------+------+----------+
| Model             | Base | Domain | Cite | Domain+Cite |
+-------------------+------+--------+------+----------+
| openai-gpt-5.4    | 57.5 |  72.5  | 81.8 |   80.4   |
| claude-opus-4-6   | 60.9 |  68.6  | 71.1 |   71.5   |
| llama4-maverick   | 38.4 |  65.2  | 66.2 |   63.9   |
+-------------------+------+--------+------+----------+
```

These 4 conditions per model provide **external validity** for the factorial results.

---
# Controls and Isolation

Strict controls ensure results are comparable:

- **No leaked answers:** Canonical answers were never visible to any respondent
- **Sandboxed execution:** Non-agentic runs used isolated Python scripts calling CORTEX.COMPLETE
- **Sandboxed agentic runs:** Cortex Code sessions had access only to question files
- **Same backbone model:** All 16 factorial runs use claude-opus-4-6
- **Same judge rubric:** All answers scored by the same 3-judge panel with identical criteria
- **Independent judging:** Judges never see each other's scores

---
# What We Expected

Going into the experiment, our hypotheses were:

- **More instructions = better answers** (the domain prompt should help)
- **Self-critique catches mistakes** (a review pass should improve accuracy)
- **All 4 levers ON = best score** (more is more)
- **Agentic tools matter most** (the biggest lever)

Did the results confirm or challenge these assumptions?

---
# Ready for Results?

You now understand the full experimental framework:

- **50 questions**, 15 categories, 5 scoring dimensions
- **4 binary levers** tested in all 16 combinations
- **2 execution engines** sharing the same LLM backbone
- **3 cross-model reference points** for external validity
- **Strict isolation** and independent 3-judge scoring

**Next:** Open the results presentation to see what happened.
