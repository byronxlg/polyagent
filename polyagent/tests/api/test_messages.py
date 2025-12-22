"""Tests for /messages API endpoints."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.models import Message


def test_list_messages_structure(client: TestClient) -> None:
    """Test listing messages returns correct structure."""
    response = client.get("/messages")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert isinstance(data["items"], list)
    assert isinstance(data["total"], int)


def test_list_messages(
    client: TestClient, agent, human_principal, db_session: Session
) -> None:
    """Test listing messages."""
    # Create a message
    message = Message(
        from_principal_id=human_principal.id,
        to_principal_id=agent.principal_id,
        content="Hello agent!",
    )
    db_session.add(message)
    db_session.flush()

    response = client.get("/messages")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1


def test_list_messages_filter_by_agent(
    client: TestClient, agent, human_principal, db_session: Session
) -> None:
    """Test filtering messages by agent."""
    # Create a message to the agent
    message = Message(
        from_principal_id=human_principal.id,
        to_principal_id=agent.principal_id,
        content="Hello agent!",
    )
    db_session.add(message)
    db_session.flush()

    response = client.get(f"/messages?agent_id={agent.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1


def test_get_inbox_empty(client: TestClient, agent) -> None:
    """Test getting empty inbox."""
    response = client.get(f"/agents/{agent.id}/inbox")
    assert response.status_code == 200
    data = response.json()
    assert data == []


def test_get_inbox_with_messages(
    client: TestClient, agent, human_principal, db_session: Session
) -> None:
    """Test getting inbox with unread messages."""
    # Create an unread message (received_at is None)
    message = Message(
        from_principal_id=human_principal.id,
        to_principal_id=agent.principal_id,
        content="Unread message",
        received_at=None,
    )
    db_session.add(message)
    db_session.flush()

    response = client.get(f"/agents/{agent.id}/inbox")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[0]["content"] == "Unread message"


def test_get_inbox_marks_as_received(
    client: TestClient, agent, human_principal, db_session: Session
) -> None:
    """Test that getting inbox marks messages as received."""
    # Create an unread message
    message = Message(
        from_principal_id=human_principal.id,
        to_principal_id=agent.principal_id,
        content="Will be marked read",
        received_at=None,
    )
    db_session.add(message)
    db_session.flush()

    # First call gets the message
    response = client.get(f"/agents/{agent.id}/inbox")
    assert response.status_code == 200
    assert len(response.json()) >= 1

    # Second call should return empty (message now received)
    response = client.get(f"/agents/{agent.id}/inbox")
    assert response.status_code == 200
    assert len(response.json()) == 0


def test_send_message(
    client: TestClient, agent, human_principal
) -> None:
    """Test sending a message via API."""
    response = client.post(
        "/messages",
        json={
            "from_principal_id": str(human_principal.id),
            "to_principal_id": str(agent.principal_id),
            "content": "Hello from API test!",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["content"] == "Hello from API test!"
    assert data["from_principal_id"] == str(human_principal.id)
    assert data["to_principal_id"] == str(agent.principal_id)
    assert data["sent_at"] is not None
    assert data["received_at"] is None
