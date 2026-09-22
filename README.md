# Agents Cookbook

Runnable, from-scratch implementations of the techniques covered in [Agents, Deep Dive](https://dhruvmakwana.github.io/agents-deep-dive/) — one folder per technique, no framework abstraction layer by default, so every step of each loop stays visible and readable. (A framework shootout recipe, when it lands, is the deliberate exception — that's the point of that one.)

## Recipes

| Recipe | What it builds | Status |
|---|---|---|
| [`what-is-an-agent/`](what-is-an-agent/) | The same customer-support task built as a fixed workflow and as a decision-point agent, with a real captured trace showing the structural difference | ✅ |

More recipes land alongside new pages on the blog.

## Using a recipe

Each folder is self-contained: its own `requirements.txt`, its own `README.md` with install/configure/run instructions, its own `.env.example`. Start with that folder's README.

```bash
git clone git@github.com:DhruvMakwana/agents-cookbook.git
cd agents-cookbook/what-is-an-agent
# follow that folder's README from here
```

## A note on API keys and the default provider

Every recipe reads credentials from a local `.env` file that is git-ignored in every recipe folder — never committed, never logged, never printed by any script here. Unlike the companion RAG cookbook, recipes here default to a **local Ollama model** (no key, no cost) because that's the provider actually verified when these recipes were built. Anthropic and OpenAI are supported through the same pluggable `llm.py` pattern and can be switched on via `LLM_PROVIDER` in `.env`, but check each recipe's own README for which providers were actually exercised versus just supported.

## `_shared/`

`_shared/llm.py` is the canonical copy of the provider-dispatch module used across recipes. It is **copied into each recipe folder**, not imported across folders — every recipe stays pip-installable and runnable entirely on its own. When `_shared/llm.py` changes, re-copy it into any recipe that needs the update.
