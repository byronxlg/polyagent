"""MCP server for trigger subscription management tools."""

from fastmcp import FastMCP

from src.database import SessionLocal
from src.models import Agent, AgentTrigger
from src.services.trigger_service import TriggerService

mcp = FastMCP("trigger")


def _get_agent_id(principal_id: str) -> str | None:
    """Get agent_id from principal_id."""
    session = SessionLocal()
    try:
        agent = session.query(Agent).filter(Agent.principal_id == principal_id).first()
        return str(agent.id) if agent else None
    finally:
        session.close()


def _authorize_trigger_access(
    principal_id: str, trigger_id: str
) -> tuple[str | None, dict | None, dict | None]:
    """Authorize agent access to a trigger.

    Returns:
        Tuple of (agent_id, trigger_dict, error_dict).
        If error_dict is set, access is denied. Otherwise agent_id and trigger are valid.
    """
    agent_id = _get_agent_id(principal_id)
    if not agent_id:
        return None, None, {"success": False, "error": "Agent not found"}

    service = TriggerService()
    trigger = service.get_subscription(trigger_id)
    if not trigger:
        return None, None, {"success": False, "error": "Trigger not found"}

    if str(trigger.agent_id) != agent_id:
        return None, None, {"success": False, "error": "Unauthorized: trigger belongs to another agent"}

    return agent_id, trigger, None


def _serialize_trigger(trigger: AgentTrigger) -> dict:
    """Serialize a trigger to a dict."""
    return {
        "id": str(trigger.id),
        "agent_id": str(trigger.agent_id),
        "simulation_id": str(trigger.simulation_id),
        "table_name": trigger.table_name,
        "change_type": trigger.change_type,
        "conditions": trigger.conditions or {},
        "is_active": trigger.is_active,
        "created_at": trigger.created_at.isoformat(),
        "last_triggered_at": trigger.last_triggered_at.isoformat() if trigger.last_triggered_at else None,
    }


@mcp.tool()
def subscribe_to_trigger(
    principal_id: str,
    table_name: str,
    change_type: str,
    conditions: dict | None = None,
) -> dict:
    """Subscribe to database events to be automatically triggered.

    When a matching event occurs, the worker process will execute your agent.
    Use this to react to new tasks, messages, or other changes without polling.

    Args:
        principal_id: Your principal ID (injected by agent)
        table_name: Table to watch. Options:
            - "tasks": Task creation/updates
            - "messages": New messages (filter by to_principal_id for your inbox)
            - "agent_tasks": Task assignment/submission updates
            - "transactions": Credit movements
        change_type: Type of change. Options:
            - "INSERT": New record created
            - "UPDATE": Existing record modified
            - "DELETE": Record deleted
        conditions: Optional filters as key-value pairs. Examples:
            - {"status": "available"}: Only tasks with available status
            - {"to_principal_id": "<your-principal-id>"}: Messages to you

    Returns:
        {"success": bool, "trigger_id": str, "trigger": dict, "message": str}

    Examples:
        # Be notified when new tasks are created
        subscribe_to_trigger(principal_id, "tasks", "INSERT")

        # Be notified when messages are sent to you
        subscribe_to_trigger(principal_id, "messages", "INSERT",
                           {"to_principal_id": principal_id})

        # Be notified when any agent submits work
        subscribe_to_trigger(principal_id, "agent_tasks", "UPDATE",
                           {"status": "submitted"})
    """
    agent_id = _get_agent_id(principal_id)
    if not agent_id:
        return {"success": False, "error": "Agent not found"}

    service = TriggerService()
    try:
        trigger = service.create_subscription(
            agent_id=agent_id,
            table_name=table_name,
            change_type=change_type,
            conditions=conditions,
        )
        return {
            "success": True,
            "trigger_id": str(trigger.id),
            "trigger": _serialize_trigger(trigger),
            "message": f"Subscribed to {change_type} events on {table_name}",
        }
    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": f"Error: {e!s}"}


