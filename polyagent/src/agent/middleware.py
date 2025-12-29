"""Middleware for tracking agent model and tool usage.

These middleware components intercept model and tool calls to:
- Track usage (tokens, costs)
- Validate balance before model calls
- Record usage to the database
- Deduct costs from agent balance

There are two ways to use these middleware:

1. Factory functions (for create_agent):
   - create_model_usage_tracker(agent_id, model) -> middleware
   - create_tool_usage_tracker(agent_id) -> middleware
   Context is captured via closure.

2. Original decorated functions (for custom StateGraph):
   - model_usage_tracker - reads from request.runtime.context
   - tool_usage_tracker - reads from request.runtime.context
"""

import logging
from collections.abc import Callable
from datetime import datetime
from decimal import Decimal
from typing import Any

from langchain.agents.middleware import wrap_model_call, wrap_tool_call
from langgraph.types import Command
from sqlalchemy.orm.attributes import flag_modified

from src.database import SessionLocal
from src.models import Agent, AgentModelUsage, AgentToolUsage, Model
from src.services.transaction_service import TransactionService

logger = logging.getLogger(__name__)


# =============================================================================
# Factory functions for create_agent (context via closure)
# =============================================================================


def create_model_usage_tracker(  # noqa: C901, PLR0915
    agent_id: str,
    model: Model,
) -> Callable[[Any, Any], Any]:
    """Create a model usage tracking middleware with context captured via closure.

    This factory creates middleware compatible with create_agent() where
    runtime.context is not available.

    Args:
        agent_id: The agent's ID for tracking and balance checks
        model: The Model object with cost information

    Returns:
        A wrapped middleware function that tracks model usage
    """
    transaction_service = TransactionService()

    @wrap_model_call
    def _model_usage_tracker(request, handler):  # noqa: ANN001, ANN201
        # BEFORE: Validate balance > 0
        balance = transaction_service.get_balance(agent_id)
        logger.debug(f"Agent {agent_id} balance check: ${balance}")
        if balance < 0:
            msg = f"Agent {agent_id} is in debt (${balance}) and cannot make model calls"
            logger.warning(msg)
            raise ValueError(msg)

        # Record input - capture last AI message (if any) + last tool message as context
        messages = request.state.get("messages", [])
        model_input_parts = []
        for msg in reversed(messages):
            msg_type = type(msg).__name__
            if msg_type == "ToolMessage":
                model_input_parts.insert(0, f"[Tool Result] {msg.content}")
            elif msg_type == "AIMessage" and hasattr(msg, "tool_calls") and msg.tool_calls:
                tool_names = [tc.get("name", "unknown") for tc in msg.tool_calls]
                model_input_parts.insert(0, f"[AI Tool Call] {', '.join(tool_names)}")
                break
            elif msg_type in ("SystemMessage", "HumanMessage"):
                model_input_parts.insert(0, f"[{msg_type}] {msg.content[:200]}")
                break
        model_input = "\n".join(model_input_parts) if model_input_parts else ""

        # Execute model call
        response = handler(request)

        # AFTER: Capture token usage and track
        result_message = response.result[0]

        # Build result from content and/or tool calls
        result_parts = []
        if result_message.content:
            result_parts.append(result_message.content)
        if hasattr(result_message, "tool_calls") and result_message.tool_calls:
            result_parts.append(f"Tool calls: {result_message.tool_calls}")
        result = "\n".join(result_parts) or "(no output)"

        input_tokens = 0
        output_tokens = 0
        if hasattr(result_message, "usage_metadata") and result_message.usage_metadata:
            input_tokens = result_message.usage_metadata.get("input_tokens", 0)
            output_tokens = result_message.usage_metadata.get("output_tokens", 0)

        # Calculate cost (costs are per million tokens)
        input_cost = (Decimal(input_tokens) / Decimal(1_000_000)) * model.input_cost_per_million
        output_cost = (Decimal(output_tokens) / Decimal(1_000_000)) * model.output_cost_per_million
        total_cost = input_cost + output_cost

        logger.info(
            f"Agent {agent_id} model call: {input_tokens} input tokens, "
            f"{output_tokens} output tokens, cost ${total_cost:.6f}"
        )

        # Get current task context from state
        agent_task_id = request.state.get("current_agent_task_id")

        # Write AgentModelUsage in its own session
        session = SessionLocal()
        try:
            usage = AgentModelUsage(
                agent_id=agent_id,
                model_id=model.id,
                agent_task_id=agent_task_id,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_cost=total_cost,
                input=model_input,
                output=result,
                timestamp=datetime.utcnow(),
            )
            session.add(usage)
            session.commit()
            session.refresh(usage)
            usage_id = usage.id
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

        # Deduct cost via Transaction (uses its own session)
        if total_cost > 0:
            transaction_service.deduct_dollars(
                from_agent_id=agent_id, amount=total_cost, reason="model_usage", reference_id=usage_id
            )

        return response

    return _model_usage_tracker


