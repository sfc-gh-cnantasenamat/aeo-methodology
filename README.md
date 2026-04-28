# AEO Benchmark

**AI Engine Optimization (AEO)** measures how accurately AI coding assistants answer Snowflake developer questions. Think of it as SEO, but for AI: does your assistant return the canonical, current Snowflake answer, or does it hallucinate?

## Methodology

**Question bank:** 128 questions across 32 product categories, covering four task types: Explain, Implement, Debug, and Compare.

**Experiment design:** A 2⁴ fully factorial experiment across 4 binary factors (Domain Prompt, Citation, Agentic, Self-Critique), producing 16 runs for the primary model (`claude-opus-4-6`). An additional 8 runs (17–24) benchmark five respondent models under baseline and agentic conditions for cross-model comparison.

**Scoring:** Each response is scored on 5 dimensions (Correctness, Completeness, Recency, Citation, Recommendation), each rated 0–2 for a maximum of 10 points. Each question also has up to 5 must-have elements graded PASS/FAIL.

**Judge panel:** Scores are averaged across a 5-judge panel (claude-opus-4-6, claude-opus-4-7, openai-gpt-5.4, llama4-maverick, gemini-3.1-pro) to reduce single-model bias. Runs 1–16 used a 3-judge subset; runs 17–24 use the full 5-judge panel.

**Storage:** All runs, responses, and scores are stored in `DEVREL.CNANTASENAMAT_DEV` on Snowhouse for leaderboard analysis and Snowsight visualization.

## Results Summary

**Factorial runs 1–16 (claude-opus-4-6):** Best configuration is Citation + Agentic (no domain prompt), scoring **75.9%**, a 22.7pp improvement over the bare baseline of 53.2%. Citation instruction is the dominant factor (+9.5pp average); self-critique is consistently counterproductive (−2.6pp average).

**Cross-model baseline (runs 17–21, CORTEX.COMPLETE):**

| Model | Score |
|-------|-------|
| `claude-opus-4-7` | **63.7%** |
| `openai-gpt-5.4` | 57.1% |
| `gemini-3.1-pro` | 56.6% |
| `claude-opus-4-6` | 53.1% |
| `llama4-maverick` | 37.4% |

**Cross-model agentic (runs 22–24, native Cortex Code):**

| Model | Score |
|-------|-------|
| `openai-gpt-5.4` | **63.7%** |
| `claude-opus-4-6` | 63.2% |
| `claude-opus-4-7` | 63.0% |

In agentic mode all three models converge within 0.7pp, showing that tool access equalizes parametric knowledge differences across models.

## Repository Structure

| Folder | Contents |
|--------|----------|
| [`input/`](input/) | Question bank, canonical answers, experiment prompts, and run summary |
| [`results/`](results/) | Analysis views sliced by category, question type, dimension, factor, engine, and more |
| [`scores/`](scores/) | Per-question JSON scoring files for experimental runs |
| [`slides/`](slides/) | Markdown source for methodology and results presentations |
| [`scripts/`](scripts/) | Orchestrator, sweep scripts, SPCS job specs, and utilities for running and scoring benchmarks |
| [`streamlit-app-snowhouse/`](streamlit-app-snowhouse/) | Production Streamlit app deployed on Snowhouse (`DEVREL.CNANTASENAMAT_DEV`) |
| [`streamlit-app-devrel/`](streamlit-app-devrel/) | Streamlit app variant for the DevRel Snowflake account |
| [`streamlit-app-local/`](streamlit-app-local/) | Local development version of the Streamlit app |
| [`streamlit/`](streamlit/) | Legacy Streamlit app (superseded by the per-environment variants above) |
| [`paper/`](paper/) | Research paper (Markdown + LaTeX/PDF) and supporting assets |
| [`skill/`](skill/) | Cortex Code skill definition for AEO benchmark |

## Presentations

- [Methodology](https://sfc-gh-cnantasenamat.github.io/aeo-methodology/) ([md](https://sfc-gh-cnantasenamat.github.io/aeo-methodology/slides.md))
- [Results](https://sfc-gh-cnantasenamat.github.io/aeo-results/) ([md](https://sfc-gh-cnantasenamat.github.io/aeo-results/slides.md))

## Pipeline

```mermaid
flowchart TD
    A["128 Benchmark Questions
    32 Categories · 4 Task Types"] --> B["2⁴ Factorial Design
    16 Runs · claude-opus-4-6"]

    B --> B1["4 Factors
    Domain Prompt · Citation
    Agentic · Self-Critique"]

    B1 --> E1["CORTEX.COMPLETE
    Agentic = off · 8 runs"]
    B1 --> E2["Native Cortex Code via SPCS
    Agentic = on · 8 runs"]

    A --> CM["Cross-Model Comparison
    Runs 17–24"]
    CM --> CM1["CORTEX.COMPLETE baseline
    5 models · runs 17–21"]
    CM --> CM2["Native Cortex Code
    3 models · runs 22–24"]

    E1 --> F[Generated Responses]
    E2 --> F
    CM1 --> F
    CM2 --> F

    F --> G{5-Judge Panel}
    G --> G1[claude-opus-4-6]
    G --> G2[claude-opus-4-7]
    G --> G3[openai-gpt-5.4]
    G --> G4[llama4-maverick]
    G --> G5[gemini-3.1-pro]

    G1 --> H[Panel-Averaged Scores]
    G2 --> H
    G3 --> H
    G4 --> H
    G5 --> H

    H --> I["5-Dimension Score
    max 10 pts"]
    H --> J["Must-Have Check
    up to 5× PASS/FAIL"]

    I --> K[(DEVREL.CNANTASENAMAT_DEV)]
    J --> K
    K --> L["Leaderboard & Analysis
    Snowhouse Streamlit App"]
```
