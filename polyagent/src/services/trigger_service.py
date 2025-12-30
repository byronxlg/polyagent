"""Service for managing agent trigger subscriptions and simulation configuration."""

from datetime import datetime
from uuid import UUID

from src.database import SessionLocal
from src.models import Agent, AgentTrigger, AgentTriggerEvent, Simulation
from src.schemas import TriggerChangeType, TriggerTableName


class TriggerService:
    """Service for managing agent trigger subscriptions."""

    def create_subscription(
        self,
        agent_id: UUID | str,
        table_name: str,
        change_type: str,
        conditions: dict | None = None,
    ) -> AgentTrigger:
        """Create a new trigger subscription for an agent.

        Args:
            agent_id: The agent subscribing to events
            table_name: Table to watch (tasks, messages, agent_tasks, transactions)
            change_type: Type of change (INSERT, UPDATE, DELETE)
            conditions: Optional filters (e.g., {"status": "available"})

        Returns:
            The created AgentTrigger

        Raises:
            ValueError: If table_name or change_type is invalid
        """
        valid_tables = {t.value for t in TriggerTableName}
        valid_change_types = {c.value for c in TriggerChangeType}
        if table_name not in valid_tables:
            msg = f"Invalid table_name. Choose from: {valid_tables}"
            raise ValueError(msg)
        if change_type not in valid_change_types:
            msg = f"Invalid change_type. Choose from: {valid_change_types}"
            raise ValueError(msg)

        session = SessionLocal()
        try:
            # Verify agent exists
            agent = session.query(Agent).filter(Agent.id == agent_id).first()
            if not agent:
                msg = f"Agent {agent_id} not found"
                raise ValueError(msg)

            # Check for existing active trigger with same params
            existing = (
                session.query(AgentTrigger)
                .filter(
                    AgentTrigger.agent_id == agent_id,
                    AgentTrigger.table_name == table_name,
                    AgentTrigger.change_type == change_type,
                    AgentTrigger.is_active == True,  # noqa: E712
                )
                .first()
            )
            if existing:
                msg = (
                    f"Duplicate trigger exists (id={existing.id}). "
                    "Deactivate it first or use a different table/change_type."
                )
                raise ValueError(msg)

            trigger = AgentTrigger(
                agent_id=agent_id,
                table_name=table_name,
                change_type=change_type,
                conditions=conditions or {},
                is_active=True,
                created_at=datetime.utcnow(),
            )
            session.add(trigger)
            session.commit()
            session.refresh(trigger)
            session.expunge(trigger)
            return trigger
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_subscription(self, subscription_id: UUID | str) -> AgentTrigger | None:
        """Get a specific subscription by ID."""
        session = SessionLocal()
        try:
            trigger = session.query(AgentTrigger).filter(AgentTrigger.id == subscription_id).first()
            if trigger:
                session.expunge(trigger)
            return trigger
        finally:
            session.close()

    def list_subscriptions(
        self,
        agent_id: UUID | str | None = None,
        *,
        is_active: bool | None = True,
    ) -> list[AgentTrigger]:
        """List trigger subscriptions with optional filters."""
        session = SessionLocal()
        try:
            query = session.query(AgentTrigger)
            if agent_id:
                query = query.filter(AgentTrigger.agent_id == agent_id)
            if is_active is not None:
                query = query.filter(AgentTrigger.is_active == is_active)

            triggers = query.order_by(AgentTrigger.created_at.desc()).all()
            for t in triggers:
                session.expunge(t)
            return triggers
        finally:
            session.close()

    def update_subscription(
        self,
        subscription_id: UUID | str,
        conditions: dict | None = None,
        *,
        is_active: bool | None = None,
    ) -> AgentTrigger:
        """Update subscription properties."""
        session = SessionLocal()
        try:
            trigger = session.query(AgentTrigger).filter(AgentTrigger.id == subscription_id).first()
            if not trigger:
                msg = f"Trigger {subscription_id} not found"
                raise ValueError(msg)

            if is_active is not None:
                trigger.is_active = is_active
            if conditions is not None:
                trigger.conditions = conditions

            session.commit()
            session.refresh(trigger)
            session.expunge(trigger)
            return trigger
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def delete_subscription(self, subscription_id: UUID | str) -> bool:
        """Delete a trigger subscription (hard delete)."""
        session = SessionLocal()
        try:
            trigger = session.query(AgentTrigger).filter(AgentTrigger.id == subscription_id).first()
            if not trigger:
                return False
            session.delete(trigger)
            session.commit()
            return True
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_active_triggers_for_simulation(self, simulation_id: UUID | str) -> list[AgentTrigger]:
        """Get all active triggers for agents in a simulation."""
        session = SessionLocal()
        try:
            # Get agent IDs for this simulation
            agent_ids = [
                a.id for a in session.query(Agent).filter(Agent.simulation_id == simulation_id).all()
            ]
            if not agent_ids:
                return []

            triggers = (
                session.query(AgentTrigger)
                .filter(
                    AgentTrigger.agent_id.in_(agent_ids),
                    AgentTrigger.is_active == True,  # noqa: E712
                )
                .all()
            )
            for t in triggers:
                session.expunge(t)
            return triggers
        finally:
            session.close()

    def update_last_triggered(self, subscription_id: UUID | str) -> None:
        """Update the last_triggered_at timestamp."""
        session = SessionLocal()
        try:
            trigger = session.query(AgentTrigger).filter(AgentTrigger.id == subscription_id).first()
            if trigger:
                trigger.last_triggered_at = datetime.utcnow()
                session.commit()
        finally:
            session.close()


