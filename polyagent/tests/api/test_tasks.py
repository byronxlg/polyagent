"""Tests for /tasks API endpoints."""

from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient


def test_create_task(client: TestClient, simulation, human_principal) -> None:
    """Test creating a task."""
    deadline = (datetime.utcnow() + timedelta(days=1)).isoformat() + "Z"
    response = client.post(
        "/tasks",
        json={
            "simulation_id": str(simulation.id),
            "created_by_principal_id": str(human_principal.id),
            "description": "Write a haiku",
            "reward_dollars": "0.05",
            "deadline": deadline,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["description"] == "Write a haiku"
    assert Decimal(data["reward_dollars"]) == Decimal("0.05")
    assert data["status"] == "available"
    assert "id" in data


def test_list_tasks_structure(client: TestClient) -> None:
    """Test listing tasks returns proper structure."""
    response = client.get("/tasks")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert "limit" in data
    assert "offset" in data
    assert "has_more" in data


def test_list_tasks(client: TestClient, task) -> None:
    """Test listing tasks."""
    response = client.get("/tasks")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1


def test_list_available_tasks_only(client: TestClient, task, expired_task) -> None:
    """Test filtering for available tasks only."""
    response = client.get("/tasks?available_only=true")
    assert response.status_code == 200
    data = response.json()

    # Only the non-expired task should be in the list
    descriptions = [t["description"] for t in data["items"]]
    assert "Test task description" in descriptions
    assert "Expired task" not in descriptions


def test_get_task(client: TestClient, task) -> None:
    """Test getting a specific task."""
    response = client.get(f"/tasks/{task.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(task.id)
    assert data["description"] == "Test task description"
    assert data["status"] == "available"
    assert "agent_tasks" in data


def test_get_task_not_found(client: TestClient) -> None:
    """Test 404 for non-existent task."""
    fake_id = uuid4()
    response = client.get(f"/tasks/{fake_id}")
    assert response.status_code == 404


def test_update_task_deadline(client: TestClient, task) -> None:
    """Test updating a task deadline."""
    new_deadline = (datetime.utcnow() + timedelta(days=7)).isoformat() + "Z"
    response = client.patch(
        f"/tasks/{task.id}",
        json={"deadline": new_deadline},
    )
    assert response.status_code == 200
    data = response.json()
    # Deadline should be updated
    assert data["deadline"] is not None


def test_task_status_expired(client: TestClient, expired_task) -> None:
    """Test that expired tasks have 'expired' status."""
    response = client.get(f"/tasks/{expired_task.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "expired"
