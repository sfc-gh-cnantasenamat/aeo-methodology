# AEO Benchmark

**AI Engine Optimization (AEO)** measures how accurately AI coding assistants answer Snowflake developer questions. Think of it as SEO, but for AI: does your assistant return the canonical, current Snowflake answer, or does it hallucinate?

## Methodology

**Question bank:** 128 questions across 32 product categories, covering four task types: Explain, Implement, Debug, and Compare.

**Experiment design:** A 2⁴ fully factorial experiment across 4 binary factors (Domain Prompt, Citation, Agentic, Self-Critique), producing 16 runs for the primary model (claude-opus-4-6). Additional baseline-only runs benchmark alternative models for cross-model comparison.

**Scoring:** Each response is scored on 5 dimensions (Correctness, Completeness, Recency, Citation, Recommendation), each rated 0–2 for a maximum of 10 points. Each question also has 4 must-have elements graded PASS/FAIL.

**Judge panel:** Scores are averaged across 3 independent LLM judges (claude-opus-4-6, openai-gpt-5.4, llama4-maverick) to reduce single-model bias.

**Storage:** All runs, responses, and scores are stored in `DEVREL.CNANTASENAMAT_DEV` on Snowhouse for leaderboard analysis and Snowsight visualization.

## Repository Structure

| Folder | Contents |
|--------|----------|
| [`input/`](input/) | Question bank, canonical answers, experiment prompts, and run summary |
| [`results/`](results/) | Analysis views sliced by category, question type, dimension, factor, engine, and more |
| [`scores/`](scores/) | Per-question JSON scoring files for all 16 experimental runs |
| [`slides/`](slides/) | Markdown source for methodology and results presentations |
| [`scripts/`](scripts/) | Orchestrator, sweep scripts, and utilities for running and scoring benchmarks |
| [`streamlit/`](streamlit/) | Multi-page Streamlit app for leaderboard, heatmaps, and model comparison |
| [`paper/`](paper/) | Research paper (Markdown + LaTeX/PDF) and supporting assets |

## Presentations

- [Methodology](https://sfc-gh-cnantasenamat.github.io/aeo-methodology/) ([md](https://sfc-gh-cnantasenamat.github.io/aeo-methodology/slides.md))
- [Results](https://sfc-gh-cnantasenamat.github.io/aeo-results/) ([md](https://sfc-gh-cnantasenamat.github.io/aeo-results/slides.md))

## Pipeline

```mermaid
flowchart TD
    A["128 Benchmark Questions
    32 Categories · 4 Task Types"] --> B["2⁴ Factorial Design
    16 Runs"]

    B --> B1["4 Factors
    Domain Prompt · Citation
    Agentic · Self-Critique"]

    B1 --> E1["CORTEX.COMPLETE
    Agentic = off · 8 runs"]
    B1 --> E2["Native Cortex Code
    Agentic = on · 8 runs"]

    E1 --> F[Generated Responses]
    E2 --> F

    F --> G{3-Judge Panel}
    G --> G1[claude-opus-4-6]
    G --> G2[openai-gpt-5.4]
    G --> G3[llama4-maverick]

    G1 --> H[Panel-Averaged Scores]
    G2 --> H
    G3 --> H

    H --> I["5-Dimension Score
    max 10 pts"]
    H --> J["Must-Have Check
    4× PASS/FAIL"]

    I --> K[(DEVREL.CNANTASENAMAT_DEV)]
    J --> K
    K --> L["Leaderboard & Analysis
    Snowsight"]
```
