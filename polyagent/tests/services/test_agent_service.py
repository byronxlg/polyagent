"""Tests for AgentService."""

from decimal import Decimal
from uuid import uuid4

from sqlalchemy.orm import Session

from src.models import Agent, Principal, Transaction
from src.services.agent_service import AgentService


def test_get_agents(db_session: Session, agent, override_session_local):
    """Test getting all agents."""
    service = AgentService()
    agents = service.get_agents()

    agent_ids = [a.id for a in agents]
    assert agent.id in agent_ids


def test_get_agents_exclude(db_session: Session, simulation, model, human_principal, override_session_local):
    """Test getting agents with exclusion."""
    # Create two agents
    agent1_principal = Principal(username="agent1", principal_type="ai_agent")
    agent2_principal = Principal(username="agent2", principal_type="ai_agent")
    db_session.add_all([agent1_principal, agent2_principal])
    db_session.flush()

    agent1 = Agent(
        simulation_id=simulation.id,
        principal_id=agent1_principal.id,
        model_id=model.id,
        created_by_principal_id=human_principal.id,
        name="Agent 1",
    )
    agent2 = Agent(
        simulation_id=simulation.id,
        principal_id=agent2_principal.id,
        model_id=model.id,
        created_by_principal_id=human_principal.id,
        name="Agent 2",
    )
    db_session.add_all([agent1, agent2])
    db_session.flush()

    service = AgentService()
    agents = service.get_agents(exclude_agent_id=agent1.id)

    agent_ids = [a.id for a in agents]
    assert agent1.id not in agent_ids
    assert agent2.id in agent_ids


def test_get_agent(db_session: Session, agent, override_session_local):
    """Test getting a specific agent."""
    service = AgentService()
    result = service.get_agent(agent.id)

    assert result is not None
    assert result.id == agent.id
    assert result.name == agent.name


def test_get_agent_not_found(db_session: Session, override_session_local):
    """Test getting non-existent agent returns None."""
    service = AgentService()
    result = service.get_agent(uuid4())

    assert result is None


def test_get_agent_balance_zero(db_session: Session, agent, override_session_local):
    """Test balance is zero for agent with no transactions."""
    service = AgentService()
    balance = service.get_agent_balance(agent.id)

    assert balance == "0.0000"


def test_get_agent_balance(db_session: Session, agent, override_session_local):
    """Test balance calculation with transactions."""
    # Add incoming transaction
    tx_in = Transaction(
        from_principal_id=None,
        to_principal_id=agent.principal_id,
        amount=Decimal("0.50"),
        reason="test_grant",
    )
    db_session.add(tx_in)

    # Add outgoing transaction
    tx_out = Transaction(
        from_principal_id=agent.principal_id,
        to_principal_id=None,
        amount=Decimal("0.15"),
        reason="test_deduct",
    )
    db_session.add(tx_out)
    db_session.flush()

    service = AgentService()
    balance = service.get_agent_balance(agent.id)

    assert balance == "0.3500"  # 0.50 - 0.15


def test_get_agent_balance_not_found(db_session: Session, override_session_local):
    """Test balance for non-existent agent returns zero."""
    service = AgentService()
    balance = service.get_agent_balance(uuid4())

    assert balance == "0.0000"


def test_update_profile_name(db_session: Session, agent, override_session_local):
    """Test updating agent name."""
    service = AgentService()
    result = service.update_profile(agent.id, name="New Name")

    assert result is not None
    assert result.name == "New Name"


def test_update_profile_public_profile(db_session: Session, agent, override_session_local):
    """Test updating agent public profile."""
    service = AgentService()
    result = service.update_profile(agent.id, public_profile="I am a helpful agent.")

    assert result is not None
    assert result.public_profile == "I am a helpful agent."


def test_update_profile_both(db_session: Session, agent, override_session_local):
    """Test updating both name and public profile."""
    service = AgentService()
    result = service.update_profile(agent.id, name="Updated Name", public_profile="Updated profile")

    assert result is not None
    assert result.name == "Updated Name"
    assert result.public_profile == "Updated profile"


def test_update_profile_not_found(db_session: Session, override_session_local):
    """Test updating non-existent agent returns None."""
    service = AgentService()
    result = service.update_profile(uuid4(), name="New Name")

    assert result is None
