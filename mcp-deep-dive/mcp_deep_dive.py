"""
Two real repros against the official MCP Python SDK (mcp==2.2.0, which
targets the 2026-07-28 spec revision):

1. Statelessness in practice -- spin up a real Streamable HTTP MCP server
   in both its default (session-based) mode and its stateless_http=True
   mode, and inspect real, raw HTTP responses for the Mcp-Session-Id
   header the 2026-07-28 spec says is removed.
2. requestState security -- exercise the SDK's own real AES-256-GCM
   codec (mcp.server.request_state) to seal/unseal a claims envelope
   modeled on the real RequestStateBoundary logic, and confirm tamper
   detection, request-binding rejection, principal-binding rejection
   (the mitigation for "state handle hijacking"), and expiry all work.

No Anthropic API key needed -- this is protocol mechanics, not model
calls.

Run: python mcp_deep_dive.py
"""

import asyncio
import base64
import hashlib
import json
import logging
import socket
import sys
import threading
import time
from pathlib import Path

import httpx2
import uvicorn
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from mcp.server.mcpserver import MCPServer
from mcp.server.request_state import InvalidRequestState, RequestStateSecurity

logging.getLogger("httpx2").setLevel(logging.WARNING)
logging.getLogger("uvicorn").setLevel(logging.WARNING)
logging.getLogger("uvicorn.error").setLevel(logging.WARNING)
logging.getLogger("mcp").setLevel(logging.WARNING)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _build_demo_server() -> MCPServer:
    server = MCPServer("DemoServer")

    @server.tool()
    def add(a: int, b: int) -> int:
        """Add two numbers."""
        return a + b

    @server.tool()
    def multiply(a: int, b: int) -> int:
        """Multiply two numbers."""
        return a * b

    @server.tool()
    def greet(name: str, formal: bool = False) -> str:
        """Greet someone by name."""
        return f"Good day, {name}." if formal else f"Hey {name}!"

    return server


class _RunningServer:
    """Starts a real MCPServer over Streamable HTTP on 127.0.0.1 in a background thread."""

    def __init__(self, stateless_http: bool):
        self.server = _build_demo_server()
        self.port = _free_port()
        app = self.server.streamable_http_app(stateless_http=stateless_http)
        self._uvicorn = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=self.port, log_level="warning"))
        self._thread = threading.Thread(target=lambda: asyncio.run(self._uvicorn.serve()), daemon=True)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/mcp"

    def __enter__(self) -> "_RunningServer":
        self._thread.start()
        time.sleep(1.0)  # real startup, no health-check loop -- GET on this transport can open a long-lived stream
        return self

    def __exit__(self, *exc) -> None:
        self._uvicorn.should_exit = True
        self._thread.join(timeout=5)


# ------------------------------------------------------- Demo 0: basic usage -- build a server, connect a client, call a tool

async def basic_usage_demo() -> dict:
    with _RunningServer(stateless_http=True) as running:
        async with Client(running.url) as client:
            tools = await client.list_tools()
            call_result = await client.call_tool("add", {"a": 2, "b": 3})
            return {
                "tools": [{"name": t.name, "description": t.description} for t in tools.tools],
                "add(2, 3)": call_result.structured_content,
            }


# ------------------------------------------------------- Demo: multiple tools and their real schemas

async def multi_tool_schema_demo() -> dict:
    with _RunningServer(stateless_http=True) as running:
        async with Client(running.url) as client:
            tools = await client.list_tools()
            schemas = [{"name": t.name, "description": t.description, "inputSchema": t.input_schema} for t in tools.tools]
            add_result = await client.call_tool("add", {"a": 2, "b": 3})
            greet_result = await client.call_tool("greet", {"name": "Dhruv", "formal": True})
            return {
                "tool_schemas": schemas,
                "add(2, 3)": add_result.structured_content,
                'greet(name="Dhruv", formal=True)': greet_result.structured_content,
            }


# ------------------------------------------------------- Demo: the same server, reached over stdio instead of HTTP

async def stdio_demo() -> dict:
    server_script = Path(__file__).parent / "stdio_server.py"
    params = StdioServerParameters(command=sys.executable, args=[str(server_script)])
    async with Client(params) as client:
        tools = await client.list_tools()
        add_result = await client.call_tool("add", {"a": 4, "b": 5})
        greet_result = await client.call_tool("greet", {"name": "Dhruv"})
        return {
            "tools": [t.name for t in tools.tools],
            "add(4, 5)": add_result.structured_content,
            'greet(name="Dhruv")': greet_result.structured_content,
        }


# ------------------------------------------------------- Demo 1: statelessness in practice

async def _raw_tools_list(client: httpx2.AsyncClient, url: str, request_id: int) -> httpx2.Response:
    return await client.post(
        url,
        json={"jsonrpc": "2.0", "id": request_id, "method": "tools/list", "params": {}},
        headers={"Accept": "application/json, text/event-stream", "Content-Type": "application/json"},
    )


async def statelessness_demo() -> dict:
    result = {}

    # Default mode: session-based (the SDK's stateless_http defaults to False)
    with _RunningServer(stateless_http=False) as running:
        async with httpx2.AsyncClient() as raw:
            resp = await _raw_tools_list(raw, running.url, 1)
            result["default_mode"] = {
                "status": resp.status_code,
                "has_session_id_header": "mcp-session-id" in resp.headers,
                "body": resp.text.strip(),
            }

    # Spec-compliant stateless mode: explicit opt-in
    with _RunningServer(stateless_http=True) as running:
        async with httpx2.AsyncClient() as raw:
            resp1 = await _raw_tools_list(raw, running.url, 1)
            resp2 = await _raw_tools_list(raw, running.url, 2)  # a second, fully independent request
            result["stateless_mode"] = {
                "call_1": {"status": resp1.status_code, "has_session_id_header": "mcp-session-id" in resp1.headers},
                "call_2": {"status": resp2.status_code, "has_session_id_header": "mcp-session-id" in resp2.headers},
                "identical_tool_lists": _extract_tool_names(resp1.text) == _extract_tool_names(resp2.text),
                "tool_names": _extract_tool_names(resp1.text),
            }

        # A real Client, used the way the SDK's own README shows it
        async with Client(running.url) as client:
            tools = await client.list_tools()
            call_result = await client.call_tool("add", {"a": 2, "b": 3})
            result["real_client_call"] = {
                "tools": [t.name for t in tools.tools],
                "add(2, 3)": call_result.structured_content,
            }

    return result


