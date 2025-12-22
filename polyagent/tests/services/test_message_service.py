"""Tests for MessageService."""

import pytest
from sqlalchemy.orm import Session

from src.models import Agent, Message, Principal
from src.services.message_service import MessageService


def test_send_message(db_session: Session, simulation, model, human_principal, override_session_local):
    """Test sending a message between agents."""
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

    service = MessageService()
    message = service.send_message(agent1.principal_id, agent2.principal_id, "Hello Agent 2!")

    assert message.content == "Hello Agent 2!"
    assert message.from_principal_id == agent1.principal_id
    assert message.to_principal_id == agent2.principal_id
    assert message.sent_at is not None
    assert message.received_at is None


def test_send_message_nonexistent_sender(db_session: Session, agent, override_session_local):
    """Test sending message from non-existent agent fails."""
    from uuid import uuid4

    service = MessageService()

    with pytest.raises(ValueError, match="not found"):
        service.send_message(uuid4(), agent.principal_id, "Hello")


def test_send_message_nonexistent_recipient(db_session: Session, agent, override_session_local):
    """Test sending message to non-existent agent fails."""
    from uuid import uuid4

    service = MessageService()

    with pytest.raises(ValueError, match="not found"):
        service.send_message(agent.principal_id, uuid4(), "Hello")


def test_get_inbox_empty(db_session: Session, agent, override_session_local):
    """Test getting inbox when no messages."""
    service = MessageService()
    messages = service.get_inbox(agent.principal_id)
    assert messages == []


def test_get_inbox_with_messages(db_session: Session, simulation, model, human_principal, override_session_local):
    """Test getting inbox with unread messages."""
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

    # Send a message
    service = MessageService()
    service.send_message(agent1.principal_id, agent2.principal_id, "Hello Agent 2!")

    # Get inbox for agent2
    messages = service.get_inbox(agent2.principal_id)
    assert len(messages) == 1
    assert messages[0].content == "Hello Agent 2!"


def test_get_inbox_marks_as_received(db_session: Session, simulation, model, human_principal, override_session_local):
    """Test that getting inbox marks messages as received."""
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

    # Send a message
    service = MessageService()
    service.send_message(agent1.principal_id, agent2.principal_id, "Hello!")

    # First call gets the message
    messages = service.get_inbox(agent2.principal_id)
    assert len(messages) == 1
    assert messages[0].received_at is not None

    # Second call returns empty (message already received)
    messages = service.get_inbox(agent2.principal_id)
    assert len(messages) == 0


def test_get_inbox_nonexistent_agent(db_session: Session, override_session_local):
    """Test getting inbox for non-existent agent fails."""
    from uuid import uuid4

    service = MessageService()

    with pytest.raises(ValueError, match="not found"):
        service.get_inbox(uuid4())
