"""Service for managing agent trigger subscriptions and simulation configuration."""

from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from src.database import SessionLocal
from src.models import Agent, AgentTrigger, AgentTriggerEvent, Simulation, SimulationConfig
from src.services.trigger_constants import CHANGE_TYPES, WATCHABLE_TABLES


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
        if table_name not in WATCHABLE_TABLES:
            raise ValueError(f"Invalid table_name. Choose from: {WATCHABLE_TABLES}")
        if change_type not in CHANGE_TYPES:
            raise ValueError(f"Invalid change_type. Choose from: {CHANGE_TYPES}")

        session = SessionLocal()
        try:
            # Get agent to find simulation_id
            agent = session.query(Agent).filter(Agent.id == agent_id).first()
            if not agent:
                raise ValueError(f"Agent {agent_id} not found")

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
                raise ValueError(
                    f"Duplicate trigger exists (id={existing.id}). "
                    "Deactivate it first or use a different table/change_type."
                )

            trigger = AgentTrigger(
                agent_id=agent_id,
                simulation_id=agent.simulation_id,
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
        simulation_id: UUID | str | None = None,
        is_active: bool | None = True,
    ) -> list[AgentTrigger]:
        """List trigger subscriptions with optional filters."""
        session = SessionLocal()
        try:
            query = session.query(AgentTrigger)
            if agent_id:
                query = query.filter(AgentTrigger.agent_id == agent_id)
            if simulation_id:
                query = query.filter(AgentTrigger.simulation_id == simulation_id)
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
        is_active: bool | None = None,
        conditions: dict | None = None,
    ) -> AgentTrigger:
        """Update subscription properties."""
        session = SessionLocal()
        try:
            trigger = session.query(AgentTrigger).filter(AgentTrigger.id == subscription_id).first()
            if not trigger:
                raise ValueError(f"Trigger {subscription_id} not found")

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
        """Get all active triggers for a simulation."""
        session = SessionLocal()
        try:
            triggers = (
                session.query(AgentTrigger)
                .filter(
                    AgentTrigger.simulation_id == simulation_id,
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

    def record_trigger_event(
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
        simulation_id: UUID | str | None = None,
        limit: int = 50,
    ) -> list[AgentTriggerEvent]:
        """Get recent trigger events."""
        session = SessionLocal()
        try:
            query = session.query(AgentTriggerEvent)
            if agent_id:
                query = query.filter(AgentTriggerEvent.agent_id == agent_id)
            # For simulation filtering, we'd need to join with triggers
            events = query.order_by(AgentTriggerEvent.created_at.desc()).limit(limit).all()
            for e in events:
                session.expunge(e)
            return events
        finally:
            session.close()


class SimulationConfigService:
    """Service for managing simulation execution state."""

    def get_or_create_config(self, simulation_id: UUID | str) -> SimulationConfig:
        """Get simulation config, creating if doesn't exist."""
        session = SessionLocal()
        try:
            config = (
                session.query(SimulationConfig)
                .filter(SimulationConfig.simulation_id == simulation_id)
                .first()
            )
            if not config:
                # Verify simulation exists
                simulation = session.query(Simulation).filter(Simulation.id == simulation_id).first()
                if not simulation:
                    raise ValueError(f"Simulation {simulation_id} not found")

                config = SimulationConfig(
                    simulation_id=simulation_id,
                    is_paused=False,
                    config_json={},
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
                session.add(config)
                session.commit()
                session.refresh(config)
            session.expunge(config)
            return config
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def pause_simulation(self, simulation_id: UUID | str) -> SimulationConfig:
        """Pause a simulation (agents won't be triggered)."""
        session = SessionLocal()
        try:
            config = self._get_or_create_config_in_session(session, simulation_id)
            config.is_paused = True
            config.updated_at = datetime.utcnow()
            session.commit()
            session.refresh(config)
            session.expunge(config)
            return config
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def resume_simulation(self, simulation_id: UUID | str) -> SimulationConfig:
        """Resume a paused simulation."""
        session = SessionLocal()
        try:
            config = self._get_or_create_config_in_session(session, simulation_id)
            config.is_paused = False
            config.updated_at = datetime.utcnow()
            session.commit()
            session.refresh(config)
            session.expunge(config)
            return config
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def is_paused(self, simulation_id: UUID | str) -> bool:
        """Check if a simulation is paused."""
        config = self.get_or_create_config(simulation_id)
        return config.is_paused

    def _get_or_create_config_in_session(
        self, session: Session, simulation_id: UUID | str
    ) -> SimulationConfig:
        """Get or create config within an existing session."""
        config = (
            session.query(SimulationConfig)
            .filter(SimulationConfig.simulation_id == simulation_id)
            .first()
        )
        if not config:
            simulation = session.query(Simulation).filter(Simulation.id == simulation_id).first()
            if not simulation:
                raise ValueError(f"Simulation {simulation_id} not found")

            config = SimulationConfig(
                simulation_id=simulation_id,
                is_paused=False,
                config_json={},
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            session.add(config)
            session.flush()
        return config


class EventMatcherService:
    """Service for matching events against trigger conditions."""

    def matches_conditions(self, record_data: dict, conditions: dict | None) -> bool:
        """Check if record data matches subscription conditions.

        Simple equality matching for now. Can be extended with operators later.
        """
        if not conditions:
            return True

        for key, expected_value in conditions.items():
            if key not in record_data:
                return False

            actual_value = record_data[key]

            # Handle UUID comparison
            if hasattr(actual_value, "hex"):
                actual_value = str(actual_value)
            if hasattr(expected_value, "hex"):
                expected_value = str(expected_value)

            # Simple string comparison
            if str(actual_value) != str(expected_value):
                return False

        return True
