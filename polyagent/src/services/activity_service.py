from typing import Any
from uuid import UUID

from sqlalchemy import desc, literal, union_all
from sqlalchemy.orm import Session

from src.models import Agent, AgentModelUsage, AgentTask, AgentToolUsage, Message, Transaction


class ActivityService:
    """Service for fetching unified activity feed across all entity types."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_activity(  # noqa: C901, PLR0912
        self,
        *,
        limit: int = 30,
        offset: int = 0,
        agent_id: UUID | str | None = None,
        types: list[str] | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """Fetch unified activity feed combining all activity types."""
        valid_types = {"agent_task", "message", "transaction", "tool_usage", "model_usage"}
        types = list(valid_types) if types is None else [t for t in types if t in valid_types]

        if not types:
            return [], 0

        # Build subqueries for each type
        subqueries = []

        if "agent_task" in types:
            at_query = self.db.query(
                AgentTask.id.label("entity_id"),
                literal("agent_task").label("type"),
                AgentTask.created_at.label("timestamp"),
                AgentTask.agent_id.label("agent_id"),
            )
            if agent_id is not None:
                at_query = at_query.filter(AgentTask.agent_id == agent_id)
            subqueries.append(at_query)

        if "message" in types:
            # Join with Agent to convert from_principal_id to agent_id
            from_agent = Agent
            msg_query = self.db.query(
                Message.id.label("entity_id"),
                literal("message").label("type"),
                Message.sent_at.label("timestamp"),
                from_agent.id.label("agent_id"),
            ).join(from_agent, from_agent.principal_id == Message.from_principal_id)
            if agent_id is not None:
                # Need to check if agent is sender OR recipient
                # Join with Agent table twice to get both sender and recipient agent IDs
                to_agent = Agent.__table__.alias("to_agent")
                msg_query = msg_query.outerjoin(
                    to_agent, to_agent.c.principal_id == Message.to_principal_id
                ).filter((from_agent.id == agent_id) | (to_agent.c.id == agent_id))
            subqueries.append(msg_query)

        if "transaction" in types:
            # Join with Agent to convert from_principal_id to agent_id
            from_agent = Agent
            tx_query = self.db.query(
                Transaction.id.label("entity_id"),
                literal("transaction").label("type"),
                Transaction.timestamp.label("timestamp"),
                from_agent.id.label("agent_id"),
            ).outerjoin(from_agent, from_agent.principal_id == Transaction.from_principal_id)
            if agent_id is not None:
                # Need to check if agent is sender OR recipient
                to_agent = Agent.__table__.alias("to_agent")
                tx_query = tx_query.outerjoin(
                    to_agent, to_agent.c.principal_id == Transaction.to_principal_id
                ).filter((from_agent.id == agent_id) | (to_agent.c.id == agent_id))
            subqueries.append(tx_query)

        if "tool_usage" in types:
            tu_query = self.db.query(
                AgentToolUsage.id.label("entity_id"),
                literal("tool_usage").label("type"),
                AgentToolUsage.timestamp.label("timestamp"),
                AgentToolUsage.agent_id.label("agent_id"),
            )
            if agent_id is not None:
                tu_query = tu_query.filter(AgentToolUsage.agent_id == agent_id)
            subqueries.append(tu_query)

        if "model_usage" in types:
            mu_query = self.db.query(
                AgentModelUsage.id.label("entity_id"),
                literal("model_usage").label("type"),
                AgentModelUsage.timestamp.label("timestamp"),
                AgentModelUsage.agent_id.label("agent_id"),
            )
            if agent_id is not None:
                mu_query = mu_query.filter(AgentModelUsage.agent_id == agent_id)
            subqueries.append(mu_query)

        if not subqueries:
            return [], 0

        # Combine all subqueries with UNION ALL
        combined = union_all(*subqueries).subquery()

        # Get total count
        total = self.db.query(combined).count()

        # Get paginated results ordered by timestamp desc
        rows = self.db.query(combined).order_by(desc(combined.c.timestamp)).offset(offset).limit(limit).all()

        # Fetch full entity data for each row
        items = []
        for row in rows:
            entity_id = row.entity_id
            entity_type = row.type
            data = self._fetch_entity_data(entity_type, entity_id)
            if data:
                items.append(
                    {
                        "id": f"{entity_type[:2]}-{entity_id}",
                        "type": entity_type,
                        "timestamp": row.timestamp.isoformat() if row.timestamp else None,
                        "agent_id": row.agent_id,
                        "data": data,
                    }
                )

        return items, total

    def _fetch_entity_data(self, entity_type: str, entity_id: UUID | str) -> dict[str, Any] | None:  # noqa: C901
        """Fetch the full entity data for a given type and id."""
        if entity_type == "agent_task":
            entity = self.db.query(AgentTask).filter(AgentTask.id == entity_id).first()
            if entity:
                return {
                    "id": entity.id,
                    "task_id": entity.task_id,
                    "agent_id": entity.agent_id,
                    "status": entity.status,
                    "result": entity.result,
                    "created_at": entity.created_at.isoformat() if entity.created_at else None,
                    "submitted_at": entity.submitted_at.isoformat() if entity.submitted_at else None,
                }

        elif entity_type == "message":
            entity = self.db.query(Message).filter(Message.id == entity_id).first()
            if entity:
                # Convert principal_ids to agent_ids
                from_agent = self.db.query(Agent).filter(Agent.principal_id == entity.from_principal_id).first()
                to_agent = self.db.query(Agent).filter(Agent.principal_id == entity.to_principal_id).first()
                return {
                    "id": entity.id,
                    "from_agent_id": from_agent.id if from_agent else None,
                    "to_agent_id": to_agent.id if to_agent else None,
                    "content": entity.content,
                    "sent_at": entity.sent_at.isoformat() if entity.sent_at else None,
                    "received_at": entity.received_at.isoformat() if entity.received_at else None,
                }

        elif entity_type == "transaction":
            entity = self.db.query(Transaction).filter(Transaction.id == entity_id).first()
            if entity:
                # Convert principal_ids to agent_ids
                from_agent = (
                    self.db.query(Agent).filter(Agent.principal_id == entity.from_principal_id).first()
                    if entity.from_principal_id
                    else None
                )
                to_agent = (
                    self.db.query(Agent).filter(Agent.principal_id == entity.to_principal_id).first()
                    if entity.to_principal_id
                    else None
                )
                return {
                    "id": entity.id,
                    "from_agent_id": from_agent.id if from_agent else None,
                    "to_agent_id": to_agent.id if to_agent else None,
                    "amount": str(entity.amount),
                    "reason": entity.reason,
                    "reference_id": entity.reference_id,
                    "timestamp": entity.timestamp.isoformat() if entity.timestamp else None,
                }

        elif entity_type == "tool_usage":
            entity = self.db.query(AgentToolUsage).filter(AgentToolUsage.id == entity_id).first()
            if entity:
                return {
                    "id": entity.id,
                    "agent_id": entity.agent_id,
                    "server_name": entity.server_name,
                    "tool_name": entity.tool_name,
                    "input": entity.input,
                    "output": entity.output,
                    "timestamp": entity.timestamp.isoformat() if entity.timestamp else None,
                }

        elif entity_type == "model_usage":
            entity = self.db.query(AgentModelUsage).filter(AgentModelUsage.id == entity_id).first()
            if entity:
                return {
                    "id": entity.id,
                    "agent_id": entity.agent_id,
                    "model_id": entity.model_id,
                    "input_tokens": entity.input_tokens,
                    "output_tokens": entity.output_tokens,
                    "total_cost": str(entity.total_cost),
                    "input": entity.input,
                    "output": entity.output,
                    "timestamp": entity.timestamp.isoformat() if entity.timestamp else None,
                }

        return None
