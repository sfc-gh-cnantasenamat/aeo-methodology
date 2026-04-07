# Results Overview

Executive summary of the AEO 2^4 factorial experiment.

## Leaderboard (All 16 Runs, Ranked by Score %)

| Rank | Run | Configuration | Engine | Score % | MH % |
|-----:|----:|---------------|--------|--------:|-----:|
| 1 | 4 | cite, agentic | cortex-code | 93.8% | 91.5% |
| 2 | 7 | cite, agentic, selfcritique | cortex-code | 93.2% | 93.5% |
| 3 | 10 | domain, cite, agentic | cortex-code | 76.0% | 90.5% |
| 4 | 8 | domain, cite, agentic, selfcritique | cortex-code | 73.0% | 91.2% |
| 5 | 3 | agentic | cortex-code | 72.2% | 93.5% |
| 6 | 2 | domain | claude | 71.5% | 63.5% |
| 7 | 5 | domain, cite | claude | 71.5% | 54.5% |
| 8 | 16 | domain, agentic, selfcritique | cortex-code | 71.2% | 88.7% |
| 9 | 6 | cite | claude | 71.1% | 48.5% |
| 10 | 15 | agentic, selfcritique | cortex-code | 70.8% | 88.2% |
| 11 | 9 | domain, agentic | cortex-code | 70.4% | 89.8% |
| 12 | 14 | domain, cite, selfcritique | claude | 67.4% | 69.3% |
| 13 | 13 | cite, selfcritique | claude | 65.7% | 60.7% |
| 14 | 12 | domain, selfcritique | claude | 62.0% | 69.0% |
| 15 | 1 | (baseline) | claude | 60.9% | 68.5% |
| 16 | 11 | selfcritique | claude | 56.9% | 66.5% |

## Best and Worst Product Categories

**Best run (Run 4, 93.8% overall):**

| Category | Score % |
|----------|--------:|
| Snowpark Container Services | 100.0% |
| Streams, Tasks, Snowpipe | 100.0% |
| Snowpark | 99.3% |
| Native Apps Framework | 98.4% |
| Architecture and Fundamentals | 97.8% |
| Dynamic Tables | 96.7% |
| Apache Iceberg Tables | 96.7% |
| Governance and Security | 96.6% |
| Cortex Search (RAG) | 94.1% |
| Cortex AI Functions | 91.3% |
| Snowflake ML | 90.0% |
| Streamlit in Snowflake | 88.3% |
| Cortex Agents | 68.9% |

**Worst run (Run 11, 56.9% overall):**

| Category | Score % |
|----------|--------:|
| Streams, Tasks, Snowpipe | 70.0% |
| Snowpark Container Services | 68.3% |
| Cortex Search (RAG) | 62.5% |
| Architecture and Fundamentals | 62.2% |
| Dynamic Tables | 62.0% |
| Governance and Security | 61.7% |
| Snowpark | 58.7% |
| Streamlit in Snowflake | 57.9% |
| Apache Iceberg Tables | 55.3% |
| Native Apps Framework | 55.0% |
| Cortex Agents | 47.2% |
| Snowflake ML | 46.0% |
| Cortex AI Functions | 42.0% |

## Hardest and Easiest Questions (Averaged Across All 16 Runs)

**5 Hardest Questions:**

| Q# | Category | Test Type | Avg Score | Avg % |
|---:|----------|-----------|----------:|------:|
| 11 | Cortex Agents | Implement | 4.7/10 | 46.6% |
| 12 | Cortex Agents | Implement | 5.0/10 | 49.8% |
| 35 | Snowflake ML | Implement | 5.9/10 | 58.5% |
| 5 | Cortex AI Functions | Debug | 6.0/10 | 60.0% |
| 21 | Snowpark | Compare | 6.0/10 | 60.2% |

**5 Easiest Questions:**

| Q# | Category | Test Type | Avg Score | Avg % |
|---:|----------|-----------|----------:|------:|
| 45 | Streams, Tasks, Snowpipe | Compare | 8.1/10 | 81.3% |
| 8 | Cortex Search (RAG) | Implement | 8.2/10 | 81.7% |
| 17 | Dynamic Tables | Explain | 8.4/10 | 83.5% |
| 18 | Snowpark | Explain | 8.4/10 | 83.6% |
| 6 | Cortex Search (RAG) | Explain | 8.6/10 | 85.6% |

## Key Findings

1. **Agentic + Citation (no domain prompt) is the optimal configuration** (Run 4: 93.8% score, 91.5% MH).
2. **Agentic tools are the dominant factor**, improving both score (+12.5pp) and must-have compliance (+19.2pp).
3. **Citation is the second most impactful factor** (+8.7pp score), especially when combined with agentic tools.
4. **Domain prompt helps non-agentic runs but harms agentic ones** (-2.0pp average, but -17 to -20pp when agentic+citation are present).
5. **Self-critique is counterproductive** (-4.6pp score average), degrading quality in 7 of 8 paired comparisons.

See [results-by-factor.md](results-by-factor.md) for detailed factor analysis.
