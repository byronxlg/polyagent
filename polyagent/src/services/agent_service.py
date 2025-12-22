from uuid import UUID

from sqlalchemy import func

from src.database import SessionLocal
from src.models import Agent, Transaction


class AgentService:
    def __init__(self) -> None:
        pass

    def get_agents(self, exclude_agent_id: UUID | str | None = None) -> list[Agent]:
        """Get all agents, optionally excluding one agent."""
        session = SessionLocal()
        try:
            query = session.query(Agent)
            if exclude_agent_id is not None:
                query = query.filter(Agent.id != exclude_agent_id)
            agents = query.all()
            for agent in agents:
                session.refresh(agent)
                session.expunge(agent)
            return agents
        finally:
            session.close()

    def get_agent(self, agent_id: UUID | str) -> Agent | None:
        """Get a specific agent by ID."""
        session = SessionLocal()
        try:
            agent = session.query(Agent).filter(Agent.id == agent_id).first()
            if agent:
                session.refresh(agent)
                session.expunge(agent)
            return agent
        finally:
            session.close()

    def get_agent_balance(self, agent_id: UUID | str) -> str:
        """Get an agent's balance."""
        session = SessionLocal()
        try:
            # Convert agent_id to principal_id
            agent = session.query(Agent).filter(Agent.id == agent_id).first()
            if not agent:
                return "0.0000"

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
            balance = float(incoming) - float(outgoing)
            return f"{balance:.4f}"
        finally:
            session.close()

    def update_profile(
        self, agent_id: UUID | str, name: str | None = None, public_profile: str | None = None
    ) -> Agent | None:
        """Update an agent's profile (name and/or public_profile)."""
        session = SessionLocal()
        try:
            agent = session.query(Agent).filter(Agent.id == agent_id).first()
            if not agent:
                return None
            if name is not None:
                agent.name = name
            if public_profile is not None:
                agent.public_profile = public_profile
            session.commit()
            session.refresh(agent)
            session.expunge(agent)
            return agent
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
