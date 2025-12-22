"""
Example: Note storage tool using agent memory.

Shows how to create tools that interact with the database.
This example uses agent memory to store and retrieve notes.
"""

from langchain_core.tools import tool

from src.database import SessionLocal
from src.models import Agent


def create_tools(agent_id: int) -> list:
    """Create note storage tools."""

    @tool("save_note", description="Save a note to your personal storage")
    def save_note(key: str, content: str) -> dict:
        """Save a note with a given key.

        Args:
            key: The key to store the note under
            content: The content of the note

        Returns:
            Dictionary with success status
        """
        session = SessionLocal()
        try:
            agent = session.query(Agent).filter(Agent.id == agent_id).first()
            if not agent:
                return {"success": False, "error": "Agent not found"}

            if "notes" not in agent.memory:
                agent.memory["notes"] = {}

            agent.memory["notes"][key] = content
            session.commit()
            return {"success": True, "message": f"Note '{key}' saved"}
        finally:
            session.close()

    @tool("get_note", description="Retrieve a saved note by key")
    def get_note(key: str) -> dict:
        """Retrieve a note by key.

        Args:
            key: The key of the note to retrieve

        Returns:
            Dictionary with success status and note content
        """
        session = SessionLocal()
        try:
            agent = session.query(Agent).filter(Agent.id == agent_id).first()
            if not agent:
                return {"success": False, "error": "Agent not found"}

            notes = agent.memory.get("notes", {})
            if key not in notes:
                return {"success": False, "error": f"Note '{key}' not found"}

            return {"success": True, "content": notes[key]}
        finally:
            session.close()

    @tool("list_notes", description="List all saved note keys")
    def list_notes() -> dict:
        """List all saved note keys.

        Returns:
            Dictionary with success status and list of keys
        """
        session = SessionLocal()
        try:
            agent = session.query(Agent).filter(Agent.id == agent_id).first()
            if not agent:
                return {"success": False, "error": "Agent not found"}

            notes = agent.memory.get("notes", {})
            return {"success": True, "keys": list(notes.keys()), "count": len(notes)}
        finally:
            session.close()

    return [save_note, get_note, list_notes]
