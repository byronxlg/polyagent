"""Tests for /simulations API endpoints."""

from uuid import uuid4

from fastapi.testclient import TestClient


def test_create_simulation(client: TestClient, human_principal) -> None:
    """Test creating a simulation."""
    response = client.post(
        "/simulations",
        json={
            "principal_id": str(human_principal.id),
            "name": "My Simulation",
            "description": "Test description",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "My Simulation"
    assert data["description"] == "Test description"
    assert data["principal_id"] == str(human_principal.id)
    assert "id" in data
    assert "created_at" in data


def test_create_simulation_without_description(
    client: TestClient, human_principal
) -> None:
    """Test creating a simulation without description."""
    response = client.post(
        "/simulations",
        json={
            "principal_id": str(human_principal.id),
            "name": "Minimal Simulation",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Minimal Simulation"
    assert data["description"] is None


def test_list_simulations_structure(client: TestClient) -> None:
    """Test listing simulations returns proper structure."""
    response = client.get("/simulations")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert "limit" in data
    assert "offset" in data
    assert "has_more" in data


def test_list_simulations(client: TestClient, simulation) -> None:
    """Test listing simulations."""
    response = client.get("/simulations")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1

    # Verify the fixture simulation is in the list
    names = [s["name"] for s in data["items"]]
    assert "Test Simulation" in names


def test_get_simulation(client: TestClient, simulation) -> None:
    """Test getting a specific simulation."""
    response = client.get(f"/simulations/{simulation.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(simulation.id)
    assert data["name"] == "Test Simulation"


def test_get_simulation_not_found(client: TestClient) -> None:
    """Test 404 for non-existent simulation."""
    fake_id = uuid4()
    response = client.get(f"/simulations/{fake_id}")
    assert response.status_code == 404


def test_update_simulation(client: TestClient, simulation) -> None:
    """Test updating a simulation."""
    response = client.patch(
        f"/simulations/{simulation.id}",
        json={
            "name": "Updated Name",
            "description": "Updated description",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Name"
    assert data["description"] == "Updated description"


def test_update_simulation_partial(client: TestClient, simulation) -> None:
    """Test partial update of a simulation."""
    original_description = simulation.description

    response = client.patch(
        f"/simulations/{simulation.id}",
        json={"name": "Only Name Updated"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Only Name Updated"
    assert data["description"] == original_description


def test_delete_simulation_empty(client: TestClient, simulation) -> None:
    """Test deleting an empty simulation."""
    response = client.delete(f"/simulations/{simulation.id}")
    assert response.status_code == 200

    # Verify it's gone
    response = client.get(f"/simulations/{simulation.id}")
    assert response.status_code == 404


def test_delete_simulation_with_agents_fails(client: TestClient, agent) -> None:
    """Test that deleting simulation with agents fails."""
    simulation_id = agent.simulation_id
    response = client.delete(f"/simulations/{simulation_id}")
    assert response.status_code == 400
    assert "agents exist" in response.json()["detail"].lower()
