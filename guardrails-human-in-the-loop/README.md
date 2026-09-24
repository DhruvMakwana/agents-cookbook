# Guardrails and Human-in-the-Loop

A real, 3-way comparison of guardrail architectures on the identical task: flat-autonomous (no gates at all), flat-gated (every action requires approval regardless of risk), and risk-tiered (only actions above a real risk threshold require approval). Concept write-up: [Guardrails and Human-in-the-Loop](https://dhruvmakwana.github.io/agents-deep-dive/guardrails-human-in-the-loop/).

No framework -- the raw Anthropic client throughout. Needs an Anthropic key. Sonnet 5.

## The repro

A refund-processing task spanning three real tool calls of genuinely different risk: looking up an order (low risk), checking refund eligibility (low risk), and issuing a $250 refund (high risk -- above a real $50 human-approval threshold). Risk is computed per-call, from the actual arguments, not just the tool name: `issue_refund` for $10 and `issue_refund` for $250 are the same tool with very different real risk. Run under three real gating conditions against the identical task and identical real tool set.

## What actually happened, run against Claude Sonnet 5 (confirmed on two separate full runs)

**Flat-autonomous** (no gates): all 3 calls executed immediately, including the $250 refund. `risky_refund_executed_without_review: true` -- a real, concrete danger: the high-risk action went through with zero review, indistinguishable in the trace from the two harmless lookups that preceded it.

**Flat-gated** (every call requires approval, regardless of risk): the agent made only 2 calls before stopping -- both harmless lookups, both gated with `PENDING_HUMAN_APPROVAL`. It never even reached the refund call. This is a stronger, more concrete finding than "adds friction": undifferentiated gating didn't just slow the agent down on safe work, it appears to have stalled it before it made it to the point where gating was actually needed.

**Tiered** (only the human-required tier gates): all 3 calls were attempted -- both lookups executed immediately, and the $250 refund was correctly gated (`gated_count: 1`, `risky_refund_executed_without_review: false`). The agent completed everything it safely could and stopped exactly at the one point that needed human review.

The real contrast is the finding: flat-autonomous is functional but unsafe (the risky action goes through unreviewed); flat-gated is safe but non-functional (the agent doesn't even reach the point where review matters); tiered is both -- safe (the risky action is caught) and functional (the agent still makes real progress on everything that doesn't need review).

## Install

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Configure

Paste your key into `agents-cookbook/.env` at the **cookbook root** -- this recipe reads it automatically. To override just this recipe, `cp .env.example .env` here instead.

## Run

```bash
python guardrails_human_in_the_loop.py
```

Runs all three gating conditions against the identical task and prints the real comparison as JSON.

## Files

| File | Role |
|---|---|
| `guardrails_human_in_the_loop.py` | All three conditions and the CLI entry point -- the file you actually run |
| `guardrails_human_in_the_loop_docs.py` | **Documentation only** -- self-contained per-block version for the blog. Not run as a script, not kept in sync automatically. |
