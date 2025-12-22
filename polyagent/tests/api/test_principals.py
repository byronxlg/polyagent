"""Tests for /principals API endpoints."""

from uuid import uuid4

from fastapi.testclient import TestClient


def test_create_principal(client: TestClient) -> None:
    """Test creating a new principal."""
    response = client.post(
        "/principals",
        json={
            "username": "new_user",
            "principal_type": "human",
            "email": "new@example.com",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "new_user"
    assert data["principal_type"] == "human"
    assert data["email"] == "new@example.com"
    assert "id" in data
    assert "created_at" in data


def test_create_principal_without_email(client: TestClient) -> None:
    """Test creating a principal without email."""
    response = client.post(
        "/principals",
        json={
            "username": "agent_user",
            "principal_type": "ai_agent",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "agent_user"
    assert data["email"] is None


def test_list_principals_empty(client: TestClient) -> None:
    """Test listing principals when none exist."""
    response = client.get("/principals")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert "limit" in data
    assert "offset" in data
    assert "has_more" in data


def test_list_principals(client: TestClient, human_principal) -> None:
    """Test listing principals with pagination."""
    response = client.get("/principals")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert len(data["items"]) >= 1

    # Verify the fixture principal is in the list
    usernames = [p["username"] for p in data["items"]]
    assert "test_human" in usernames


def test_get_principal(client: TestClient, human_principal) -> None:
    """Test getting a specific principal."""
    response = client.get(f"/principals/{human_principal.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(human_principal.id)
    assert data["username"] == "test_human"
    assert data["principal_type"] == "human"


def test_get_principal_not_found(client: TestClient) -> None:
    """Test 404 for non-existent principal."""
    fake_id = uuid4()
    response = client.get(f"/principals/{fake_id}")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()
