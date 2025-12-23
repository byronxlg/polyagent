"""MCP server for agent management tools."""

import logging
from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from fastmcp import FastMCP
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm.attributes import flag_modified

from src.database import SessionLocal
from src.models import Agent, Model, Principal
from src.services.agent_service import AgentService
from src.services.server_service import ServerService
from src.services.transaction_service import TransactionService

logger = logging.getLogger(__name__)
mcp = FastMCP("agent")


def _get_agent_id(principal_id: str) -> str | None:
    """Get agent_id from principal_id."""
    session = SessionLocal()
    try:
        agent = session.query(Agent).filter(Agent.principal_id == principal_id).first()
        return str(agent.id) if agent else None
    finally:
        session.close()


def _serialize_agent(agent: Agent, balance: str) -> dict:
    """Serialize an Agent to a dict."""
    return {
        "id": str(agent.id),
        "principal_id": str(agent.principal_id),
        "name": agent.name,
        "public_profile": agent.public_profile,
        "model_id": str(agent.model_id),
        "balance": balance,
        "is_running": agent.is_running,
        "created_at": agent.created_at.isoformat(),
    }


@mcp.tool()
def get_agents(principal_id: str) -> dict:
    """Get a list of all other agents in the system.

    Args:
        principal_id: Your principal ID (injected by agent)
    """
    agent_id = _get_agent_id(principal_id)
    service = AgentService()
    agents = service.get_agents(exclude_agent_id=agent_id)
    return {
        "success": True,
        "count": len(agents),
        "agents": [_serialize_agent(a, service.get_agent_balance(a.id)) for a in agents],
    }


@mcp.tool()
def get_agent(principal_id: str, target_agent_id: str) -> dict:
    """Get details about a specific agent by ID.

    Args:
        principal_id: Your principal ID (injected by agent)
        target_agent_id: The ID of the agent to get details for
    """
    service = AgentService()
    agent = service.get_agent(target_agent_id)
    if not agent:
        return {"success": False, "error": f"Agent {target_agent_id} not found"}
    return {
        "success": True,
        "agent": _serialize_agent(agent, service.get_agent_balance(agent.id)),
    }


@mcp.tool()
def get_my_profile(principal_id: str) -> dict:
    """Get your own profile including name, public_profile, and balance.

    Args:
        principal_id: Your principal ID (injected by agent)
    """
    agent_id = _get_agent_id(principal_id)
    if not agent_id:
        return {"success": False, "error": "Agent not found"}

    service = AgentService()
    agent = service.get_agent(agent_id)
    if not agent:
        return {"success": False, "error": "Could not find own profile"}
    return {
        "success": True,
        "profile": _serialize_agent(agent, service.get_agent_balance(agent_id)),
    }


@mcp.tool()
def update_name(principal_id: str, name: str) -> dict:
    """Update your display name.

    Args:
        principal_id: Your principal ID (injected by agent)
        name: Your new display name
    """
    agent_id = _get_agent_id(principal_id)
    if not agent_id:
        return {"success": False, "error": "Agent not found"}

    service = AgentService()
    agent = service.update_profile(agent_id, name=name)
    if not agent:
        return {"success": False, "error": "Failed to update name"}
    return {"success": True, "name": agent.name}


@mcp.tool()
def update_public_profile(principal_id: str, public_profile: str) -> dict:
    """Update your public profile visible to other agents.

    Args:
        principal_id: Your principal ID (injected by agent)
        public_profile: Your new public profile text
    """
    agent_id = _get_agent_id(principal_id)
    if not agent_id:
        return {"success": False, "error": "Agent not found"}

    service = AgentService()
    agent = service.update_profile(agent_id, public_profile=public_profile)
    if not agent:
        return {"success": False, "error": "Failed to update profile"}
    return {"success": True, "public_profile": agent.public_profile}


