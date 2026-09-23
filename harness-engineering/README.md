# Harness Engineering

Two real repros of Anthropic's own documented harness pattern for long-running agents: a genuine multi-session continuation across separate, budget-limited conversations that only share a progress file, and a self-verification discipline test against a deliberately ambiguous real tool result. Concept write-up: [Harness Engineering](https://dhruvmakwana.github.io/agents-deep-dive/harness-engineering/).

No framework -- the raw Anthropic client throughout. Needs an Anthropic key. Sonnet 5 throughout.

## The two repros

- **Multi-session continuation** (`multi_session_continuation_demo`): a policy-comparison checklist (3 fictional products x 2 criteria = 6 items), filled in across two genuinely separate sessions -- separate message histories, no shared conversation state -- that only share a `ProgressFile` object, mirroring the documented `claude-progress.txt` pattern. Session 1 is deliberately turn-limited to simulate a real context reset mid-task.
- **Self-verification discipline** (`self_verification_demo`): the same checklist, including one deliberately ambiguous real tool result (a policy lookup that says "contact support for specifics" instead of giving an actual answer), run under a plain instruction vs. an explicit self-verify instruction modeled on Anthropic's own cited discipline: *"Self-verify all features. Only mark features as 'passing' after careful testing."*

## What actually happened, run against Claude Sonnet 5

**A real bug was caught and fixed before any result was trusted**: the first version of the session loop treated any non-`tool_use` stop reason as "the agent finished," which silently mishandled a real `max_tokens` truncation mid-response as if the agent had genuinely completed its turn. Caught because session 1 (deliberately capped to force a fast reset) reported "finished" with the model's own text explicitly saying *"Now recording all six findings"* immediately followed by zero actual `update_progress_file` calls -- the response had been cut off mid-generation, not concluded. Fixed by explicitly distinguishing `stop_reason == "max_tokens"` (real truncation) from any other stop reason, and by using turn-count rather than an ambiguous token-based cutoff to force a clean, predictable reset point for the demo.

**With that fixed, the multi-session continuation worked exactly as the documented pattern predicts.** Session 1 (capped at 1 turn) made all 6 real `lookup_policy` calls but was cut off by the turn limit before recording anything — `remaining: 6`, nothing persisted to the progress file. Session 2 started as a **genuinely fresh conversation** with no memory of session 1's tool calls, read the current (still-empty) progress file first, **re-did all 6 lookups from scratch** (since only the progress file — not the raw conversation — survives a real reset), then recorded all 6 real findings, including correctly flagging the deliberately ambiguous Vertex Sync data-retention result as `needs_follow_up` rather than `passing` — unprompted, with no explicit self-verify instruction in this demo's system prompt. Final state: `remaining: 0`, every item correctly filled.

**The self-verification test was a clean, honest negative.** Run explicitly to compare a plain instruction against Anthropic's cited self-verify discipline, both conditions independently and correctly marked the ambiguous item `needs_follow_up`, with real, specific reasoning each time ("no concrete retention period was returned, so this is not a usable, comparable answer" vs. "does not state an actual retention period or rule"). Sonnet 5's baseline judgment about an ambiguous result was already good enough that the explicit instruction didn't change the outcome here — reported plainly rather than adjusted to fit the predicted gap.

## Install

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Configure

Paste your key into `agents-cookbook/.env` at the **cookbook root** -- this recipe reads it automatically. To override just this recipe, `cp .env.example .env` here instead.

## Run

```bash
python harness_engineering.py
```

Runs both demos in sequence and prints each result as JSON.

## Files

| File | Role |
|---|---|
| `harness_engineering.py` | Both demos and the CLI entry point -- the file you actually run |
| `harness_engineering_docs.py` | **Documentation only** -- self-contained per-block version for the blog. Not run as a script, not kept in sync automatically. |
