"""MCP server for memory operations."""

from fastmcp import FastMCP

from src.database import SessionLocal
from src.models import Agent

mcp = FastMCP("memory")


def _get_agent(principal_id: str) -> Agent | None:
    """Get agent from principal_id."""
    session = SessionLocal()
    try:
        agent = session.query(Agent).filter(Agent.principal_id == principal_id).first()
        if agent:
            session.expunge(agent)
        return agent
    finally:
        session.close()


@mcp.tool()
def read_memory(principal_id: str, key: str | None = None) -> dict:
    """Read structured memory (JSON). For data/metrics/templates. For narrative use read_notes.

    Args:
        principal_id: Your principal ID (injected by agent)
        key: Optional specific key to read. If None, returns all memory.
    """
    session = SessionLocal()
    try:
        agent = session.query(Agent).filter(Agent.principal_id == principal_id).first()
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


@mcp.tool()
def write_memory(principal_id: str, key: str, value: str) -> dict:
    """Write structured memory (JSON). For data/metrics/templates. For plans use write_notes.

    Args:
        principal_id: Your principal ID (injected by agent)
        key: The key to store the value under
        value: The value to store
    """
    session = SessionLocal()
    try:
        agent = session.query(Agent).filter(Agent.principal_id == principal_id).first()
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


@mcp.tool()
def delete_memory(principal_id: str, key: str) -> dict:
    """Delete a key from structured memory (JSON). Does not affect notes.

    Args:
        principal_id: Your principal ID (injected by agent)
        key: The key to delete
    """
    session = SessionLocal()
    try:
        agent = session.query(Agent).filter(Agent.principal_id == principal_id).first()
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


@mcp.tool()
def list_memory(principal_id: str) -> dict:
    """List all keys in structured memory storage.

    Args:
        principal_id: Your principal ID (injected by agent)
    """
    session = SessionLocal()
    try:
        agent = session.query(Agent).filter(Agent.principal_id == principal_id).first()
        if not agent:
            return {"success": False, "error": "Agent not found"}

        memory = agent.memory_json or {}
        return {
            "success": True,
            "keys": list(memory.keys()),
            "key_count": len(memory),
        }
    finally:
        session.close()


@mcp.tool()
def read_notes(principal_id: str) -> dict:
    """Read notes (markdown). For strategies/plans/observations. For data use read_memory.

    Args:
        principal_id: Your principal ID (injected by agent)
    """
    session = SessionLocal()
    try:
        agent = session.query(Agent).filter(Agent.principal_id == principal_id).first()
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


@mcp.tool()
def write_notes(principal_id: str, content: str) -> dict:
    """Write notes (markdown). For strategies/plans. Overwrites all. Use write_memory for data.

    Args:
        principal_id: Your principal ID (injected by agent)
        content: The markdown content to write (replaces existing notes)
    """
    session = SessionLocal()
    try:
        agent = session.query(Agent).filter(Agent.principal_id == principal_id).first()
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


@mcp.tool()
def append_notes(principal_id: str, content: str) -> dict:
    """Append to notes (markdown). Add observations. Keeps old notes. Use write_memory for data.

    Args:
        principal_id: Your principal ID (injected by agent)
        content: The markdown content to append
    """
    session = SessionLocal()
    try:
        agent = session.query(Agent).filter(Agent.principal_id == principal_id).first()
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


if __name__ == "__main__":
    mcp.run()
