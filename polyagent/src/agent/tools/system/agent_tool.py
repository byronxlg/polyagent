import logging
from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from langchain_core.tools import tool
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm.attributes import flag_modified

from src.database import SessionLocal
from src.models import Agent, Model, Principal
from src.services.agent_service import AgentService
from src.services.tool_service import ToolService
from src.services.transaction_service import TransactionService

logger = logging.getLogger(__name__)


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


def create_tools(principal_id: str) -> list:  # noqa: C901, PLR0915
    """Create agent tools for a principal."""
    # Get agent_id from principal_id for operations that need it
    session = SessionLocal()
    try:
        agent = session.query(Agent).filter(Agent.principal_id == principal_id).first()
        agent_id = agent.id if agent else None
    finally:
        session.close()

    service = AgentService()

    @tool("get_agents", description="Get a list of all other agents in the system.")
    def get_agents() -> dict:
        """List all other agents."""
        agents = service.get_agents(exclude_agent_id=agent_id)
        return {
            "success": True,
            "count": len(agents),
            "agents": [
                _serialize_agent(a, service.get_agent_balance(a.id))
                for a in agents
            ],
        }

    @tool("get_agent", description="Get details about a specific agent by ID.")
    def get_agent(target_agent_id: str) -> dict:
        """Get details of a specific agent."""
        agent = service.get_agent(target_agent_id)
        if not agent:
            return {"success": False, "error": f"Agent {target_agent_id} not found"}
        return {
            "success": True,
            "agent": _serialize_agent(agent, service.get_agent_balance(agent.id)),
        }

    @tool("get_my_profile", description="Get your own profile including name, public_profile, and balance.")
    def get_my_profile() -> dict:
        """Get the agent's own profile."""
        agent = service.get_agent(agent_id)
        if not agent:
            return {"success": False, "error": "Could not find own profile"}
        return {
            "success": True,
            "profile": _serialize_agent(agent, service.get_agent_balance(agent_id)),
        }

    @tool("update_name", description="Update your display name.")
    def update_name(name: str) -> dict:
        """Update the agent's name."""
        agent = service.update_profile(agent_id, name=name)
        if not agent:
            return {"success": False, "error": "Failed to update name"}
        return {"success": True, "name": agent.name}

    @tool("update_public_profile", description="Update your public profile visible to other agents.")
    def update_public_profile(public_profile: str) -> dict:
        """Update the agent's public profile."""
        agent = service.update_profile(agent_id, public_profile=public_profile)
        if not agent:
            return {"success": False, "error": "Failed to update profile"}
        return {"success": True, "public_profile": agent.public_profile}

    @tool("agent_idle", description="Signal completion and end your thinking cycle.")
    def agent_idle(reason: str) -> dict:
        """Signal that you have completed your current work and are now idle.

        Call this when you have finished your current objective and there is no
        immediate next action to take. This ends your thinking cycle.

        Args:
            reason: Why you are going idle. Write whatever context is relevant.

        Returns:
            Dict with idle status confirmation
        """
        session = SessionLocal()
        try:
            agent = session.query(Agent).filter(Agent.id == agent_id).first()
            if not agent:
                return {"success": False, "error": f"Agent {agent_id} not found"}

            # Update memory_json with idle reason and timestamp
            if agent.memory_json is None:
                agent.memory_json = {}

            agent.memory_json["idle_reason"] = reason
            agent.memory_json["idle_timestamp"] = "now"

            # Mark as modified so SQLAlchemy detects the change
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

    @tool("create_agent", description="Create a new agent and transfer credits from your balance to fund it.")
    def create_agent(name: str, initial_balance: str, model_id: str) -> dict:  # noqa: PLR0911
        """Create a new agent by transferring credits from your balance.

        Args:
            name: Display name for the new agent
            initial_balance: Amount in dollars to transfer to new agent (e.g., "1.50")
            model_id: ID of the LLM model for the new agent to use

        Returns:
            Dict with success status and new agent details or error message
        """
        session = SessionLocal()
        transaction_service = TransactionService()
        tool_service = ToolService()

        try:
            # Parse and validate initial_balance
            try:
                balance_amount = Decimal(initial_balance)
            except (ValueError, TypeError) as e:
                return {"success": False, "error": f"Invalid initial_balance: {e}"}

            if balance_amount <= 0:
                return {"success": False, "error": "initial_balance must be positive"}

            # Get creator agent to determine simulation and verify balance
            creator_agent = session.query(Agent).filter(Agent.id == agent_id).first()
            if not creator_agent:
                return {"success": False, "error": "Creator agent not found"}

            # Check creator has enough balance
            creator_balance = transaction_service.get_balance(agent_id)
            if creator_balance < balance_amount:
                return {
                    "success": False,
                    "error": f"Insufficient balance. You have ${creator_balance}, need ${balance_amount}",
                }

            # Validate model exists
            model = session.query(Model).filter(Model.id == model_id).first()
            if not model:
                return {"success": False, "error": f"Model {model_id} not found"}

            # Create Principal for the new agent
            base_name = name or "Agent"
            unique_username = f"{base_name}_{uuid4().hex[:8]}"

            principal = Principal(
                username=unique_username,
                principal_type="ai_agent",
                email=None,
                created_at=datetime.utcnow(),
            )
            session.add(principal)
            session.flush()

            # Create Agent record
            new_agent = Agent(
                simulation_id=creator_agent.simulation_id,
                principal_id=principal.id,
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

        # Transfer credits from creator to new agent (uses its own session)
        try:
            transaction_service.transfer_dollars(
                from_agent_id=agent_id,
                to_agent_id=new_agent_id,
                amount=balance_amount,
                reason="agent_creation",
            )
        except Exception as e:  # noqa: BLE001
            logger.error(f"Error transferring credits to new agent: {e}")
            return {"success": False, "error": f"Agent created but credit transfer failed: {e}"}

        # Grant system tools to new agent (uses its own session)
        try:
            tool_service.grant_system_tools(new_agent_id)
        except Exception as e:  # noqa: BLE001
            logger.error(f"Error granting tools to new agent: {e}")
            return {"success": False, "error": f"Agent created but tool granting failed: {e}"}

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

    return [
        get_agents,
        get_agent,
        get_my_profile,
        update_name,
        update_public_profile,
        agent_idle,
        create_agent,
    ]
