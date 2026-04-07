# AEO Benchmark Results

Pre-computed analysis views of the 2^4 factorial experiment (16 runs, 50 questions, 3-judge panel).
Generated from the scoring JSONs in `../scores/`.

## Files

| File | Description |
|------|-------------|
| [results-overview.md](results-overview.md) | Executive summary: ranked leaderboard, key findings, best/worst |
| [results-by-category.md](results-by-category.md) | Scores broken down by the 13 product categories |
| [results-by-test-type.md](results-by-test-type.md) | Scores by test type: Explain, Implement, Debug, Compare |
| [results-by-dimension.md](results-by-dimension.md) | Scores by the 5 scoring dimensions |
| [results-by-question.md](results-by-question.md) | Per-question scores across all 16 runs |
| [results-by-factor.md](results-by-factor.md) | Main effects and interaction analysis of the 4 factors |
| [results-by-engine.md](results-by-engine.md) | claude (CORTEX.COMPLETE) vs cortex-code (agentic) comparison |

## Data Sources

- Scoring JSONs: `../scores/run-{1..16}-*.json`
- Question metadata: `../input/question-bank.md`
- Experiment design: `../input/README.md`
