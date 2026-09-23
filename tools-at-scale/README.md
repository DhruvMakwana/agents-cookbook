# Tools at Scale

The same 3-step, real-tool-dependent helpdesk task, answered against a 25-tool library three ways: naively (every tool definition in context, one call per turn), with tool search (pre-filtering to only relevant tools before the model ever sees the rest), and with programmatic tool calling (the model writes one program that calls all three real tools and returns only the final result). Concept write-up: [Tools at Scale](https://dhruvmakwana.github.io/agents-deep-dive/tools-at-scale/).

No framework -- the raw Anthropic client throughout, same as the rest of this cookbook. Needs an Anthropic key. Sonnet only (the task needs real multi-step tool reasoning).

## The task

*"Employee EMP-4471 needs access to DataViz Pro. Look up the employee, check whether a license seat is available for their department, and provision access if one is."*

Three real tools solve it: `lookup_employee`, `check_license_availability`, `provision_access`. 22 unrelated helpdesk-adjacent filler tools (password resets, hardware orders, badge access, facilities requests, ...) sit alongside them, for scale -- illustrative of a real, larger internal tool library, not part of this task's real path.

## The three conditions

- **A. Naive** (`naive_demo`): all 25 tool definitions in context on every turn, standard one-tool-call-per-turn loop.
- **B. Tool search** (`tool_search_demo`): a minimal keyword-overlap retriever (`search_relevant_tools`) pre-filters the library down to the 3 relevant tools before the model ever sees the rest -- illustrative of the mechanism (Anthropic's real Tool Search Tool uses `defer_loading` + a proper search index), not a production embedding search.
- **C. Programmatic tool calling** (`programmatic_demo`): a single `execute_workflow` tool takes a Python code string; the model writes code that calls all three real functions in order and prints only what it wants returned. Intermediate results (the employee record, the seat count) never enter the conversation as separate turns.

## What actually happened, run against Claude Sonnet 5

All three conditions reached the correct outcome, independently verifiable against the fixture data (12 seats available for DataViz Pro in Engineering, so provisioning should succeed): employee Jamie Cole looked up correctly, 12 seats confirmed available, access provisioned with a real confirmation ID (`prov_EMP-4471_DataVizPro`).

| Condition | Calls | Total tokens | vs. naive |
|---|---|---|---|
| A. Naive (25 tools in context) | 4 | 9,011 | -- |
| B. Tool search (pre-filtered to 3) | 4 | 4,065 | -55% |
| C. Programmatic (1 workflow tool) | 3 | 3,743 | -58% |

Same call count for naive and tool search (4) -- the token savings come entirely from not paying for 22 irrelevant tool definitions on every turn, not from fewer round-trips. Programmatic tool calling saved both a call *and* tokens: the model chained all three real tools inside one generated program instead of one tool call per turn, so the loop finished in 3 calls instead of 4, and none of the intermediate `lookup_employee`/`check_license_availability` results were echoed back into the conversation as separate turns -- they stayed inside the executed code, with only the final summary printed and returned.

**A real bug caught before any paid calls were made**: the first version of `search_relevant_tools` used raw whole-sentence word overlap, and returned `['check_printer_status', 'check_license_availability', 'check_ticket_status']` for the task question -- only 1 of the 3 tools actually needed, with the model's task-critical `lookup_employee` and `provision_access` missing entirely. The cause: generic words like "check" and "status" appear in the task question *and* in most of the filler tools' descriptions ("Check the status of a support ticket", "Check whether a printer is online"), so filler tools scored as high or higher than the real tools' hand-curated, more specific keyword sets. Fixed by filtering common stopwords (including "check" and "status" specifically) from both the question and the fallback description-word matching before scoring -- confirmed via a zero-cost dry run (`search_relevant_tools(TASK_QUESTION)` returning exactly the 3 real tools) before spending any real API calls on condition B.

## Install

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Configure

Paste your key into `agents-cookbook/.env` at the **cookbook root** -- this recipe reads it automatically. To override just this recipe, `cp .env.example .env` here instead.

## Run

```bash
python tools_at_scale.py
```

Runs all three conditions in sequence and prints each result as JSON.

## Files

| File | Role |
|---|---|
| `tools_at_scale.py` | All three demos and the CLI entry point -- the file you actually run |
| `tools_at_scale_docs.py` | **Documentation only** -- self-contained per-block version for the blog. Not run as a script, not kept in sync automatically. |
