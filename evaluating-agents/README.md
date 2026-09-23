# Evaluating Agents

Three real experiments in how agent evals actually work, not just the vocabulary. Concept write-up: [Evaluating Agents](https://dhruvmakwana.github.io/agents-deep-dive/evaluating-agents/).

No framework — the raw Anthropic client throughout, same as the rest of this cookbook. Needs an Anthropic key.

## The three demos

- **Outcome vs. trajectory** (`outcome_vs_trajectory_demo`): a model may call a reference tool or just answer directly — tested on a well-known fact (where skipping the tool and guessing could still get the right *outcome*) and an unguessable fictional fact (where only the tool's *trajectory* can produce the right answer). Both the outcome and whether the tool was actually called are captured.
- **pass@k vs. pass^k** (`pass_at_k_demo`): the identical probability question, run 5 independent times. pass@k asks whether at least one of the 5 succeeded; pass^k asks whether *all 5* succeeded — the real reliability question, since a production agent runs once per real request, not 5 times with a human picking the best try.
- **Capability vs. regression suite** (`capability_vs_regression_demo`): a small suite of trivial arithmetic tasks that should never fail, re-run under a system prompt changed for a plausible, real reason (an accessibility-style requirement to spell out numbers) — checking whether that change silently broke the suite's own automated grader.

All three default to Haiku — these are eval-methodology demonstrations, not tests of reasoning difficulty.

## What actually happened, run against Claude Haiku 4.5

**Outcome vs. trajectory**: on this real run, the model called the reference tool for *both* questions — the well-known one (boiling point) and the unguessable fictional one (a colony's founding year) — and got both outcomes right. No divergence observed here: the model didn't take the shortcut of skipping verification on the easy case. That's a genuinely disclosed negative result, not a wasted one — the real risk this test is built to catch (a model getting the right outcome by *skipping* the intended trajectory) is documented elsewhere in the literature (the Holistic Agent Leaderboard reports catching agents "searching for the benchmark on HuggingFace instead of solving a task" — an outcome that would pass an outcome-only grader while the trajectory is entirely wrong). This run shows the *mechanism* for catching that kind of gap, even on a run where nothing needed catching.

**pass@k vs. pass^k** (k=5): the same probability question ("at least 2 women on a 3-person committee from 5 men and 4 women," correct answer 17/42), run 5 independent times — **5/5 correct**. pass@5 = true, pass^5 = true — no gap observed on this specific task. Real published numbers show why the gap matters when it does show up: τ-bench reports GPT-4o's retail-domain success dropping from under 50% at pass@1 to under 25% at pass^8 — "a staggering 60% drop," in Sierra's own words, from a single-shot number to a real reliability number. This recipe's own 5/5 shows the *computation* the metric performs; it doesn't claim to reproduce that scale of gap on a well-structured, medium-difficulty combinatorics problem.

**Capability vs. regression suite**: this one caught a real, clean regression. All 4 baseline tasks passed under a plain system prompt. Under the accessibility-motivated system prompt ("express all numeric answers in words, not digits"), the model's *arithmetic stayed completely correct* — "Six squared is thirty-six," "One hundred divided by four equals twenty-five" — but **all 4 tasks failed the automated grader**, because that grader was written expecting literal digit substrings ("36", "25") and word-form numbers don't contain them. The model didn't regress; the grader did. This is exactly the realistic failure mode a regression suite exists to catch: a well-intentioned, unrelated change that silently breaks how correctness gets checked, not how correctly the task gets done.

## Install

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Configure

Paste your key into `agents-cookbook/.env` at the **cookbook root** — this recipe reads it automatically. To override just this recipe, `cp .env.example .env` here instead.

## Run

```bash
python evaluating_agents.py
```

Runs all three demos in sequence and prints each result as JSON.

## Files

| File | Role |
|---|---|
| `evaluating_agents.py` | All three demos and the CLI entry point — the file you actually run |
| `evaluating_agents_docs.py` | **Documentation only** — self-contained per-block version for the blog. Not run as a script, not kept in sync automatically. |
