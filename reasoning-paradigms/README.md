# Reasoning Paradigms

Four mechanisms from the agent-reasoning literature, each with real code and a real run against a checkable ground truth. Concept write-up: [Reasoning Paradigms](https://dhruvmakwana.github.io/agents-deep-dive/reasoning-paradigms/).

No framework — the raw Anthropic client throughout, same as [`agent-loop-from-scratch/`](../agent-loop-from-scratch/) and [`workflow-patterns/`](../workflow-patterns/). Needs an Anthropic key.

## The demos

- **Reflexion** (`reflexion_demo`): solve a state-tracking puzzle (9 sequential swaps of who holds which key), verify the answer against a local, non-LLM ground truth, and only if wrong, generate a verbal self-reflection and retry with it in context.
- **ReWOO** (`rewoo_demo`): plan every tool call up front in one call, with `#E`-style variable substitution across steps, execute the plan deterministically (no LLM calls), then solve from the gathered evidence in one more call.
- **ReAct** (`react_demo`): the same question, solved by deciding one tool call at a time based on the latest observation — deliberately restricted to one tool call per turn even when the model requests several, so native parallel tool-calling can't quietly collapse it into fewer turns.
- **LLM Compiler** (`llm_compiler_demo`): reuses ReWOO's own plan, but dispatches its independent steps concurrently instead of strictly in written order.
- **Plan-and-Solve** (`plan_and_solve_demo`): the same word problem solved with a plain "let's think step by step" prompt and with an explicit plan-then-solve prompt — this technique's entire mechanism is the prompt, not an architecture.

Model choice is task-scaled: Reflexion and Plan-and-Solve default to Haiku (both are deliberately testing a fast/cheap model's failure-and-recovery behavior). ReWOO and ReAct hardcode `claude-sonnet-5` — planning or executing a multi-step tool sequence needs more than Haiku-tier reasoning.

## What actually happened, run against Claude Haiku 4.5 and Claude Sonnet 5

**Reflexion**: Haiku got the 9-swap puzzle right on the **first attempt** — it wrote out the holder state after every single swap instead of trying to track it mentally, and that showed up in the actual output. No reflection fired. An honest result, not a weaker one: the mechanism exists and is real, but this run's failure precondition (a wrong first attempt) didn't occur — writing out intermediate state, not the model's raw capability, is the likely reason.

**ReWOO vs. ReAct**, same question, same model (Sonnet), same final numeric answer (**69.21%**):

| | Calls | Total tokens |
|---|---|---|
| ReWOO | 2 | 756 |
| ReAct | 5 | 5,141 |

ReAct needed **2.5x the calls and 6.8x the tokens** of ReWOO for the identical result — matching the paper's own claim (5x token efficiency on a different benchmark) far more than any latency claim, which the paper never makes. The gap isn't just call count: ReAct's transcript grows every turn and gets resent in full on the next call, so tokens grow faster than calls do.

A genuine finding, not a smoothed-over one: ReWOO's own plan had 6 steps, and step `E6` tried to call `round(E5, 2)` — a function this recipe's calculator deliberately doesn't support (it only allows `+ - * / **`, the same restriction as `agent-loop-from-scratch`'s calculator). That step errored. The plan-then-execute split means a bad step is only caught once it's actually run, not before — unlike ReAct, where the model sees each result before choosing the next action. The final synthesis call still produced the correct `69.21%` anyway, reasoning from `E5`'s raw (unrounded) value and the error message together. One real trace, one real partial failure, one real recovery.

**LLM Compiler**, reusing that same plan: it correctly identified `E1`, `E2`, `E3` (the three lookups) as having no dependency on each other's results, and `E4`–`E6` (the arithmetic) as dependent. Dispatching the three independent lookups concurrently took **0.45s** against **1.22s** run one at a time — a ~2.7x speedup for 3 calls, close to the theoretical 3x here because these are simulated, uniform-latency waits rather than real network calls with queueing variance (see `workflow-patterns`' parallelization demo for that more realistic 2.6x-of-3x number).

**Plan-and-Solve vs. zero-shot chain-of-thought**: both prompts, run once each on the same 6-step bakery word problem (ground truth: 72 loaves), got **72 correct**. Another honest negative result: the paper's claim is a distributional one — Plan-and-Solve "consistently outperforms zero-shot-CoT... across all datasets" over many problems — not a guarantee that it wins on any single problem. This one, Haiku's zero-shot-CoT answer already matched.

## Install

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Configure

Paste your key into `agents-cookbook/.env` at the **cookbook root** — this recipe reads it automatically. To override just this recipe, `cp .env.example .env` here instead.

## Run

```bash
python reasoning_paradigms.py
```

Runs all four demos in sequence and prints each result as JSON.

## Files

| File | Role |
|---|---|
| `reasoning_paradigms.py` | All demos and the CLI entry point — the file you actually run |
| `reasoning_paradigms_docs.py` | **Documentation only** — self-contained per-block version for the blog. Not run as a script, not kept in sync automatically. |