@mcp.tool()
def unsubscribe_from_trigger(principal_id: str, trigger_id: str) -> dict:
    """Unsubscribe from a trigger (deactivate it).

    The trigger is deactivated, not deleted, so you can reactivate it later.

    Args:
        principal_id: Your principal ID (injected by agent)
        trigger_id: ID of trigger to deactivate

    Returns:
        {"success": bool, "message": str}
    """
    _, _trigger, error = _authorize_trigger_access(principal_id, trigger_id)
    if error:
        return error

    service = TriggerService()
    try:
        service.update_subscription(trigger_id, is_active=False)
        return {"success": True, "message": "Trigger deactivated"}
    except Exception as e:
        return {"success": False, "error": f"Error: {e!s}"}


@mcp.tool()
def reactivate_trigger(principal_id: str, trigger_id: str) -> dict:
    """Reactivate a previously deactivated trigger.

    Args:
        principal_id: Your principal ID (injected by agent)
        trigger_id: ID of trigger to reactivate

    Returns:
        {"success": bool, "trigger": dict, "message": str}
    """
    agent_id, trigger, error = _authorize_trigger_access(principal_id, trigger_id)
    if error:
        return error

    service = TriggerService()
    try:
        # Check if an active trigger with same table/change_type already exists
        existing_triggers = service.list_subscriptions(agent_id=agent_id, is_active=True)
        for existing in existing_triggers:
            if (
                str(existing.id) != trigger_id
                and existing.table_name == trigger.table_name
                and existing.change_type == trigger.change_type
            ):
                return {
                    "success": False,
                    "error": (
                        f"An active trigger for {trigger.change_type} on {trigger.table_name} "
                        f"already exists (id={existing.id}). Deactivate it first."
                    ),
                }

        updated = service.update_subscription(trigger_id, is_active=True)
        return {
            "success": True,
            "trigger": _serialize_trigger(updated),
            "message": "Trigger reactivated",
        }
    except Exception as e:
        return {"success": False, "error": f"Error: {e!s}"}


@mcp.tool()
def list_my_triggers(principal_id: str, include_inactive: bool = False) -> dict:
    """List your current trigger subscriptions.

    Args:
        principal_id: Your principal ID (injected by agent)
        include_inactive: Whether to include inactive subscriptions

    Returns:
        {"success": bool, "triggers": list, "count": int, "message": str}
    """
    agent_id = _get_agent_id(principal_id)
    if not agent_id:
        return {"success": False, "triggers": [], "count": 0, "error": "Agent not found"}

    service = TriggerService()
    try:
        is_active = None if include_inactive else True
        triggers = service.list_subscriptions(agent_id=agent_id, is_active=is_active)
        return {
            "success": True,
            "triggers": [_serialize_trigger(t) for t in triggers],
            "count": len(triggers),
            "message": f"Found {len(triggers)} triggers",
        }
    except Exception as e:
        return {"success": False, "triggers": [], "count": 0, "error": f"Error: {e!s}"}


@mcp.tool()
def update_trigger_conditions(
    principal_id: str,
    trigger_id: str,
    conditions: dict,
) -> dict:
    """Update the filter conditions for a trigger.

    Args:
        principal_id: Your principal ID (injected by agent)
        trigger_id: ID of trigger to update
        conditions: New filter conditions (replaces existing)

    Returns:
        {"success": bool, "trigger": dict, "message": str}
    """
    _, _trigger, error = _authorize_trigger_access(principal_id, trigger_id)
    if error:
        return error

    service = TriggerService()
    try:
        updated = service.update_subscription(trigger_id, conditions=conditions)
        return {
            "success": True,
            "trigger": _serialize_trigger(updated),
            "message": "Trigger conditions updated",
        }
    except Exception as e:
        return {"success": False, "error": f"Error: {e!s}"}


@mcp.tool()
def delete_trigger(principal_id: str, trigger_id: str) -> dict:
    """Permanently delete a trigger subscription.

    Unlike unsubscribe, this completely removes the trigger.
    Use unsubscribe if you might want to reactivate later.

    Args:
        principal_id: Your principal ID (injected by agent)
        trigger_id: ID of trigger to delete

    Returns:
        {"success": bool, "message": str}
    """
    _, _trigger, error = _authorize_trigger_access(principal_id, trigger_id)
    if error:
        return error

    service = TriggerService()
    try:
        service.delete_subscription(trigger_id)
        return {"success": True, "message": "Trigger deleted"}
    except Exception as e:
        return {"success": False, "error": f"Error: {e!s}"}


if __name__ == "__main__":
    mcp.run()
