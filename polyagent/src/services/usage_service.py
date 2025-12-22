from datetime import datetime
from uuid import UUID

from src.database import SessionLocal
from src.models import Agent, AgentModelUsage, AgentToolUsage, Tool, Transaction


class UsageService:
    def __init__(self) -> None:
        pass

    def get_model_usage(  # noqa: PLR0913
        self,
        agent_id: UUID | str,
        *,
        agent_task_id: UUID | str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[dict], dict]:
        """Get model usage records for an agent.

        Args:
            agent_id: The agent to get usage for
            agent_task_id: Filter by specific agent task
            since: Only include usage after this timestamp
            until: Only include usage before this timestamp
            limit: Maximum number of records to return
            offset: Number of records to skip

        Returns:
            Tuple of (usage records, summary stats)
        """
        session = SessionLocal()
        try:
            query = session.query(AgentModelUsage).filter(AgentModelUsage.agent_id == agent_id)

            if agent_task_id is not None:
                query = query.filter(AgentModelUsage.agent_task_id == agent_task_id)
            if since is not None:
                query = query.filter(AgentModelUsage.timestamp >= since)
            if until is not None:
                query = query.filter(AgentModelUsage.timestamp <= until)

            # Get total count before pagination
            total_count = query.count()

            # Get summary stats (on filtered but unpaginated query)
            all_filtered = query.all()
            total_cost = sum(float(u.total_cost) for u in all_filtered)
            total_input_tokens = sum(u.input_tokens for u in all_filtered)
            total_output_tokens = sum(u.output_tokens for u in all_filtered)

            # Apply pagination
            usages = query.order_by(AgentModelUsage.timestamp.desc()).offset(offset).limit(limit).all()

            records = [
                {
                    "id": str(u.id),
                    "agent_task_id": str(u.agent_task_id) if u.agent_task_id else None,
                    "input_tokens": u.input_tokens,
                    "output_tokens": u.output_tokens,
                    "total_cost": str(u.total_cost),
                    "timestamp": u.timestamp.isoformat(),
                }
                for u in usages
            ]

            summary = {
                "total_count": total_count,
                "total_cost": f"{total_cost:.6f}",
                "total_input_tokens": total_input_tokens,
                "total_output_tokens": total_output_tokens,
            }

            return records, summary
        finally:
            session.close()

    def get_tool_usage(  # noqa: PLR0913
        self,
        agent_id: UUID | str,
        *,
        agent_task_id: UUID | str | None = None,
        tool_name: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[dict], dict]:
        """Get tool usage records for an agent.

        Args:
            agent_id: The agent to get usage for
            agent_task_id: Filter by specific agent task
            tool_name: Filter by specific tool name
            since: Only include usage after this timestamp
            until: Only include usage before this timestamp
            limit: Maximum number of records to return
            offset: Number of records to skip

        Returns:
            Tuple of (usage records, summary stats)
        """
        session = SessionLocal()
        try:
            query = session.query(AgentToolUsage).filter(AgentToolUsage.agent_id == agent_id)

            if agent_task_id is not None:
                query = query.filter(AgentToolUsage.agent_task_id == agent_task_id)
            if tool_name is not None:
                tool = session.query(Tool).filter(Tool.name == tool_name).first()
                if tool:
                    query = query.filter(AgentToolUsage.tool_id == tool.id)
                else:
                    # Tool not found, return empty results
                    return [], {"total_count": 0, "tools_used": {}}
            if since is not None:
                query = query.filter(AgentToolUsage.timestamp >= since)
            if until is not None:
                query = query.filter(AgentToolUsage.timestamp <= until)

            # Get total count before pagination
            total_count = query.count()

            # Get tool usage counts
            all_filtered = query.all()
            tool_ids = {u.tool_id for u in all_filtered}
            tools = {t.id: t.name for t in session.query(Tool).filter(Tool.id.in_(tool_ids)).all()}

            tools_used: dict[str, int] = {}
            for u in all_filtered:
                name = tools.get(u.tool_id, "unknown")
                tools_used[name] = tools_used.get(name, 0) + 1

            # Apply pagination
            usages = query.order_by(AgentToolUsage.timestamp.desc()).offset(offset).limit(limit).all()

            records = [
                {
                    "id": str(u.id),
                    "agent_task_id": str(u.agent_task_id) if u.agent_task_id else None,
                    "tool_name": tools.get(u.tool_id, "unknown"),
                    "input": u.input[:500] if u.input else None,
                    "output": u.output[:500] if u.output else None,
                    "timestamp": u.timestamp.isoformat(),
                }
                for u in usages
            ]

            summary = {
                "total_count": total_count,
                "tools_used": tools_used,
            }

            return records, summary
        finally:
            session.close()

    def get_transactions(  # noqa: PLR0913
        self,
        agent_id: UUID | str,
        *,
        direction: str | None = None,
        reason: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[dict], dict]:
        """Get transaction records for an agent.

        Args:
            agent_id: The agent to get transactions for
            direction: Filter by 'in' or 'out'
            reason: Filter by transaction reason (e.g., 'model_usage', 'task_reward')
            since: Only include transactions after this timestamp
            until: Only include transactions before this timestamp
            limit: Maximum number of records to return
            offset: Number of records to skip

        Returns:
            Tuple of (transaction records, summary stats)
        """
        session = SessionLocal()
        try:
            agent = session.query(Agent).filter(Agent.id == agent_id).first()
            if not agent:
                return [], {"total_count": 0, "total_in": "0", "total_out": "0", "net": "0"}

            principal_id = agent.principal_id

            query = session.query(Transaction).filter(
                (Transaction.from_principal_id == principal_id) | (Transaction.to_principal_id == principal_id)
            )

            if direction == "in":
                query = query.filter(Transaction.to_principal_id == principal_id)
            elif direction == "out":
                query = query.filter(Transaction.from_principal_id == principal_id)

            if reason is not None:
                query = query.filter(Transaction.reason == reason)
            if since is not None:
                query = query.filter(Transaction.timestamp >= since)
            if until is not None:
                query = query.filter(Transaction.timestamp <= until)

            # Get total count before pagination
            total_count = query.count()

            # Get summary stats
            all_filtered = query.all()
            total_in = sum(float(t.amount) for t in all_filtered if t.to_principal_id == principal_id)
            total_out = sum(float(t.amount) for t in all_filtered if t.from_principal_id == principal_id)

            # Count by reason
            reasons: dict[str, int] = {}
            for t in all_filtered:
                reasons[t.reason] = reasons.get(t.reason, 0) + 1

            # Apply pagination
            transactions = query.order_by(Transaction.timestamp.desc()).offset(offset).limit(limit).all()

            records = [
                {
                    "id": str(t.id),
                    "direction": "in" if t.to_principal_id == principal_id else "out",
                    "amount": str(t.amount),
                    "reason": t.reason,
                    "reference_id": str(t.reference_id) if t.reference_id else None,
                    "timestamp": t.timestamp.isoformat(),
                }
                for t in transactions
            ]

            summary = {
                "total_count": total_count,
                "total_in": f"{total_in:.6f}",
                "total_out": f"{total_out:.6f}",
                "net": f"{total_in - total_out:.6f}",
                "by_reason": reasons,
            }

            return records, summary
        finally:
            session.close()

    def get_task_cost_summary(self, agent_id: UUID | str, agent_task_id: UUID | str) -> dict:
        """Get a cost summary for a specific task.

        Returns total model costs and tool usage for the task.
        """
        session = SessionLocal()
        try:
            # Get model usage for this task
            model_usages = (
                session.query(AgentModelUsage)
                .filter(AgentModelUsage.agent_id == agent_id, AgentModelUsage.agent_task_id == agent_task_id)
                .all()
            )

            total_model_cost = sum(float(u.total_cost) for u in model_usages)
            total_input_tokens = sum(u.input_tokens for u in model_usages)
            total_output_tokens = sum(u.output_tokens for u in model_usages)

            # Get tool usage for this task
            tool_usages = (
                session.query(AgentToolUsage)
                .filter(AgentToolUsage.agent_id == agent_id, AgentToolUsage.agent_task_id == agent_task_id)
                .all()
            )

            tool_ids = {u.tool_id for u in tool_usages}
            tools = {t.id: t.name for t in session.query(Tool).filter(Tool.id.in_(tool_ids)).all()}

            tools_used: dict[str, int] = {}
            for u in tool_usages:
                name = tools.get(u.tool_id, "unknown")
                tools_used[name] = tools_used.get(name, 0) + 1

            return {
                "agent_task_id": str(agent_task_id),
                "model_calls": len(model_usages),
                "total_model_cost": f"{total_model_cost:.6f}",
                "total_input_tokens": total_input_tokens,
                "total_output_tokens": total_output_tokens,
                "tool_calls": len(tool_usages),
                "tools_used": tools_used,
            }
        finally:
            session.close()
