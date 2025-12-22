from langchain_core.tools import tool

from src.database import SessionLocal
from src.models import Agent


def create_tools(principal_id: str) -> list:  # noqa: C901, PLR0915
    """Create memory tools for a principal."""
    # Get agent_id from principal_id for operations that need it
    session = SessionLocal()
    try:
        agent = session.query(Agent).filter(Agent.principal_id == principal_id).first()
        agent_id = agent.id if agent else None
    finally:
        session.close()

    # Structured memory (JSON) tools
    @tool(
        "read_memory",
        description="Read structured memory (JSON). For data/metrics/templates. For narrative use read_notes.",
    )
    def read_memory(key: str | None = None) -> dict:
        """Read value(s) from structured memory."""
        session = SessionLocal()
        try:
            agent = session.query(Agent).filter(Agent.id == agent_id).first()
            if not agent:
                return {"success": False, "error": "Agent not found"}

            memory = agent.memory_json or {}

            if key is None:
                return {
                    "success": True,
                    "key": None,
                    "value": memory,
                    "key_count": len(memory),
                }

            if key in memory:
                return {
                    "success": True,
                    "key": key,
                    "value": memory[key],
                }
            return {
                "success": False,
                "key": key,
                "error": (
                    f"Key '{key}' not found in memory. "
                    f"Use read_memory without a key to see all {len(memory)} stored keys."
                ),
            }
        finally:
            session.close()

    @tool(
        "write_memory",
        description="Write structured memory (JSON). For data/metrics/templates. For plans use write_notes.",
    )
    def write_memory(key: str, value: str) -> dict:
        """Store a value in structured memory."""
        session = SessionLocal()
        try:
            agent = session.query(Agent).filter(Agent.id == agent_id).first()
            if not agent:
                return {"success": False, "error": "Agent not found"}

            memory = agent.memory_json.copy() if agent.memory_json else {}
            was_update = key in memory
            memory[key] = value
            agent.memory_json = memory
            session.commit()
            return {
                "success": True,
                "key": key,
                "value": value,
                "was_update": was_update,
                "key_count": len(memory),
            }
        finally:
            session.close()

    @tool(
        "delete_memory",
        description="Delete a key from structured memory (JSON). Does not affect notes.",
    )
    def delete_memory(key: str) -> dict:
        """Remove a key from structured memory."""
        session = SessionLocal()
        try:
            agent = session.query(Agent).filter(Agent.id == agent_id).first()
            if not agent:
                return {"success": False, "error": "Agent not found"}

            memory = agent.memory_json.copy() if agent.memory_json else {}

            if key not in memory:
                return {
                    "success": False,
                    "key": key,
                    "error": (
                        f"Key '{key}' not found in memory. "
                        f"Use read_memory without a key to see all {len(memory)} stored keys."
                    ),
                }

            deleted_value = memory.pop(key)
            agent.memory_json = memory
            session.commit()
            return {
                "success": True,
                "key": key,
                "deleted_value": deleted_value,
                "key_count": len(memory),
            }
        finally:
            session.close()

    # Notes (markdown text) tools
    @tool(
        "read_notes",
        description="Read notes (markdown). For strategies/plans/observations. For data use read_memory.",
    )
    def read_notes() -> dict:
        """Read the full notes document."""
        session = SessionLocal()
        try:
            agent = session.query(Agent).filter(Agent.id == agent_id).first()
            if not agent:
                return {"success": False, "error": "Agent not found"}

            notes = agent.memory_text or ""
            return {
                "success": True,
                "content": notes,
                "length": len(notes),
                "is_empty": len(notes) == 0,
            }
        finally:
            session.close()

    @tool(
        "write_notes",
        description="Write notes (markdown). For strategies/plans. Overwrites all. Use write_memory for data.",
    )
    def write_notes(content: str) -> dict:
        """Write notes, replacing existing content."""
        session = SessionLocal()
        try:
            agent = session.query(Agent).filter(Agent.id == agent_id).first()
            if not agent:
                return {"success": False, "error": "Agent not found"}

            agent.memory_text = content
            session.commit()
            return {
                "success": True,
                "length": len(content),
            }
        finally:
            session.close()

    @tool(
        "append_notes",
        description="Append to notes (markdown). Add observations. Keeps old notes. Use write_memory for data.",
    )
    def append_notes(content: str) -> dict:
        """Append content to notes."""
        session = SessionLocal()
        try:
            agent = session.query(Agent).filter(Agent.id == agent_id).first()
            if not agent:
                return {"success": False, "error": "Agent not found"}

            current = agent.memory_text or ""
            separator = "\n\n" if current and not current.endswith("\n\n") else ""
            agent.memory_text = current + separator + content
            session.commit()
            return {
                "success": True,
                "new_length": len(agent.memory_text),
            }
        finally:
            session.close()

    return [read_memory, write_memory, delete_memory, read_notes, write_notes, append_notes]