class TriggerEventService:
    """Service for tracking trigger event history."""

    def record_trigger_event(  # noqa: PLR0913
        self,
        trigger_id: UUID | str,
        agent_id: UUID | str,
        table_name: str,
        record_id: UUID | str,
        change_type: str,
        matched_conditions: dict | None = None,
    ) -> AgentTriggerEvent:
        """Record a triggered event."""
        session = SessionLocal()
        try:
            event = AgentTriggerEvent(
                trigger_id=trigger_id,
                agent_id=agent_id,
                table_name=table_name,
                record_id=record_id,
                change_type=change_type,
                matched_conditions=matched_conditions,
                agent_executed=False,
                created_at=datetime.utcnow(),
            )
            session.add(event)
            session.commit()
            session.refresh(event)
            session.expunge(event)
            return event
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def mark_execution_started(self, event_id: UUID | str) -> None:
        """Mark that agent execution has started."""
        session = SessionLocal()
        try:
            event = session.query(AgentTriggerEvent).filter(AgentTriggerEvent.id == event_id).first()
            if event:
                event.agent_executed = True
                event.execution_started_at = datetime.utcnow()
                session.commit()
        finally:
            session.close()

    def mark_execution_completed(
        self,
        event_id: UUID | str,
        error: str | None = None,
    ) -> None:
        """Mark that agent execution has completed."""
        session = SessionLocal()
        try:
            event = session.query(AgentTriggerEvent).filter(AgentTriggerEvent.id == event_id).first()
            if event:
                event.execution_completed_at = datetime.utcnow()
                if error:
                    event.execution_error = error[:1000]  # Truncate long errors
                session.commit()
        finally:
            session.close()

    def get_recent_events(
        self,
        agent_id: UUID | str | None = None,
        simulation_id: UUID | str | None = None,  # noqa: ARG002 - reserved for future use
        limit: int = 50,
    ) -> list[AgentTriggerEvent]:
        """Get recent trigger events."""
        session = SessionLocal()
        try:
            query = session.query(AgentTriggerEvent)
            if agent_id:
                query = query.filter(AgentTriggerEvent.agent_id == agent_id)
            # TODO(byron): Add simulation filtering when needed (requires join with triggers)  # noqa: TD003
            events = query.order_by(AgentTriggerEvent.created_at.desc()).limit(limit).all()
            for e in events:
                session.expunge(e)
            return events
        finally:
            session.close()


class SimulationConfigService:
    """Service for managing simulation execution state."""

    def get_simulation(self, simulation_id: UUID | str) -> Simulation:
        """Get simulation by ID."""
        session = SessionLocal()
        try:
            simulation = session.query(Simulation).filter(Simulation.id == simulation_id).first()
            if not simulation:
                msg = f"Simulation {simulation_id} not found"
                raise ValueError(msg)
            session.expunge(simulation)
            return simulation
        finally:
            session.close()

    def pause_simulation(self, simulation_id: UUID | str) -> Simulation:
        """Pause a simulation (agents won't be triggered)."""
        session = SessionLocal()
        try:
            simulation = session.query(Simulation).filter(Simulation.id == simulation_id).first()
            if not simulation:
                msg = f"Simulation {simulation_id} not found"
                raise ValueError(msg)
            simulation.is_paused = True
            session.commit()
            session.refresh(simulation)
            session.expunge(simulation)
            return simulation
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def resume_simulation(self, simulation_id: UUID | str) -> Simulation:
        """Resume a paused simulation."""
        session = SessionLocal()
        try:
            simulation = session.query(Simulation).filter(Simulation.id == simulation_id).first()
            if not simulation:
                msg = f"Simulation {simulation_id} not found"
                raise ValueError(msg)
            simulation.is_paused = False
            session.commit()
            session.refresh(simulation)
            session.expunge(simulation)
            return simulation
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def is_paused(self, simulation_id: UUID | str) -> bool:
        """Check if a simulation is paused."""
        simulation = self.get_simulation(simulation_id)
        return simulation.is_paused


class EventMatcherService:
    """Service for matching events against trigger conditions."""

    def matches_conditions(self, record_data: dict, conditions: dict | None) -> bool:
        """Check if record data matches subscription conditions.

        Simple equality matching for now. Can be extended with operators later.
        """
        if not conditions:
            return True

        for key, expected in conditions.items():
            if key not in record_data:
                return False

            actual = record_data[key]

            # Convert to strings for comparison (handles UUIDs and other types)
            if str(actual) != str(expected):
                return False

        return True
