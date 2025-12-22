"""Tests for /transactions API endpoints."""

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.models import Transaction


def test_list_transactions_structure(client: TestClient) -> None:
    """Test listing transactions returns proper structure."""
    response = client.get("/transactions")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert "limit" in data
    assert "offset" in data
    assert "has_more" in data


def test_list_transactions(client: TestClient, agent_with_balance) -> None:
    """Test listing transactions."""
    # agent_with_balance fixture creates a transaction
    response = client.get("/transactions")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1


def test_list_transactions_filter_by_agent(
    client: TestClient, agent_with_balance
) -> None:
    """Test filtering transactions by agent."""
    response = client.get(f"/transactions?agent_id={agent_with_balance.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1

    # All transactions should involve this agent's principal
    for tx in data["items"]:
        principal_id = str(agent_with_balance.principal_id)
        assert tx["to_principal_id"] == principal_id or tx["from_principal_id"] == principal_id


def test_transactions_ordered_by_timestamp(
    client: TestClient, agent, db_session: Session
) -> None:
    """Test that transactions are ordered by timestamp descending."""
    # Create multiple transactions
    for i in range(3):
        tx = Transaction(
            from_principal_id=None,
            to_principal_id=agent.principal_id,
            amount=Decimal(f"0.0{i + 1}"),
            reason=f"test_{i}",
        )
        db_session.add(tx)
    db_session.flush()

    response = client.get("/transactions")
    assert response.status_code == 200
    data = response.json()

    # Verify descending order by timestamp
    timestamps = [tx["timestamp"] for tx in data["items"]]
    assert timestamps == sorted(timestamps, reverse=True)
