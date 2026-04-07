# AEO Benchmark

**AI Engine Optimization (AEO)** measures how accurately AI coding assistants answer Snowflake developer questions. Think of it as SEO, but for AI: does your assistant return the canonical, current Snowflake answer, or does it hallucinate?

## Methodology

**Question bank:** 50 questions across 13 product categories, covering four task types: Explain, Implement, Debug, and Compare.

**Conditions tested:**

| Condition | Description |
|-----------|-------------|
| Baseline | Bare LLM with no system prompt |
| Augmented | LLM with a Snowflake-focused system prompt |
| Native | Full Cortex Code harness |

**Scoring:** Each response is scored on 5 dimensions (Correctness, Completeness, Recency, Citation, Recommendation), each rated 0–2 for a maximum of 10 points. Each question also has 4 must-have elements graded PASS/FAIL.

**Judge panel:** Scores are averaged across 3 independent LLM judges (claude-opus-4-6, openai-gpt-5.4, llama4-maverick) to reduce single-model bias.

**Storage:** All runs, responses, and scores are stored in `DEVREL.AEO_OBSERVABILITY` on Snowhouse for leaderboard analysis and Snowsight visualization.

## Presentations

- [Methodology](https://sfc-gh-cnantasenamat.github.io/aeo-methodology/)
- [Results](https://sfc-gh-cnantasenamat.github.io/aeo-results/)

## Pipeline

```mermaid
flowchart TD
    A[50 Benchmark Questions] --> B{3 Conditions}
    B --> C[Baseline\nBare LLM]
    B --> D[Augmented\nSystem Prompt]
    B --> E[Native\nCortex Code]

    C --> F[Generated Responses]
    D --> F
    E --> F

    F --> G{3-Judge Panel}
    G --> G1[claude-opus-4-6]
    G --> G2[openai-gpt-5.4]
    G --> G3[llama4-maverick]

    G1 --> H[Panel-Averaged Scores]
    G2 --> H
    G3 --> H

    H --> I[5-Dimension Score\nmax 10 pts]
    H --> J[Must-Have Check\n4x PASS/FAIL]

    I --> K[(DEVREL.AEO_OBSERVABILITY)]
    J --> K
    K --> L[Leaderboard & Analysis\nSnowsight]
```
