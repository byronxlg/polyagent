from langchain_core.tools import tool

from src.models import Message
from src.services.message_service import MessageService


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


def create_tools(principal_id: str) -> list:
    """Create message tools for a principal."""
    service = MessageService()

    @tool(
        "send_message",
        description="Send a message to another principal. Use get_agents to find principal IDs.",
    )
    def send_message(to_principal_id: str, content: str) -> dict:
        """Send message to specified principal.

        Args:
            to_principal_id: The principal_id of the recipient (get from get_agents)
            content: The message content

        Returns:
            Success status and message details
        """
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
        except Exception as e:  # noqa: BLE001
            error_msg = str(e)
            return {"success": False, "error": f"Failed to send message: {error_msg}"}

    @tool(
        "check_inbox",
        description="Check inbox for new unread messages from other principals.",
    )
    def check_inbox() -> dict:
        """Retrieve unread messages sent to your principal."""
        try:
            messages = service.get_inbox(principal_id)
            return {
                "success": True,
                "count": len(messages),
                "messages": [_serialize_message(msg) for msg in messages],
            }
        except Exception as e:  # noqa: BLE001
            error_msg = str(e)
            return {"success": False, "error": f"Failed to check inbox: {error_msg}"}

    return [send_message, check_inbox]
