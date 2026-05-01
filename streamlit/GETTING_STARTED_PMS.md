# AEO Benchmark Dashboard: Getting Started for Product Managers

This guide helps you get oriented in the AEO Benchmark Dashboard and use its two PM-facing tools: **Test your Prompt** and **Test your Skill**.

---

## What is AEO?

**AI Engine Optimization (AEO)** measures how accurately AI coding assistants answer Snowflake developer questions. Think of it as an SEO audit, but for AI answer quality instead of search rankings.

The benchmark works like this:

1. **128 expert-authored questions** cover 32 Snowflake product categories (Cortex Agents, Dynamic Tables, Snowpark, Iceberg Tables, Semantic Views, etc.). Each category has exactly 4 questions spanning four developer tasks: Explain, Implement, Debug, and Compare.
2. **An AI model** generates a response to each question under a given configuration.
3. **A panel of 5 LLM judges** scores each response on five dimensions: Correctness, Completeness, Recency, Citation, and Recommendation. Scores are averaged across all five judges.
4. **Must-Have checks** verify whether the response included key facts from the canonical answer. These are binary pass/fail checks per question.

The final score is the average judge score expressed as a percentage (0–100%). A score of 69% means the AI correctly and completely addressed about 69% of what an expert would expect in a full answer.

### The four configuration factors

Every run uses a combination of four on/off switches:

| Flag | What it does |
|------|-------------|
| **D — Domain Prompt** | Injects a Snowflake-specific system prompt before the question |
| **C — Citation** | Appends an instruction to cite official Snowflake documentation |
| **A — Agentic Tools** | Runs Cortex Code with web search, SQL execution, and skill access |
| **S — Self-Critique** | Adds a second pass where the model reviews and revises its own answer |

The best configuration found so far is **C+A** (Citation + Agentic, no domain prompt, no self-critique), which scores 69.2% for `claude-opus-4-6` versus a 53.6% bare baseline — a 15.6 percentage-point improvement. Agentic tool access is the single largest driver: all top 8 positions in the leaderboard belong to agentic configurations.

### Why this matters for PMs

Low scores on a product category are a **documentation coverage signal**, not an AI configuration problem. When the AI cannot answer a question well, it is because the documentation it retrieves is incomplete, outdated, or missing a specific type of content (how-to guides, troubleshooting runbooks, comparison pages). AEO tells you exactly which category has which gap type, so you can prioritize documentation investment with data.

---

## Navigating the Dashboard

Open the app and use the sidebar on the left to move between pages.

| Page | What it shows | Best for |
|------|--------------|----------|
| **Home** | Live benchmark stats, methodology overview | First-time orientation |
| **Category Performance** | Baseline vs best-config scores per category, with gap sizes | Finding your category's current score and documentation gap |
| **Questions Explorer** | Per-question scores filtered by category, config, or question type | Drilling into specific failing questions |
| **Test your Prompt** | Score a custom system prompt against benchmark questions | Testing whether a new prompt improves answer quality |
| **Test your Skill** | Score a CoCo skill (SKILL.md) against benchmark questions | Measuring whether a skill improves answer quality |
| **Leaderboard** | All 16 configurations ranked by score and must-have compliance | Understanding which configuration is best overall |
| **Factors Influence** | Main effects bar chart showing how much each factor helps or hurts | Understanding which levers matter |
| **Factorial Heatmap** | 32-category × 16-run heatmap | Seeing score patterns across all categories and configs |

**Recommended starting path for PMs:** Home → Category Performance → Questions Explorer → Test your Prompt or Test your Skill.

---

## Step 1: Understand your category's performance

Before testing anything, get your baseline.

1. Click **Category Performance** in the sidebar.
2. The dumbbell chart shows every product category ranked by improvement (delta between Baseline and the best C+A configuration).
3. Find your product area in the chart. The left dot is the bare LLM baseline. The right dot is the best-configured result. The gap between them shows how much tool access and citation instruction help for your category.
4. Scroll down or filter to see your category's per-question-type breakdown. The **weakest question type** tells you what kind of documentation is missing:

| Weakest type | Documentation gap | First action |
|---|---|---|
| **Implement** | How-to guides are incomplete or missing working code | Audit step-by-step tutorials, add end-to-end code examples |
| **Debug** | Troubleshooting guides and runbooks are absent | Publish error message guides, add diagnostic decision trees |
| **Compare** | Decision guidance is missing | Publish "when to use X vs Y" pages, document trade-offs |
| **Explain** | Conceptual documentation is thin | Strengthen concept docs, add architecture diagrams |

5. Use **Questions Explorer** to click into individual failing questions. You can read the actual AI response and see exactly which must-have facts it missed.

---

