"""MCP server for usage tracking tools."""

from fastmcp import FastMCP

from src.database import SessionLocal
from src.models import Agent
from src.services.usage_service import UsageService

mcp = FastMCP("usage")


def _get_agent_id(principal_id: str) -> str | None:
    """Get agent_id from principal_id."""
    session = SessionLocal()
    try:
        agent = session.query(Agent).filter(Agent.principal_id == principal_id).first()
        return str(agent.id) if agent else None
    finally:
        session.close()


@mcp.tool()
def get_my_model_usage(
    principal_id: str,
    limit: int = 10,
) -> dict:
    """Get your recent model usage history showing tokens and costs.

    Args:
        principal_id: Your principal ID (injected by agent)
        limit: Maximum number of records to return (default 10)
    """
    agent_id = _get_agent_id(principal_id)
    if not agent_id:
        return {"success": False, "error": "Agent not found"}

    service = UsageService()
    records, summary = service.get_model_usage(
        agent_id,
        limit=limit,
    )
    return {
        "success": True,
        "count": len(records),
        "summary": summary,
        "usages": records,
    }


@mcp.tool()
def get_my_mcp_usage(
    principal_id: str,
    limit: int = 20,
    tool_name: str | None = None,
) -> dict:
    """Get your recent MCP tool usage history.

    Args:
        principal_id: Your principal ID (injected by agent)
        limit: Maximum number of records to return (default 20)
        tool_name: Optional - filter by specific tool
    """
    agent_id = _get_agent_id(principal_id)
    if not agent_id:
        return {"success": False, "error": "Agent not found"}

    service = UsageService()
    records, summary = service.get_mcp_usage(
        agent_id,
        tool_name=tool_name,
        limit=limit,
    )
    return {
        "success": True,
        "count": len(records),
        "summary": summary,
        "usages": records,
    }


@mcp.tool()
def get_my_transactions(
    principal_id: str,
    limit: int = 20,
    direction: str | None = None,
    reason: str | None = None,
) -> dict:
    """Get your recent transaction history showing credits in and out.

    Args:
        principal_id: Your principal ID (injected by agent)
        limit: Maximum number of records to return (default 20)
        direction: Optional - filter by 'in' or 'out'
        reason: Optional - filter by reason (e.g., 'model_usage', 'task_reward', 'transfer')
    """
    agent_id = _get_agent_id(principal_id)
    if not agent_id:
        return {"success": False, "error": "Agent not found"}

    service = UsageService()
    records, summary = service.get_transactions(
        agent_id,
        direction=direction,
        reason=reason,
        limit=limit,
    )
    return {
        "success": True,
        "count": len(records),
        "summary": summary,
        "transactions": records,
    }


if __name__ == "__main__":
    mcp.run(show_banner=False)
