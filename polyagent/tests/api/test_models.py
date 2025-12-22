"""Tests for /models API endpoints."""

from uuid import uuid4

from fastapi.testclient import TestClient


def test_create_model(client: TestClient) -> None:
    """Test creating a model."""
    response = client.post(
        "/models",
        json={
            "name": "GPT-4",
            "provider_name": "OpenAI",
            "provider": "openai",
            "provider_model_id": "gpt-4",
            "description": "GPT-4 model",
            "is_reasoning": False,
            "input_cost_per_million": "30.00",
            "output_cost_per_million": "60.00",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "GPT-4"
    assert data["provider"] == "openai"
    assert data["is_reasoning"] is False
    assert "id" in data


def test_create_model_reasoning(client: TestClient) -> None:
    """Test creating a reasoning model."""
    response = client.post(
        "/models",
        json={
            "name": "o1",
            "provider_name": "OpenAI",
            "provider": "openai",
            "provider_model_id": "o1",
            "description": "OpenAI o1 reasoning model",
            "is_reasoning": True,
            "input_cost_per_million": "15.00",
            "output_cost_per_million": "60.00",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["is_reasoning"] is True


def test_list_models_structure(client: TestClient) -> None:
    """Test listing models returns proper structure."""
    response = client.get("/models")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert "limit" in data
    assert "offset" in data
    assert "has_more" in data


def test_list_models(client: TestClient, model) -> None:
    """Test listing models."""
    response = client.get("/models")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1

    # Verify the fixture model is in the list
    names = [m["name"] for m in data["items"]]
    assert "Test Model" in names


def test_get_model(client: TestClient, model) -> None:
    """Test getting a specific model."""
    response = client.get(f"/models/{model.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(model.id)
    assert data["name"] == "Test Model"
    assert data["provider"] == "test"


def test_get_model_not_found(client: TestClient) -> None:
    """Test 404 for non-existent model."""
    fake_id = uuid4()
    response = client.get(f"/models/{fake_id}")
    assert response.status_code == 404


def test_delete_model_unused(client: TestClient, model) -> None:
    """Test deleting an unused model."""
    response = client.delete(f"/models/{model.id}")
    assert response.status_code == 200

    # Verify it's gone
    response = client.get(f"/models/{model.id}")
    assert response.status_code == 404


def test_delete_model_in_use_fails(client: TestClient, agent) -> None:
    """Test that deleting a model in use by agents fails."""
    model_id = agent.model_id
    response = client.delete(f"/models/{model_id}")
    assert response.status_code == 400
    assert "cannot delete" in response.json()["detail"].lower()
