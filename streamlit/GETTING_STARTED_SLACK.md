👋 AEO Benchmark Dashboard

What is AEO?
The AI Engine Optimization (AEO) Benchmark measures how accurately Cortex Code and other LLMs answer Snowflake developer questions. It scores 128 questions across 32 product categories using three frontier models (claude-opus-4-6, claude-opus-4-7, openai-gpt-5.4) evaluated by a 5-judge LLM panel (claude-opus-4-6, claude-opus-4-7, openai-gpt-5.4, llama4-maverick, gemini-3.1-pro). Low scores on a given category signal documentation gaps, not an AI problem.

How the AEO benchmark was run
Each run is one of 16 configurations built from four binary factors: D (Domain Prompt — a static Snowflake knowledge primer in the system prompt), C (Citation instruction — telling the model to cite sources), A (Agentic tools — giving the model access to the native agentic tools built into Cortex Code), and S (Self-Critique — a generate-then-revise step). The baseline is the bare configuration with none of these factors enabled: no system prompt, no citation instruction, no tool access, no self-critique. C+A is the best-performing configuration, which enables Citation instruction and Agentic tools together, without a domain prompt or self-critique step.

Access the AEO app
Go to go/aeo

What can PMs do in the app?

1. Check a category's score → open Category Performance in the sidebar. The chart shows a product area's score under the baseline (bare LLM, no tools or instructions) and under C+A (Citation + Agentic tools, the best configuration found). The weakest question type (Implement / Debug / Compare / Explain) points directly to the documentation gap to fix first.

2. Test a system prompt or a new custom question → open Test your Prompt page. A PM can paste a system prompt, pick a category or a custom question, choose a model, and hit Run Eval. The score delta vs the baseline (bare LLM with no factors enabled) appears in seconds.

3. Test a CoCo skill → open Test your Skill. Upload a SKILL.md, pick a category, and hit Run Eval. A positive delta means the skill is helping; a negative delta means something in it is conflicting or outdated.

4. Browse individual questions → open Questions Explorer. A PM can filter by product category and question type (Implement / Debug / Compare / Explain) to see exactly which questions scored lowest and read the full model response alongside the expert-authored canonical answer. This is the fastest way to understand what the model is getting wrong and why.

Where to start: Home → Category Performance → Questions Explorer → Test your Prompt or Skill

Full guide: streamlit/GETTING_STARTED_PMS.md in the aeo repo
Questions? Ping @Chanin