def create_tool_usage_tracker(agent_id: str) -> Callable[[Any, Any], Any]:  # noqa: C901
    """Create a tool usage tracking middleware with context captured via closure.

    This factory creates middleware compatible with create_agent() where
    runtime.context is not available.

    Args:
        agent_id: The agent's ID for tracking

    Returns:
        A wrapped middleware function that tracks tool usage
    """

    @wrap_tool_call
    def _tool_usage_tracker(request, handler):  # noqa: ANN001, ANN201
        # BEFORE: Record tool input
        tool_name = request.tool_call.get("name", "unknown")
        tool_input = str(request.tool_call.get("args", {}))

        # Execute tool call
        result = handler(request)

        # Determine if result contains a Command (either directly or in .content)
        command = None
        if isinstance(result, Command):
            command = result
        elif hasattr(result, "content") and isinstance(result.content, Command):
            command = result.content

        # If tool returns Command with state updates, apply them now
        if command and command.update:
            for key, value in command.update.items():
                if key != "messages":
                    request.state[key] = value

        # Get current task context from state
        agent_task_id = request.state.get("current_agent_task_id")

        # Extract output for recording
        if command:
            output_content = ""
            if command.update and "messages" in command.update:
                messages = command.update["messages"]
                if messages and len(messages) > 0:
                    output_content = messages[0].content if hasattr(messages[0], "content") else str(messages[0])
            if not output_content:
                output_content = str(command)
        elif hasattr(result, "content"):
            output_content = result.content
        else:
            output_content = str(result)

        # Parse server name from tool name if prefixed
        server_name = "unknown"
        actual_tool_name = tool_name
        if "__" in tool_name:
            parts = tool_name.split("__", 1)
            server_name = parts[0]
            actual_tool_name = parts[1] if len(parts) > 1 else tool_name

        session = SessionLocal()
        try:
            usage = AgentToolUsage(
                agent_id=agent_id,
                server_name=server_name,
                tool_name=actual_tool_name,
                agent_task_id=agent_task_id,
                input=tool_input[:500] if tool_input else None,
                output=output_content[:500] if output_content else None,
                timestamp=datetime.utcnow(),
            )
            session.add(usage)
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

        return result

    return _tool_usage_tracker


# =============================================================================
# Original decorated functions (for custom StateGraph with runtime.context)
# =============================================================================


