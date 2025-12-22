from langchain_core.tools import tool


def create_tools(agent_id: int) -> list:
    """Create and return custom tools for the given agent.

    Args:
        agent_id: The ID of the agent that will use these tools

    Returns:
        A list of LangChain tool objects
    """

    @tool("hello_tool", description="Responds with 'Hello {name}' given a name")
    def hello_tool(name: str) -> dict:
        """Return a greeting for the provided name.

        Args:
            name: The name to greet

        Returns:
            A dict with success status and the greeting string in 'result'
        """
        return {"success": True, "result": f"Hello {name}"}

    return [hello_tool]