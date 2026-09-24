# MCP and Tool Ecosystem

A real repro of registry-driven MCP server discovery — against the live, official MCP registry, not a mock. Concept write-up: [MCP and Tool Ecosystem](https://dhruvmakwana.github.io/agents-deep-dive/mcp-tool-ecosystem/).

No framework — the raw Anthropic client throughout, plus real HTTP calls to `registry.modelcontextprotocol.io`. Needs an Anthropic key; the registry itself needs no auth for reads. Sonnet 5.

## The repro

An agent is given exactly one tool, `search_mcp_registry`, wired to the **real, live official MCP registry's public read API** (`GET /v0/servers?search=...`) — not a fixture, not a mock. Given a real fictional task, the agent must decide what to search for, call the real registry, and pick a real, currently-listed server from the real results, explaining its choice.

Two real tasks: checking a customer's payment status (should point toward a payments-related server), and automating clicks/form-fills on a web page (should point toward a browser-automation server).

## What actually happened, run against the live registry and Claude Sonnet 5

**Payment task**: the agent's first real search, `"payment charges status"` (a natural-language capability description), returned **zero results**. It adjusted to a brand-name query, `"Stripe"`, and got 5 real results back — correctly identifying and picking the official `com.stripe/mcp` server, with real, substantive reasoning: it explicitly favored the first-party server over a third-party hosted wrapper (`eu.nordicmcp/stripe`) specifically because of the added trust/dependency cost of an intermediary sitting between the agent and live payment data — a real, security-aware distinction the agent made on its own.

**Browser automation task**: took **6 real search queries** before landing on a usable pick. Four of those six — `"browser automation form filling"`, `"web page interaction click form"`, `"Microsoft official playwright mcp"`, `"stagehand browserbase automate website"` — all returned **zero results**. Only single-keyword, brand-style queries (`"playwright"`, `"puppeteer"`, `"browser"`) returned anything. The agent ultimately picked `ai.smithery/browserbasehq-mcp-browserbase` (Stagehand + Browserbase), with genuine reasoning about why a natural-language-action browser layer fits agentic form-filling better than raw low-level automation.

**A real, separately-confirmed finding, not from the agent's own search but from a direct check of the registry**: Microsoft's own official `microsoft/playwright-mcp` — a genuinely popular server (37.5k+ GitHub stars) — **does not currently appear in the registry at all**, under any of the query terms tried, including `"Microsoft official playwright mcp"` and a direct `search=microsoft` query. The agent's pick wasn't wrong given what the real registry actually returned; it just couldn't recommend a server that isn't listed.

The real, combined finding: the official registry's search is closer to keyword/brand matching than semantic search — natural-language capability descriptions reliably return zero results, while a specific product or company name usually works. And as a preview-stage product, the registry's population is real but genuinely incomplete — even a very well-known server can be absent. Both are honest, current facts about the ecosystem's youngest layer, not flaws in this recipe's own code.

## Install

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Configure

Paste your key into `agents-cookbook/.env` at the **cookbook root** — this recipe reads it automatically. To override just this recipe, `cp .env.example .env` here instead.

## Run

```bash
python mcp_tool_ecosystem.py
```

Runs both real discovery tasks against the live registry and prints each real search trace plus the agent's final pick as JSON.

## Files

| File | Role |
|---|---|
| `mcp_tool_ecosystem.py` | The demo and the CLI entry point — the file you actually run |
| `mcp_tool_ecosystem_docs.py` | **Documentation only** — self-contained per-block version for the blog. Not run as a script, not kept in sync automatically. |
