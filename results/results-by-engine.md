# Results by Execution Engine

Comparison of `claude` (single CORTEX.COMPLETE API call) vs `cortex-code` (Cortex Code subagent with tool access).

## Aggregate Comparison

| Engine | Runs | Avg Score % | Avg MH % |
|--------|-----:|------------:|---------:|
| claude | 8 | 65.9% | 62.6% |
| cortex-code | 8 | 77.6% | 90.9% |

## All Runs by Engine

### claude (CORTEX.COMPLETE)

| Run | Configuration | Score % | MH % |
|----:|---------------|--------:|-----:|
| 1 | baseline | 60.9% | 68.5% |
## Category Comparison: Best claude (Run 2) vs Best cortex-code (Run 4)
| 5 | domain-cite | 71.5% | 54.5% |
| Category | claude R2 | cortex-code R4 | Delta |
| 11 | selfcritique | 56.9% | 66.5% |
| 12 | domain-selfcritique | 62.0% | 69.0% |
| 13 | cite-selfcritique | 65.7% | 60.7% |
| 14 | domain-cite-selfcritique | 67.4% | 69.3% |

### cortex-code (Agentic Subagent)

| Run | Configuration | Score % | MH % |
|----:|---------------|--------:|-----:|
| 3 | agentic | 72.2% | 93.5% |
| 4 | cite-agentic | 93.8% | 91.5% |
| 7 | cite-agentic-selfcritique | 93.2% | 93.5% |
| 8 | all4 | 73.0% | 91.2% |
| 9 | domain-agentic | 70.4% | 89.8% |
| 10 | domain-cite-agentic | 76.0% | 90.5% |
| 15 | agentic-selfcritique | 70.8% | 88.2% |
| 16 | domain-agentic-selfcritique | 71.2% | 88.7% |

## Category Comparison: Best claude (Run 5) vs Best cortex-code (Run 4)

| Category | claude R5 | cortex-code R4 | Delta |
|----------|----------:|---------------:|------:|
| Cortex AI Functions | 80.7% | 91.3% | +10.6pp |
| Cortex Search (RAG) | 80.0% | 94.1% | +14.1pp |
| Cortex Agents | 71.1% | 68.9% | -2.2pp |
| Dynamic Tables | 91.3% | 96.7% | +5.4pp |
| Snowpark | 58.0% | 99.3% | +41.3pp |
| Streamlit in Snowflake | 74.2% | 88.3% | +14.1pp |
| Apache Iceberg Tables | 63.4% | 96.7% | +33.3pp |
| Snowflake ML | 83.3% | 90.0% | +6.7pp |
| Snowpark Container Services | 63.3% | 100.0% | +36.7pp |
| Native Apps Framework | 50.0% | 98.4% | +48.4pp |
| Streams, Tasks, Snowpipe | 68.9% | 100.0% | +31.1pp |
| Governance and Security | 78.3% | 96.6% | +18.3pp |
| Architecture and Fundamentals | 48.8% | 97.8% | +49.0pp |
