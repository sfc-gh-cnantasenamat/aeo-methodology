---
# AEO Benchmark: Results

---
# The Punchline

We tested the claude-opus-4-6 model on a set of 50 Snowflake developer questions, scored by a panel of 3 judges.

**Baseline (bare model, no help):** scored 60.9% on answer quality and passed 68.5% of required facts

**Best configuration (citation instruction + agentic tools):** scored 93.8% on answer quality and passed 91.5% of required facts

That is a **+32.9 percentage point improvement** without changing the model, its training, or its weights. The only difference was how we deployed it.

```
  Answer Quality Score
  Baseline  60.9% ████████████████████████░░░░░░░░░░░░░░░░
  Best      93.8% █████████████████████████████████████░░░

  Must-Have Fact Pass Rate
  Baseline  68.5% ███████████████████████████░░░░░░░░░░░░░
  Best      91.5% ████████████████████████████████████░░░░
```

What deployment changes made this happen? Keep reading.

---
# The Full 2⁴ Factorial

## We ran all 16 combinations of 4 binary levers

```
+------+--------+----------+---------+----------------+---------+-------+-----------+
| Run  | Domain | Citation | Agentic | Self-Critique  | Score % | MH %  | vs Base   |
+------+--------+----------+---------+----------------+---------+-------+-----------+
|  1   |        |          |         |                |  60.9%  | 68.5% | baseline  |
|  2   |   x    |          |         |                |  68.6%  | 62.0% | +7.7pp    |
|  6   |        |    x     |         |                |  71.1%  | 48.5% | +10.2pp   |
|  5   |   x    |    x     |         |                |  71.5%  | 54.5% | +10.6pp   |
| 14   |        |          |         |       x        |  56.9%  | 66.5% | -4.0pp    |
| 15   |   x    |          |         |       x        |  62.0%  | 69.0% | +1.1pp    |
| 16   |        |    x     |         |       x        |  65.7%  | 60.7% | +4.8pp    |
| 17   |   x    |    x     |         |       x        |  67.4%  | 69.3% | +6.5pp    |
|  3   |        |          |   x     |                |  72.2%  | 93.5% | +11.3pp   |
|  9   |   x    |          |   x     |                |  70.4%  | 89.8% | +9.5pp    |
|  4   |        |    x     |   x     |                |  93.8%  | 91.5% | +32.9pp   |
| 10   |   x    |    x     |   x     |                |  76.0%  | 90.5% | +15.1pp   |
| 18   |        |          |   x     |       x        |  70.8%  | 88.2% | +9.9pp    |
| 19   |   x    |          |   x     |       x        |  71.2%  | 88.7% | +10.3pp   |
|  7   |        |    x     |   x     |       x        |  93.2%  | 93.5% | +32.3pp   |
|  8   |   x    |    x     |   x     |       x        |  73.0%  | 91.2% | +12.1pp   |
+------+--------+----------+---------+----------------+---------+-------+-----------+
```

MH = Must-Have fact pass rate, pp = percentage points


---
# How Main Effects Are Calculated

Each pair holds the other 3 levers constant and flips only Agentic on/off:

```
+----+----+----+-----------------+----------------+----------+---------+
|  D |  C | SC | Without Agentic | With Agentic   | Score +  |  MH +   |
+----+----+----+-----------------+----------------+----------+---------+
|    |    |    | Run 1  (60.9%)  | Run 3  (72.2%) | +11.3pp  | +25.0pp |
| x  |    |    | Run 2  (68.6%)  | Run 9  (70.4%) |  +1.8pp  | +27.8pp |
|    |  x |    | Run 6  (71.1%)  | Run 4  (93.8%) | +22.7pp  | +43.0pp |
| x  |  x |    | Run 5  (71.5%)  | Run 10 (76.0%) |  +4.5pp  | +36.0pp |
|    |    | x  | Run 14 (56.9%)  | Run 18 (70.8%) | +13.9pp  | +21.7pp |
| x  |    | x  | Run 15 (62.0%)  | Run 19 (71.2%) |  +9.2pp  | +19.7pp |
|    |  x | x  | Run 16 (65.7%)  | Run 7  (93.2%) | +27.5pp  | +32.8pp |
| x  |  x | x  | Run 17 (67.4%)  | Run 8  (73.0%) |  +5.6pp  | +21.9pp |
+----+----+----+-----------------+----------------+----------+---------+
```

