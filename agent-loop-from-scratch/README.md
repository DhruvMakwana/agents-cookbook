# The Agent Loop From Scratch

What actually happens between the model deciding to call a tool and the tool's result reaching the model again — built with the raw Anthropic client, no framework. Concept write-up: [The Agent Loop From Scratch](https://dhruvmakwana.github.io/agents-deep-dive/agent-loop-from-scratch/).

This recipe deliberately doesn't use this cookbook's pluggable `llm.py` — seeing the real request/response shape (`tool_use` blocks, `tool_result` messages, `stop_reason`) is the point, so it talks to the Anthropic client directly. Needs an Anthropic key.

## What's in it

- **`calculate(expression)`** — a real calculator. Not `eval()` on model output: an AST walk that only permits numbers and `+ - * / **`, so a malformed or adversarial expression can't do anything beyond arithmetic.
- **`convert_currency(amount, from_currency, to_currency)`** — a fixed exchange-rate table (illustrative, not live data — the tool description says so).
- **`run_agent_loop`** — the loop itself: send the conversation, and if the model's `stop_reason` is `"tool_use"`, actually execute the requested tool(s) and send the results back as a new message. Capped at 6 iterations; if the model still hasn't finished, the loop returns an honest "ran out of steps" result instead of looping forever.
- **`ask_without_tools`** — the same question with no tools at all, as a baseline.

## What actually happened, run against Claude Haiku 4.5

Question: *"I'm splitting a €127.50 dinner bill among 4 friends, and we want to add an 18% tip on top before splitting. What does each person owe, in US dollars?"* Ground truth, computed independently in plain Python, not by the model: **$40.62**.

**Baseline, no tools**, got every arithmetic step right on its own (18% tip: €22.95; total: €150.45; per person: €37.61) but had no real exchange rate to work with, and rather than asserting a confident wrong number, it said so and gave a range: *"Each person owes approximately $40.80–$41.50 USD (depending on the current EUR/USD exchange rate, which fluctuates daily) ... Check a current converter for the exact amount with today's rate."* A genuinely useful finding to state plainly: the failure mode here isn't bad arithmetic, it's a model being reasonably honest about not having live data — and a range built on a guessed rate is still off from the real answer by real money, at any amount above pocket change.

**Tool-using loop** converged in 3 turns and landed on **$40.62 — the exact ground truth**. The real trace:

```json
{
  "outcome": "answered",
  "answer": "Each person owes approximately $40.62 USD. ...",
  "trace": [
    {"step": 1, "tool": "calculate", "arguments": {"expression": "127.50 * 1.18"}, "result": {"result": 150.45}},
    {"step": 1, "tool": "calculate", "arguments": {"expression": "127.50 * 1.18 / 4"}, "result": {"result": 37.6125}},
    {"step": 2, "tool": "convert_currency", "arguments": {"amount": 37.6125, "from_currency": "EUR", "to_currency": "USD"}, "result": {"result": 40.6215}}
  ],
  "steps": 3
}
```

Two things worth naming precisely. First, the two `calculate` calls both landed in `step: 1` — the model issued them in the same turn, in parallel, without being asked to (Anthropic's tool use allows multiple `tool_use` blocks in one response by default). Second, that first turn is mildly redundant: the second `calculate` call recomputes the whole tip-and-split expression instead of reusing the first call's result — not wrong, just not the most efficient path available, and worth knowing that a real tool-using model doesn't always take the shortest route even when it reaches the right answer.

## Install

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Configure

Paste your key into `agents-cookbook/.env` at the **cookbook root** (see the cookbook's top-level README) — this recipe reads it automatically. To override just this recipe, `cp .env.example .env` here instead.

## Run

```bash
python agent_loop.py
```

Prints the no-tools baseline, then the full tool-using loop (including its trace) as JSON, then the independently computed ground truth.

## Files

| File | Role |
|---|---|
| `agent_loop.py` | Both tools, the loop, the baseline, and the CLI entry point — the file you actually run |
| `agent_loop_docs.py` | **Documentation only** — self-contained per-block version for the blog. Not run as a script, not kept in sync automatically. |
