"""LangChain agent middleware for tracking usage and managing lifecycle.

Uses decorator-based middleware:
- @before_agent: Runs before agent starts (set is_running, validate balance)
- @after_agent: Runs after agent completes (save reflection, clear is_running)
- @wrap_model_call: Wraps model calls (track usage, deduct costs)
- @wrap_tool_call: Wraps tool calls (track MCP tool usage)
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from langchain.agents.middleware import after_agent, before_agent, wrap_model_call, wrap_tool_call
from sqlalchemy.orm.attributes import flag_modified

from src.database import SessionLocal
from src.models import Agent, AgentMcpUsage, AgentModelUsage, McpServer, Model
from src.services.transaction_service import TransactionService


@dataclass
class AgentContext:
    """Context schema for agent middleware.

    This dataclass defines the context that will be available to middleware
    via runtime.context when using create_agent with context_schema=AgentContext.
    """

    agent_id: UUID | str | None = None
    model: Model | None = field(default=None, repr=False)

logger = logging.getLogger(__name__)


@before_agent
def validate_and_start(_state: dict[str, Any], runtime: Any) -> None:  # noqa: ANN401
    """Set is_running=True and validate agent has positive balance."""
    if not runtime.context:
        return
    agent_id = runtime.context.agent_id
    if not agent_id:
        return

    session = SessionLocal()
    try:
        agent = session.query(Agent).filter(Agent.id == agent_id).first()
        if agent:
            agent.is_running = True
            session.commit()
            logger.debug(f"Agent {agent_id} is_running set to True")
    finally:
        session.close()

    # Validate balance
    transaction_service = TransactionService()
    balance = transaction_service.get_balance(agent_id)
    if balance < 0:
        msg = f"Agent {agent_id} is in debt (${balance}) and cannot execute"
        logger.warning(msg)
        raise ValueError(msg)

    return


@after_agent
def save_reflection_and_stop(state: dict[str, Any], runtime: Any) -> None:  # noqa: ANN401
    """Set is_running=False and save final reflection to memory."""
    if not runtime.context:
        return
    agent_id = runtime.context.agent_id
    if not agent_id:
        return

    # Extract final message from state
    messages = state.get("messages", [])
    final_message = None
    if messages:
        last_msg = messages[-1]
        final_message = last_msg.content if hasattr(last_msg, "content") else str(last_msg)

    session = SessionLocal()
    try:
        agent = session.query(Agent).filter(Agent.id == agent_id).first()
        if agent:
            agent.is_running = False

            # Save reflection to memory
            if final_message:
                if agent.memory_json is None:
                    agent.memory_json = {}
                agent.memory_json["last_run_reflection"] = final_message
                agent.memory_json["last_run_timestamp"] = datetime.utcnow().isoformat()
                flag_modified(agent, "memory_json")
                logger.info(f"Agent {agent_id} reflection saved: {final_message[:100]}...")

            session.commit()
            logger.debug(f"Agent {agent_id} is_running set to False")
    finally:
        session.close()

    return


@wrap_model_call
def track_model_usage(request: Any, handler: Callable[[Any], Any]) -> Any:  # noqa: ANN401
    """Track model usage, calculate costs, and deduct from agent balance."""
    if not request.runtime.context:
        return handler(request)

    agent_id = request.runtime.context.agent_id
    model: Model = request.runtime.context.model

    if not all([agent_id, model]):
        return handler(request)

    transaction_service = TransactionService()

    # Validate balance before call
    balance = transaction_service.get_balance(agent_id)
    if balance < 0:
        msg = f"Agent {agent_id} is in debt (${balance}) and cannot make model calls"
        logger.warning(msg)
        raise ValueError(msg)

    # Build input context for logging
    messages = request.state.get("messages", [])
    model_input = _build_model_input_context(messages)

    # Execute model call
    response = handler(request)

    # Extract usage and calculate cost
    result_message = response.result[0]
    input_tokens = 0
    output_tokens = 0
    if hasattr(result_message, "usage_metadata") and result_message.usage_metadata:
        input_tokens = result_message.usage_metadata.get("input_tokens", 0)
        output_tokens = result_message.usage_metadata.get("output_tokens", 0)

    input_cost = (Decimal(input_tokens) / Decimal(1_000_000)) * model.input_cost_per_million
    output_cost = (Decimal(output_tokens) / Decimal(1_000_000)) * model.output_cost_per_million
    total_cost = input_cost + output_cost

    logger.info(
        f"Agent {agent_id} model call: {input_tokens} input, "
        f"{output_tokens} output tokens, cost ${total_cost:.6f}"
    )

    # Build output for logging
    output_parts = []
    if result_message.content:
        output_parts.append(result_message.content)
    if hasattr(result_message, "tool_calls") and result_message.tool_calls:
        output_parts.append(f"Tool calls: {result_message.tool_calls}")
    output = "\n".join(output_parts) or "(no output)"

    # Record usage
    session = SessionLocal()
    try:
        usage = AgentModelUsage(
            agent_id=agent_id,
            model_id=model.id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_cost=total_cost,
            input=model_input,
            output=output,
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

    # Deduct cost
    if total_cost > 0:
        transaction_service.deduct_dollars(
            from_agent_id=agent_id,
            amount=total_cost,
            reason="model_usage",
            reference_id=usage_id,
        )

    return response


@wrap_tool_call
def track_tool_usage(request: Any, handler: Callable[[Any], Any]) -> Any:  # noqa: ANN401
    """Track MCP tool usage."""
    if not request.runtime.context:
        return handler(request)

    agent_id = request.runtime.context.agent_id

    if not agent_id:
        return handler(request)

    # Record tool input
    tool_name = request.tool_call.get("name", "unknown")
    tool_input = str(request.tool_call.get("args", {}))

    # Execute tool call
    result = handler(request)

    # Extract output
    output_content = result.content if hasattr(result, "content") else str(result)

    # Parse server name from tool name (e.g., "task__accept_task" -> server="task", tool="accept_task")
    server_name = "unknown"
    actual_tool_name = tool_name
    if "__" in tool_name:
        parts = tool_name.split("__", 1)
        server_name = parts[0]
        actual_tool_name = parts[1] if len(parts) > 1 else tool_name

    # Look up server ID and record usage
    session = SessionLocal()
    try:
        server = session.query(McpServer).filter(McpServer.name == server_name).first()
        mcp_server_id = server.id if server else None

        if mcp_server_id:
            usage = AgentMcpUsage(
                agent_id=agent_id,
                mcp_server_id=mcp_server_id,
                tool_name=actual_tool_name,
                input=tool_input[:500] if tool_input else "",
                output=output_content[:500] if output_content else "",
                timestamp=datetime.utcnow(),
            )
            session.add(usage)
            session.commit()
        else:
            logger.warning(f"Could not find MCP server '{server_name}' for tool usage tracking")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    return result


def _build_model_input_context(messages: list) -> str:
    """Build a summary of recent messages for logging."""
    input_parts = []
    for msg in reversed(messages):
        msg_type = type(msg).__name__
        if msg_type == "ToolMessage":
            input_parts.insert(0, f"[Tool Result] {msg.content}")
        elif msg_type == "AIMessage" and hasattr(msg, "tool_calls") and msg.tool_calls:
            tool_names = [tc.get("name", "unknown") for tc in msg.tool_calls]
            input_parts.insert(0, f"[AI Tool Call] {', '.join(tool_names)}")
            break
        elif msg_type in ("SystemMessage", "HumanMessage"):
            content = msg.content if hasattr(msg, "content") else str(msg)
            input_parts.insert(0, f"[{msg_type}] {content[:200]}")
            break
    return "\n".join(input_parts) if input_parts else ""


# Export middleware instances for use in agent
MIDDLEWARE = [
    validate_and_start,
    track_model_usage,
    track_tool_usage,
    save_reflection_and_stop,
]