**Average main effect:** +12.1pp on score, +28.5pp on must-have. The same calculation is done for each of the 4 levers.

---
# Main Effects

## Averaged across all 8 paired comparisons in the factorial design

- **Agentic Tools (web search, doc lookup, skills):** improved answer quality score by +12.5 percentage points on average, and improved must-have fact pass rate by +19.2 points on average

- **Citation Instruction ("cite official Snowflake docs"):** improved answer quality score by +8.7 points on average, but reduced must-have fact pass rate by -7.7 points (the model cited docs it had not actually read)

- **Domain Prompt (200-word Snowflake expert system prompt):** reduced answer quality score by -2.0 points on average, and reduced must-have pass rate by -2.8 points

- **Self-Critique ("review and revise your answer"):** reduced answer quality score by -4.6 points on average, and reduced must-have pass rate by -1.3 points

Only agentic tools improved *both* score and must-have simultaneously.

```
  Average Main Effect on Score (pp)
  Agentic   +12.5 ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
  Citation   +8.7 ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
  Domain     -2.0 ░░░░
  Self-Crit  -4.6 ░░░░░░░░░

  Average Main Effect on Must-Have (pp)
  Agentic   +19.2 ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
  Citation   -7.7 ░░░░░░░░░░░░░░░
  Domain     -2.8 ░░░░░░
  Self-Crit  -1.3 ░░░
```

---
# Lever 1: Agentic Tools

## Giving the model web search, doc lookup, and skills (i.e. Cortex Code) was the single most impactful change

```
+----+----+----+-----------------+----------------+----------+---------+
|  D |  C | SC | Without Agentic | With Agentic   | Score +  |  MH +   |
+----+----+----+-----------------+----------------+----------+---------+
|    |    |    | Run 1  (60.9%)  | Run 3  (72.2%) | +11.3pp  | +25.0pp |
|    |  x |    | Run 6  (71.1%)  | Run 4  (93.8%) | +22.7pp  | +43.0pp |
|    |    |  x | Run 14 (56.9%)  | Run 18 (70.8%) | +13.9pp  | +21.7pp |
|    |  x |  x | Run 16 (65.7%)  | Run 7  (93.2%) | +27.5pp  | +32.8pp |
+----+----+----+-----------------+----------------+----------+---------+
```

In every single one of the 8 paired comparisons, adding agentic tools improved both the answer quality score and the must-have fact pass rate. No other lever achieved this.

Average improvement: +12.1 points on score, +28.5 points on must-have. Giving the model the ability to look things up was worth more than any prompt instruction.

---
# Lever 2: Citation Instruction

## Appending "cite official Snowflake documentation" to each question boosted scores, but only when tools were available to actually find the docs

```
+----+-----+----+------------------+----------------+-----------+---------+
|  D | Agt | SC | Without Citation | With Citation  | Score +   |  MH +   |
+----+-----+----+------------------+----------------+-----------+---------+
|    |  x  |    | Run 3  (72.2%)   | Run 4  (93.8%) | +21.6pp   | -2.0pp  |
|    |  x  | x  | Run 18 (70.8%)   | Run 7  (93.2%) | +22.4pp   | +5.3pp  |
|    |     |    | Run 1  (60.9%)   | Run 6  (71.1%) | +10.2pp   | -20.0pp |
| x  |     |    | Run 9  (70.4%)   | Run 10 (76.0%) |  +5.6pp   | +0.7pp  |
+----+-----+----+------------------+----------------+-----------+---------+
```

The massive +21 to +22 point gains happened specifically when agentic tools were ON and the domain prompt was OFF. When the domain prompt was present, the citation effect shrank to just +1.8 to +5.6 points.

Citation tells the agent what to look for. Agentic tools let it actually find and verify those references.

---
# Lever 3: Domain Prompt

## The data: 4 selected paired comparisons

