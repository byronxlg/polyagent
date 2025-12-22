"""
Demo tool package for agent 30383c18-d6dc-436d-9ed7-57e815c45f59
Provides two simple tools:
- demo_greet(name: str): returns a friendly greeting string
- demo_reverse(text: str): returns the reversed text and its length

The file exposes create_tools(agent_id: int) -> list which returns LangChain @tool-decorated functions.
"""

from langchain_core.tools import tool


def create_tools(agent_id: int) -> list:
    """Create and return custom demo tools for the given agent.

    Args:
        agent_id: The ID of the agent that will use these tools

    Returns:
        A list of LangChain tool callables
    """

    @tool("demo_greet", description="Return a friendly greeting for a given name")
    def demo_greet(name: str) -> dict:
        """Return a friendly greeting message.

        Args:
            name: Person or entity name to greet

        Returns:
            Dict with success flag and greeting message
        """
        if not name:
            return {"success": False, "error": "No name provided"}
        greeting = f"Hello, {name}! This is a demo tool from agent {agent_id}."
        return {"success": True, "greeting": greeting}

    @tool("demo_reverse", description="Reverse input text and return its length")
    def demo_reverse(text: str) -> dict:
        """Reverse the provided text and return metadata.

        Args:
            text: The string to reverse

        Returns:
            Dict with success flag, reversed text, and length
        """
        if text is None:
            return {"success": False, "error": "No text provided"}
        reversed_text = text[::-1]
        return {"success": True, "original": text, "reversed": reversed_text, "length": len(text)}

    return [demo_greet, demo_reverse]