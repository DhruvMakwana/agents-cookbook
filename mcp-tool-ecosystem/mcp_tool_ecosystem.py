"""
A real repro of registry-driven MCP server discovery -- against the REAL,
live official MCP registry at registry.modelcontextprotocol.io, not a
mock or a fixed local tool list. An agent is given exactly one tool,
search_mcp_registry, wired to the real public registry API (no auth
needed for reads). Given a fictional task, it must decide what to search
for, call the real registry, and pick a real, currently-listed server
from the real results -- demonstrating dynamic, ecosystem-level tool
discovery, distinct from a pre-configured local tool library.

Run: python mcp_tool_ecosystem.py
"""

import json
import os

import requests
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
SONNET = "claude-sonnet-5"
REGISTRY_BASE = "https://registry.modelcontextprotocol.io/v0"

# ------------------------------------------------------- The real registry tool

def search_mcp_registry(query: str, limit: int = 5) -> list:
    """A real, live call to the official MCP registry's public read API. No auth needed."""
    last_error = None
    for _ in range(3):
        try:
            response = requests.get(f"{REGISTRY_BASE}/servers", params={"search": query, "limit": limit}, timeout=20)
            response.raise_for_status()
            break
        except requests.exceptions.RequestException as e:
            last_error = e
    else:
        raise last_error
    servers = response.json().get("servers", [])
    return [
        {
            "name": s["server"].get("name"),
            "title": s["server"].get("title"),
            "description": s["server"].get("description"),
            "remotes": [r.get("url") for r in s["server"].get("remotes", [])],
        }
        for s in servers
    ]


_REGISTRY_TOOL = [{
    "name": "search_mcp_registry",
    "description": (
        "Search the real, live official MCP server registry for servers matching a query. "
        "Returns real, currently-listed servers with their name, description, and remote endpoint URLs."
    ),
    "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
}]

_TASKS = [
    "You need to let an agent check the status of a customer's payment and look up recent charges. Find a real MCP server in the registry that could do this, and tell me which one you'd pick and why.",
    "You need to let an agent automate clicking through a web page and filling out a form. Find a real MCP server in the registry for this, and tell me which one you'd pick and why.",
]


def _run_discovery_task(task: str) -> dict:
    messages = [{"role": "user", "content": task}]
    real_search_calls = []

    for _ in range(8):
        response = client.messages.create(model=SONNET, max_tokens=1200, tools=_REGISTRY_TOOL, messages=messages)
        messages.append({"role": "assistant", "content": response.content})
        if response.stop_reason != "tool_use":
            final_text = "\n".join(b.text for b in response.content if b.type == "text")
            return {"task": task, "real_search_calls": real_search_calls, "final_answer": final_text}
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            real_results = search_mcp_registry(block.input["query"])
            real_search_calls.append({"query": block.input["query"], "real_results_count": len(real_results), "real_results": real_results})
            tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": json.dumps(real_results)})
        messages.append({"role": "user", "content": tool_results})

    return {"task": task, "real_search_calls": real_search_calls, "final_answer": None}


def registry_discovery_demo() -> list:
    return [_run_discovery_task(task) for task in _TASKS]


def main() -> None:
    print("=" * 70)
    print("Real repro: agent discovers MCP servers via the live official registry")
    print("=" * 70)
    print(json.dumps(registry_discovery_demo(), indent=2))


if __name__ == "__main__":
    main()
