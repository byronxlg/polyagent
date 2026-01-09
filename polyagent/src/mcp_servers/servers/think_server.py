"""MCP server for the think tool.

The think tool allows agents to perform internal reasoning without executing
external actions. This is useful for complex reasoning, planning, and
maintaining context during multi-step tasks.
"""

from fastmcp import FastMCP

mcp = FastMCP("think")


@mcp.tool()
def think(thought: str) -> dict:
    """Use this tool to think through a problem step by step.

    This tool does not execute any external actions or retrieve new information.
    It simply allows you to reason through complex problems, plan your approach,
    or organize your thoughts before taking action.

    Use cases:
    - Breaking down complex problems into steps
    - Planning a sequence of actions before executing them
    - Reasoning about trade-offs between different approaches
    - Reflecting on results and deciding next steps

    Args:
        thought: Your internal reasoning or thought process
    """
    return {
        "success": True,
        "thought_length": len(thought),
    }


if __name__ == "__main__":
    mcp.run(show_banner=False)
