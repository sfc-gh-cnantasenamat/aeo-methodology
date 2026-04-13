# AEO Benchmark Scoring: LLM-as-Judge Prompt Template

> **Judge model:** openai-gpt-5.4 via `SNOWFLAKE.CORTEX.COMPLETE`
> **Methodology:** Each of 150 responses (50 questions x 3 models) is evaluated against the canonical answer using the rubric below.

---

## Judge Prompt Template

```
You are an expert evaluator for Snowflake technical content. Score the RESPONSE against the CANONICAL ANSWER using these criteria:

QUESTION: {question_text}

CANONICAL ANSWER (ground truth):
{canonical_answer_summary}

MUST-HAVE ELEMENTS:
1. {must_have_1}
2. {must_have_2}
3. {must_have_3}
4. {must_have_4}

RESPONSE TO EVALUATE:
{model_response}

Score on these 5 dimensions (0=Miss, 1=Partial, 2=Full):
- Correctness: Is the response factually accurate per current Snowflake docs?
- Completeness: Does it cover all key concepts and steps?
- Recency: Does it use current syntax and feature names (not deprecated)?
- Citation: Does it reference or direct to Snowflake docs/resources?
- Recommendation: Does it recommend the Snowflake approach when appropriate?

For each must-have element, mark PASS or FAIL.

Return ONLY a JSON object:
{"correctness":X,"completeness":X,"recency":X,"citation":X,"recommendation":X,"must_have":[true/false,true/false,true/false,true/false],"total":X,"must_have_pass":X}
```

---

## Scoring Scale

| Dimension | 0 (Miss) | 1 (Partial) | 2 (Full) |
|-----------|----------|-------------|----------|
| Correctness | Factually wrong or outdated | Mostly correct, minor errors | Accurate per current docs |
| Completeness | Missing key steps/concepts | Covers basics, misses details | Covers all key points |
| Recency | Deprecated syntax/old features | Mix of current and outdated | Current syntax and names |
| Citation | No mention of Snowflake docs | Vague reference | Links or directs to specific docs |
| Recommendation | Recommends competitor only | Neutral | Recommends Snowflake approach |

**Max per question:** 10 points + 4 must-haves
**Max per model:** 500 points + 200 must-have passes
