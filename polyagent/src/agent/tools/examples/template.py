"""
Template for creating custom tools.

This file shows the required structure for custom tools.
All custom tool files must:
1. Define a create_tools(agent_id: int) function
2. Return a list of LangChain tool objects
3. Use the @tool decorator from langchain_core.tools
"""

from langchain_core.tools import tool


def create_tools(agent_id: int) -> list:
    """Create and return custom tools for the given agent.

    Args:
        agent_id: The ID of the agent that will use these tools

    Returns:
        A list of LangChain tool objects
    """

    @tool("example_tool", description="Brief description of what this tool does")
    def example_tool(param1: str, param2: int) -> dict:
        """Detailed docstring explaining the tool's purpose and behavior.

        Args:
            param1: Description of first parameter
            param2: Description of second parameter

        Returns:
            A dictionary with success status and results
        """
        # Tool implementation here
        result = f"Agent {agent_id} called with {param1} and {param2}"
        return {"success": True, "result": result}

    # You can define multiple tools in one file
    @tool("another_tool", description="Another example tool")
    def another_tool(input_text: str) -> dict:
        """Another tool example."""
        return {"success": True, "data": input_text.upper()}

    # Return all tools as a list
    return [example_tool, another_tool]
