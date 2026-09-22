# Workflow Patterns

Four of Anthropic's five named workflow patterns, each with real code and a real run. The fifth, routing, is exactly what the [`what-is-an-agent/`](../what-is-an-agent/) recipe's fixed pipeline already demonstrates — see that recipe instead of repeating it here. Concept write-up: [Workflow Patterns](https://dhruvmakwana.github.io/agents-deep-dive/workflow-patterns/).

No framework — the raw Anthropic client throughout, same as [`agent-loop-from-scratch/`](../agent-loop-from-scratch/). Needs an Anthropic key.

## The four patterns

- **Chaining** (`chaining_demo`): generate an outline, gate it against a concrete criterion, only expand if the gate passes.
- **Parallelization** (`parallelization_demo`): the same input reviewed along three independent dimensions, dispatched concurrently, with real wall-clock timing against running the same calls sequentially.
- **Orchestrator-workers** (`orchestrator_demo`): a planning call decides its *own* sub-questions per topic — not a fixed, developer-chosen split like parallelization above — workers answer them, a synthesis call combines the results. Run against two different topics to check the split genuinely varies with the input.
- **Evaluator-optimizer** (`evaluator_optimizer_demo`): generate, evaluate against a deterministic (non-LLM) check, retry with feedback, capped at a hard attempt budget.

Model choice is task-scaled: everything defaults to Haiku except the orchestrator's planning step, which uses Sonnet explicitly (hardcoded, not env-configurable) — deciding a sensible task breakdown needs more than Haiku-tier reasoning, while the narrow worker answers and the final synthesis don't.

## What actually happened, run against Claude Haiku 4.5 (Sonnet 5 for orchestrator planning)

**Chaining** passed its gate on the first attempt — the outline covered all three required concepts (hash function, collisions, O(1) average case), and the 150-word explainer that got generated from it stayed accurate to the outline.

**Parallelization**: **4.79s run sequentially, 1.86s run concurrently** for the same 3 review calls — about 2.6x faster, not the theoretical 3x, which is a realistic number given real network and queueing overhead rather than a suspiciously clean multiple. More interesting than the speedup: each dimension found genuinely different, non-overlapping issues in the same 5-sentence paragraph about binary search. Technical accuracy found none this run (a real, honest result — not every review finds something, and it didn't in this pass). Clarity flagged that the text never states the array must be sorted first, and that "bigger or smaller" doesn't say which half gets eliminated. Grammar correctly caught all four planted issues (its/it's, your/you're, theres/there's, then/than). Three focused reviewers surfaced three different kinds of problems that one generic "review this" call would have had to catch all at once, or not caught at all.

**Orchestrator-workers**, run on two topics, produced genuinely differently-*shaped* breakdowns (both happened to land on 4 sub-questions, which is a coincidence, not the interesting part):
- *"Arrays vs. linked lists"* → a comparison-shaped split: storage/access speed, insertion/deletion cost, memory overhead, real-world use cases.
- *"How binary search achieves O(log n) time"* → a derivation-shaped split: the core halving idea, the math translating halving into a log, why that identity holds, the real-world implication of the result.

Nothing in the code told the planner to compare dimensions for one topic and derive a proof for the other — that structure came from the planner reading the topic itself, which is the actual distinguishing feature of this pattern versus parallelization's fixed, developer-chosen split.

**Evaluator-optimizer** passed on the first attempt both times it was tried (a 13-to-15-word to-do-app description, no banned marketing words) — the retry-with-feedback path exists in the code and is real, but this run didn't need to exercise it. That's an honest result, not a weaker one.

## Install

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Configure

Paste your key into `agents-cookbook/.env` at the **cookbook root** — this recipe reads it automatically. To override just this recipe, `cp .env.example .env` here instead.

## Run

```bash
python workflow_patterns.py
```

Runs all four demos in sequence and prints each result as JSON.

## Files

| File | Role |
|---|---|
| `workflow_patterns.py` | All four demos and the CLI entry point — the file you actually run |
| `workflow_patterns_docs.py` | **Documentation only** — self-contained per-block version for the blog. Not run as a script, not kept in sync automatically. |
