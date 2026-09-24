"""
Same logic as mcp_tool_ecosystem.py, split into self-contained blocks for
blog embedding via pymdownx.snippets.
"""

# --8<-- [start:registry-search]
import requests

REGISTRY_BASE = "https://registry.modelcontextprotocol.io/v0"


def search_mcp_registry(query: str, limit: int = 5) -> list:
    """A real, live call to the official MCP registry's public read API. No auth needed."""
    response = requests.get(f"{REGISTRY_BASE}/servers", params={"search": query, "limit": limit}, timeout=20)
    response.raise_for_status()
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
# --8<-- [end:registry-search]

# --8<-- [start:discovery-tasks]
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
# --8<-- [end:discovery-tasks]
