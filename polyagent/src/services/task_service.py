from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import selectinload

from src.database import SessionLocal
from src.models import AgentTask, Task
from src.services.transaction_service import TransactionService


class TaskService:
    def __init__(self) -> None:
        self.transaction_service = TransactionService()

    def create_task(
        self,
        simulation_id: UUID | str,
        created_by_principal_id: UUID | str,
        description: str,
        reward_dollars: Decimal,
        deadline: datetime,
    ) -> Task:
        session = SessionLocal()
        try:
            task = Task(
                simulation_id=simulation_id,
                created_by_principal_id=created_by_principal_id,
                description=description,
                reward_dollars=reward_dollars,
                deadline=deadline,
                created_at=datetime.utcnow(),
            )
            session.add(task)
            session.commit()
            # Re-query with eager loading to avoid detached instance issues
            task = (
                session.query(Task).options(selectinload(Task.agent_tasks)).filter(Task.id == task.id).first()
            )
            session.expunge(task)
            return task
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_tasks(
        self,
        *,
        status: str | None = None,
        is_completed: bool | None = None,
        has_deadline_passed: bool | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Task]:
        """
        Get tasks with optional filters.

        Args:
            status: Filter by computed status ('available', 'closed', 'expired').
                   This is a convenience filter that sets is_completed and has_deadline_passed.
            is_completed: Filter by is_completed flag (True/False).
            has_deadline_passed: Filter by whether deadline has passed (True/False).
            limit: Maximum number of tasks to return (default 20).
            offset: Number of tasks to skip (default 0).

        Returns:
            List of tasks matching the filters.
        """
        session = SessionLocal()
        try:
            now = datetime.utcnow()

            # Handle status filter by converting to underlying filters
            if status == "available":
                is_completed = False
                has_deadline_passed = False
            elif status == "closed":
                is_completed = True
            elif status == "expired":
                is_completed = False
                has_deadline_passed = True

            query = session.query(Task).options(selectinload(Task.agent_tasks))

            if is_completed is not None:
                query = query.filter(Task.is_completed == is_completed)

            if has_deadline_passed is not None:
                if has_deadline_passed:
                    query = query.filter(Task.deadline <= now)
                else:
                    query = query.filter(Task.deadline > now)

            tasks = query.order_by(Task.id).offset(offset).limit(limit).all()
            for task in tasks:
                session.expunge(task)
            return tasks
        finally:
            session.close()

    def get_available_tasks(self) -> list[Task]:
        """Get tasks that are not completed and deadline has not passed."""
        return self.get_tasks(status="available")

    def get_agent_tasks(self, agent_id: UUID | str) -> list[AgentTask]:
        """Get all AgentTask records for an agent."""
        session = SessionLocal()
        try:
            agent_tasks = (
                session.query(AgentTask)
                .options(selectinload(AgentTask.task))
                .filter(AgentTask.agent_id == agent_id)
                .all()
            )
            for at in agent_tasks:
                session.expunge(at)
            return agent_tasks
        finally:
            session.close()

    def accept_task(self, task_id: UUID | str, agent_id: UUID | str) -> AgentTask:
        # Terminal statuses that allow re-accepting the task
        terminal_statuses = {"accepted", "denied", "not_selected", "abandoned", "late"}

        session = SessionLocal()
        try:
            # Check if agent has an active (non-terminal) AgentTask for this task
            existing = (
                session.query(AgentTask)
                .filter(
                    AgentTask.task_id == task_id,
                    AgentTask.agent_id == agent_id,
                    AgentTask.status.not_in(terminal_statuses),
                )
                .first()
            )
            if existing:
                msg = (
                    f"You already have an active AgentTask for task {task_id} "
                    f"(AgentTask {existing.id}, status: {existing.status})"
                )
                raise ValueError(msg)

            agent_task = AgentTask(
                task_id=task_id, agent_id=agent_id, status="in_progress", created_at=datetime.utcnow()
            )
            session.add(agent_task)
            session.commit()
            # Re-query with eager loading
            agent_task = (
                session.query(AgentTask)
                .options(selectinload(AgentTask.task))
                .filter(AgentTask.id == agent_task.id)
                .first()
            )
            session.expunge(agent_task)
            return agent_task
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def submit_task(self, agent_task_id: UUID | str, result: str) -> AgentTask:
        session = SessionLocal()
        try:
            agent_task = (
                session.query(AgentTask)
                .options(selectinload(AgentTask.task))
                .filter(AgentTask.id == agent_task_id)
                .first()
            )

            if not agent_task:
                msg = f"AgentTask {agent_task_id} not found"
                raise ValueError(msg)

            if agent_task.status != "in_progress":
                msg = (
                    f"Cannot submit: AgentTask {agent_task_id} has status '{agent_task.status}' "
                    "(must be 'in_progress')"
                )
                raise ValueError(msg)

            task = agent_task.task
            if not task:
                msg = f"Task {agent_task.task_id} not found"
                raise ValueError(msg)

            now = datetime.utcnow()

            if task.is_completed:
                # Task already closed - another submission was accepted
                agent_task.result = result
                agent_task.status = "not_selected"
                agent_task.submitted_at = now
                session.commit()
                session.refresh(agent_task)
                session.expunge(agent_task)
                return agent_task

            if now > task.deadline:
                # Submission is past deadline - mark as late
                agent_task.result = result
                agent_task.status = "late"
                agent_task.submitted_at = now
                session.commit()
                session.refresh(agent_task)
                session.expunge(agent_task)
                return agent_task

            agent_task.result = result
            agent_task.status = "submitted"
            agent_task.submitted_at = now
            session.commit()
            session.refresh(agent_task)
            session.expunge(agent_task)
            return agent_task
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def abandon_task(self, agent_task_id: UUID | str) -> AgentTask:
        session = SessionLocal()
        try:
            agent_task = (
                session.query(AgentTask)
                .options(selectinload(AgentTask.task))
                .filter(AgentTask.id == agent_task_id)
                .first()
            )

            if not agent_task:
                msg = f"AgentTask {agent_task_id} not found"
                raise ValueError(msg)

            agent_task.status = "abandoned"
            session.commit()
            session.refresh(agent_task)
            session.expunge(agent_task)
            return agent_task
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_next_pending_submission(self, task_id: UUID | str) -> AgentTask | None:
        session = SessionLocal()
        try:
            task = session.query(Task).filter(Task.id == task_id).first()
            if not task:
                return None

            if datetime.utcnow() > task.deadline:
                return None

            agent_task = (
                session.query(AgentTask)
                .options(selectinload(AgentTask.task))
                .filter(AgentTask.task_id == task_id, AgentTask.status == "submitted")
                .order_by(AgentTask.submitted_at)
                .first()
            )
            if agent_task:
                session.expunge(agent_task)
            return agent_task
        finally:
            session.close()

    def accept_submission(self, agent_task_id: UUID | str) -> AgentTask:
        session = SessionLocal()
        try:
            agent_task = (
                session.query(AgentTask)
                .options(selectinload(AgentTask.task))
                .filter(AgentTask.id == agent_task_id)
                .first()
            )

            if not agent_task:
                msg = f"AgentTask {agent_task_id} not found"
                raise ValueError(msg)

            agent_task.status = "accepted"

            task = agent_task.task
            task.is_completed = True
            task.closed_at = datetime.utcnow()

            # Mark other submitted AgentTasks as not_selected (not explicitly denied)
            other_submissions = (
                session.query(AgentTask)
                .filter(
                    AgentTask.task_id == task.id, AgentTask.id != agent_task_id, AgentTask.status == "submitted"
                )
                .all()
            )
            for submission in other_submissions:
                submission.status = "not_selected"

            session.commit()

            self.transaction_service.grant_dollars(
                to_agent_id=agent_task.agent_id,
                amount=task.reward_dollars,
                reason="task_reward",
                reference_id=task.id,
            )

            session.refresh(agent_task)
            session.expunge(agent_task)
            return agent_task
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def deny_submission(self, agent_task_id: UUID | str) -> AgentTask:
        session = SessionLocal()
        try:
            agent_task = (
                session.query(AgentTask)
                .options(selectinload(AgentTask.task))
                .filter(AgentTask.id == agent_task_id)
                .first()
            )

            if not agent_task:
                msg = f"AgentTask {agent_task_id} not found"
                raise ValueError(msg)

            agent_task.status = "denied"
            session.commit()
            session.refresh(agent_task)
            session.expunge(agent_task)
            return agent_task
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
