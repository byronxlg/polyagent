"""Tests for /agents API endpoints."""

from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient


def test_create_agent(
    client: TestClient, simulation, model, human_principal, system_principal
) -> None:
    """Test creating an agent."""
    response = client.post(
        "/agents",
        json={
            "simulation_id": str(simulation.id),
            "model_id": str(model.id),
            "created_by_principal_id": str(human_principal.id),
            "name": "New Agent",
            "initial_balance": "0.15",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "New Agent"
    assert data["simulation_id"] == str(simulation.id)
    assert data["model_id"] == str(model.id)
    assert "id" in data
    assert "principal_id" in data


def test_create_agent_with_memory(
    client: TestClient, simulation, model, human_principal, system_principal
) -> None:
    """Test creating an agent with initial memory."""
    response = client.post(
        "/agents",
        json={
            "simulation_id": str(simulation.id),
            "model_id": str(model.id),
            "created_by_principal_id": str(human_principal.id),
            "name": "Memory Agent",
            "initial_balance": "0.10",
            "memory_json": {"goals": ["survive", "thrive"]},
            "memory_text": "I am a test agent.",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["memory_json"] == {"goals": ["survive", "thrive"]}
    assert data["memory_text"] == "I am a test agent."


def test_list_agents_structure(client: TestClient) -> None:
    """Test listing agents returns proper structure."""
    response = client.get("/agents")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert "limit" in data
    assert "offset" in data
    assert "has_more" in data


def test_list_agents(client: TestClient, agent) -> None:
    """Test listing agents."""
    response = client.get("/agents")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1

    # Verify the fixture agent is in the list
    names = [a["name"] for a in data["items"]]
    assert "Test Agent" in names


def test_get_agent(client: TestClient, agent) -> None:
    """Test getting a specific agent."""
    response = client.get(f"/agents/{agent.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(agent.id)
    assert data["name"] == "Test Agent"


def test_get_agent_not_found(client: TestClient) -> None:
    """Test 404 for non-existent agent."""
    fake_id = uuid4()
    response = client.get(f"/agents/{fake_id}")
    assert response.status_code == 404


def test_update_agent(client: TestClient, agent) -> None:
    """Test updating an agent."""
    response = client.patch(
        f"/agents/{agent.id}",
        json={
            "name": "Updated Agent",
            "public_profile": "I am an updated agent.",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Agent"
    assert data["public_profile"] == "I am an updated agent."


def test_get_agent_balance_zero(client: TestClient, agent) -> None:
    """Test getting agent balance when no transactions exist."""
    response = client.get(f"/agents/{agent.id}/balance")
    assert response.status_code == 200
    data = response.json()
    assert data["agent_id"] == str(agent.id)
    assert Decimal(data["balance"]) == Decimal("0")


def test_get_agent_balance(client: TestClient, agent_with_balance) -> None:
    """Test getting agent balance with transactions."""
    response = client.get(f"/agents/{agent_with_balance.id}/balance")
    assert response.status_code == 200
    data = response.json()
    assert Decimal(data["balance"]) == Decimal("0.10")


def test_get_agent_servers(client: TestClient, agent) -> None:
    """Test getting MCP servers granted to an agent."""
    response = client.get(f"/agents/{agent.id}/servers")
    assert response.status_code == 200
    data = response.json()
    # Should be a list (possibly empty if no servers granted in test env)
    assert isinstance(data, list)


def test_delete_agent(client: TestClient, agent) -> None:
    """Test deleting an agent."""
    agent_id = agent.id
    response = client.delete(f"/agents/{agent_id}")
    assert response.status_code == 200

    # Verify it's gone
    response = client.get(f"/agents/{agent_id}")
    assert response.status_code == 404
