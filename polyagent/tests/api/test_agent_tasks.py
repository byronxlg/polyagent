"""Tests for /agent-tasks API endpoints."""

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.models import AgentTask


def test_list_agent_tasks_structure(client: TestClient) -> None:
    """Test listing agent tasks returns proper structure."""
    response = client.get("/agent-tasks")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert "limit" in data
    assert "offset" in data
    assert "has_more" in data


def test_list_agent_tasks(client: TestClient, agent, task, db_session: Session) -> None:
    """Test listing agent tasks."""
    # Create an agent task
    agent_task = AgentTask(
        task_id=task.id,
        agent_id=agent.id,
        status="in_progress",
    )
    db_session.add(agent_task)
    db_session.flush()

    response = client.get("/agent-tasks")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1


def test_list_agent_tasks_filter_by_agent(
    client: TestClient, agent, task, db_session: Session
) -> None:
    """Test filtering agent tasks by agent ID."""
    # Create an agent task
    agent_task = AgentTask(
        task_id=task.id,
        agent_id=agent.id,
        status="in_progress",
    )
    db_session.add(agent_task)
    db_session.flush()

    response = client.get(f"/agent-tasks?agent_id={agent.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1

    # All items should be for this agent
    for item in data["items"]:
        assert item["agent_id"] == str(agent.id)


def test_get_agent_task(client: TestClient, agent, task, db_session: Session) -> None:
    """Test getting a specific agent task."""
    agent_task = AgentTask(
        task_id=task.id,
        agent_id=agent.id,
        status="in_progress",
    )
    db_session.add(agent_task)
    db_session.flush()

    response = client.get(f"/agent-tasks/{agent_task.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(agent_task.id)
    assert data["status"] == "in_progress"


def test_accept_submission(
    client: TestClient, agent_with_balance, task, db_session: Session
) -> None:
    """Test accepting a submission."""
    # Create a submitted agent task
    agent_task = AgentTask(
        task_id=task.id,
        agent_id=agent_with_balance.id,
        status="submitted",
        result="My submission result",
    )
    db_session.add(agent_task)
    db_session.flush()

    response = client.post(f"/agent-tasks/{agent_task.id}/accept")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "accepted"


def test_deny_submission(
    client: TestClient, agent, task, db_session: Session
) -> None:
    """Test denying a submission."""
    # Create a submitted agent task
    agent_task = AgentTask(
        task_id=task.id,
        agent_id=agent.id,
        status="submitted",
        result="My submission result",
    )
    db_session.add(agent_task)
    db_session.flush()

    response = client.post(f"/agent-tasks/{agent_task.id}/deny")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "denied"


def test_accept_in_progress_task(
    client: TestClient, agent, task, db_session: Session
) -> None:
    """Test accepting a task that is still in progress.

    Note: The current implementation allows accepting tasks in any status.
    This test documents the current behavior.
    """
    agent_task = AgentTask(
        task_id=task.id,
        agent_id=agent.id,
        status="in_progress",
    )
    db_session.add(agent_task)
    db_session.flush()

    response = client.post(f"/agent-tasks/{agent_task.id}/accept")
    # Current behavior: accepts regardless of status
    assert response.status_code == 200
    assert response.json()["status"] == "accepted"


def test_accept_submission_grants_reward(
    client: TestClient, agent_with_balance, task, db_session: Session
) -> None:
    """Test that accepting a submission grants the reward."""
    initial_balance = Decimal("0.10")
    reward = Decimal("0.05")

    # Create a submitted agent task
    agent_task = AgentTask(
        task_id=task.id,
        agent_id=agent_with_balance.id,
        status="submitted",
        result="My result",
    )
    db_session.add(agent_task)
    db_session.flush()

    # Accept the submission
    response = client.post(f"/agent-tasks/{agent_task.id}/accept")
    assert response.status_code == 200

    # Check the new balance
    response = client.get(f"/agents/{agent_with_balance.id}/balance")
    assert response.status_code == 200
    new_balance = Decimal(response.json()["balance"])
    assert new_balance == initial_balance + reward
