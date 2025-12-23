"""Trigger worker process for event-driven agent execution.

This worker polls the database for changes in watched tables (tasks, messages,
agent_tasks, transactions), matches them against agent trigger subscriptions,
and executes agents whose triggers match.
"""

import logging
import signal
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from src.agent.agent import Agent as AgentExecutor
from src.database import SessionLocal
from src.models import Agent, AgentTask, AgentTrigger, Message, Simulation, Task, Transaction
from src.schemas import TriggerTableName
from src.services.trigger_service import (
    EventMatcherService,
    SimulationConfigService,
    TriggerEventService,
    TriggerService,
)
from src.worker.config import WorkerConfig

logger = logging.getLogger(__name__)


def _build_table_model_map() -> dict:
    """Build mapping from table names to model classes dynamically from TriggerTableName enum."""
    # Map enum values to their corresponding model classes
    model_map = {
        TriggerTableName.TASKS.value: Task,
        TriggerTableName.MESSAGES.value: Message,
        TriggerTableName.AGENT_TASKS.value: AgentTask,
        TriggerTableName.TRANSACTIONS.value: Transaction,
    }
    # Verify all enum values have mappings
    for table_name in TriggerTableName:
        if table_name.value not in model_map:
            msg = f"Missing model mapping for table: {table_name.value}"
            raise RuntimeError(msg)
    return model_map


TABLE_MODEL_MAP = _build_table_model_map()


