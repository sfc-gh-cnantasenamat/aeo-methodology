# AEO Benchmark

AI Engine Optimization — a benchmark and evaluation platform for measuring how accurately AI assistants answer Snowflake developer questions.  
[https://github.com/snowflake-eng/aeo](https://github.com/snowflake-eng/aeo)

# Vision

AI coding assistants are now part of the Snowflake developer workflow. But there is no systematic way to measure whether those assistants are giving developers correct, current answers. AEO exists to close that gap.

Two use cases drive it:

* **Benchmark intelligence** — a controlled, reproducible way to measure AI answer quality across Snowflake product categories, using a consistent rubric, a multi-model judge panel, and a factorial experiment design that isolates the effect of each deployment lever.
* **Product intelligence** — giving PMs and DevRel a live testing environment to evaluate how prompt design, system prompt choices, and tool access affect answer quality, before those choices ship to developers.

# Targeted Outcome

* DevRel has a repeatable, data-backed benchmark for AI assistant quality on Snowflake developer questions
* PMs can test prompt configurations in real time without writing code or running pipelines
* Eval results are automatically inserted into Snowflake for leaderboard analysis and Snowsight visualization
* An automated SPCS pipeline runs nightly evals against the full question bank without manual intervention
* A CoCo skill surfaces benchmark results and per-question analysis in natural language

**What success looks like:** a PM can add a new prompt configuration, run it against all 50 questions, and see scored results on a leaderboard within minutes, without engineering involvement.

# Milestones

## **Phase 1 — Evaluation Foundation** · *completed*

Establish the question bank, scoring rubric, judge panel, and initial data pipeline into Snowflake.

- [x] Define 50-question benchmark across 15 Snowflake product categories
- [x] Write canonical answers and must-have fact checklists for all 50 questions
- [x] Design 5-dimension scoring rubric (Correctness, Completeness, Recency, Citation, Recommendation)
- [x] Build 3-judge panel (claude-opus-4-6, openai-gpt-5.4, llama4-maverick)
- [x] Create `DEVREL.AEO_OBSERVABILITY` schema and tables (`AEO_QUESTIONS`, `AEO_RUNS`, `AEO_RESPONSES`, `AEO_SCORES`)
- [x] Upload question bank and canonical answers to Snowflake
- [x] Run baseline, augmented, and native Cortex Code conditions (19 experimental runs)
- [x] Build analytics views (`V_AEO_LEADERBOARD`, `V_AEO_FACTORIAL_EFFECTS`, `V_AEO_PER_QUESTION_HEATMAP`, `V_AEO_JUDGE_AGREEMENT`)
- [x] Create methodology and results presentations (GitHub Pages)

**Quality Gate — Phase 1 → Phase 2**

- [x] All 50 questions have canonical answers and must-have checklists
- [x] Judge panel produces consistent scores (inter-judge correlation > 0.7)
- [x] At least 3 experimental conditions scored and stored in Snowhouse
- [x] Leaderboard view returns ranked results without errors

---

## **Phase 2 — TruLens Integration & Local Pipeline POC**

Research TruLens best practices and build a reproducible local eval pipeline with Snowhouse insertion.

- [x] Research TruLens best practices for evals at scale
- [x] Design TruLens integration architecture (OpenTelemetry spans, feedback functions, SnowflakeConnector)
- [x] Implement `@instrument` decorators on `AEOBenchmarkApp` for retrieval, generation, and self-critique spans
- [x] Build custom feedback functions matching the 5-dimension AEO rubric (0.0–1.0 TruLens-compatible)
- [x] Register TruApp + SnowflakeConnector for Snowflake AI Observability integration
- [x] Build local POC pipeline with profile system (`--profile devrel` / `--profile snowhouse`)
- [x] Validate end-to-end: generate → score → insert → query from Snowhouse
- [ ] Add retry logic and error handling for judge panel failures at scale
- [ ] Write test suite covering feedback functions and pipeline correctness

**Quality Gate — Phase 2 → Phase 3**

- [x] Local pipeline runs all 50 questions without manual intervention
- [x] Results visible in Snowsight under AI & ML > Cortex AI > Evaluations
- [x] All 5 feedback function dimensions return values in [0.0, 1.0] with no nulls
- [x] Pipeline inserts into `AEO_RUNS`, `AEO_RESPONSES`, `AEO_SCORES` in correct schema

---

## **Phase 3 — SPCS Sandbox & Automated Pipeline**

Build and validate a Snowpark Container Services environment for running evals at scale without warehouse credit overhead.

- [x] Design SPCS job architecture (Dockerfile, job spec, scoring template)
- [x] Write `setup.sql` for compute pool, image repository, and service provisioning
- [x] Build `aeo_runner.py` for containerized response generation and judge scoring
- [ ] Build and push Docker image to Snowflake image registry
- [ ] Submit and validate SPCS job against full 50-question bank
- [ ] Implement nightly scheduled SPCS job for automated baseline runs
- [ ] Add Slack or email alert on job failure
- [ ] Document SPCS spin-up / spin-down workflow to control compute costs

**Quality Gate — Phase 3 → Phase 4**

- [ ] SPCS job completes full 50-question run end-to-end without manual steps
- [ ] Results inserted into Snowhouse within expected time window
- [ ] Compute pool auto-suspends after job completes
- [ ] Cost per run is documented and within budget

---

## **Phase 4 — Product Manager Tooling**

Give PMs and DevRel a live testing environment and a self-serve interface for adding prompt configurations to the pipeline.

- [ ] Develop Streamlit app for PMs to live test prompt configurations against sample questions
- [ ] Add real-time scoring display in Streamlit (per-dimension breakdown + must-have pass/fail)
- [ ] Design interface for PMs to define and submit new prompt configurations (domain prompt, citation, agentic, self-critique toggles)
- [ ] Connect PM-submitted configurations to the automated SPCS pipeline
- [ ] Build leaderboard view in Streamlit showing all runs ranked by score
- [ ] Add per-question drill-down: show judge reasoning, scores, and canonical answer side-by-side
- [ ] Add export to CSV / Snowflake table for sharing results with engineering and PMM

**Quality Gate — Phase 4 → Phase 5**

- [ ] PM can submit a new prompt configuration and receive scored results without engineering involvement
- [ ] Streamlit app loads leaderboard in under 5 seconds
- [ ] All Streamlit inputs are validated before triggering a pipeline run
- [ ] App is accessible to DevRel and PM teams via Streamlit in Snowflake (SiS)

---

## **Phase 5 — Observability, Skills & Rollout**

Surface benchmark results in natural language and roll out access to broader stakeholders.

- [ ] Build CoCo skill for DevRel — query leaderboard, per-question scores, and factorial effects in natural language
- [ ] Build CoCo skill for PM profile — compare prompt configurations, surface top/bottom questions, identify weak categories
- [ ] Create Snowsight dashboard with leaderboard, heatmap, and main effects charts
- [x] Publish methodology and results documentation to `snowflake-eng/aeo`
- [ ] Internal DevRel testing of CoCo skills and Streamlit app
- [ ] Open PM-facing Streamlit app to broader PM team
- [ ] Add AEO CoCo skill to DevRel team CoCo profile
- [ ] Weekly automated digest of new run results shared to team Slack

---

## **Current Status**

Active: Phase 3 — SPCS sandbox implementation

Phases 1 and 2 are complete. The TruLens integration is built and validated locally. The SPCS infrastructure is designed; container build and nightly scheduling are in progress. PM tooling (Phase 4) begins once the automated pipeline is stable.

# What's Not In Scope

* Real-time or streaming eval runs — batch per configuration is sufficient
* Evaluating models outside the Snowflake Cortex ecosystem
* Automated prompt optimization or fine-tuning recommendations
* Replacing human judgment for high-stakes product decisions — AEO provides signal, not verdicts
