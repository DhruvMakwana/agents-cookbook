# Data and Environments

A real repro of two mechanisms this topic is built around: SWE-smith's real task-synthesis approach (breaking real tests in working code, no historical PR/issue needed) and the "verifiers" concept behind RLVR (a real, deterministic pass/fail check, not an LLM's opinion). Concept write-up: [Data and Environments](https://dhruvmakwana.github.io/agents-deep-dive/data-environments/).

No framework — the raw Anthropic client throughout, plus real local `pytest` execution. Needs an Anthropic key. Sonnet 5.

## The repro

A real, working Python function (`merge_intervals`) with a real, passing 5-test suite. Four real steps:

1. **Synthesize a task** — a real Claude call introduces exactly one subtle, realistic bug into the working function, the same way SWE-smith generates tasks from arbitrary working code rather than requiring an existing real-world bug report.
2. **Verify the task is genuine** — the real test suite is actually executed against the buggy code. This is the real, deterministic verifier: pass/fail comes from running code, not from an LLM judging whether the change "looks buggy."
3. **Attempt a fix** — a second real Claude call, given *only* the real failing pytest output (not the original correct code), attempts to fix the bug.
4. **Verify the fix** — the real test suite runs again against the fix.

## What actually happened, run against Claude Sonnet 5

**Synthesis**: Claude changed one comparison operator — `start <= last_end` became `start < last_end` — a genuinely subtle, realistic boundary bug (intervals that exactly touch, like `[1,4]` and `[4,5]`, no longer merge). **Real verification**: 4 of 5 tests passed, 1 failed — `test_touching_intervals`, exactly the case the injected bug breaks, and nothing else. A clean, real synthesized task: hard enough to be real, narrow enough to be solvable, verified by actually running the tests rather than trusting the injection was "plausible."

**Fix**: given only the real failing pytest output — not the original correct code — the second Claude call correctly diagnosed the boundary condition and restored `start <= last_end`. **Real re-verification**: all 5 tests passed.

A real bug was caught and fixed in this recipe's own code along the way: an earlier version indexed `response.content[0].text` directly, which broke with `AttributeError: 'ThinkingBlock' object has no attribute 'text'` — a real, recurring gotcha (the first content block isn't reliably the text block). Fixed by filtering for `block.type == "text"` explicitly rather than assuming an index, then the real run above was captured clean.

## Install

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Configure

Paste your key into `agents-cookbook/.env` at the **cookbook root** — this recipe reads it automatically. To override just this recipe, `cp .env.example .env` here instead.

## Run

```bash
python data_environments.py
```

Runs the full real synthesis-then-fix loop and prints both real pytest verification results as JSON.

## Files

| File | Role |
|---|---|
| `data_environments.py` | The full loop and the CLI entry point — the file you actually run |
| `data_environments_docs.py` | **Documentation only** — self-contained per-block version for the blog. Not run as a script, not kept in sync automatically. |