class TriggerWorker:
    """Worker process for event-driven agent triggering.

    Polls the database for changes, matches them against trigger subscriptions,
    and executes agents that should respond.
    """

    def __init__(self, config: WorkerConfig | None = None) -> None:
        self.config = config or WorkerConfig()
        self.shutdown_flag = False
        self.last_poll_time: datetime | None = None

        # Services
        self.trigger_service = TriggerService()
        self.event_service = TriggerEventService()
        self.config_service = SimulationConfigService()
        self.matcher_service = EventMatcherService()

        # Thread pool for concurrent agent execution
        self.executor = ThreadPoolExecutor(max_workers=4)

        # Register signal handlers
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)

    def _handle_shutdown(self, signum: int, frame: Any) -> None:
        """Handle shutdown signals gracefully."""
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.shutdown_flag = True

    def start(self) -> None:
        """Start the worker (blocking)."""
        logger.info(f"Starting trigger worker with {self.config.poll_interval}s poll interval")

        # Initialize last poll time to now minus one interval
        self.last_poll_time = datetime.utcnow() - timedelta(seconds=self.config.poll_interval)

        try:
            while not self.shutdown_flag:
                try:
                    self._poll_cycle()
                except Exception as e:
                    logger.error(f"Error in poll cycle: {e}", exc_info=True)
                    time.sleep(self.config.error_backoff)
                    continue

                time.sleep(self.config.poll_interval)
        finally:
            self._cleanup()

        logger.info("Worker shutdown complete")

    def _cleanup(self) -> None:
        """Clean up resources."""
        logger.info("Cleaning up worker resources...")
        self.executor.shutdown(wait=True)

    def _poll_cycle(self) -> None:
        """Execute one poll cycle: detect changes, match triggers, execute agents."""
        current_time = datetime.utcnow()

        session = SessionLocal()
        try:
            # Get all active simulations that are not paused
            simulations = session.query(Simulation).all()
            active_sim_ids = []

            for sim in simulations:
                if not self.config_service.is_paused(sim.id):
                    active_sim_ids.append(sim.id)

            if not active_sim_ids:
                self.last_poll_time = current_time
                return

            # Get all active triggers for active simulations
            all_triggers = []
            for sim_id in active_sim_ids:
                triggers = self.trigger_service.get_active_triggers_for_simulation(sim_id)
                all_triggers.extend(triggers)

            if not all_triggers:
                self.last_poll_time = current_time
                return

            # Group triggers by table name for efficient querying
            triggers_by_table: dict[str, list[AgentTrigger]] = defaultdict(list)
            for trigger in all_triggers:
                triggers_by_table[trigger.table_name].append(trigger)

            # Detect changes in each watched table
            agents_to_trigger: list[tuple[UUID, AgentTrigger, dict]] = []

            for table_name, table_triggers in triggers_by_table.items():
                changes = self._detect_changes(session, table_name, self.last_poll_time)

                for change in changes:
                    for trigger in table_triggers:
                        if self._matches_trigger(change, trigger):
                            agents_to_trigger.append((trigger.agent_id, trigger, change))

            # Deduplicate: only trigger each agent once per cycle
            seen_agents: set[UUID] = set()
            unique_triggers: list[tuple[UUID, AgentTrigger, dict]] = []

            for agent_id, trigger, change in agents_to_trigger:
                if agent_id not in seen_agents:
                    seen_agents.add(agent_id)
                    unique_triggers.append((agent_id, trigger, change))

            # Execute agents concurrently
            if unique_triggers:
                logger.info(f"Triggering {len(unique_triggers)} agents")
                self._execute_agents(unique_triggers)

        finally:
            session.close()
            self.last_poll_time = current_time

    def _detect_changes(
        self,
        session: Any,
        table_name: str,
        since: datetime | None,
    ) -> list[dict]:
        """Detect changes in a table since the last poll.

        Returns a list of change records with their data.
        """
        if table_name not in TABLE_MODEL_MAP:
            return []

        model_class = TABLE_MODEL_MAP[table_name]
        changes = []

        # Query for records created since last poll (INSERTs)
        query = session.query(model_class)
        if since and hasattr(model_class, "created_at"):
            query = query.filter(model_class.created_at >= since)

        records = query.all()

        for record in records:
            change_data = self._record_to_dict(record, table_name)
            change_data["_change_type"] = "INSERT"
            changes.append(change_data)

        # For UPDATE detection, we'd need updated_at columns on tables
        # This is a simplification - we only detect INSERTs for now
        # TODO: Add UPDATE detection when updated_at columns are added

        return changes

    def _record_to_dict(self, record: Any, table_name: str) -> dict:
        """Convert a database record to a dict for condition matching."""
        data = {
            "id": record.id,
            "_table_name": table_name,
        }

        # Add table-specific fields
        if table_name == "tasks":
            data.update(
                {
                    "simulation_id": record.simulation_id,
                    "description": record.description,
                    "reward_dollars": str(record.reward_dollars),
                    "is_completed": record.is_completed,
                    "status": record.status,
                    "created_at": record.created_at,
                }
            )
        elif table_name == "messages":
            data.update(
                {
                    "from_principal_id": record.from_principal_id,
                    "to_principal_id": record.to_principal_id,
                    "content": record.content[:100] if record.content else None,
                    "sent_at": record.sent_at,
                }
            )
        elif table_name == "agent_tasks":
            data.update(
                {
                    "task_id": record.task_id,
                    "agent_id": record.agent_id,
                    "status": record.status,
                    "created_at": record.created_at,
                    "submitted_at": record.submitted_at,
                }
            )
            # Add simulation_id from the task
            if record.task:
                data["simulation_id"] = record.task.simulation_id
        elif table_name == "transactions":
            data.update(
                {
                    "from_principal_id": record.from_principal_id,
                    "to_principal_id": record.to_principal_id,
                    "amount": str(record.amount),
                    "reason": record.reason,
                    "timestamp": record.timestamp,
                }
            )

        return data

    def _matches_trigger(self, change: dict, trigger: AgentTrigger) -> bool:
        """Check if a change matches a trigger's conditions."""
        # Check change type
        if change.get("_change_type") != trigger.change_type:
            return False

        # Check simulation scope - the change must be in the same simulation as the trigger
        change_sim_id = change.get("simulation_id")
        if change_sim_id and str(change_sim_id) != str(trigger.simulation_id):
            return False

        # Check conditions
        if trigger.conditions:
            return self.matcher_service.matches_conditions(change, trigger.conditions)

        return True

    def _execute_agents(
        self,
        triggers: list[tuple[UUID, AgentTrigger, dict]],
    ) -> None:
        """Execute agents for matched triggers."""
        futures = []

        for agent_id, trigger, change in triggers:
            # Check if agent is already running
            session = SessionLocal()
            try:
                agent = session.query(Agent).filter(Agent.id == agent_id).first()
                if not agent:
                    logger.warning(f"Agent {agent_id} not found, skipping")
                    continue
                if agent.is_running:
                    logger.info(f"Agent {agent_id} already running, skipping")
                    continue
            finally:
                session.close()

            # Record trigger event
            event = self.event_service.record_trigger_event(
                trigger_id=trigger.id,
                agent_id=agent_id,
                table_name=change.get("_table_name", "unknown"),
                record_id=change.get("id"),
                change_type=change.get("_change_type", "unknown"),
                matched_conditions=trigger.conditions,
            )

            # Update trigger last_triggered_at
            self.trigger_service.update_last_triggered(trigger.id)

            # Submit agent execution to thread pool
            future = self.executor.submit(
                self._execute_single_agent,
                agent_id,
                event.id,
            )
            futures.append(future)

        # Wait for all executions to complete
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                logger.error(f"Agent execution failed: {e}", exc_info=True)

    def _execute_single_agent(self, agent_id: UUID, event_id: UUID) -> None:
        """Execute a single agent and update the event record."""
        logger.info(f"Executing agent {agent_id} for trigger event {event_id}")

        # Mark execution started
        self.event_service.mark_execution_started(event_id)

        try:
            executor = AgentExecutor(agent_id)
            result = executor.think()
            logger.info(f"Agent {agent_id} completed: {result[:100]}...")

            # Mark execution completed successfully
            self.event_service.mark_execution_completed(event_id)

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Agent {agent_id} execution failed: {error_msg}", exc_info=True)

            # Mark execution completed with error
            self.event_service.mark_execution_completed(event_id, error=error_msg)
