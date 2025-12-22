from langchain_core.tools import tool

from src.database import SessionLocal
from src.models import Agent
from src.services.usage_service import UsageService


def create_tools(principal_id: str) -> list:
    """Create usage tools for a principal."""
    # Get agent_id from principal_id for operations that need it
    session = SessionLocal()
    try:
        agent = session.query(Agent).filter(Agent.principal_id == principal_id).first()
        agent_id = agent.id if agent else None
    finally:
        session.close()

    service = UsageService()

    @tool("get_my_model_usage", description="Get your recent model usage history showing tokens and costs.")
    def get_my_model_usage(limit: int = 10, agent_task_id: str | None = None) -> dict:
        """Get recent model usage records.

        Args:
            limit: Maximum number of records to return (default 10)
            agent_task_id: Optional - filter by specific task
        """
        records, summary = service.get_model_usage(
            agent_id,
            agent_task_id=agent_task_id,
            limit=limit,
        )
        return {
            "success": True,
            "count": len(records),
            "summary": summary,
            "usages": records,
        }

    @tool("get_my_tool_usage", description="Get your recent tool usage history.")
    def get_my_tool_usage(
        limit: int = 20,
        agent_task_id: str | None = None,
        tool_name: str | None = None,
    ) -> dict:
        """Get recent tool usage records.

        Args:
            limit: Maximum number of records to return (default 20)
            agent_task_id: Optional - filter by specific task
            tool_name: Optional - filter by specific tool
        """
        records, summary = service.get_tool_usage(
            agent_id,
            agent_task_id=agent_task_id,
            tool_name=tool_name,
            limit=limit,
        )
        return {
            "success": True,
            "count": len(records),
            "summary": summary,
            "usages": records,
        }

    @tool("get_my_transactions", description="Get your recent transaction history showing credits in and out.")
    def get_my_transactions(
        limit: int = 20,
        direction: str | None = None,
        reason: str | None = None,
    ) -> dict:
        """Get recent transaction records.

        Args:
            limit: Maximum number of records to return (default 20)
            direction: Optional - filter by 'in' or 'out'
            reason: Optional - filter by reason (e.g., 'model_usage', 'task_reward', 'transfer')
        """
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

    @tool("get_task_cost_summary", description="Get a cost summary for a specific task you worked on.")
    def get_task_cost_summary(agent_task_id: str) -> dict:
        """Get cost breakdown for a specific task.

        Args:
            agent_task_id: The agent task ID to get costs for
        """
        summary = service.get_task_cost_summary(agent_id, agent_task_id)
        return {
            "success": True,
            **summary,
        }

    return [get_my_model_usage, get_my_tool_usage, get_my_transactions, get_task_cost_summary]
