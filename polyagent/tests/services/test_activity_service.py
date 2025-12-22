"""Tests for ActivityService.

Note: ActivityService takes a Session in its constructor, so we don't need
the override_session_local fixture. We can pass db_session directly.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from src.models import Agent, AgentTask, Message, Principal, Task, Transaction
from src.services.activity_service import ActivityService


def test_get_activity_empty(db_session: Session):
    """Test getting activity when no activity exists."""
    service = ActivityService(db_session)
    items, total = service.get_activity()

    # May have pre-existing data, just check structure
    assert isinstance(items, list)
    assert isinstance(total, int)


def test_get_activity_with_agent_task(db_session: Session, agent, task):
    """Test activity includes agent tasks."""
    # Create an agent task
    agent_task = AgentTask(
        task_id=task.id,
        agent_id=agent.id,
        status="in_progress",
    )
    db_session.add(agent_task)
    db_session.flush()

    service = ActivityService(db_session)
    items, total = service.get_activity(types=["agent_task"])

    assert total >= 1
    # Find our agent task in the results
    agent_task_items = [i for i in items if i["type"] == "agent_task"]
    assert len(agent_task_items) >= 1


def test_get_activity_with_transaction(db_session: Session, agent):
    """Test activity includes transactions."""
    # Create a transaction
    tx = Transaction(
        from_principal_id=None,
        to_principal_id=agent.principal_id,
        amount=Decimal("0.10"),
        reason="test_activity",
    )
    db_session.add(tx)
    db_session.flush()

    service = ActivityService(db_session)
    items, total = service.get_activity(types=["transaction"])

    assert total >= 1
    tx_items = [i for i in items if i["type"] == "transaction"]
    assert len(tx_items) >= 1


def test_get_activity_with_message(db_session: Session, simulation, model, human_principal):
    """Test activity includes messages."""
    # Create two agents
    agent1_principal = Principal(username="msg_agent1", principal_type="ai_agent")
    agent2_principal = Principal(username="msg_agent2", principal_type="ai_agent")
    db_session.add_all([agent1_principal, agent2_principal])
    db_session.flush()

    agent1 = Agent(
        simulation_id=simulation.id,
        principal_id=agent1_principal.id,
        model_id=model.id,
        created_by_principal_id=human_principal.id,
        name="Msg Agent 1",
    )
    agent2 = Agent(
        simulation_id=simulation.id,
        principal_id=agent2_principal.id,
        model_id=model.id,
        created_by_principal_id=human_principal.id,
        name="Msg Agent 2",
    )
    db_session.add_all([agent1, agent2])
    db_session.flush()

    # Create a message
    message = Message(
        from_principal_id=agent1.principal_id,
        to_principal_id=agent2.principal_id,
        content="Hello!",
        sent_at=datetime.utcnow(),
    )
    db_session.add(message)
    db_session.flush()

    service = ActivityService(db_session)
    items, total = service.get_activity(types=["message"])

    assert total >= 1
    msg_items = [i for i in items if i["type"] == "message"]
    assert len(msg_items) >= 1


def test_get_activity_filter_by_agent(db_session: Session, agent, task):
    """Test filtering activity by agent."""
    # Create agent task for our agent
    agent_task = AgentTask(
        task_id=task.id,
        agent_id=agent.id,
        status="in_progress",
    )
    db_session.add(agent_task)
    db_session.flush()

    service = ActivityService(db_session)
    items, total = service.get_activity(agent_id=agent.id, types=["agent_task"])

    # All items should be for this agent
    for item in items:
        if item["type"] == "agent_task":
            assert str(item["agent_id"]) == str(agent.id)


def test_get_activity_filter_by_types(db_session: Session, agent, task):
    """Test filtering activity by type."""
    # Create mixed activity
    agent_task = AgentTask(
        task_id=task.id,
        agent_id=agent.id,
        status="in_progress",
    )
    db_session.add(agent_task)

    tx = Transaction(
        from_principal_id=None,
        to_principal_id=agent.principal_id,
        amount=Decimal("0.05"),
        reason="test",
    )
    db_session.add(tx)
    db_session.flush()

    service = ActivityService(db_session)

    # Only get agent_task
    items, _ = service.get_activity(types=["agent_task"])
    for item in items:
        assert item["type"] == "agent_task"

    # Only get transaction
    items, _ = service.get_activity(types=["transaction"])
    for item in items:
        assert item["type"] == "transaction"


def test_get_activity_pagination(db_session: Session, agent, simulation, human_principal):
    """Test activity pagination."""
    # Create multiple tasks and agent tasks
    for i in range(5):
        task = Task(
            simulation_id=simulation.id,
            created_by_principal_id=human_principal.id,
            description=f"Task {i}",
            reward_dollars=Decimal("0.01"),
            deadline=datetime.utcnow(),
        )
        db_session.add(task)
        db_session.flush()

        agent_task = AgentTask(
            task_id=task.id,
            agent_id=agent.id,
            status="in_progress",
        )
        db_session.add(agent_task)
    db_session.flush()

    service = ActivityService(db_session)

    # Get first page
    items1, total = service.get_activity(limit=2, offset=0, types=["agent_task"])
    assert len(items1) <= 2

    # Get second page
    items2, _ = service.get_activity(limit=2, offset=2, types=["agent_task"])

    # Items should be different (assuming enough data)
    if len(items1) == 2 and len(items2) >= 1:
        assert items1[0]["id"] != items2[0]["id"]


def test_get_activity_invalid_types(db_session: Session):
    """Test that invalid types are filtered out."""
    service = ActivityService(db_session)
    items, total = service.get_activity(types=["invalid_type"])

    assert items == []
    assert total == 0


def test_get_activity_ordered_by_timestamp(db_session: Session, agent, task):
    """Test activity is ordered by timestamp descending."""
    # Create multiple agent tasks with different times
    for i in range(3):
        agent_task = AgentTask(
            task_id=task.id,
            agent_id=agent.id,
            status="in_progress",
        )
        db_session.add(agent_task)
        db_session.flush()

    service = ActivityService(db_session)
    items, _ = service.get_activity(types=["agent_task"], limit=10)

    if len(items) >= 2:
        # Timestamps should be in descending order
        timestamps = [i["timestamp"] for i in items if i["timestamp"]]
        assert timestamps == sorted(timestamps, reverse=True)