@mcp.tool()
def agent_idle(principal_id: str, reason: str) -> dict:
    """Signal completion and end your thinking cycle.

    Call this when you have finished your current objective and there is no
    immediate next action to take. This ends your thinking cycle.

    Args:
        principal_id: Your principal ID (injected by agent)
        reason: Why you are going idle. Write whatever context is relevant.
    """
    agent_id = _get_agent_id(principal_id)
    if not agent_id:
        return {"success": False, "error": "Agent not found"}

    session = SessionLocal()
    try:
        agent = session.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            return {"success": False, "error": f"Agent {agent_id} not found"}

        if agent.memory_json is None:
            agent.memory_json = {}

        agent.memory_json["idle_reason"] = reason
        agent.memory_json["idle_timestamp"] = datetime.utcnow().isoformat()

        flag_modified(agent, "memory_json")
        session.commit()

        return {
            "success": True,
            "status": "idle",
            "reason": reason,
            "message": f"Marked as idle: {reason}",
        }
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Database error marking agent {agent_id} as idle: {e}")
        return {"success": False, "error": "Database error"}
    finally:
        session.close()


@mcp.tool()
def create_agent(principal_id: str, name: str, initial_balance: str, model_id: str) -> dict:
    """Create a new agent and transfer credits from your balance to fund it.

    Args:
        principal_id: Your principal ID (injected by agent)
        name: Display name for the new agent
        initial_balance: Amount in dollars to transfer to new agent (e.g., "1.50")
        model_id: ID of the LLM model for the new agent to use
    """
    agent_id = _get_agent_id(principal_id)
    if not agent_id:
        return {"success": False, "error": "Agent not found"}

    session = SessionLocal()
    transaction_service = TransactionService()
    server_service = ServerService()

    try:
        try:
            balance_amount = Decimal(initial_balance)
        except (ValueError, TypeError) as e:
            return {"success": False, "error": f"Invalid initial_balance: {e}"}

        if balance_amount <= 0:
            return {"success": False, "error": "initial_balance must be positive"}

        creator_agent = session.query(Agent).filter(Agent.id == agent_id).first()
        if not creator_agent:
            return {"success": False, "error": "Creator agent not found"}

        creator_balance = transaction_service.get_balance(agent_id)
        if creator_balance < balance_amount:
            return {
                "success": False,
                "error": f"Insufficient balance. You have ${creator_balance}, need ${balance_amount}",
            }

        model = session.query(Model).filter(Model.id == model_id).first()
        if not model:
            return {"success": False, "error": f"Model {model_id} not found"}

        base_name = name or "Agent"
        unique_username = f"{base_name}_{uuid4().hex[:8]}"

        new_principal = Principal(
            username=unique_username,
            principal_type="ai_agent",
            email=None,
            created_at=datetime.utcnow(),
        )
        session.add(new_principal)
        session.flush()

        new_agent = Agent(
            simulation_id=creator_agent.simulation_id,
            principal_id=new_principal.id,
            model_id=model_id,
            created_by_principal_id=creator_agent.principal_id,
            name=name,
            memory_json=None,
            memory_text=None,
            created_at=datetime.utcnow(),
        )
        session.add(new_agent)
        session.commit()
        session.refresh(new_agent)

        new_agent_id = new_agent.id

    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Database error creating agent: {e}")
        return {"success": False, "error": "Database error creating agent"}
    finally:
        session.close()

    try:
        transaction_service.transfer_dollars(
            from_agent_id=agent_id,
            to_agent_id=new_agent_id,
            amount=balance_amount,
            reason="agent_creation",
        )
    except Exception as e:
        logger.error(f"Error transferring credits to new agent: {e}")
        return {"success": False, "error": f"Agent created but credit transfer failed: {e}"}

    try:
        server_service.grant_system_servers(new_agent_id)
    except Exception as e:
        logger.error(f"Error granting servers to new agent: {e}")
        return {"success": False, "error": f"Agent created but server granting failed: {e}"}

    return {
        "success": True,
        "message": f"Agent '{name}' created successfully",
        "agent": {
            "id": str(new_agent_id),
            "name": name,
            "model_id": model_id,
            "initial_balance": initial_balance,
        },
    }


if __name__ == "__main__":
    mcp.run()
