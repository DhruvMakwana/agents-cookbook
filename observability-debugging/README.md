# Observability and Debugging

A real repro of the actual OpenTelemetry GenAI semantic conventions applied to an agent that produces a confidently wrong final answer while every individual call succeeds cleanly -- no exceptions, no errors, `stop_reason == "end_turn"`. Concept write-up: [Observability and Debugging](https://dhruvmakwana.github.io/agents-deep-dive/observability-debugging/).

No framework -- the raw Anthropic client throughout. Needs an Anthropic key. Sonnet 5.

## The repro

A real, subtly buggy tool (`get_daily_active_users`) that actually returns *cumulative all-time* users instead of yesterday's daily figure -- the bug is in the tool implementation, not anything the model does. The agent calls it, trusts the result, and confidently reports it against a target. The demo emits real, spec-shaped OpenTelemetry GenAI trace spans (`gen_ai.operation.name`, `gen_ai.provider.name`, `gen_ai.tool.name`, `gen_ai.usage.*`, and `gen_ai.input.messages`/`gen_ai.output.messages` -- the real spec's own place for tool call arguments and results) for the whole run, then runs a second, fully independent diagnostic pass that uses *only* the trace's own data -- no access to the final answer, no re-running the agent -- to check whether the real root cause is actually findable from the trace alone.

## What actually happened, run against Claude Sonnet 5

**A real bug was caught and fixed first.** The trace emitter's first version assumed every non-text content block was a `tool_use` block and read `.name`/`.input` off it unconditionally -- it crashed the first time Sonnet 5's real response included an adaptive-thinking block ahead of its tool call, since a `ThinkingBlock` has neither attribute. Fixed by handling `text`, `tool_use`, and any other block type explicitly rather than assuming a fixed two-type universe.

**With that fixed, the real run produced exactly the scenario the topic is about.** The traditional "did the call succeed" view: `{"status": "success", "stop_reason": "end_turn", "error": null}` -- clean, no red flags anywhere. The real final answer: *"Yesterday's DAU for Nimbus was 2,340,000. Compared to your target of 50,000 DAU, that's well above target — roughly 46.8x the goal... This is a very healthy result."* A confident, wrong, business-relevant claim, produced by a tool bug the model had no way to detect from its own reasoning -- the number it received really was what the tool returned, it just wasn't the daily figure the tool's name and description promised.

**The independent trace-only diagnosis found the real root cause immediately.** Given only the real trace's spans -- not the final answer, not a re-run -- the diagnostic pass inspected the `execute_tool get_daily_active_users` span's real `gen_ai.output.messages` attribute, found `daily_active_users: 2340000`, and correctly flagged it: *"implausibly large for a single day, likely a cumulative/all-time figure mislabeled as daily."* The exact tool call, the exact bad value, and a specific, correct hypothesis about the bug -- all from the trace alone, with zero need to reproduce the failure.

## Install

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Configure

Paste your key into `agents-cookbook/.env` at the **cookbook root** -- this recipe reads it automatically. To override just this recipe, `cp .env.example .env` here instead.

## Run

```bash
python observability_debugging.py
```

Runs the traced agent call once and the trace-only diagnosis, printing both as JSON.

## Files

| File | Role |
|---|---|
| `observability_debugging.py` | The demo and the CLI entry point -- the file you actually run |
| `observability_debugging_docs.py` | **Documentation only** -- self-contained per-block version for the blog. Not run as a script, not kept in sync automatically. |
