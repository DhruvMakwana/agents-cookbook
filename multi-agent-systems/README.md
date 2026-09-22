# Multi-Agent Systems

Anthropic and Cognition published influential, opposite-leaning posts about multi-agent systems in mid-2025. This recipe tests both claims directly, on real toy tasks, rather than just quoting the debate. Concept write-up: [Multi-Agent Systems](https://dhruvmakwana.github.io/agents-deep-dive/multi-agent-systems/).

No framework — the raw Anthropic client throughout, same as the rest of this cookbook. Needs an Anthropic key.

## The two demos

- **Token economics** (`single_agent_research` / `multi_agent_research`, testing Anthropic's claim): three genuinely independent, breadth-first sub-questions, answered by one agent in one call versus a lead agent dispatching three separate subagents (each blind to the other two) plus a synthesis call. Real token cost measured.
- **Consistency risk** (`single_agent_faq` / `multi_agent_faq`, testing Cognition's claim): a tightly-coupled task — a Pricing FAQ section and a Refunds FAQ section that must agree on one shared, unspecified fact (a trial length in days). One agent writing both sections in a single pass versus two subagents, each blind to the other's output, each independently inventing that fact. Real agreement checked with a fact-extractor, not a subjective read.

Both demos hardcode `claude-sonnet-5` — a fair, controlled comparison needs the same model on both sides of each split, and writing coherent sections needs more than Haiku-tier reasoning.

## What actually happened, run against Claude Sonnet 5

**Token economics**: single agent, one call, **1,048 tokens**. Multi-agent (lead + 3 subagents + synthesis), 4 calls, **3,369 tokens** — a real measured **3.21x** multiplier. Smaller than Anthropic's own reported 4x (agents vs. chat) or 15x (multi-agent vs. chat) — those are measured against a plain chat baseline on real production workloads, not a single-agent-doing-everything baseline on a 3-question toy task — but the same direction, on our own real numbers, with model id and date disclosed rather than borrowed from the source post.

**Consistency risk**, first attempt: both the pricing and refund instructions asked for "a specific, reasonable number of days" with no further constraint. Result: **both conditions converged** — single-agent (trivially, same generation) and, more interestingly, the two blind subagents *also* landed on the same value (14 days) despite neither seeing the other's output. Rerunning with a small design fix — explicitly asking for "a specific, slightly unusual number of days, not a common default like 7, 14, or 30" — to remove the obvious cultural-default convergence risk, the real result was still **both conditions consistent**: single-agent 19/19, multi-agent subagents independently landed on 11/11.

This is an honest negative result for the specific mechanism this repro tested (numeric-fact recall), and it points to a real, disclosed scope limitation worth stating precisely: Cognition's own example (two subagents on a Flappy Bird clone, one building a Mario-style background, the other a bird that doesn't match) is about **open creative/stylistic interpretation** — genuinely high-variance choices with no shared convention to fall back on. This repro tested convergence on a **single scalar number**, which real runs suggest the same model tends to agree with itself on even when blind and explicitly told to be unusual — a narrower, easier-to-coincidentally-agree-on case than Cognition's original example. The risk Cognition describes is real and well-documented; this specific repro's design wasn't the one to reproduce it, and that's disclosed rather than glossed over.

## Install

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Configure

Paste your key into `agents-cookbook/.env` at the **cookbook root** — this recipe reads it automatically. To override just this recipe, `cp .env.example .env` here instead.

## Run

```bash
python multi_agent_systems.py
```

Runs both demos in sequence and prints each result as JSON.

## Files

| File | Role |
|---|---|
| `multi_agent_systems.py` | Both demos and the CLI entry point — the file you actually run |
| `multi_agent_systems_docs.py` | **Documentation only** — self-contained per-block version for the blog. Not run as a script, not kept in sync automatically. |
