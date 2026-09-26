"""A standalone MCP server, run as a subprocess and talked to over stdio.

This file is not imported -- it's launched as its own process by
stdio_demo() in mcp_deep_dive.py, exactly the way a real local MCP
server (one running on your own machine) is launched by its host.
"""

from mcp.server.mcpserver import MCPServer

server = MCPServer("StdioDemoServer")


@server.tool()
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


@server.tool()
def greet(name: str, formal: bool = False) -> str:
    """Greet someone by name."""
    return f"Good day, {name}." if formal else f"Hey {name}!"


if __name__ == "__main__":
    server.run()  # defaults to transport="stdio"
