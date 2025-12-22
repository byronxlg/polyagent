from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func

from src.database import SessionLocal
from src.models import Agent, Transaction


class TransactionService:
    def __init__(self) -> None:
        pass

    def get_balance(self, agent_id: UUID | str) -> Decimal:
        session = SessionLocal()
        try:
            # Convert agent ID to principal ID
            agent = session.get(Agent, agent_id)
            if not agent:
                msg = f"Agent {agent_id} not found"
                raise ValueError(msg)

            incoming = (
                session.query(func.coalesce(func.sum(Transaction.amount), 0))
                .filter(Transaction.to_principal_id == agent.principal_id)
                .scalar()
            )

            outgoing = (
                session.query(func.coalesce(func.sum(Transaction.amount), 0))
                .filter(Transaction.from_principal_id == agent.principal_id)
                .scalar()
            )

            return Decimal(str(incoming)) - Decimal(str(outgoing))
        finally:
            session.close()

    def grant_dollars(
        self, to_agent_id: UUID | str, amount: Decimal, reason: str, reference_id: UUID | str | None = None
    ) -> Transaction:
        session = SessionLocal()
        try:
            # Convert agent ID to principal ID
            agent = session.get(Agent, to_agent_id)
            if not agent:
                msg = f"Agent {to_agent_id} not found"
                raise ValueError(msg)

            transaction = Transaction(
                from_principal_id=None,
                to_principal_id=agent.principal_id,
                amount=amount,
                reason=reason,
                reference_id=reference_id,
                timestamp=datetime.utcnow(),
            )
            session.add(transaction)
            session.commit()
            session.refresh(transaction)
            session.expunge(transaction)
            return transaction
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def deduct_dollars(
        self, from_agent_id: UUID | str, amount: Decimal, reason: str, reference_id: UUID | str | None = None
    ) -> Transaction:
        """Deduct dollars from an agent. Does not check balance - caller is responsible for validation."""
        session = SessionLocal()
        try:
            # Convert agent ID to principal ID
            agent = session.get(Agent, from_agent_id)
            if not agent:
                msg = f"Agent {from_agent_id} not found"
                raise ValueError(msg)

            transaction = Transaction(
                from_principal_id=agent.principal_id,
                to_principal_id=None,
                amount=amount,
                reason=reason,
                reference_id=reference_id,
                timestamp=datetime.utcnow(),
            )
            session.add(transaction)
            session.commit()
            session.refresh(transaction)
            session.expunge(transaction)
            return transaction
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def transfer_dollars(
        self, from_agent_id: UUID | str, to_agent_id: UUID | str, amount: Decimal, reason: str = "transfer"
    ) -> Transaction:
        session = SessionLocal()
        try:
            balance = self.get_balance(from_agent_id)
            if balance < 0:
                msg = f"Agent {from_agent_id} is in debt (balance: {balance})"
                raise ValueError(msg)
            if balance < amount:
                msg = f"Insufficient balance: {balance} < {amount}"
                raise ValueError(msg)

            # Convert agent IDs to principal IDs
            from_agent = session.get(Agent, from_agent_id)
            to_agent = session.get(Agent, to_agent_id)

            if not from_agent:
                msg = f"Agent {from_agent_id} not found"
                raise ValueError(msg)
            if not to_agent:
                msg = f"Agent {to_agent_id} not found"
                raise ValueError(msg)

            transaction = Transaction(
                from_principal_id=from_agent.principal_id,
                to_principal_id=to_agent.principal_id,
                amount=amount,
                reason=reason,
                reference_id=None,
                timestamp=datetime.utcnow(),
            )
            session.add(transaction)
            session.commit()
            session.refresh(transaction)
            session.expunge(transaction)
            return transaction
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
