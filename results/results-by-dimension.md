# Results by Scoring Dimension

Average score per dimension (0-2 scale) across all 50 questions, for each of the 16 runs.
Dimensions: Correctness, Completeness, Recency, Citation, Recommendation.

## Average Dimension Scores (0-2 scale)

| Dimension | Max | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10 | R11 | R12 | R13 | R14 | R15 | R16 |
|-----------|----:|-----:|-----:|-----:|-----:|-----:|-----:|-----:|-----:|-----:|-----:|-----:|-----:|-----:|-----:|-----:|-----:|
| Correctness | 2.0 | 1.52 | 1.60 | 1.73 | 1.77 | 1.49 | 1.36 | 1.78 | 1.74 | 1.71 | 1.77 | 1.40 | 1.51 | 1.40 | 1.55 | 1.72 | 1.75 |
| Completeness | 2.0 | 1.47 | 1.50 | 1.91 | 1.88 | 1.25 | 1.19 | 1.91 | 1.85 | 1.80 | 1.81 | 1.25 | 1.38 | 1.13 | 1.41 | 1.80 | 1.78 |
| Recency | 2.0 | 1.58 | 1.70 | 1.79 | 1.85 | 1.67 | 1.57 | 1.81 | 1.83 | 1.79 | 1.84 | 1.53 | 1.67 | 1.55 | 1.67 | 1.83 | 1.81 |
| Citation | 2.0 | 0.01 | 0.81 | 0.01 | 1.99 | 1.40 | 1.68 | 1.91 | 0.22 | 0.08 | 0.49 | 0.25 | 0.25 | 1.71 | 0.83 | 0.08 | 0.09 |
| Recommendation | 2.0 | 1.51 | 1.55 | 1.77 | 1.89 | 1.33 | 1.31 | 1.91 | 1.77 | 1.70 | 1.77 | 1.45 | 1.55 | 1.48 | 1.65 | 1.73 | 1.71 |
| **Total** | **10.0** | **6.09** | **7.15** | **7.22** | **9.38** | **7.15** | **7.11** | **9.32** | **7.30** | **7.04** | **7.60** | **5.69** | **6.20** | **6.57** | **6.74** | **7.08** | **7.12** |

## Dimension Scores as % of Maximum

| Dimension | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10 | R11 | R12 | R13 | R14 | R15 | R16 |
|-----------|-----:|-----:|-----:|-----:|-----:|-----:|-----:|-----:|-----:|-----:|-----:|-----:|-----:|-----:|-----:|-----:|
| Correctness | 76.0% | 80.0% | 86.4% | 88.7% | 74.6% | 68.0% | 89.1% | 87.0% | 85.3% | 88.3% | 69.8% | 75.5% | 69.8% | 77.3% | 86.2% | 87.3% |
| Completeness | 73.7% | 75.0% | 95.7% | 94.0% | 62.3% | 59.7% | 95.4% | 92.3% | 90.0% | 90.3% | 62.5% | 69.0% | 56.5% | 70.5% | 90.0% | 89.2% |
| Recency | 79.0% | 85.0% | 89.7% | 92.7% | 83.6% | 78.7% | 90.7% | 91.3% | 89.3% | 92.0% | 76.7% | 83.7% | 77.7% | 83.3% | 91.7% | 90.3% |
| Citation | 0.7% | 40.3% | 0.7% | 99.3% | 70.0% | 84.0% | 95.7% | 11.0% | 4.0% | 24.7% | 12.3% | 12.3% | 85.7% | 41.7% | 4.0% | 4.7% |
| Recommendation | 75.3% | 77.3% | 88.4% | 94.3% | 66.7% | 65.3% | 95.3% | 88.7% | 85.0% | 88.7% | 72.3% | 77.7% | 74.0% | 82.7% | 86.7% | 85.7% |

## Weakest Dimension per Run

| Run | Configuration | Weakest Dimension | Avg Score |
|----:|---------------|-------------------|----------:|
| 1 | baseline | Citation | 0.01/2.0 |
| 2 | domain | Citation | 0.81/2.0 |
| 3 | agentic | Citation | 0.01/2.0 |
| 4 | cite-agentic | Correctness | 1.77/2.0 |
| 5 | domain-cite | Completeness | 1.25/2.0 |
| 6 | cite | Completeness | 1.19/2.0 |
| 7 | cite-agentic-selfcritique | Correctness | 1.78/2.0 |
| 8 | all4 | Citation | 0.22/2.0 |
| 9 | domain-agentic | Citation | 0.08/2.0 |
| 10 | domain-cite-agentic | Citation | 0.49/2.0 |
| 11 | selfcritique | Citation | 0.25/2.0 |
| 12 | domain-selfcritique | Citation | 0.25/2.0 |
| 13 | cite-selfcritique | Completeness | 1.13/2.0 |
| 14 | domain-cite-selfcritique | Citation | 0.83/2.0 |
| 15 | agentic-selfcritique | Citation | 0.08/2.0 |
| 16 | domain-agentic-selfcritique | Citation | 0.09/2.0 |
