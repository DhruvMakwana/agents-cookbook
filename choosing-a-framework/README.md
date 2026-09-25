# Choosing a Framework

The identical tiny tool-calling task, solved four real ways on the identical Claude model: the raw Anthropic client (own the loop), LangChain/LangGraph's `create_agent`, Pydantic AI's `Agent`, and CrewAI's `Agent` (direct `kickoff`, no `Task`/`Crew` wrapper). Real lines of code, real call counts, real answers — not a feature-comparison table copied from each project's marketing page. Concept write-up: [Choosing a Framework](https://dhruvmakwana.github.io/agents-deep-dive/choosing-a-framework/).

Needs an Anthropic key. Unlike the rest of this cookbook, this recipe's `requirements.txt` pulls in real third-party framework packages (LangChain, LangGraph, Pydantic AI, CrewAI) rather than just the Anthropic SDK — that's the entire point of this one.

## The four implementations

- **Raw Anthropic client** (`run_raw`): the same tool-calling loop pattern as `agent-loop-from-scratch/` — full manual control over the message list, the tool-result construction, and the stop condition.
- **LangChain / LangGraph** (`run_langgraph`): `create_agent(model, tools=[...])` builds a compiled graph; `.invoke(...)` runs it.
- **Pydantic AI** (`run_pydantic_ai`): `Agent(model, tools=[...])`; `.run_sync(...)` runs it.
- **CrewAI** (`run_crewai`): `Agent(role=, goal=, backstory=, tools=[...], llm=...)`; `.kickoff(...)` runs it directly — CrewAI's own real, documented "direct Agent interaction" path, skipping the `Task`/`Crew` wrapper most of its docs lead with, for the closest apples-to-apples comparison with the other three.

All four use the identical `calculate` tool (a safe AST-walk evaluator, the same pattern used throughout this cookbook) and the identical question, so the only thing that varies is the framework's own orchestration code.

## What actually happened, run against Claude Haiku 4.5

**Input**, identical for all four: *"What is 15% of 240, plus 30?"* Ground truth (computed independently): 66.0.

| Implementation | Real lines of orchestration code | Real calls | Real answer |
|---|---|---|---|
| Raw Anthropic client | 15 | 2 | *"15% of 240 plus 30 is **66**... 15% of 240 = 0.15 × 240 = 36. 36 + 30 = 66"* |
| LangChain / LangGraph `create_agent` | 8 | 2 | *"15% of 240 is 36, and when you add 30 to that, you get **66**."* |
| Pydantic AI `Agent` | 5 | 2 | *"15% of 240 is 36, and when you add 30 to that, you get **66**."* |
| CrewAI `Agent.kickoff` | 9 | 2 | *"The answer is **66**. Here's the breakdown: 15% of 240 = 36. 36 + 30 = 66."* |

All four got the correct answer, in the same number of real calls, on the first real run — no framework needed a second attempt or produced a wrong result. LangGraph's and Pydantic AI's final answers came back character-for-character identical, which looks suspicious but is most likely coincidental convergence on the same natural phrasing for a simple, well-defined task, not evidence of a shared code path (their internal message handling and tool-calling wiring are genuinely different).

The line-count gap is real and matches what each framework is actually for: the raw client's 15 lines are entirely the tool-calling loop itself (send, check `stop_reason`, execute, append, repeat) — visible and modifiable, at the cost of writing it. LangGraph's 8 lines hand that loop to a compiled graph in exchange for accepting its state-and-message conventions. Pydantic AI's 5 lines go further, in exchange for accepting its typed-agent conventions instead. **CrewAI's 9 lines are real, and real about something the others aren't**: two of those lines are `role=`/`goal=`/`backstory=` — CrewAI's own design asks you to describe the agent as a persona, not just wire up a model and tools, which is a real, deliberate difference in what the framework is actually for (role-based multi-agent orchestration), not a sign the direct-`kickoff` path is poorly suited to a single-tool task. None of this measures "quality" — it measures how much of the mechanism each approach makes you write by hand versus adopt as-is, which is the real, honest version of the own-the-loop trade-off.

**Two more real, disclosed observations**: Pydantic AI prints a startup banner to stdout by default (framework version, model, tool count, an "observability: off" nudge toward its paid Logfire product) unless `PYDANTIC_AI_NO_BANNER=1` is set. CrewAI, by default, prints real, rich, boxed console output for every agent lifecycle event (`LiteAgent Started`, `Tool Execution Started/Completed`, `LiteAgent Completed`) — a real, tested surprise: passing `verbose=False` to the `Agent` constructor (already done in this recipe's own code) reduces some of it, but real, live runs still show CrewAI's own `LiteAgent Started`/`LiteAgent Completed` banners regardless — this appears to be framework-level lifecycle logging that isn't fully gated by the per-agent verbose flag, worth knowing about before it shows up unexpectedly in a production log stream.

## Install

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Note `pydantic-ai-slim[anthropic]` rather than the full `pydantic-ai` package in `requirements.txt` — the full package's `mcp` extra pulls in `fastmcp-slim`, which requires a newer `python-dotenv` than this cookbook's shared pin. This recipe doesn't need MCP, so the slim install avoids that particular conflict. Separately, CrewAI itself requires `python-dotenv>=1.2.2`, which is why this recipe's own `python-dotenv` pin is newer than the rest of the cookbook's shared `.env`-loading pin — a real, current dependency requirement, not an oversight.

## Configure

Paste your key into `agents-cookbook/.env` at the **cookbook root** — this recipe reads it automatically. To override just this recipe, `cp .env.example .env` here instead.

## Run

```bash
python framework_shootout.py
```

Runs all four implementations in sequence and prints each result.

## Files

| File | Role |
|---|---|
| `framework_shootout.py` | All four implementations and the CLI entry point — the file you actually run |
| `framework_shootout_docs.py` | **Documentation only** — self-contained per-block version for the blog. Not run as a script, not kept in sync automatically. |
