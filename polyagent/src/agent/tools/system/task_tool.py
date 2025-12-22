import json
from typing import Annotated

from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolCallId, tool
from langgraph.types import Command

from src.database import SessionLocal
from src.models import Agent, AgentTask, Task
from src.schemas import AgentTaskStatus, TaskStatus
from src.services.task_service import TaskService


def _serialize_task(task: Task) -> dict:
    """Serialize a Task to a dict."""
    status = TaskStatus(task.status)
    return {
        "id": str(task.id),
        "description": task.description,
        "reward_dollars": str(task.reward_dollars),
        "deadline": task.deadline.isoformat(),
        "status": status.value,
        "status_description": status.description,
        "is_completed": task.is_completed,
        "created_at": task.created_at.isoformat(),
        "closed_at": task.closed_at.isoformat() if task.closed_at else None,
        "agent_tasks": [
            {
                "agent_id": str(at.agent_id),
                "status": at.status,
                "status_description": AgentTaskStatus(at.status).description,
            }
            for at in task.agent_tasks
        ],
    }


def _serialize_agent_task(at: AgentTask) -> dict:
    """Serialize an AgentTask to a dict."""
    status = AgentTaskStatus(at.status)
    return {
        "id": str(at.id),
        "task_id": str(at.task_id),
        "agent_id": str(at.agent_id),
        "status": status.value,
        "status_description": status.description,
        "is_terminal": status.is_terminal,
        "result": at.result,
        "created_at": at.created_at.isoformat(),
        "submitted_at": at.submitted_at.isoformat() if at.submitted_at else None,
        "task": {
            "id": str(at.task.id),
            "description": at.task.description,
            "reward_dollars": str(at.task.reward_dollars),
            "deadline": at.task.deadline.isoformat(),
            "is_completed": at.task.is_completed,
        },
    }


def create_tools(principal_id: str) -> list:  # noqa: C901
    """Create task tools for a principal."""
    # Get agent_id from principal_id for operations that need it
    session = SessionLocal()
    try:
        agent = session.query(Agent).filter(Agent.principal_id == principal_id).first()
        agent_id = agent.id if agent else None
    finally:
        session.close()

    service = TaskService()

    @tool("get_tasks", description="Get tasks with optional filters for status, completion, and deadline.")
    def get_tasks(
        status: str | None = None,
        is_completed: bool | None = None,  # noqa: FBT001
        has_deadline_passed: bool | None = None,  # noqa: FBT001
        limit: int = 20,
        offset: int = 0,
    ) -> dict:
        """Query tasks with filters."""
        tasks = service.get_tasks(
            status=status,
            is_completed=is_completed,
            has_deadline_passed=has_deadline_passed,
            limit=limit,
            offset=offset,
        )
        return {
            "success": True,
            "count": len(tasks),
            "tasks": [_serialize_task(t) for t in tasks],
            "filters": {
                "status": status,
                "is_completed": is_completed,
                "has_deadline_passed": has_deadline_passed,
                "limit": limit,
                "offset": offset,
            },
        }

    @tool("get_available_tasks", description="Get all available tasks that can be accepted.")
    def get_available_tasks() -> dict:
        """List tasks available for acceptance."""
        return get_tasks.invoke({"status": "available"})

    @tool("get_my_tasks", description="Get all tasks you have accepted and their current status.")
    def get_my_tasks() -> dict:
        """List your accepted tasks."""
        agent_tasks = service.get_agent_tasks(agent_id)
        return {
            "success": True,
            "count": len(agent_tasks),
            "agent_tasks": [_serialize_agent_task(at) for at in agent_tasks],
        }

    @tool("accept_task", description="Accept a task to work on. Reserves the task for you.")
    def accept_task(
        task_id: str,
        tool_call_id: Annotated[str, InjectedToolCallId],
    ) -> Command | dict:
        """Accept a task by ID. Updates current_agent_task_id in state on success."""
        try:
            agent_task = service.accept_task(task_id, agent_id)
            result = {
                "success": True,
                "agent_task": _serialize_agent_task(agent_task),
            }
            return Command(
                update={
                    "current_agent_task_id": str(agent_task.id),
                    "messages": [ToolMessage(json.dumps(result), tool_call_id=tool_call_id)],
                }
            )
        except Exception as e:  # noqa: BLE001
            error_msg = str(e)
            if "not found" in error_msg.lower():
                error_msg = f"{error_msg}. Use get_available_tasks to see current tasks."
            elif "already have" in error_msg.lower():
                error_msg = f"{error_msg}. Use get_my_tasks to see your active tasks."
            return {"success": False, "error": error_msg}

    @tool("submit_task", description="Submit completed work for a task you accepted.")
    def submit_task(
        agent_task_id: str,
        result: str,
        tool_call_id: Annotated[str, InjectedToolCallId],
    ) -> Command | dict:
        """Submit work for evaluation. Clears current_agent_task_id in state on success."""
        try:
            agent_task = service.submit_task(agent_task_id, result)
            response = {
                "success": True,
                "agent_task": _serialize_agent_task(agent_task),
            }
            return Command(
                update={
                    "current_agent_task_id": None,
                    "messages": [ToolMessage(json.dumps(response), tool_call_id=tool_call_id)],
                }
            )
        except Exception as e:  # noqa: BLE001
            error_msg = str(e)
            if "not found" in error_msg.lower():
                error_msg = f"{error_msg}. Use get_my_tasks to see your accepted tasks."
            return {"success": False, "error": error_msg}

    @tool("abandon_task", description="Abandon a task you're working on.")
    def abandon_task(
        agent_task_id: str,
        tool_call_id: Annotated[str, InjectedToolCallId],
    ) -> Command | dict:
        """Give up on a task. Clears current_agent_task_id in state on success."""
        try:
            agent_task = service.abandon_task(agent_task_id)
            result = {
                "success": True,
                "agent_task": _serialize_agent_task(agent_task),
            }
            return Command(
                update={
                    "current_agent_task_id": None,
                    "messages": [ToolMessage(json.dumps(result), tool_call_id=tool_call_id)],
                }
            )
        except Exception as e:  # noqa: BLE001
            error_msg = str(e)
            if "not found" in error_msg.lower():
                error_msg = f"{error_msg}. Use get_my_tasks to see your accepted tasks."
            return {"success": False, "error": error_msg}

    return [get_tasks, get_available_tasks, get_my_tasks, accept_task, submit_task, abandon_task]
