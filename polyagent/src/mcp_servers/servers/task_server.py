"""MCP server for task management tools."""

from fastmcp import FastMCP

from src.database import SessionLocal
from src.models import Agent, AgentTask, Task
from src.schemas import AgentTaskStatus, TaskStatus
from src.services.task_service import TaskService

mcp = FastMCP("task")


def _get_agent_id(principal_id: str) -> str | None:
    """Get agent_id from principal_id."""
    session = SessionLocal()
    try:
        agent = session.query(Agent).filter(Agent.principal_id == principal_id).first()
        return str(agent.id) if agent else None
    finally:
        session.close()


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


def _get_tasks_impl(
    status: str | None = None,
    is_completed: bool | None = None,
    has_deadline_passed: bool | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    """Internal implementation for getting tasks with filters."""
    service = TaskService()
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


@mcp.tool()
def get_tasks(
    principal_id: str,
    status: str | None = None,
    is_completed: bool | None = None,
    has_deadline_passed: bool | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    """Get tasks with optional filters for status, completion, and deadline.

    Args:
        principal_id: Your principal ID (injected by agent)
        status: Filter by status (available, closed, expired)
        is_completed: Filter by completion status
        has_deadline_passed: Filter by whether deadline has passed
        limit: Maximum number of tasks to return
        offset: Number of tasks to skip
    """
    return _get_tasks_impl(status, is_completed, has_deadline_passed, limit, offset)


@mcp.tool()
def get_available_tasks(principal_id: str) -> dict:
    """Get all available tasks that can be accepted.

    Args:
        principal_id: Your principal ID (injected by agent)
    """
    return _get_tasks_impl(status="available")


@mcp.tool()
def get_my_tasks(principal_id: str) -> dict:
    """Get all tasks you have accepted and their current status.

    Args:
        principal_id: Your principal ID (injected by agent)
    """
    agent_id = _get_agent_id(principal_id)
    if not agent_id:
        return {"success": False, "error": "Agent not found"}

    service = TaskService()
    agent_tasks = service.get_agent_tasks(agent_id)
    return {
        "success": True,
        "count": len(agent_tasks),
        "agent_tasks": [_serialize_agent_task(at) for at in agent_tasks],
    }


@mcp.tool()
def accept_task(principal_id: str, task_id: str) -> dict:
    """Accept a task to work on. Reserves the task for you.

    Args:
        principal_id: Your principal ID (injected by agent)
        task_id: The ID of the task to accept

    Returns:
        On success, includes agent_task_id for state tracking.
    """
    agent_id = _get_agent_id(principal_id)
    if not agent_id:
        return {"success": False, "error": "Agent not found"}

    service = TaskService()
    try:
        agent_task = service.accept_task(task_id, agent_id)
        return {
            "success": True,
            "agent_task": _serialize_agent_task(agent_task),
            "agent_task_id": str(agent_task.id),
        }
    except Exception as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            error_msg = f"{error_msg}. Use get_available_tasks to see current tasks."
        elif "already have" in error_msg.lower():
            error_msg = f"{error_msg}. Use get_my_tasks to see your active tasks."
        return {"success": False, "error": error_msg}


@mcp.tool()
def submit_task(principal_id: str, agent_task_id: str, result: str) -> dict:
    """Submit completed work for a task you accepted.

    Args:
        principal_id: Your principal ID (injected by agent)
        agent_task_id: The ID of the agent_task (from accept_task)
        result: Your work result to submit

    Returns:
        On success, includes clear_agent_task_id=True for state tracking.
    """
    service = TaskService()
    try:
        agent_task = service.submit_task(agent_task_id, result)
        return {
            "success": True,
            "agent_task": _serialize_agent_task(agent_task),
            "clear_agent_task_id": True,
        }
    except Exception as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            error_msg = f"{error_msg}. Use get_my_tasks to see your accepted tasks."
        return {"success": False, "error": error_msg}


@mcp.tool()
def abandon_task(principal_id: str, agent_task_id: str) -> dict:
    """Give up on a task you're working on.

    Args:
        principal_id: Your principal ID (injected by agent)
        agent_task_id: The ID of the agent_task to abandon

    Returns:
        On success, includes clear_agent_task_id=True for state tracking.
    """
    service = TaskService()
    try:
        agent_task = service.abandon_task(agent_task_id)
        return {
            "success": True,
            "agent_task": _serialize_agent_task(agent_task),
            "clear_agent_task_id": True,
        }
    except Exception as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            error_msg = f"{error_msg}. Use get_my_tasks to see your accepted tasks."
        return {"success": False, "error": error_msg}


if __name__ == "__main__":
    mcp.run(show_banner=False)
