# Coding Agent Products and Configuration

Two real repros of the configuration mechanisms coding agent products expose: a CLAUDE.md-style project-instructions file's real effect on generated code, delivered the way Anthropic's own docs say it's actually delivered, and a real comparison of a prompted-only rule against a structural hook when nothing else protects a file. Concept write-up: [Coding Agent Products and Configuration](https://dhruvmakwana.github.io/agents-deep-dive/coding-agent-config/).

No framework -- the raw Anthropic client throughout. Needs an Anthropic key. Sonnet 5 throughout.

## The two repros

- **CLAUDE.md-style project instructions** (`project_instructions_demo`): a code-generation task run with and without a project-instructions block (no f-strings, `do_`-prefixed function names, imperative-mood docstrings), delivered exactly the way Anthropic's own docs describe real CLAUDE.md delivery -- as a user message after the system prompt, not folded into the system prompt itself. Real, programmatic compliance checking (regex + AST), not LLM judgment.
- **Hook vs. no hook, with no protective rule at all** (`hook_vs_prompt_demo`): a cleanup task with an explicit, reasonable-sounding request to delete three files including one deliberately unprotected-by-prompt but structurally protected-by-hook file. Neither condition's system prompt says anything about protecting the file -- this isolates what a hook adds when nothing else does.

## What actually happened, run against Claude Sonnet 5

**CLAUDE.md-style instructions produced a real, strong, measurable compliance shift.** Without project instructions, generated code followed no particular convention: `do_` prefix compliance was 0% across all trials, and f-string avoidance ranged 67%–100% run to run (Sonnet 5 sometimes defaults to `.format()` on its own, but never reliably). With the project-instructions block delivered as a user message (matching real CLAUDE.md mechanics), compliance was 100% on both the `do_` prefix and f-string avoidance, every trial, across multiple full runs -- real code like `def do_format_total_as_currency(order_totals):` with a correct imperative-mood docstring, every time.

**The hook comparison required a real design correction to actually test the right thing.** The first version gave the prompted-only condition an explicit system-level rule ("never delete config.json"), and Sonnet 5 never violated it even under a persuasive override attempt -- but that meant the hook never actually fired in any trial (`blocked_by_hook: false` throughout), so the comparison wasn't testing what a hook adds. Redesigned with **no protective rule in either condition's system prompt** -- isolating exactly what the hook protects against when nothing else does. Real result: with no hook, the model complied with an explicit, direct request and deleted `config.json` in all 5 trials (`prompted_only_survival_rate: 0.0`). With the hook active -- a plain deterministic check before the tool executes, not a second model call -- `config.json` survived in all 5 trials (`with_hook_survival_rate: 1.0`), and the model reported the block gracefully and suggested real alternatives (rename the file first, use a different access method) rather than treating it as an error.

## Install

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Configure

Paste your key into `agents-cookbook/.env` at the **cookbook root** -- this recipe reads it automatically. To override just this recipe, `cp .env.example .env` here instead.

## Run

```bash
python coding_agent_config.py
```

Runs both demos in sequence and prints each result as JSON.

## Files

| File | Role |
|---|---|
| `coding_agent_config.py` | Both demos and the CLI entry point -- the file you actually run |
| `coding_agent_config_docs.py` | **Documentation only** -- self-contained per-block version for the blog. Not run as a script, not kept in sync automatically. |