def _extract_tool_names(sse_body: str) -> list:
    for line in sse_body.splitlines():
        if line.startswith("data:"):
            data = json.loads(line[len("data:"):].strip())
            return [t["name"] for t in data["result"]["tools"]]
    return []


# ------------------------------------------------------- Demo 2: requestState security

def _compact_json(value: dict) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _args_digest(args: dict) -> str:
    raw = hashlib.sha256(_compact_json(args).encode()).digest()[:16]
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _seal_state(security: RequestStateSecurity, *, method: str, target: str, args: dict, principal: str, state: str) -> str:
    """Models the real claims envelope built by RequestStateBoundary._seal in
    mcp/server/request_state.py, sealed with the SDK's own real AES-256-GCM codec."""
    now = time.time()
    claims = {
        "v": 1, "iat": now, "exp": now + security.ttl,
        "m": method, "t": target, "a": _args_digest(args), "p": principal,
        "s": state,
    }
    return security.codec.seal(_compact_json(claims).encode())


def _unseal_state(security: RequestStateSecurity, token: str, *, method: str, target: str, args: dict, principal: str) -> str:
    """Models the real verification in RequestStateBoundary._unseal: codec
    integrity check, then expiry, request-binding, and principal checks."""
    payload = security.codec.unseal(token)  # real AEAD verification -- raises InvalidRequestState on tamper/wrong-key
    claims = json.loads(payload)
    if time.time() >= claims["exp"]:
        raise InvalidRequestState("expired")
    if claims["m"] != method or claims["t"] != target or claims["a"] != _args_digest(args):
        raise InvalidRequestState("request binding")
    if claims["p"] != principal:
        raise InvalidRequestState("principal")
    return claims["s"]


def request_state_security_demo() -> dict:
    result = {}
    security = RequestStateSecurity.ephemeral(ttl=1.0)

    # A checkout flow mints requestState for Alice's cart, awaiting payment confirmation
    token = _seal_state(
        security, method="tools/call", target="checkout", args={"cart_id": "cart_42"},
        principal="user:alice", state="awaiting_payment_confirmation",
    )

    # 1. Legitimate round-trip: Alice retries with the same cart
    result["legit_round_trip"] = _unseal_state(
        security, token, method="tools/call", target="checkout", args={"cart_id": "cart_42"}, principal="user:alice",
    )

    # 2. Tampering: flip one character in the sealed token
    tampered = token[:60] + ("A" if token[60] != "A" else "B") + token[61:]
    try:
        _unseal_state(security, tampered, method="tools/call", target="checkout", args={"cart_id": "cart_42"}, principal="user:alice")
        result["tamper_rejected"] = False
    except InvalidRequestState as e:
        result["tamper_rejected"] = str(e)

    # 3. Request-binding: same token, presented against a different cart's checkout
    try:
        _unseal_state(security, token, method="tools/call", target="checkout", args={"cart_id": "cart_99_bobs_cart"}, principal="user:alice")
        result["request_binding_rejected"] = False
    except InvalidRequestState as e:
        result["request_binding_rejected"] = str(e)

    # 4. Principal binding (the "state handle hijacking" mitigation): Mallory obtains
    # Alice's token and cart_id, and tries to redeem it as herself
    try:
        _unseal_state(security, token, method="tools/call", target="checkout", args={"cart_id": "cart_42"}, principal="user:mallory")
        result["hijack_rejected"] = False
    except InvalidRequestState as e:
        result["hijack_rejected"] = str(e)

    # 5. Expiry: wait past the 1-second TTL, then retry legitimately
    time.sleep(1.2)
    try:
        _unseal_state(security, token, method="tools/call", target="checkout", args={"cart_id": "cart_42"}, principal="user:alice")
        result["expiry_rejected"] = False
    except InvalidRequestState as e:
        result["expiry_rejected"] = str(e)

    return result


def main() -> None:
    print("=" * 70)
    print("DEMO 0: basic usage -- build a server, connect a client, call a tool")
    print("=" * 70)
    print(json.dumps(asyncio.run(basic_usage_demo()), indent=2))

    print()
    print("=" * 70)
    print("DEMO 0b: multiple tools and their real schemas")
    print("=" * 70)
    print(json.dumps(asyncio.run(multi_tool_schema_demo()), indent=2))

    print()
    print("=" * 70)
    print("DEMO 0c: the same server, reached over stdio instead of HTTP")
    print("=" * 70)
    print(json.dumps(asyncio.run(stdio_demo()), indent=2))

    print()
    print("=" * 70)
    print("DEMO 1: statelessness in practice (mcp==2.2.0, Streamable HTTP)")
    print("=" * 70)
    print(json.dumps(asyncio.run(statelessness_demo()), indent=2))

    print()
    print("=" * 70)
    print("DEMO 2: requestState security (tamper, request-binding, hijack, expiry)")
    print("=" * 70)
    print(json.dumps(request_state_security_demo(), indent=2))


if __name__ == "__main__":
    main()
