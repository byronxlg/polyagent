"""
Custom MCP Server Template.

This file shows the required structure for custom MCP servers.
All custom servers must:
1. Import FastMCP from fastmcp
2. Create an mcp instance with FastMCP('server_name')
3. Define at least one tool with @mcp.tool() decorator
4. All tools must accept principal_id: str as first parameter
"""

from fastmcp import FastMCP

mcp = FastMCP("my_server")


@mcp.tool()
def my_tool(principal_id: str, param1: str) -> dict:
    """Description of what this tool does.

    Args:
        principal_id: Your principal ID (injected by agent)
        param1: Description of parameter
    """
    # Tool implementation here
    return {"success": True, "result": f"Processed: {param1}"}


@mcp.tool()
def another_tool(principal_id: str, value: int) -> dict:
    """Another example tool.

    Args:
        principal_id: Your principal ID (injected by agent)
        value: A numeric value to process
    """
    return {"success": True, "doubled": value * 2}


if __name__ == "__main__":
    mcp.run()