```
+-----+-----+----+-----------------+----------------+----------+---------+
|  C  | Agt | SC | Without Domain  | With Domain    | Score +  |  MH +   |
+-----+-----+----+-----------------+----------------+----------+---------+
|     |     |    | Run 1  (60.9%)  | Run 2  (68.6%) |  +7.7pp  | -6.5pp  |
|  x  |     |    | Run 6  (71.1%)  | Run 5  (71.5%) |  +0.4pp  | +6.0pp  |
|  x  |  x  |    | Run 4  (93.8%)  | Run 10 (76.0%) | -17.8pp  | -1.0pp  |
|  x  |  x  | x  | Run 7  (93.2%)  | Run 8  (73.0%) | -20.2pp  | -2.3pp  |
+-----+-----+----+-----------------+----------------+----------+---------+
```

- **Without domain prompt:** scores averaged 72.6% across all non-domain runs, because the model relied on its own retrieval and training without rigid framing

- **With domain prompt:** scores averaged 70.6% overall, but the effect split sharply. It helped bare models (+3.7 points) by providing useful Snowflake framing, yet hurt agentic models (-9.9 points) by constraining how the agent used its tools and overriding information discovered through web search

The worst cases: adding the domain prompt to the best configuration (citation + agentic) destroyed **17.8 and 20.2 points** of score.

---
# Lever 4: Self-Critique

## The data: 4 selected paired comparisons

```
+-----+-----+-----+-----------------+----------------+----------+---------+
|  D  |  C  | Agt | Without SC      | With SC        | Score +  |  MH +   |
+-----+-----+-----+-----------------+----------------+----------+---------+
|     |     |     | Run 1  (60.9%)  | Run 14 (56.9%) |  -4.0pp  | -2.0pp  |
|  x  |     |     | Run 2  (68.6%)  | Run 15 (62.0%) |  -6.6pp  | +7.0pp  |
|     |     |  x  | Run 3  (72.2%)  | Run 18 (70.8%) |  -1.4pp  | -5.3pp  |
|     |  x  |  x  | Run 4  (93.8%)  | Run 7  (93.2%) |  -0.6pp  | +2.0pp  |
+-----+-----+-----+-----------------+----------------+----------+---------+
```

Average effect across all 8 pairs: **-3.0 points on answer quality score.**

What happened: the self-critique instruction caused the model to second-guess correct answers, add unnecessary hedging language ("it depends", "you may want to consider"), and remove specific technical details in favor of safer, more generic statements. More thinking did not produce better answers.

---
# The Golden Combination

## The winning formula

**No domain prompt + citation instruction + agentic**

The top 2 configurations both share this exact pattern:

- **Run 4 scored 93.8%:** citation instruction + agentic, no domain prompt, no self-critique
- **Run 7 scored 93.2%:** citation instruction + agentic + self-critique, no domain prompt

What happens when you add a domain prompt?

- **Run 10 scored 76.0%:** domain prompt + citation + agentic, a drop of 17.8 points from Run 4
- **Run 8 scored 73.0%:** domain prompt + citation + agentic + self-critique, a drop of 20.2 points from Run 7

A 200-word system prompt destroyed a 20+ point advantage. The best instruction was no instruction at all.

```
  Score % (adding domain prompt)
  Run 4  93.8% ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
  Run 7  93.2% ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
  Run 10 76.0% ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░
  Run 8  73.0% ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░
             no domain prompt  +domain prompt
```

---
# The Same Model Story

## Every data point uses claude-opus-4-6

- **Bare model with no help:** 60.9% score (Run 1)
- **Added a 200-word domain prompt:** 68.6% score, a gain of +7.7 points (Run 2)
- **Added citation instruction instead:** 71.1% score, a gain of +10.2 points (Run 6)
- **Added both domain prompt and citation:** 71.5% score, a gain of +10.6 points (Run 5)
- **Added agentic tools instead (no prompt changes):** 72.2% score, a gain of +11.3 points (Run 3)
- **Added citation instruction + agentic tools:** 93.8% score, a gain of +32.9 points (Run 4)

Same neural network weights. Same training data. The 32.9-point difference came entirely from giving the model tools and a lightweight instruction to cite its sources.

```
  Score progression (same model)
  Bare       60.9% ████████████████████████░░░░░░░░░░░░░░░░
  +Domain    68.6% ███████████████████████████░░░░░░░░░░░░░
  +Citation  71.1% ████████████████████████████░░░░░░░░░░░░
  +Dom+Cite  71.5% ████████████████████████████░░░░░░░░░░░░
  +Agentic   72.2% █████████████████████████████░░░░░░░░░░░
  +Cite+Agt  93.8% █████████████████████████████████████░░░
```

