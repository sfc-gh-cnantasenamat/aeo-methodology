# AEO Benchmark Input Data

This directory contains the input data for the AEO (AI Engine Optimization) benchmark. Generated responses are in `../output/`, scoring results in `../scores/`.

## Directory Structure

```
aeo/
├── input/
│   ├── README.md                 ← This file
│   ├── question-bank.md          ← 50 Snowflake developer questions (13 categories)
│   ├── canonical-answers.md      ← Ground-truth answers with must-have scoring elements
│   ├── experiment-prompts.md     ← Full 2^4 factorial design, prompts, and judge template
│   └── summary.md                ← Results summary with factor analysis
├── output/                       ← Generated responses per run (16 files)
└── scores/                       ← LLM-as-judge scoring results per run (16 JSON files)
```

## Experiment Design

A **2^4 factorial design** with 4 binary factors, all using **claude-opus-4-6** as the backbone model:

| Factor | OFF | ON |
|--------|-----|-----|
| **Domain Prompt** | No system message | Snowflake knowledge primer as system message |
| **Citation** | Raw question only | "Reference official Snowflake documentation" appended |
| **Agentic** | Single CORTEX.COMPLETE call | Cortex Code subagent with web search, skills, doc search |
| **Self-Critique** | Single-turn generation | Two-turn generate-then-revise pattern |

## Run Mapping

The run numbers below correspond to the files in `../output/` and `../scores/`. Runs 1-16 cover the full 2^4 factorial (16 unique factor combinations). Early physical experiment folders used non-contiguous numbering; the Source Folder Mapping section below provides traceability.

| Run | Domain | Citation | Agentic | Self-Critique | Execution | Response File | Score % |
|-----|:------:|:--------:|:-------:|:-------------:|-----------|---------------|--------:|
| 1 | | | | | CORTEX.COMPLETE | `run-1-baseline-claude.md` | 60.9% |
| 2 | x | | | | CORTEX.COMPLETE | `run-2-domain-claude.md` | 71.5% |
| 3 | | | x | | Cortex Code | `run-3-agentic-cortex-code.md` | 72.2% |
| 4 | | x | x | | Cortex Code | `run-4-cite-agentic-cortex-code.md` | 93.8% |
| 5 | x | x | | | CORTEX.COMPLETE | `run-5-domain-cite-claude.md` | 71.5% |
| 6 | | x | | | CORTEX.COMPLETE | `run-6-cite-claude.md` | 71.1% |
| 7 | | x | x | x | Cortex Code | `run-7-cite-agentic-selfcritique-cortex-code.md` | 93.2% |
| 8 | x | x | x | x | Cortex Code | `run-8-all4-cortex-code.md` | 73.0% |
| 9 | x | | x | | Cortex Code | `run-9-domain-agentic-cortex-code.md` | 70.4% |
| 10 | x | x | x | | Cortex Code | `run-10-domain-cite-agentic-cortex-code.md` | 76.0% |
| 11 | | | | x | CORTEX.COMPLETE | `run-11-selfcritique-claude.md` | 56.9% |
| 12 | x | | | x | CORTEX.COMPLETE | `run-12-domain-selfcritique-claude.md` | 62.0% |
| 13 | | x | | x | CORTEX.COMPLETE | `run-13-cite-selfcritique-claude.md` | 65.7% |
| 14 | x | x | | x | CORTEX.COMPLETE | `run-14-domain-cite-selfcritique-claude.md` | 67.4% |
| 15 | | | x | x | Cortex Code | `run-15-agentic-selfcritique-cortex-code.md` | 70.8% |
| 16 | x | | x | x | Cortex Code | `run-16-domain-agentic-selfcritique-cortex-code.md` | 71.2% |

## File Naming Convention

**Response files** (in `../output/`) follow the pattern:
```
run-{N}-{factors}-{engine}.md
```
- `{N}` = run number (1-16)
- `{factors}` = active factors (e.g., `baseline`, `domain-cite`, `cite-agentic-selfcritique`, `all4`)
- `{engine}` = `claude` (CORTEX.COMPLETE) or `cortex-code` (agentic subagent)

**Score files** (in `../scores/`) follow the pattern:
```
run-{N}-{factors}.json
```
Each JSON contains per-question scores from a 3-judge panel (openai-gpt-5.4, claude-opus-4-6, llama4-maverick), with 5 scoring dimensions (0-2 each) and 4 must-have elements per question.

## Source Folder Mapping

For traceability back to the original experiment data:

| Run | Physical Folder |
|-----|-----------------|
| 1 | `run-3-baseline-8192tok` |
| 2 | `run-4-augmented-curated-8192tok` |
| 3 | `run-6-native-cc-opus` |
| 4 | `run-7-native-cc-opus-cite` |
| 5 | `run-8-augmented-cite-8192tok` |
| 6 | `run-9-baseline-cite-8192tok` |
| 7 | `run-10-native-cc-opus-refine` |
| 8 | `run-11-native-cc-opus-all4` |
| 9 | `run-12-native-cc-opus-prompt-agentic` |
| 10 | `run-13-native-cc-opus-prompt-cite-agentic` |
| 11 | `run-14-selfcritique-only` |
| 12 | `run-15-domain-selfcritique` |
| 13 | `run-16-cite-selfcritique` |
| 14 | `run-17-domain-cite-selfcritique` |
| 15 | `run-18-agentic-selfcritique` |
| 16 | `run-19-domain-agentic-selfcritique` |
