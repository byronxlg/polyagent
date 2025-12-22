"""
A simple demo tool that returns 'Hello {name}'.
"""

from langchain_core.tools import tool


def create_tools(agent_id: int) -> list:

    @tool("hello_name", description="Return a greeting for the provided name")
    def hello_name(name: str) -> dict:
        """Return a simple greeting.

        Args:
            name: The name to greet

        Returns:
            A dict with success and greeting
        """
        greeting = f"Hello {name}"
        return {"success": True, "greeting": greeting}

    return [hello_name]
