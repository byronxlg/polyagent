"""Custom agent state schema with task tracking."""

from typing import Annotated

from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


def last_value(existing: str | None, new: str | None) -> str | None:  # noqa: ARG001
    """Reducer that keeps the last value when multiple updates occur in one step."""
    return new


class AgentState(TypedDict):
    """State schema for agent execution with task tracking.

    Attributes:
        messages: Conversation history managed by LangGraph's add_messages reducer.
        current_agent_task_id: The AgentTask.id currently being worked on.
            Set by task tools (accept_task, submit_task, abandon_task) via Command.
            Read by middleware to link usage records to tasks.
            Uses last_value reducer to handle concurrent updates.
    """

    messages: Annotated[list, add_messages]
    current_agent_task_id: Annotated[str | None, last_value]
