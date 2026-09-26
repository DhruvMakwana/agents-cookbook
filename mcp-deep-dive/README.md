# MCP Deep Dive

A progressive, tutorial-style walkthrough of MCP: build a real server, connect a real client, call a tool, inspect multiple tools' real schemas, reach the same server over both transports (stdio and Streamable HTTP) -- then two deeper repros against the official MCP Python SDK (`mcp==2.2.0`, targeting the current 2026-07-28 spec): statelessness in practice, and the `requestState` security envelope MCP uses today for multi-round-trip flows. Concept write-up: [MCP Deep Dive](https://dhruvmakwana.github.io/agents-deep-dive/mcp-deep-dive/).

No Anthropic API key needed -- this recipe is pure protocol mechanics against the real SDK, not model calls.

## The demos and the two repros

- **Basic usage** (`basic_usage_demo`): the minimal real path -- define a tool with `@server.tool()`, run the server, connect with the SDK's own `Client`, list tools, call one, get a real result back.
- **Multiple tools and their real schemas** (`multi_tool_schema_demo`): a three-tool server (`add`, `multiply`, `greet` -- one with an optional, defaulted parameter), with the real, raw JSON Schema the SDK auto-generates for each tool from its Python signature.
- **The same server over stdio** (`stdio_demo`, using the standalone `stdio_server.py`): the SDK's own `Client` connecting to a server launched as a real local subprocess and talked to over stdin/stdout, instead of over HTTP -- the other of MCP's two transports.
- **Statelessness in practice** (`statelessness_demo`): a real Streamable HTTP MCP server, run twice -- once in the SDK's default mode, once with `stateless_http=True` -- with raw HTTP requests inspected directly for the `Mcp-Session-Id` header the current spec says a stateless server doesn't need.
- **`requestState` security** (`request_state_security_demo`): the SDK's own real `AESGCMRequestStateCodec` (from `mcp.server.request_state`), exercised through a claims envelope modeled on the real `RequestStateBoundary._seal`/`_unseal` logic (read directly from the installed SDK's source) -- tamper detection, request-binding rejection, principal-binding rejection (the mitigation for "state handle hijacking"), and expiry.

## What actually happened, run against mcp==2.2.0

**Basic usage, first**: a server with one tool (`add`) started, a real `Client` connected, `list_tools()` returned `[{"name": "add", "description": "Add two numbers."}]`, and `call_tool("add", {"a": 2, "b": 3})` returned `{"result": 5}` -- the whole round trip, no cryptography or protocol edge cases involved.

**Multiple tools, real schemas**: a three-tool server's `list_tools()` returned real, auto-generated JSON Schema for each -- `add`/`multiply` each require two integers (`"required": ["a", "b"]`), while `greet` requires only `name` and makes `formal` optional with a real default (`"default": false`) baked into its schema. `call_tool("greet", {"name": "Dhruv", "formal": True})` returned `{"result": "Good day, Dhruv."}`.

**The same server over stdio**: a second, standalone script (`stdio_server.py`) launched as a real child process via `StdioServerParameters(command=sys.executable, args=[...])`, with the SDK's own `Client` accepting those parameters directly and talking to that process over stdin/stdout -- no HTTP, no port, no network at all. `list_tools()` and `call_tool()` both worked identically to the HTTP case: `{"tools": ["add", "greet"], "add(4, 5)": {"result": 9}, "greet(name=\"Dhruv\")": {"result": "Hey Dhruv!"}}`.

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

Runs all five demos in sequence and prints each result as JSON. `stdio_demo` launches `stdio_server.py` itself as a subprocess -- nothing else to start by hand.

## Files

| File | Role |
|---|---|
| `mcp_deep_dive.py` | All five demos and the CLI entry point -- the file you actually run |
| `stdio_server.py` | A standalone MCP server launched as a real subprocess by `stdio_demo` -- this is what "the stdio transport" actually looks like: a separate process talked to over stdin/stdout |
| `mcp_deep_dive_docs.py` | **Documentation only** -- self-contained per-block version for the blog. Not run as a script, not kept in sync automatically. |
