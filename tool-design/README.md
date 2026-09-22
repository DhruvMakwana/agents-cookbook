# Tool Design

The same underlying fictional task-tracker data, exposed through three different tool surfaces to the same model, measured on real call count and token count -- plus a real comparison of terse versus actionable tool-error messages. Concept write-up: [Tool Design](https://dhruvmakwana.github.io/agents-deep-dive/tool-design/).

No framework -- the raw Anthropic client throughout, same as the rest of this cookbook. Needs an Anthropic key.

## The demos

- **Tool surfaces** (`tool_surface_demo`): the identical question -- "which tasks are blocked, and why?" -- asked three ways: **endpoint wrappers** (`list_tasks`, `list_comments`, composition left to the model), **consolidated** (one purpose-built `get_blocked_tasks_with_reasons` tool), and **code execution** (one `execute_python` tool running model-written code against a small library, so raw intermediate data never has to become tokens in context).
- **Errors as observations** (`error_message_demo`): the same ambiguous request to create a task, sent to a tool with a terse validation error (`"ValidationError: priority"`) and with an actionable one (`"Invalid priority 'pretty urgent'. Must be exactly one of: low, medium, high, urgent."`) -- comparing not just how many turns each takes to recover, but what value it recovers *to*.

Model choice is task-scaled: the tool-surface comparison hardcodes `claude-sonnet-5` (writing correct filtering code for the code-execution surface needs more than Haiku-tier reasoning). The error-message demo defaults to Haiku -- deliberately testing a fast/cheap model's recovery behavior.

## What actually happened, run against Claude Sonnet 5 and Claude Haiku 4.5

**Tool surfaces**, same question, same model, same correct answer (3 blocked tasks, each with the right blocking reason):

| Surface | Calls | Total tokens |
|---|---|---|
| Endpoint wrappers | 3 | 3,079 |
| Consolidated | 2 | 1,563 |
| Code execution | 3 | 2,951 |

Consolidated won outright on both axes -- half the tokens of endpoint wrappers, fewest calls. Code execution didn't beat endpoint wrappers on call count in this run (both needed 3), but did use noticeably fewer tokens (2,951 vs. 3,079) -- an honest, unglamorous result: for a query shape this simple, a single well-designed purpose-built tool is hard to beat, and code execution's real advantage (avoiding a combinatorial explosion of purpose-built tools for every possible query shape) doesn't show up on one fixed question. It's a scaling argument, not a per-call one -- and it's exactly the reason this recipe doesn't oversell code execution as a strict win here.

**Errors as observations**: both conditions converged in exactly the same number of calls -- 2. The terse error didn't cost extra turns, which might suggest it doesn't matter. What differed was the *value* the model recovered to. Given `{"error": "ValidationError: priority"}` (no information about what's valid), the model guessed `"high"` -- a safe, generic middle value, disconnected from the user's actual words ("pretty urgent"). Given the actionable error (`"Invalid priority 'pretty urgent'. Must be exactly one of: low, medium, high, urgent."`), the model chose `"urgent"` -- a closer, better-justified match. The real finding isn't retry count, it's recovery quality: an actionable error didn't make the loop faster here, it made the eventual answer more correct.

## Install

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Configure

Paste your key into `agents-cookbook/.env` at the **cookbook root** -- this recipe reads it automatically. To override just this recipe, `cp .env.example .env` here instead.

## Run

```bash
python tool_design.py
```

Runs both demos in sequence and prints each result as JSON.

## Files

| File | Role |
|---|---|
| `tool_design.py` | Both demos and the CLI entry point -- the file you actually run |
| `tool_design_docs.py` | **Documentation only** -- self-contained per-block version for the blog. Not run as a script, not kept in sync automatically. |
