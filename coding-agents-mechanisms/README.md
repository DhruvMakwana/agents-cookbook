# Coding Agents: Mechanisms

Two real repros of SWE-agent's documented Agent-Computer Interface (ACI) principles: a real syntax-linting guardrail on a multi-step code edit, and a real review-loop repro -- giving the agent a verifiable check (a real, independently-run test suite) versus no way to check its own work before submitting. Concept write-up: [Coding Agents: Mechanisms](https://dhruvmakwana.github.io/agents-deep-dive/coding-agents-mechanisms/).

No framework -- the raw Anthropic client throughout. Needs an Anthropic key. Sonnet 5 throughout.

## The two repros

- **Syntax-linting guardrail** (`linting_guardrail_demo`): a nested-conditional code restructuring (adding a new parameter and a nested branch inside two existing branches), the kind of multi-line, indentation-sensitive edit that's genuinely error-prone to get right in one `str_replace` call. Run with and without a real `ast.parse`-based syntax check fed back after each edit, mirroring SWE-agent's own documented linting guardrail.
- **Review loop / verifiable tasks** (`review_loop_demo`): a real, subtle binary-search off-by-one bug (only breaks correctness for specific inputs, not obvious from reading the code) that the agent must fix. Run with a `run_tests` tool available (a real, independently-executed test suite the agent can check its fix against) and without one (the agent submits its first attempt with no way to verify it).

## What actually happened, run against Claude Sonnet 5

**Both repros, across two independently-designed task variants each, were clean, honest ties -- 1.0 vs. 1.0 (100% vs. 100%) on every real measurement, four times over.** The linting guardrail demo was first tried against a flatter elif-chain edit (perfect on both sides), then redesigned around a genuinely harder nested-restructuring edit requiring a new parameter and branch logic threaded through two existing conditional branches -- still perfect on both sides, 5/5 trials each, every single edit made in one clean `str_replace` call with valid syntax. The review-loop demo's first bug (an averaging-window off-by-one) turned out to be one Sonnet 5 solved correctly every time regardless of whether it could run tests; redesigned around a real, verified-divergent binary-search bug (confirmed with a 2,000-case random search to actually trigger the failure, since the first hand-picked test cases for it didn't), it was *still* a clean 5/5 vs. 5/5 tie -- Sonnet 5 fixed a genuinely subtle, classic off-by-one correctly on the first attempt, every time, with zero ability to check its own work in the no-review-loop condition.

**This is a real, dated, honestly-reported finding worth stating precisely, not a failed demo.** SWE-agent's own real, cited ablation (2024) found removing its linting guardrail dropped SWE-bench Lite performance from 18.0% to 10.3% -- a real, measured, substantial gap for the models available then. A real, small-scale repro against Sonnet 5 (2026) found no measurable gap from either the linting guardrail or the review-loop's test-checking ability, across two genuinely different, independently redesigned task variants per demo. The honest interpretation is scoped precisely: for tasks at this scale and this specific current-generation model, these particular ACI safety nets didn't move the needle in this repro -- not a claim that they're universally unnecessary now, but a real, current data point on how much the underlying model's reliability has shifted since the original ablation, worth checking rather than assuming either way.

## Install

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Configure

Paste your key into `agents-cookbook/.env` at the **cookbook root** -- this recipe reads it automatically. To override just this recipe, `cp .env.example .env` here instead.

## Run

```bash
python coding_agents_mechanisms.py
```

Runs both demos in sequence (5 trials per condition, 4 conditions total) and prints each result as JSON.

## Files

| File | Role |
|---|---|
| `coding_agents_mechanisms.py` | Both demos and the CLI entry point -- the file you actually run |
| `coding_agents_mechanisms_docs.py` | **Documentation only** -- self-contained per-block version for the blog. Not run as a script, not kept in sync automatically. |
