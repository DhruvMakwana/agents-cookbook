# KV-Cache Economics

Three real repros against the live Anthropic API: cache write vs. cache read economics, the real invalidation hierarchy (`tools` → `system` → `messages`), and tool masking vs. removal using the real `mid-conversation-tool-changes` beta. Concept write-up: [KV-Cache Economics](https://dhruvmakwana.github.io/agents-deep-dive/kv-cache-economics/).

No framework -- the raw Anthropic client throughout. Needs an Anthropic key. Demo 1+2 use Sonnet 5; Demo 3 uses Opus 5, because the `mid-conversation-tool-changes` beta this demo depends on is not available on Sonnet 5.

## The three repros

- **Cache write vs. read** (`cache_economics_and_hierarchy_demo`, calls 1-2): the same stable ~18-tool library and system prompt, sent twice. First call writes the cache; second call, byte-identical prefix, reads it.
- **The invalidation hierarchy** (same function, calls 3-4): a real `tool_choice` change (should only cost the messages level, per Anthropic's docs) contrasted with a real one-word edit to a tool's description (should invalidate everything).
- **Tool masking vs. removal** (`tool_masking_vs_removal_demo`): the real `tool_removal` content block on a mid-conversation `role:"system"` message (tools array stays byte-identical, cache should survive) contrasted with physically editing the top-level `tools` array (a different array, cache should not survive) -- plus a functional check that the "masked" tool is genuinely unusable, not just hidden from view.

## What actually happened, run against Claude Sonnet 5 / Opus 5

**Cache write and read matched exactly, and the invalidation hierarchy held precisely as documented:**

| Call | Real result |
|---|---|
| 1. Cold cache | `cache_creation_input_tokens: 2279`, `cache_read_input_tokens: 0` -- a real write |
| 2. Identical tools+system prefix, different question | `cache_read_input_tokens: 2279`, `cache_creation_input_tokens: 0` -- exact match to call 1's write size |
| 3. Same tools+system, `tool_choice` changed to `{"type": "any"}` | `cache_read_input_tokens: 2279` -- **unchanged**, confirming a `tool_choice` change costs only the messages level, not tools/system |
| 4. Same tools+system, one tool's description edited by one word | `cache_creation_input_tokens: 2283`, `cache_read_input_tokens: 0` -- **full invalidation**, a fresh write covering the whole prefix again |

**Tool masking preserved the cache across multiple turns; physically editing the array did not:**

| Call | Real result |
|---|---|
| A. Baseline (tools+system already resident in cache from earlier development runs against this recipe -- prompt caching reads refresh the TTL, so this shows as a read, not a fresh write) | `cache_read_input_tokens: 2211` |
| B1. `tool_removal` directive withdraws one tool; top-level `tools` array is byte-identical to call A's | `cache_read_input_tokens: 2211` -- **identical to call A**, cache fully preserved despite the masking directive |
| B2. Same conversation continued one more turn (real assistant reply replayed, new user question) | `cache_read_input_tokens: 2211` -- masking still holds several turns later, not just on the one call it was issued |
| Forced `tool_choice` on the masked tool | Real `400` error: `"tool_choice: forced tool 'check_feature_flag' is absent from the final available-tool set (a tool_removal block removed it without a later add-back)"` -- masking is a genuine, API-enforced access change, not cosmetic |
| C. Physically remove the tool from the top-level `tools` array instead (a different array than call A's) | `cache_creation_input_tokens: 2113` -- a **fresh, distinct** cache entry, not a read of anything preceding it |

The contrast is the finding: masking (`tool_removal`) shares a cache footprint with everything before it -- three calls in a row all read the identical 2,211-token entry. Removal doesn't -- editing the array produces a new entry from scratch (2,113 tokens, reflecting one fewer tool), with no relationship to what came before. Same functional outcome (the model can no longer use that tool) via two different mechanisms, with very different cache economics.

## Install

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Configure

Paste your key into `agents-cookbook/.env` at the **cookbook root** -- this recipe reads it automatically. To override just this recipe, `cp .env.example .env` here instead.

## Run

```bash
python kv_cache_economics.py
```

Runs both demos in sequence and prints each result as JSON. Because prompt-cache reads refresh the cache's TTL, repeated runs during development will show earlier calls as reads rather than fresh writes -- that's real, expected caching behavior, not a bug in the recipe.

## Files

| File | Role |
|---|---|
| `kv_cache_economics.py` | Both demos and the CLI entry point -- the file you actually run |
| `kv_cache_economics_docs.py` | **Documentation only** -- self-contained per-block version for the blog. Not run as a script, not kept in sync automatically. |
