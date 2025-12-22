from decimal import Decimal

from langchain_core.tools import tool

from src.database import SessionLocal
from src.models import Agent
from src.services.transaction_service import TransactionService


def create_tools(principal_id: str) -> list:
    """Create transaction tools for a principal."""
    # Get agent_id from principal_id for operations that need it
    session = SessionLocal()
    try:
        agent = session.query(Agent).filter(Agent.principal_id == principal_id).first()
        agent_id = agent.id if agent else None
    finally:
        session.close()

    service = TransactionService()

    @tool("get_balance", description="Get your current dollar balance.")
    def get_balance() -> dict:
        """Retrieve current balance."""
        balance = service.get_balance(agent_id)
        return {
            "success": True,
            "agent_id": agent_id,
            "balance": str(balance),
        }

    @tool("transfer_dollars", description="Transfer dollars to another agent.")
    def transfer_dollars(to_agent_id: str, amount: str) -> dict:
        """Send money to another agent."""
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

    return [get_balance, transfer_dollars]
