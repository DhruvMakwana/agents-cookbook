# Planning and Decomposition

Two real repros of the plan-and-execute agent pattern: a replanning trigger (a plan's assumption turns out wrong mid-execution), and the granularity tradeoff (the same task decomposed too coarse, well-sized, and over-granular), plus a minimal verifier-in-the-loop check applied to the real results. Concept write-up: [Planning and Decomposition](https://dhruvmakwana.github.io/agents-deep-dive/planning-and-decomposition/).

No framework -- the raw Anthropic client throughout. Needs an Anthropic key. Sonnet 5 throughout.

## The two repros

- **Replanning trigger** (`replanning_demo`): a release-notes task where the first planned step (`get_latest_tag`) returns null -- the repo has never been tagged -- invalidating the plan's assumption that a "since tag X" query would work. Run under two system prompts: one telling the model to execute its committed plan without second-guessing, one explicitly telling it to revise the plan when a step reveals a wrong assumption.
- **Granularity tradeoff** (`granularity_demo`): the identical task, decomposed at three levels -- too coarse (no explicit plan at all), well-sized (four concrete, tool-mapped steps), and over-granular (a highly detailed plan broken into many small sub-steps, several of which don't correspond to any real tool call) -- with a minimal verifier-in-the-loop check (`verify_step`) applied to each real result.

## What actually happened, run against Claude Sonnet 5

**The replanning test was a clean, honest negative result.** Both the "execute your plan, don't second-guess" condition and the "revise when an assumption breaks" condition produced the identical, correct real outcome: both noticed the null tag and called `list_all_merged_prs` instead of the tag-anchored query, and both produced a correct changelog covering all three real merged PRs. Sonnet 5's baseline behavior already adapts to a plan-invalidating discovery without needing an explicit "replan when surprised" instruction -- worth reporting honestly rather than adjusted to fit the predicted gap.

**The granularity test produced a real, clean, reproducible failure mode -- confirmed on two separate full runs.** Too-coarse (no explicit plan) and well-sized (four concrete steps) both completed the task correctly: 3 real tool calls each, ending in a real `draft_changelog` call with the correct three PRs. The over-granular condition never called a single tool: asked to write out a highly detailed sub-step plan before executing anything, the model spent its entire token budget articulating the plan itself and never reached execution -- `steps: 0`, `tools_called: []`, and an `answer` field containing a cut-off plan document, not a changelog. This is a real, measurable cost of over-decomposition that doesn't require a philosophical argument to demonstrate: verbose upfront planning consumes the same token budget that execution needs, and a plan detailed enough can consume all of it before a single real action happens.

**The minimal verifier caught exactly this failure, using only the real trace already produced -- no extra model call.** `verify_step` checks one condition: was `draft_changelog` actually called? Applied to the three real results: `too_coarse` → passed, `well_sized` → passed, `over_granular` → failed, with the real reason `"draft_changelog was never called -- no real output was produced."` A verifier-in-the-loop doesn't need to be a second LLM call second-guessing the first one's judgment -- checking the concrete, checkable trace a plan-and-execute loop already produced is often enough to catch a real failure like this one.

## Install

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Configure

Paste your key into `agents-cookbook/.env` at the **cookbook root** -- this recipe reads it automatically. To override just this recipe, `cp .env.example .env` here instead.

## Run

```bash
python planning_and_decomposition.py
```

Runs both demos in sequence and prints each result as JSON.

## Files

| File | Role |
|---|---|
| `planning_and_decomposition.py` | Both demos and the CLI entry point -- the file you actually run |
| `planning_and_decomposition_docs.py` | **Documentation only** -- self-contained per-block version for the blog. Not run as a script, not kept in sync automatically. |
