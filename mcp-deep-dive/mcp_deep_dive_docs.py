"""
Same logic as mcp_deep_dive.py, split into self-contained blocks for blog
embedding via pymdownx.snippets.
"""

import asyncio
import base64
import hashlib
import json
import socket
import threading
import time

import httpx2
import uvicorn
from mcp import Client
from mcp.server.mcpserver import MCPServer
from mcp.server.request_state import InvalidRequestState, RequestStateSecurity

# --8<-- [start:build-server]
def build_demo_server() -> MCPServer:
    server = MCPServer("DemoServer")

    @server.tool()
    def add(a: int, b: int) -> int:
        """Add two numbers."""
        return a + b

    return server
# --8<-- [end:build-server]

# --8<-- [start:running-server]
def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class RunningServer:
    """Starts a real MCPServer over Streamable HTTP on 127.0.0.1 in a background thread."""

    def __init__(self, server: MCPServer, stateless_http: bool):
        self.port = free_port()
        app = server.streamable_http_app(stateless_http=stateless_http)
        self._uvicorn = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=self.port, log_level="warning"))
        self._thread = threading.Thread(target=lambda: asyncio.run(self._uvicorn.serve()), daemon=True)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/mcp"

    def __enter__(self) -> "RunningServer":
        self._thread.start()
        time.sleep(1.0)
        return self

    def __exit__(self, *exc) -> None:
        self._uvicorn.should_exit = True
        self._thread.join(timeout=5)
# --8<-- [end:running-server]

# --8<-- [start:basic-usage]
async def basic_usage_demo(server: MCPServer) -> dict:
    with RunningServer(server, stateless_http=True) as running:
        async with Client(running.url) as client:
            tools = await client.list_tools()
            call_result = await client.call_tool("add", {"a": 2, "b": 3})
            return {
                "tools": [{"name": t.name, "description": t.description} for t in tools.tools],
                "add(2, 3)": call_result.structured_content,
            }
# --8<-- [end:basic-usage]

# --8<-- [start:statelessness-check]
async def raw_tools_list(client: httpx2.AsyncClient, url: str, request_id: int) -> httpx2.Response:
    return await client.post(
        url,
        json={"jsonrpc": "2.0", "id": request_id, "method": "tools/list", "params": {}},
        headers={"Accept": "application/json, text/event-stream", "Content-Type": "application/json"},
    )


async def check_session_header(server: MCPServer, stateless_http: bool) -> dict:
    with RunningServer(server, stateless_http=stateless_http) as running:
        async with httpx2.AsyncClient() as raw:
            resp = await raw_tools_list(raw, running.url, 1)
            return {"status": resp.status_code, "has_session_id_header": "mcp-session-id" in resp.headers}
# --8<-- [end:statelessness-check]

# --8<-- [start:request-state-envelope]
def compact_json(value: dict) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def args_digest(args: dict) -> str:
    raw = hashlib.sha256(compact_json(args).encode()).digest()[:16]
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def seal_state(security: RequestStateSecurity, *, method: str, target: str, args: dict, principal: str, state: str) -> str:
    """Models the real claims envelope built by RequestStateBoundary._seal in
    mcp/server/request_state.py, sealed with the SDK's own real AES-256-GCM codec."""
    now = time.time()
    claims = {
        "v": 1, "iat": now, "exp": now + security.ttl,
        "m": method, "t": target, "a": args_digest(args), "p": principal,
        "s": state,
    }
    return security.codec.seal(compact_json(claims).encode())


def unseal_state(security: RequestStateSecurity, token: str, *, method: str, target: str, args: dict, principal: str) -> str:
    """Models the real verification in RequestStateBoundary._unseal: codec
    integrity check, then expiry, request-binding, and principal checks."""
    payload = security.codec.unseal(token)  # real AEAD verification -- raises InvalidRequestState on tamper/wrong-key
    claims = json.loads(payload)
    if time.time() >= claims["exp"]:
        raise InvalidRequestState("expired")
    if claims["m"] != method or claims["t"] != target or claims["a"] != args_digest(args):
        raise InvalidRequestState("request binding")
    if claims["p"] != principal:
        raise InvalidRequestState("principal")
    return claims["s"]
# --8<-- [end:request-state-envelope]
