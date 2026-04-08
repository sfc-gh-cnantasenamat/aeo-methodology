# AGENTS.md

## Overview

AEO (AI Engine Optimization) is a benchmark that measures how accurately AI coding assistants answer Snowflake developer questions. It uses a **2^4 factorial experiment design** with 4 binary factors (Domain Prompt, Citation, Agentic, Self-Critique) tested in all 16 combinations on Claude Opus 4.6. Each of the 50 questions is scored by a 3-judge LLM panel on 5 dimensions (Correctness, Completeness, Recency, Citation, Recommendation) plus 4 binary must-have elements.

## Repository structure

```
input/                  # Question bank, canonical answers, experiment prompts, run mapping
results/                # Analysis views sliced by category, dimension, factor, engine, etc.
scores/                 # Per-question JSON scoring files for all 16 runs
slides/                 # Markdown source for methodology and results presentations
paper/                  # Internal whitepaper (see Paper section below)
```

## Snowflake data layer

All benchmark data lives in **`DEVREL.AEO_OBSERVABILITY`** (connection: `devrel`).

**Tables:**
- `AEO_QUESTIONS` — 50-question bank with canonical answers and must-have checklists
- `AEO_RUNS` — Run metadata (which factors were active, model, timestamp)
- `AEO_RESPONSES` — Generated responses per run per question
- `AEO_SCORES` — Judge scores per run per question per dimension

**Views:**
- `V_AEO_LEADERBOARD` — Runs ranked by overall score
- `V_AEO_FACTORIAL_EFFECTS` — Main effects and interaction effects of each factor
- `V_AEO_PER_QUESTION_HEATMAP` — Score matrix (run x question)
- `V_AEO_JUDGE_AGREEMENT` — Inter-judge correlation and disagreement analysis

## Git workflow

Two remotes:
- **`snowflake-eng`** — `https://github.com/snowflake-eng/aeo.git` (engineering org, primary). Uses the `chanin-nantasenamat_snow` PAT stored at `~/.github/chanin-nantasenamat_snow`.
- **`origin`** — `sfc-gh-cnantasenamat` fork (for GH Pages presentations)

Push paper and code changes to `snowflake-eng`. Presentation slides deploy via `origin` to GH Pages.

## Paper

The whitepaper source lives in `paper/paper.md`. A LaTeX/PDF version is maintained in `paper/latex/`.

### Structure

```
paper/
├── paper.md                          # Source of truth (Markdown)
├── assets/                           # Figures referenced by both .md and .tex
│   ├── fig_01_main_effects.png
│   ├── fig_02_dumbbell_chart.png
│   └── fig_03_category_heatmap.png
├── paper.pdf                         # Compiled PDF (copied here after compilation)
├── latex/
│   └── paper.tex                     # LaTeX source (manually synced from paper.md)
└── scripts/
    ├── fig_01_main_effects.py        # Main effects bar chart
    ├── fig_02_dumbbell_chart.py      # Baseline vs best dumbbell chart
    └── fig_03_category_heatmap.py    # Category heatmap (grouped by Agentic)
```

### Regenerating figures

Each script reads from the Snowflake `DEVREL.AEO_OBSERVABILITY` schema and writes its PNG to `paper/assets/`. Run from the repo root:

```bash
python paper/scripts/fig_01_main_effects.py
python paper/scripts/fig_02_dumbbell_chart.py
python paper/scripts/fig_03_category_heatmap.py
```

### Compiling the PDF

Requires TeX Live (`pdflatex`). Run two passes from the `latex/` directory so cross-references resolve:

```bash
cd paper/latex
pdflatex -interaction=nonstopmode paper.tex
pdflatex -interaction=nonstopmode paper.tex
cp paper.pdf ../paper.pdf
```

The `.tex` file uses `../assets/` relative paths for `\includegraphics`, so it must be compiled from inside `paper/latex/`. After compilation, copy the PDF up to `paper/` so it sits alongside `paper.md`.

LaTeX auxiliary files (`.aux`, `.log`, `.out`) are excluded via `.gitignore`.

### Keeping Markdown and LaTeX in sync

`paper.md` is the source of truth. When editing content, update `paper.md` first, then mirror the changes into `paper/latex/paper.tex` and recompile the PDF.
