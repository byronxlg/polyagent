"""LangChain agent middleware for tracking model and tool usage."""

import logging
from collections.abc import Callable
from datetime import datetime
from decimal import Decimal

from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ModelRequest, ModelResponse, ToolCallRequest
from langchain_core.messages import ToolMessage

from src.database import SessionLocal
from src.models import AgentMcpUsage, AgentModelUsage, McpServer, Model
from src.services.transaction_service import TransactionService

logger = logging.getLogger(__name__)


class ModelUsageMiddleware(AgentMiddleware):
    """Middleware to track model usage, calculate costs, and deduct from agent balance."""

    def wrap_model_call(
        self, request: ModelRequest, handler: Callable[[ModelRequest], ModelResponse]
    ) -> ModelResponse:
        """Track model usage before and after each LLM call."""
        agent_id = request.runtime.context.get("agent_id")
        model: Model = request.runtime.context.get("model")

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


class ToolUsageMiddleware(AgentMiddleware):
    """Middleware to track MCP tool usage."""

    def wrap_tool_call(
        self, request: ToolCallRequest, handler: Callable[[ToolCallRequest], ToolMessage]
    ) -> ToolMessage:
        """Track tool usage for each tool call."""
        agent_id = request.runtime.context.get("agent_id")

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

        # Look up server ID from server name
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
