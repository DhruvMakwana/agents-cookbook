# Choosing a Framework

The identical tiny tool-calling task, solved three real ways on the identical Claude model: the raw Anthropic client (own the loop), LangChain/LangGraph's `create_agent`, and Pydantic AI's `Agent`. Real lines of code, real call counts, real answers — not a feature-comparison table copied from each project's marketing page. Concept write-up: [Choosing a Framework](https://dhruvmakwana.github.io/agents-deep-dive/choosing-a-framework/).

Needs an Anthropic key. Unlike the rest of this cookbook, this recipe's `requirements.txt` pulls in real third-party framework packages (LangChain, LangGraph, Pydantic AI) rather than just the Anthropic SDK — that's the entire point of this one.

## The three implementations

- **Raw Anthropic client** (`run_raw`): the same tool-calling loop pattern as `agent-loop-from-scratch/` — full manual control over the message list, the tool-result construction, and the stop condition.
- **LangChain / LangGraph** (`run_langgraph`): `create_agent(model, tools=[...])` builds a compiled graph; `.invoke(...)` runs it.
- **Pydantic AI** (`run_pydantic_ai`): `Agent(model, tools=[...])`; `.run_sync(...)` runs it.

All three use the identical `calculate` tool (a safe AST-walk evaluator, the same pattern used throughout this cookbook) and the identical question, so the only thing that varies is the framework's own orchestration code.

## What actually happened, run against Claude Haiku 4.5

**Input**, identical for all three: *"What is 15% of 240, plus 30?"* Ground truth (computed independently): 66.0.

| Implementation | Real lines of orchestration code | Real calls | Real answer |
|---|---|---|---|
| Raw Anthropic client | 15 | 2 | *"15% of 240 plus 30 is **66**... 15% of 240 = 0.15 × 240 = 36. 36 + 30 = 66"* |
| LangChain / LangGraph `create_agent` | 8 | 2 | *"15% of 240 is 36, and when you add 30 to that, you get **66**."* |
| Pydantic AI `Agent` | 5 | 2 | *"15% of 240 is 36, and when you add 30 to that, you get **66**."* |

All three got the correct answer, in the same number of real calls, on the first real run — no framework needed a second attempt or produced a wrong result. LangGraph's and Pydantic AI's final answers came back character-for-character identical, which looks suspicious but is most likely coincidental convergence on the same natural phrasing for a simple, well-defined task, not evidence of a shared code path (their internal message handling and tool-calling wiring are genuinely different).

The line-count gap is real and matches what each framework is actually for: the raw client's 15 lines are entirely the tool-calling loop itself (send, check `stop_reason`, execute, append, repeat) — visible and modifiable, at the cost of writing it. LangGraph's 8 lines hand that loop to a compiled graph in exchange for accepting its state-and-message conventions. Pydantic AI's 5 lines go further, in exchange for accepting its typed-agent conventions instead. None of this measures "quality" — it measures how much of the mechanism each approach makes you write by hand versus adopt as-is, which is the real, honest version of the own-the-loop trade-off.

**One more real, disclosed observation**: Pydantic AI prints a startup banner to stdout by default (framework version, model, tool count, an "observability: off" nudge toward its paid Logfire product) unless `PYDANTIC_AI_NO_BANNER=1` is set — a real, out-of-the-box behavior difference worth knowing about before you see it appear in your own terminal or logs for the first time.

## Install

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Note `pydantic-ai-slim[anthropic]` rather than the full `pydantic-ai` package in `requirements.txt` — the full package's `mcp` extra pulls in `fastmcp-slim`, which requires `python-dotenv>=1.1.0` and conflicts with this cookbook's shared `python-dotenv==1.0.1` pin. This recipe doesn't need MCP, so the slim install avoids the conflict entirely.

## Configure

Paste your key into `agents-cookbook/.env` at the **cookbook root** — this recipe reads it automatically. To override just this recipe, `cp .env.example .env` here instead.

## Run

```bash
python framework_shootout.py
```

Runs all three implementations in sequence and prints each result.

## Files

| File | Role |
|---|---|
| `framework_shootout.py` | All three implementations and the CLI entry point — the file you actually run |
| `framework_shootout_docs.py` | **Documentation only** — self-contained per-block version for the blog. Not run as a script, not kept in sync automatically. |
