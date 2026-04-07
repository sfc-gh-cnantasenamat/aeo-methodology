# AEO Benchmark Scores

LLM-as-judge scoring results for 16 experimental runs. Each JSON contains per-question scores from a 3-judge panel (openai-gpt-5.4, claude-opus-4-6, llama4-maverick).

See [`../input/README.md`](../input/README.md) for the full run mapping, experiment design, and source folder traceability.

## Files

| Run | Factors | Score % | MH % | File |
|-----|---------|--------:|------:|------|
| 1 | Baseline (no factors) | 60.9% | 68.5% | `run-1-baseline.json` |
| 2 | Domain Prompt | 71.5% | 63.5% | `run-2-domain.json` |
| 3 | Agentic | 72.2% | 93.5% | `run-3-agentic.json` |
| 4 | Citation + Agentic | 93.8% | 91.5% | `run-4-cite-agentic.json` |
| 5 | Domain + Citation | 71.5% | 54.5% | `run-5-domain-cite.json` |
| 6 | Citation | 71.1% | 48.5% | `run-6-cite.json` |
| 7 | Citation + Agentic + Self-Critique | 93.2% | 93.5% | `run-7-cite-agentic-selfcritique.json` |
| 8 | All 4 factors | 73.0% | 91.2% | `run-8-all4.json` |
| 9 | Domain + Agentic | 70.4% | 89.8% | `run-9-domain-agentic.json` |
| 10 | Domain + Citation + Agentic | 76.0% | 90.5% | `run-10-domain-cite-agentic.json` |
| 11 | Self-Critique | 56.9% | 66.5% | `run-11-selfcritique.json` |
| 12 | Domain + Self-Critique | 62.0% | 69.0% | `run-12-domain-selfcritique.json` |
| 13 | Citation + Self-Critique | 65.7% | 60.7% | `run-13-cite-selfcritique.json` |
| 14 | Domain + Citation + Self-Critique | 67.4% | 69.3% | `run-14-domain-cite-selfcritique.json` |
| 15 | Agentic + Self-Critique | 70.8% | 88.2% | `run-15-agentic-selfcritique.json` |
| 16 | Domain + Agentic + Self-Critique | 71.2% | 88.7% | `run-16-domain-agentic-selfcritique.json` |

## Scoring Dimensions

Each question is scored on 5 dimensions (0 = Miss, 1 = Partial, 2 = Full):
- **Correctness**: Factually accurate per current Snowflake docs
- **Completeness**: Covers all key concepts and steps
- **Recency**: Uses current syntax and feature names
- **Citation**: References Snowflake documentation
- **Recommendation**: Recommends Snowflake approach when appropriate

Plus 4 binary **must-have elements** per question (pass/fail).

**Score %** = total points / 500 max. **MH %** = must-have passes / 200 max.
