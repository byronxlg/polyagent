"""Tests for TransactionService."""

from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from src.models import Agent, Principal, Transaction
from src.services.transaction_service import TransactionService


def test_get_balance_zero(
    db_session: Session, agent, override_session_local
) -> None:
    """Test balance is zero for agent with no transactions."""
    service = TransactionService()
    balance = service.get_balance(agent.id)
    assert balance == Decimal("0")


def test_get_balance_with_incoming(
    db_session: Session, agent_with_balance, override_session_local
) -> None:
    """Test balance with incoming transaction."""
    service = TransactionService()
    balance = service.get_balance(agent_with_balance.id)
    assert balance == Decimal("0.10")


def test_get_balance_with_outgoing(
    db_session: Session, agent_with_balance, override_session_local
) -> None:
    """Test balance with incoming and outgoing transactions."""
    # Add an outgoing transaction
    tx = Transaction(
        from_principal_id=agent_with_balance.principal_id,
        to_principal_id=None,
        amount=Decimal("0.03"),
        reason="test_deduction",
    )
    db_session.add(tx)
    db_session.flush()

    service = TransactionService()
    balance = service.get_balance(agent_with_balance.id)
    assert balance == Decimal("0.07")  # 0.10 - 0.03


def test_grant_dollars(
    db_session: Session, agent, override_session_local
) -> None:
    """Test granting dollars to an agent."""
    service = TransactionService()
    tx = service.grant_dollars(agent.id, Decimal("0.50"), "test_grant")

    assert tx.amount == Decimal("0.50")
    assert tx.to_principal_id == agent.principal_id
    assert tx.from_principal_id is None
    assert tx.reason == "test_grant"

    # Verify balance updated
    balance = service.get_balance(agent.id)
    assert balance == Decimal("0.50")


def test_deduct_dollars(
    db_session: Session, agent_with_balance, override_session_local
) -> None:
    """Test deducting dollars from an agent."""
    service = TransactionService()
    tx = service.deduct_dollars(agent_with_balance.id, Decimal("0.05"), "test_deduct")

    assert tx.amount == Decimal("0.05")
    assert tx.from_principal_id == agent_with_balance.principal_id
    assert tx.to_principal_id is None

    # Verify balance updated
    balance = service.get_balance(agent_with_balance.id)
    assert balance == Decimal("0.05")  # 0.10 - 0.05


def test_transfer_dollars(
    db_session: Session,
    agent_with_balance,
    simulation,
    model,
    human_principal,
    override_session_local,
) -> None:
    """Test transferring dollars between agents."""
    # Create a second agent
    agent2_principal = Principal(username="agent2", principal_type="ai_agent")
    db_session.add(agent2_principal)
    db_session.flush()

    agent2 = Agent(
        simulation_id=simulation.id,
        principal_id=agent2_principal.id,
        model_id=model.id,
        created_by_principal_id=human_principal.id,
        name="Agent 2",
    )
    db_session.add(agent2)
    db_session.flush()

    service = TransactionService()
    tx = service.transfer_dollars(
        agent_with_balance.id, agent2.id, Decimal("0.05"), "test_transfer"
    )

    assert tx.amount == Decimal("0.05")
    assert tx.from_principal_id == agent_with_balance.principal_id
    assert tx.to_principal_id == agent2.principal_id

    # Verify balances
    balance1 = service.get_balance(agent_with_balance.id)
    balance2 = service.get_balance(agent2.id)
    assert balance1 == Decimal("0.05")  # 0.10 - 0.05
    assert balance2 == Decimal("0.05")


def test_transfer_insufficient_balance_fails(
    db_session: Session,
    agent,
    simulation,
    model,
    human_principal,
    override_session_local,
) -> None:
    """Test transfer fails with insufficient balance."""
    # Create a second agent
    agent2_principal = Principal(username="agent2", principal_type="ai_agent")
    db_session.add(agent2_principal)
    db_session.flush()

    agent2 = Agent(
        simulation_id=simulation.id,
        principal_id=agent2_principal.id,
        model_id=model.id,
        created_by_principal_id=human_principal.id,
        name="Agent 2",
    )
    db_session.add(agent2)
    db_session.flush()

    service = TransactionService()

    with pytest.raises(ValueError, match="Insufficient balance"):
        service.transfer_dollars(agent.id, agent2.id, Decimal("1.00"))


def test_get_balance_nonexistent_agent(
    db_session: Session, override_session_local
) -> None:
    """Test getting balance for non-existent agent fails."""
    from uuid import uuid4

    service = TransactionService()

    with pytest.raises(ValueError, match="not found"):
        service.get_balance(uuid4())
