# MCP Deep Dive

Two real repros against the official MCP Python SDK (`mcp==2.2.0`, which targets the 2026-07-28 spec revision): statelessness in practice, and the `requestState` security envelope that replaces protocol-level sessions for multi-round-trip flows. Concept write-up: [MCP Deep Dive](https://dhruvmakwana.github.io/agents-deep-dive/mcp-deep-dive/).

No Anthropic API key needed -- this recipe is pure protocol mechanics against the real SDK, not model calls.

## The two repros

- **Statelessness in practice** (`statelessness_demo`): a real Streamable HTTP MCP server, run twice -- once in the SDK's default mode, once with `stateless_http=True` -- with raw HTTP requests inspected directly for the `Mcp-Session-Id` header the 2026-07-28 spec says is removed.
- **`requestState` security** (`request_state_security_demo`): the SDK's own real `AESGCMRequestStateCodec` (from `mcp.server.request_state`), exercised through a claims envelope modeled on the real `RequestStateBoundary._seal`/`_unseal` logic (read directly from the installed SDK's source) -- tamper detection, request-binding rejection, principal-binding rejection (the mitigation for "state handle hijacking"), and expiry.

## What actually happened, run against mcp==2.2.0

**A real, surprising finding**: despite `mcp==2.2.0` explicitly targeting the 2026-07-28 spec (SEP-2575: "Remove protocol-level sessions and the `Mcp-Session-Id` header from the Streamable HTTP transport"), the SDK's **default** `streamable_http_app()` configuration still requires and returns `Mcp-Session-Id`. A raw request without one is rejected outright:

```json
{"jsonrpc":"2.0","id":null,"error":{"code":-32600,"message":"Bad Request: Missing session ID"}}
```

Spec-compliant stateless behavior exists, but is opt-in: `streamable_http_app(stateless_http=True)`. With that flag, two fully independent raw HTTP requests -- no cookie, no session, no shared state between them -- both returned `200 OK` with **no** `Mcp-Session-Id` header in either response, and identical `tools/list` results:

```json
{
  "call_1": {"status": 200, "has_session_id_header": false},
  "call_2": {"status": 200, "has_session_id_header": false},
  "identical_tool_lists": true
}
```

This is a genuine, dated fact about the current state of the ecosystem (checked 2026-09-23), not a bug in this recipe's own code: the reference SDK's *default* hasn't caught up to the spec's stated statelessness mandate, even in the release that claims to target it. Worth knowing before assuming "uses the latest SDK" means "behaves per the latest spec" by default.

**The `requestState` security properties all held**, using the SDK's own real AES-256-GCM codec, not a reimplementation:

| Check | Real result |
|---|---|
| Legitimate round-trip (Alice retries her own checkout) | `awaiting_payment_confirmation` -- succeeds |
| Tampering (one flipped character in the sealed token) | Rejected: `seal` (AEAD authentication failure) |
| Request-binding (Alice's token replayed against a different cart) | Rejected: `request binding` |
| Principal-binding / state-handle hijacking (Mallory replays Alice's token as herself) | Rejected: `principal` |
| Expiry (same token, past its 1-second TTL) | Rejected: `expired` |

The principal-binding result is the direct, real mitigation for the exact "State Handle Hijacking" vulnerability the spec's security best practices document names: *"MCP servers **MUST NOT** treat possession of a state handle as authentication"* and *"**SHOULD** bind handles server-side to the authenticated user."* This repro shows that binding working, end to end, against the SDK's real cryptographic primitives.

## Install

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Configure

Nothing to configure -- no API key, no `.env`. This recipe only exercises the local MCP SDK against `127.0.0.1`.

## Run

```bash
python mcp_deep_dive.py
```

Runs both demos in sequence and prints each result as JSON.

## Files

| File | Role |
|---|---|
| `mcp_deep_dive.py` | Both demos and the CLI entry point -- the file you actually run |
| `mcp_deep_dive_docs.py` | **Documentation only** -- self-contained per-block version for the blog. Not run as a script, not kept in sync automatically. |
