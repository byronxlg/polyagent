"""Tests for TaskService."""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from src.models import AgentTask, Task
from src.services.task_service import TaskService


def test_accept_task(
    db_session: Session, agent, task, override_session_local
) -> None:
    """Test agent accepting a task."""
    service = TaskService()
    agent_task = service.accept_task(task.id, agent.id)

    assert agent_task.task_id == task.id
    assert agent_task.agent_id == agent.id
    assert agent_task.status == "in_progress"


def test_accept_task_duplicate_fails(
    db_session: Session, agent, task, override_session_local
) -> None:
    """Test that accepting same task twice fails."""
    service = TaskService()
    service.accept_task(task.id, agent.id)

    with pytest.raises(ValueError, match="already have an active AgentTask"):
        service.accept_task(task.id, agent.id)


def test_submit_task(
    db_session: Session, agent, task, override_session_local
) -> None:
    """Test submitting a task result."""
    service = TaskService()
    agent_task = service.accept_task(task.id, agent.id)

    result = service.submit_task(agent_task.id, "My result")

    assert result.status == "submitted"
    assert result.result == "My result"
    assert result.submitted_at is not None


def test_submit_task_after_deadline_is_late(
    db_session: Session, agent, expired_task, override_session_local
) -> None:
    """Test that submitting after deadline marks as late."""
    service = TaskService()

    # Create agent task directly since the task is already expired
    agent_task = AgentTask(
        task_id=expired_task.id,
        agent_id=agent.id,
        status="in_progress",
    )
    db_session.add(agent_task)
    db_session.flush()

    result = service.submit_task(agent_task.id, "Late result")
    assert result.status == "late"


def test_abandon_task(
    db_session: Session, agent, task, override_session_local
) -> None:
    """Test abandoning a task."""
    service = TaskService()
    agent_task = service.accept_task(task.id, agent.id)

    result = service.abandon_task(agent_task.id)

    assert result.status == "abandoned"


def test_get_available_tasks(
    db_session: Session, task, expired_task, override_session_local
) -> None:
    """Test getting only available tasks."""
    service = TaskService()
    tasks = service.get_available_tasks()

    task_ids = [t.id for t in tasks]
    assert task.id in task_ids
    assert expired_task.id not in task_ids


def test_accept_submission(
    db_session: Session, agent_with_balance, task, override_session_local
) -> None:
    """Test accepting a submission."""
    service = TaskService()

    # Create and submit
    agent_task = service.accept_task(task.id, agent_with_balance.id)
    service.submit_task(agent_task.id, "My result")

    # Accept
    result = service.accept_submission(agent_task.id)

    assert result.status == "accepted"


def test_accept_submission_marks_task_closed(
    db_session: Session, agent_with_balance, task, override_session_local
) -> None:
    """Test that accepting submission closes the task."""
    service = TaskService()

    agent_task = service.accept_task(task.id, agent_with_balance.id)
    service.submit_task(agent_task.id, "Result")
    service.accept_submission(agent_task.id)

    # Refresh task from DB
    db_session.refresh(task)
    assert task.is_completed is True


def test_deny_submission(
    db_session: Session, agent, task, override_session_local
) -> None:
    """Test denying a submission."""
    service = TaskService()

    agent_task = service.accept_task(task.id, agent.id)
    service.submit_task(agent_task.id, "My result")
    result = service.deny_submission(agent_task.id)

    assert result.status == "denied"


def test_get_next_pending_submission(
    db_session: Session, simulation, human_principal, agent, override_session_local
) -> None:
    """Test getting the next pending submission."""
    # Create a task
    task = Task(
        simulation_id=simulation.id,
        created_by_principal_id=human_principal.id,
        description="Multi-agent task",
        reward_dollars=Decimal("0.10"),
        deadline=datetime.utcnow() + timedelta(days=1),
    )
    db_session.add(task)
    db_session.flush()

    service = TaskService()

    # Accept and submit
    agent_task = service.accept_task(task.id, agent.id)
    service.submit_task(agent_task.id, "First submission")

    # Get pending
    pending = service.get_next_pending_submission(task.id)
    assert pending is not None
    assert pending.id == agent_task.id