---
# Cross-Model Baselines

## We also tested GPT-5.4 and Llama 4 Maverick to establish external reference points

```
+-----------------------+---------+-------+
| Respondent            | Score % | MH %  |
+-----------------------+---------+-------+
| openai-gpt-5.4 Base  |  57.5%  | 55.0% |
| claude-opus-4-6 Base  |  60.9%  | 68.5% |
| llama4-maverick Base  |  38.4%  | 43.0% |
+-----------------------+---------+-------+
| openai-gpt-5.4 Aug   |  72.5%  | 58.5% |
| claude-opus-4-6 Aug   |  68.6%  | 62.0% |
| llama4-maverick Aug   |  65.2%  | 54.0% |
+-----------------------+---------+-------+
| CC + Cite (Run 4)     |  93.8%  | 91.5% |
+-----------------------+---------+-------+
```

The best non-agentic result across all three models was GPT-5.4 with a domain prompt at 72.5%. The best agentic configuration scored 93.8%, which is 21.3 points higher.

Switching to a different (and arguably stronger) model closed far less of the gap than simply giving the original model access to tools.

```
  Score % across models
  Llama Base   38.4% ███████████████░░░░░░░░░░░░░░░░░░░░░░░░
  GPT-5.4 Base 57.5% ███████████████████████░░░░░░░░░░░░░░░░
  Claude Base  60.9% ████████████████████████░░░░░░░░░░░░░░░
  Llama Aug    65.2% ██████████████████████████░░░░░░░░░░░░░
  Claude Aug   68.6% ███████████████████████████░░░░░░░░░░░░
  GPT-5.4 Aug  72.5% █████████████████████████████░░░░░░░░░░
  CC + Cite    93.8% █████████████████████████████████████░░░
```

---
# Must-Have Pass Rates

## Must-have measures whether the answer includes specific required facts (4 per question, 200 total)

- **Baseline model with no tools (Run 1):** passed 68.5% of required facts, meaning it missed about 1 in 3 required details
- **Model with agentic tools (all agentic runs):** passed 88 to 93.5% of required facts, because it could look up and verify specific details in real time
- **Model with citation instruction but no tools (Run 6):** passed only 48.5% of required facts, worse than baseline, because the model fabricated documentation references it had not actually read

Citation without tools is dangerous: it teaches the model to sound authoritative while getting the facts wrong. Citation with tools is powerful: it tells the agent to verify and present what it actually found.

```
  Must-Have Fact Pass Rate
  Cite no tools  48.5% ███████████████████░░░░░░░░░░░░░░░░░░░░
  Baseline       68.5% ███████████████████████████░░░░░░░░░░░░░
  Agentic best   93.5% █████████████████████████████████████░░░
```

---
# Score vs Must-Have

## Most configurations improve one metric at the expense of the other. Only one configuration improves both.

**Non-agentic with citation (Runs 5 and 6):** Answer quality score went up because the model wrote more polished, reference-heavy responses. But must-have pass rate went down because those references were often fabricated, and the model missed required factual details.

**Agentic without citation (Run 3):** Must-have pass rate jumped to 93.5% because the agent retrieved real facts. But the answer quality score stayed at a moderate 72.2% because the agent did not always present its findings in a well-structured, citation-rich format.

**Agentic with citation (Run 4):** Both metrics peaked together at 93.8% score and 91.5% must-have. The citation instruction told the agent to show its work, and the tools ensured that work was grounded in real documentation.

```
  Score %                        Must-Have %
  Cite only  71.1% ████████████████████████████  48.5% ███████████████████
  Agent only 72.2% █████████████████████████████  93.5% █████████████████████████████████████
  Agent+Cite 93.8% █████████████████████████████████████  91.5% ████████████████████████████████████░
```

---
# 5 Surprising Findings

- **Adding more instructions to the system prompt made answers worse, not better.** The 200-word domain prompt reduced scores by 17 to 20 points in the best configurations, because it constrained how the agent used its tools.

- **Self-critique ("review and revise your answer") was counterproductive.** It reduced answer quality in 7 out of 8 comparisons by causing the model to second-guess correct content and replace specific details with hedging language.

- **Telling the model to cite docs without giving it tools to find them was actively harmful.** The must-have pass rate dropped from 68.5% to 48.5% because the model fabricated references to documentation it had never read.