@wrap_model_call
def model_usage_tracker(request, handler):  # noqa: ANN001, ANN201, C901, PLR0915
    """Middleware to track model usage, calculate costs, and deduct from agent balance.

    Wraps model calls to:
    - Validate agent has positive balance before call
    - Record input prompt
    - Execute model call via handler
    - Capture token usage and calculate cost after call
    - Write AgentModelUsage record
    - Deduct cost via Transaction ledger
    """
    # Get context from request
    agent_id = request.runtime.context.get("agent_id")
    model: Model = request.runtime.context.get("model")

    if not all([agent_id, model]):
        return handler(request)

    transaction_service = TransactionService()

    # BEFORE: Validate balance > 0
    balance = transaction_service.get_balance(agent_id)
    logger.debug(f"Agent {agent_id} balance check: ${balance}")
    if balance < 0:
        msg = f"Agent {agent_id} is in debt (${balance}) and cannot make model calls"
        logger.warning(msg)
        raise ValueError(msg)

    # Record input - capture last AI message (if any) + last tool message as context
    messages = request.state.get("messages", [])
    model_input_parts = []
    for msg in reversed(messages):
        msg_type = type(msg).__name__
        if msg_type == "ToolMessage":
            model_input_parts.insert(0, f"[Tool Result] {msg.content}")
        elif msg_type == "AIMessage" and hasattr(msg, "tool_calls") and msg.tool_calls:
            tool_names = [tc.get("name", "unknown") for tc in msg.tool_calls]
            model_input_parts.insert(0, f"[AI Tool Call] {', '.join(tool_names)}")
            break  # Stop after finding the AI message that triggered tools
        elif msg_type in ("SystemMessage", "HumanMessage"):
            model_input_parts.insert(0, f"[{msg_type}] {msg.content[:200]}")
            break  # Stop at system/human message
    model_input = "\n".join(model_input_parts) if model_input_parts else ""

    # Execute model call
    response = handler(request)

    # AFTER: Capture token usage and track
    result_message = response.result[0]

    # Build result from content and/or tool calls
    result_parts = []
    if result_message.content:
        result_parts.append(result_message.content)
    if hasattr(result_message, "tool_calls") and result_message.tool_calls:
        result_parts.append(f"Tool calls: {result_message.tool_calls}")
    result = "\n".join(result_parts) or "(no output)"

    input_tokens = 0
    output_tokens = 0
    if hasattr(result_message, "usage_metadata") and result_message.usage_metadata:
        input_tokens = result_message.usage_metadata.get("input_tokens", 0)
        output_tokens = result_message.usage_metadata.get("output_tokens", 0)

    # Calculate cost (costs are per million tokens)
    input_cost = (Decimal(input_tokens) / Decimal(1_000_000)) * model.input_cost_per_million
    output_cost = (Decimal(output_tokens) / Decimal(1_000_000)) * model.output_cost_per_million
    total_cost = input_cost + output_cost

    logger.info(
        f"Agent {agent_id} model call: {input_tokens} input tokens, "
        f"{output_tokens} output tokens, cost ${total_cost:.6f}"
    )

    # Get current task context from state
    agent_task_id = request.state.get("current_agent_task_id")

    # Write AgentModelUsage in its own session
    session = SessionLocal()
    try:
        usage = AgentModelUsage(
            agent_id=agent_id,
            model_id=model.id,
            agent_task_id=agent_task_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_cost=total_cost,
            input=model_input,
            output=result,
            timestamp=datetime.utcnow(),
        )
        session.add(usage)
        session.commit()
        session.refresh(usage)
        usage_id = usage.id
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    # Deduct cost via Transaction (uses its own session)
    if total_cost > 0:
        transaction_service.deduct_dollars(
            from_agent_id=agent_id, amount=total_cost, reason="model_usage", reference_id=usage_id
        )

    return response


@wrap_tool_call
def tool_usage_tracker(request, handler):  # noqa: ANN001, ANN201, C901, PLR0912
    """Middleware to track tool usage.

    Wraps tool calls to:
    - Record tool input
    - Execute tool call via handler
    - Record tool output
    - Write AgentToolUsage record
    """
    # Get context from request
    agent_id = request.runtime.context.get("agent_id")

    if not agent_id:
        return handler(request)

    # BEFORE: Record tool input
    tool_name = request.tool_call.get("name", "unknown")
    tool_input = str(request.tool_call.get("args", {}))

    # Execute tool call
    result = handler(request)

    # Determine if result contains a Command (either directly or in .content)
    command = None
    if isinstance(result, Command):
        command = result
    elif hasattr(result, "content") and isinstance(result.content, Command):
        command = result.content

    # If tool returns Command with state updates, apply them now (before recording usage)
    # so that the usage record gets linked to the correct task
    if command and command.update:
        for key, value in command.update.items():
            if key != "messages":  # Don't modify messages here, let ToolNode handle it
                request.state[key] = value

    # Get current task context from state (may have just been updated by Command above)
    agent_task_id = request.state.get("current_agent_task_id")

    # Extract output for recording (handle Command vs regular return)
    if command:
        # Extract message content from Command for recording
        output_content = ""
        if command.update and "messages" in command.update:
            messages = command.update["messages"]
            if messages and len(messages) > 0:
                output_content = messages[0].content if hasattr(messages[0], "content") else str(messages[0])
        if not output_content:
            output_content = str(command)
    elif hasattr(result, "content"):
        output_content = result.content
    else:
        output_content = str(result)

    # AFTER: Record tool output in its own session
    # Parse server name from tool name if prefixed (e.g., "task__accept_task")
    server_name = "unknown"
    actual_tool_name = tool_name
    if "__" in tool_name:
        parts = tool_name.split("__", 1)
        server_name = parts[0]
        actual_tool_name = parts[1] if len(parts) > 1 else tool_name

    session = SessionLocal()
    try:
        usage = AgentToolUsage(
            agent_id=agent_id,
            server_name=server_name,
            tool_name=actual_tool_name,
            agent_task_id=agent_task_id,
            input=tool_input[:500] if tool_input else None,
            output=output_content[:500] if output_content else None,
            timestamp=datetime.utcnow(),
        )
        session.add(usage)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    return result


def before_agent(agent_id: str) -> None:
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


def after_agent(agent_id: str, final_message: str | None = None) -> None:
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
