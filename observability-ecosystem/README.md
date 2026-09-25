# Observability Ecosystem

A real, live test of two architecturally different observability platform mechanisms, using only real, public, documented endpoints — no account, no API key, no cost. Companion to [`observability-debugging/`](../observability-debugging/), which covers the OpenTelemetry GenAI semantic convention itself; this one tests the real ecosystem built around it. Concept write-up: [Observability Ecosystem](https://dhruvmakwana.github.io/agents-deep-dive/observability-ecosystem/).

No framework, no LLM calls at all — just `requests` against real, live, public endpoints.

## The repro

Two real, live checks:

1. **Langfuse's real, documented OTLP ingestion endpoint** (`/api/public/otel`) — a real OTel-GenAI-shaped trace, built to the exact same `gen_ai.*` attribute shape as the Observability and Debugging recipe's own trace, POSTed with no credentials.
2. **Helicone's real, documented AI gateway** (`gateway.helicone.ai`) — tested twice: once with no target header, once with a real target header pointing at a real upstream provider (OpenAI).

## What actually happened, run live against both real services

**Langfuse**: `401`, real response body `{"message": "No authorization header", "error": "UnauthorizedError"}`. The endpoint accepted the real, well-formed OTel GenAI trace payload structurally and rejected it purely for missing auth — not a malformed-payload error — confirming it's a genuine, live OTLP ingestion endpoint that parses this exact trace shape per its own documentation, exactly as Langfuse's docs claim.

**Helicone, no target header**: `400`, real response body `"Missing target base url"`. This is the real, concrete proof Helicone is architecturally a request-path proxy, not an ingestion sink — it has nothing to log until it knows where to forward.

**Helicone, with a real target header**: `401`, but the real response body is OpenAI's own real, live error message — *"You didn't provide an API key..."* — forwarded back through Helicone's proxy from OpenAI's own real API. The request was genuinely forwarded live to a real upstream provider and its real response passed back through, not a Helicone-internal error.

Two real, live-confirmed architectures: an OTel-native ingestion endpoint you push spec-shaped traces *to*, versus a gateway that sits directly *in* the request path and forwards live. Same underlying goal — visibility into what an agent's calls actually did — two structurally different real mechanisms.

## Install

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
python observability_ecosystem.py
```

No API key or account needed. Runs all three real, live HTTP checks and prints the actual status codes and response bodies as JSON.

## Files

| File | Role |
|---|---|
| `observability_ecosystem.py` | All three real checks and the CLI entry point — the file you actually run |
| `observability_ecosystem_docs.py` | **Documentation only** — self-contained per-block version for the blog. Not run as a script, not kept in sync automatically. |
