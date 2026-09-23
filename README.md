# Agents Cookbook

Runnable, from-scratch implementations of the techniques covered in [Agents, Deep Dive](https://dhruvmakwana.github.io/agents-deep-dive/) — one folder per technique, no framework abstraction layer by default, so every step of each loop stays visible and readable. [`choosing-a-framework/`](choosing-a-framework/) is the deliberate exception — that's the point of that one.

## Recipes

| Recipe | What it builds | Status |
|---|---|---|
| [`what-is-an-agent/`](what-is-an-agent/) | The same customer-support task built as a fixed workflow and as a decision-point agent, with a real captured trace showing the structural difference | ✅ |
| [`agent-loop-from-scratch/`](agent-loop-from-scratch/) | A real tool-calling loop with the raw Anthropic client (no framework) — a safe calculator and a currency-conversion tool, checked against an independently computed ground truth, plus a no-tools baseline for contrast | ✅ |
| [`workflow-patterns/`](workflow-patterns/) | Four of Anthropic's named workflow patterns with real runs each — chaining with a gate, parallelization with measured wall-clock speedup, orchestrator-workers with a genuinely input-dependent split, evaluator-optimizer with a deterministic check | ✅ |
| [`reasoning-paradigms/`](reasoning-paradigms/) | Reflexion's solve-verify-reflect-retry loop, ReWOO vs. ReAct measured on real call count and token count, LLM Compiler's concurrent dispatch reusing ReWOO's own plan, and Plan-and-Solve vs. zero-shot CoT | ✅ |
| [`tool-design/`](tool-design/) | The same fictional task-tracker data exposed through endpoint-wrapper, consolidated, and code-execution tool surfaces, measured on real call count and token count, plus terse vs. actionable tool-error messages compared on real recovery quality | ✅ |
| [`context-engineering/`](context-engineering/) | Minimal real repros of Drew Breunig's four context failures (poisoning, distraction, confusion, clash), each with a real fix applied and a real before/after — including two honest negative results where the failure didn't reproduce | ✅ |
| [`multi-agent-systems/`](multi-agent-systems/) | Anthropic's and Cognition's opposing multi-agent claims tested directly — a real 3.21x token multiplier for a lead-plus-subagents design vs. single-agent, and a real (if inconclusive) test of Cognition's inter-agent consistency risk | ✅ |
| [`evaluating-agents/`](evaluating-agents/) | Outcome vs. trajectory grading, pass@k vs. pass^k measured on 5 real trials, and a capability-motivated prompt change that silently broke a regression suite's own grader — a real, clean regression, caught | ✅ |
| [`agent-security/`](agent-security/) | The lethal trifecta + Rule of Two, and tool poisoning (a supply-chain attack on tool descriptions) — real, safe, fully local repros with no real network calls; the tool-poisoning attack succeeded cleanly, and a static sanitizer stopped it | ✅ |
| [`durable-execution/`](durable-execution/) | A minimal event-log agent, run as two genuinely separate process invocations — a real deliberate crash mid-tool-call, replay-from-log with zero new model calls for completed steps, and idempotent resume with no duplicated side effect | ✅ |
| [`training-agents/`](training-agents/) | Real DPO preference-pair construction from real completions, plus exact GRPO/DAPO formulas run on toy reward groups — reproducing DAPO's own documented "gradient-decreasing problem" and its dynamic-sampling fix, and outcome-only vs. process credit assignment | ✅ |
| [`choosing-a-framework/`](choosing-a-framework/) | The identical tool-calling task solved three real ways on the same model — raw Anthropic client, LangChain/LangGraph `create_agent`, Pydantic AI `Agent` — with real lines-of-code, real call counts, and real answers compared | ✅ |
| [`tools-at-scale/`](tools-at-scale/) | The same 3-step helpdesk task against a 25-tool library three ways — naive (all tools in context), tool search (pre-filtered to 3), programmatic tool calling (one generated workflow) — with real call counts and real token counts, plus a real retriever bug caught and fixed before any paid calls | ✅ |
| [`mcp-deep-dive/`](mcp-deep-dive/) | Real statelessness and requestState security repros against the official MCP SDK (2026-07-28 spec) — raw HTTP header checks for the removed Mcp-Session-Id, and tamper/request-binding/principal-binding/expiry checks against the SDK's own real AES-256-GCM codec; no API key needed, pure protocol mechanics | ✅ |
| [`kv-cache-economics/`](kv-cache-economics/) | Real cache write/read token counts and the tools→system→messages invalidation hierarchy measured against the live API, plus tool masking (the real mid-conversation-tool-changes beta's tool_removal block) vs. physically editing the tools array, with real cache-footprint numbers for both | ✅ |
| [`memory-architectures/`](memory-architectures/) | Real semantic-vs-episodic memory retrieval against Claude's real memory tool (unprompted correct file-splitting and file-reading), plus a real memory-poisoning repro showing a low-stakes injected claim succeeding while a high-stakes one triggered spontaneous skepticism — and a one-instruction source-tagging mitigation closing the gap | ✅ |

More recipes land alongside new pages on the blog.

## Using a recipe

Each folder is self-contained: its own `requirements.txt`, its own `README.md` with install/configure/run instructions, its own `.env.example`. Start with that folder's README.

```bash
git clone git@github.com:DhruvMakwana/agents-cookbook.git
cd agents-cookbook/what-is-an-agent
# follow that folder's README from here
```

## A note on API keys

**Paste your Anthropic key into one file: `agents-cookbook/.env`** (copy `.env.example` at this root to `.env` and fill it in — git-ignored, never committed). Every recipe's `llm.py` reads credentials by walking up from its own folder to the nearest `.env`, so this single file covers every recipe without repeating the key per folder. A recipe can still override with its own local `.env` if it needs different settings.

Anthropic is the default provider (`LLM_PROVIDER=anthropic`), with model choice task-scaled per call — Haiku for simple classification/judgment steps, Sonnet for anything needing real reasoning. OpenAI and a local Ollama model are supported through the same pluggable `llm.py` and can be switched on via `LLM_PROVIDER`, but check each recipe's own README for which providers were actually exercised versus just supported.

## `_shared/`

`_shared/llm.py` is the canonical copy of the provider-dispatch module used across recipes. It is **copied into each recipe folder**, not imported across folders — every recipe stays pip-installable and runnable entirely on its own. When `_shared/llm.py` changes, re-copy it into any recipe that needs the update.
