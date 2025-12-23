"""MCP server for transaction/credit tools."""

from decimal import Decimal

from fastmcp import FastMCP

from src.database import SessionLocal
from src.models import Agent
from src.services.transaction_service import TransactionService

mcp = FastMCP("transaction")


def _get_agent_id(principal_id: str) -> str | None:
    """Get agent_id from principal_id."""
    session = SessionLocal()
    try:
        agent = session.query(Agent).filter(Agent.principal_id == principal_id).first()
        return str(agent.id) if agent else None
    finally:
        session.close()


@mcp.tool()
def get_balance(principal_id: str) -> dict:
    """Get your current dollar balance.

    Args:
        principal_id: Your principal ID (injected by agent)
    """
    agent_id = _get_agent_id(principal_id)
    if not agent_id:
        return {"success": False, "error": "Agent not found"}

    service = TransactionService()
    balance = service.get_balance(agent_id)
    return {
        "success": True,
        "agent_id": agent_id,
        "balance": str(balance),
    }


@mcp.tool()
def transfer_dollars(principal_id: str, to_agent_id: str, amount: str) -> dict:
    """Transfer dollars to another agent.

    Args:
        principal_id: Your principal ID (injected by agent)
        to_agent_id: The agent ID to transfer to
        amount: Amount to transfer as a string (e.g., "10.50")
    """
    agent_id = _get_agent_id(principal_id)
    if not agent_id:
        return {"success": False, "error": "Agent not found"}

    service = TransactionService()
    try:
        decimal_amount = Decimal(amount)
        service.transfer_dollars(
            from_agent_id=agent_id,
            to_agent_id=to_agent_id,
            amount=decimal_amount,
        )
        new_balance = service.get_balance(agent_id)
        return {
            "success": True,
            "from_agent_id": agent_id,
            "to_agent_id": to_agent_id,
            "amount": amount,
            "new_balance": str(new_balance),
        }
    except ValueError as e:
        error_msg = str(e)
        if "insufficient" in error_msg.lower() or "balance" in error_msg.lower():
            error_msg = f"{error_msg}. Use get_balance to check your current balance."
        elif "not found" in error_msg.lower() or "agent" in error_msg.lower():
            error_msg = f"{error_msg}. Use get_agents to see available agents."
        return {"success": False, "error": error_msg}
    except Exception as e:
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    mcp.run()