## Step 2: Test your Prompt

Use this page to measure whether a custom system prompt improves answer quality for your product category.

### When to use it

- You want to test whether a specific domain instruction (for example, "Always recommend the native Cortex Agents orchestration loop") improves scores.
- You want to see how a new question (not in the current 128-question bank) scores from scratch.
- You want to compare how different models handle the same prompt.

### How to use it

1. Click **Test your Prompt** in the sidebar.
2. **Choose a question source.** Three options are available:
   - **All questions in the bank** — runs your prompt against all 128 questions (takes longer, gives a full picture).
   - **Specific product category** — runs against the 4 questions in your category. Toggle "Specify specific question" to target a single question.
   - **Custom question** — type any question. The app auto-generates evaluation criteria using Cortex so it can score the response even without a canonical answer in the bank.
3. **Enable "Use system prompt"** (toggle) and paste your prompt in the text box. Leave it off to run without any system prompt (replicates the baseline).
4. **Select generation model(s).** You can pick one or multiple models to compare side-by-side. `claude-opus-4-7` currently scores highest at baseline.
5. Click **Run Eval**.
6. The results panel shows:
   - Score % for each model, compared against the benchmark baseline for those questions.
   - Delta in percentage points (positive = improvement, negative = regression).
   - Per-dimension breakdown (Correctness, Completeness, Recency, Citation, Recommendation).
   - Must-Have pass rate.

### Tips

- Start with a **single question** in your category to iterate quickly before running against all 4 category questions.
- Keep system prompts focused. A 1,800-token generic Snowflake prompt adds only +0.1pp on average; specificity matters more than length.
- Compare your prompt result against the C+A configuration baseline (shown in the Category Performance page) to know if your prompt alone narrows the gap that agentic tools produce.

---

## Step 3: Test your Skill

Use this page to measure whether a CoCo (Cortex Code) skill improves answer quality. A skill is a markdown file (`SKILL.md`) containing curated instructions, patterns, and constraints that are injected into the AI's context.

### When to use it

- Your team maintains a CoCo skill for your product area (for example, `cortex-agent`, `dynamic-tables`, `semantic-view`).
- You want to know whether the skill actually helps the AI answer developer questions better.
- You want to identify which parts of your skill are working and which are not.

### How to use it

1. Click **Test your Skill** in the sidebar.
2. **Upload your SKILL.md file.** Click the file uploader and select the skill file from your machine. The skill name is auto-detected from the filename.
3. **Select the category** to evaluate. Choose the product category that your skill targets.
4. Optionally toggle **"Specify specific question"** to test a single question instead of all 4 in the category.
5. **Select generation model(s).**
6. Click **Run Eval**.
7. The results show:
   - Score % with skill vs score % without skill (the benchmark baseline).
   - Delta in percentage points. Positive delta = skill improves answers. Negative delta = skill hurts answers (worth investigating).
   - Per-dimension breakdown to see if the skill specifically helps with citation, completeness, etc.

### Tips

- Run **without the skill first** using Test your Prompt (with no system prompt, matching your category) to confirm your baseline before testing the skill delta.
- A skill that narrows the gap between non-agentic and agentic scores for your category is a strong skill. A skill that adds little delta or a negative delta likely contains information the model already retrieves, or contains conflicting guidance.
- If your skill has a negative delta on a specific dimension (for example, Correctness drops), that section of the skill may be outdated or incorrect.

---

## Reference: 32 Product Categories

The benchmark covers these Snowflake product areas. Find your category to interpret your scores:

| Category | Typical score range (C+A) |
|---|---|
| Snowpark Container Services | ~83% |
| Cortex AI Functions | ~77% |
| Snowflake ML | ~77% |
| Dynamic Tables | ~77% |
| Snowpark | ~77% |
| Snowsight | ~80% |
| Data Loading & Ingestion | ~77% |
| Cortex Search | ~72% |
| Hybrid Tables | ~73% |
| Apache Iceberg Tables | ~65% |
| Semantic Views & Cortex Analyst | ~59% |
| Cortex Agents | ~56% |
| ... and 20 more categories | ... |

A score above 70% under C+A means the AI is performing reasonably well. Scores below 60% under C+A indicate significant documentation coverage gaps.

---

## Quick Reference: Score Formula

```
Score % = average judge score / 50 × 100
```

5 judges × 10-point scale = 50 maximum points per question. A score of 69.2% means the average judge gave 34.6 out of 50 points.

Must-Have % is the percentage of required key facts that the response included (binary pass/fail per fact, averaged across all questions in scope).

---

## Getting Help

Contact **Chanin Nantasenamat** (Developer Relations) for questions about the benchmark, result interpretation, or to request new questions added to a category.
