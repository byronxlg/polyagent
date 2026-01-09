"""Agent lifecycle helpers for tracking execution state."""

import logging
from datetime import datetime

from sqlalchemy.orm.attributes import flag_modified

from src.database import SessionLocal
from src.models import Agent

logger = logging.getLogger(__name__)


def before_agent(agent_id: int) -> None:
    """Set is_running=True before agent execution starts."""
    session = SessionLocal()
    try:
        agent = session.query(Agent).filter(Agent.id == agent_id).first()
        if agent:
            agent.is_running = True
            session.commit()
            logger.debug(f"Agent {agent_id} is_running set to True")
    finally:
        session.close()


def after_agent(agent_id: int, final_message: str | None = None) -> None:
    """Set is_running=False and capture final message to memory after agent execution completes.

    Args:
        agent_id: ID of the agent that just completed execution
        final_message: The agent's final text output to store in memory for future runs
    """
    session = SessionLocal()
    try:
        agent = session.query(Agent).filter(Agent.id == agent_id).first()
        if agent:
            agent.is_running = False

            # Capture final message to memory if provided
            if final_message:
                if agent.memory_json is None:
                    agent.memory_json = {}

                agent.memory_json["last_run_reflection"] = final_message
                agent.memory_json["last_run_timestamp"] = datetime.utcnow().isoformat()

                # Mark as modified so SQLAlchemy detects the JSONB change
                flag_modified(agent, "memory_json")
                logger.info(f"Agent {agent_id} final message captured to memory: {final_message[:100]}...")

            session.commit()
            logger.debug(f"Agent {agent_id} is_running set to False")
    finally:
        session.close()
