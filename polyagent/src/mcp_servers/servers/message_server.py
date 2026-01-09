"""MCP server for messaging tools."""

from fastmcp import FastMCP

from src.models import Message
from src.services.message_service import MessageService

mcp = FastMCP("message")


def _serialize_message(msg: Message) -> dict:
    """Serialize a Message to a dict with principal information."""
    return {
        "id": str(msg.id),
        "from_principal_id": str(msg.from_principal_id),
        "to_principal_id": str(msg.to_principal_id),
        "content": msg.content,
        "sent_at": msg.sent_at.isoformat(),
        "received_at": msg.received_at.isoformat() if msg.received_at else None,
    }


@mcp.tool()
def send_message(principal_id: str, to_principal_id: str, content: str) -> dict:
    """Send a message to another principal. Use get_agents to find principal IDs.

    Args:
        principal_id: Your principal ID (injected by agent)
        to_principal_id: The principal_id of the recipient
        content: The message content
    """
    service = MessageService()
    try:
        message = service.send_message(
            from_principal_id=principal_id,
            to_principal_id=to_principal_id,
            content=content,
        )
        return {
            "success": True,
            "message": _serialize_message(message),
        }
    except Exception as e:
        return {"success": False, "error": f"Failed to send message: {e}"}


@mcp.tool()
def check_inbox(principal_id: str) -> dict:
    """Check inbox for new unread messages from other principals.

    Args:
        principal_id: Your principal ID (injected by agent)
    """
    service = MessageService()
    try:
        messages = service.get_inbox(principal_id)
        return {
            "success": True,
            "count": len(messages),
            "messages": [_serialize_message(msg) for msg in messages],
        }
    except Exception as e:
        return {"success": False, "error": f"Failed to check inbox: {e}"}


if __name__ == "__main__":
    mcp.run(show_banner=False)