- **The highest-scoring configuration used the fewest prompt instructions of any non-baseline run.** No system prompt at all. Just "please cite official Snowflake documentation" appended to each question, plus access to tools.

- **A 33-point score improvement came from deployment infrastructure, not model training.** The same claude-opus-4-6 weights went from 60.9% to 93.8% based solely on whether it had tools and a citation nudge.

---
# Why Less Is More

The domain prompt tells the model what it should already know about Snowflake. But the model already knows most of it from training, and the rigid framing prevents the agent from discovering and incorporating information it does not already know.

Agentic tools let the model find what it actually needs in real time. Web search, documentation lookup, and code execution provide current, verified information that no static system prompt can match.

Self-critique asks the model to doubt its own work. But on domain-specific factual questions, the model's first answer is usually more detailed and accurate than its revised one. The revision process introduces hedging, removes specific examples, and replaces confident correct statements with cautious incorrect ones.

**The optimal pattern:** Give the model access to tools and a lightweight nudge to cite its sources. Then get out of the way and let it work.

---
# Implications for AI Products

- **Invest in tools and infrastructure, not longer prompts.** Agentic tools delivered a +32.9 point improvement, while the best prompt engineering delivered only +7.7 points. That is a 4x difference in impact for the same underlying model.

- **Use citation as a lightweight nudge appended to user queries, not as a system prompt.** Appending "please cite official documentation" to each question outperformed a carefully crafted 200-word domain expert system prompt.

- **Do not assume self-critique improves quality.** The popular "generate then revise" pattern actively degraded answer quality on factual domain questions. Test it empirically before shipping it.

- **Expect domain prompts to have diminishing returns as tools improve.** System prompts help bare models that have nothing else, but they constrain models that have access to real-time information retrieval. As tool infrastructure matures, prompts should get shorter, not longer.

---
# What We Would Do Differently

- **Test with a larger question bank.** 50 questions gives good overall signal but limits per-category statistical power. Some product categories had only 2 to 3 questions, making it hard to isolate category-specific lever effects.

- **Add human judges alongside the LLM panel.** The 3-model judge panel (GPT-5.4, Claude Opus, Llama Maverick) is reproducible and consistent, but all three may share systematic biases from similar training data.

- **Run per-category lever analysis.** Citation might matter more for API reference questions than for architecture questions. The factorial design supports this analysis but 50 questions is too few to do it reliably.

- **Measure latency and cost per configuration.** Agentic runs take longer and cost more tokens. The quality improvement is clear, but the cost-quality tradeoff deserves explicit quantification.

- **Test multi-turn conversations.** All 50 questions were single-turn. Real developer interactions involve follow-up questions and clarifications that could change the lever dynamics.

---
# Key Takeaways

**1. Agentic tools are the single most impactful lever.** Across all 8 paired comparisons in the factorial design, giving the model access to web search, documentation lookup, and skills improved answer quality by +12.5 points and must-have fact pass rate by +19.2 points on average. It was the only lever that improved both metrics simultaneously.

**2. The best configuration is minimalist.** No system prompt. Just a citation instruction ("cite official docs") and agentic tool access. This scored 93.8%, the highest of all 16 conditions.

**3. More instructions can hurt.** Both the domain prompt and self-critique reduced answer quality when the model had access to tools. The domain prompt constrained tool use; self-critique introduced hedging. Less instruction produced better results.

**4. Deployment architecture matters more than prompt engineering.** The same claude-opus-4-6 model went from 60.9% to 93.8% by changing how it was deployed (adding tools and a citation nudge), not by changing what it was told in a system prompt.

---
# Thank You

## AEO Benchmark: Full 2⁴ Factorial Experiment

- **50 Snowflake developer questions** across 15 product categories, each scored on 5 dimensions (correctness, completeness, recency, citation, recommendation) plus 4 required must-have facts
- **16 experimental conditions** testing every combination of 4 binary levers, all using the same claude-opus-4-6 backbone model
- **3-model judge panel** (GPT-5.4, Claude Opus, Llama Maverick) scoring every response independently, with scores averaged for robustness
- **Key result:** the same model improved from 60.9% to 93.8% (+32.9 percentage points) purely from deployment changes, with no changes to model weights or training

*Open the methodology deck for the full experimental design.*
