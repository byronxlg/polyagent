"""Autonomous agent using LangChain's create_agent.

This agent uses create_agent() to build a ReAct agent that runs autonomously
until it decides it has completed its objective. Tools are loaded from MCP
servers via langchain-mcp-adapters.
"""

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ModelRequest, ModelResponse, ToolCallRequest
from langchain_core.messages import ToolMessage
from langchain_litellm import ChatLiteLLM

from src.agent.middleware import after_agent, before_agent
from src.database import SessionLocal
from src.models import Agent as AgentModel
from src.models import AgentMcpUsage, AgentModelUsage, McpServer, Model
from src.services.server_service import ServerService
from src.services.transaction_service import TransactionService

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_PATH = Path(__file__).parent / "prompts" / "system.md"


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


class Agent:
    """Autonomous ReAct agent using LangChain's create_agent.

    This agent:
    - Runs autonomously until it has no more actions to take
    - Tracks model and tool usage via middleware
    - Deducts costs from agent balance
    - Stores final reflection to memory

    Tools are loaded from MCP servers via MultiServerMCPClient.
    """

    def __init__(self, agent_id: UUID | str) -> None:
        self.agent_id = agent_id
        self.transaction_service = TransactionService()
        self.server_service = ServerService()
        self._mcp_client = None
        self._tools = None

        # Load agent and model data
        session = SessionLocal()
        try:
            agent_model = session.query(AgentModel).filter(AgentModel.id == agent_id).first()
            if not agent_model:
                msg = f"Agent {agent_id} not found"
                raise ValueError(msg)

            self.principal_id = str(agent_model.principal_id)

            model = session.query(Model).filter(Model.id == agent_model.model_id).first()
            if not model:
                msg = f"Model {agent_model.model_id} not found"
                raise ValueError(msg)

            # Store model data (detached from session)
            self.model = Model(
                id=model.id,
                name=model.name,
                provider_name=model.provider_name,
                provider=model.provider,
                provider_model_id=model.provider_model_id,
                description=model.description,
                is_reasoning=model.is_reasoning,
                input_cost_per_million=model.input_cost_per_million,
                output_cost_per_million=model.output_cost_per_million,
            )
        finally:
            session.close()

        self.llm = ChatLiteLLM(model=self.model.provider_model_id)

    def _get_mcp_server_configs(self) -> dict[str, dict[str, Any]]:
        """Build MCP server configurations from granted servers."""
        servers = self.server_service.get_servers_for_agent(self.agent_id)
        configs = {}

        for server in servers:
            config = {
                "transport": server.transport,
                "command": server.command,
            }
            if server.args:
                config["args"] = server.args

            # Merge server env with principal_id injection
            env = dict(server.env) if server.env else {}
            env["PRINCIPAL_ID"] = self.principal_id
            config["env"] = env

            configs[server.name] = config

        return configs

    async def _init_mcp_client(self) -> None:
        """Initialize MCP client and load tools."""
        from langchain_mcp_adapters.client import MultiServerMCPClient  # noqa: PLC0415

        server_configs = self._get_mcp_server_configs()

        if not server_configs:
            logger.warning(f"Agent {self.agent_id} has no MCP servers granted")
            self._tools = []
            return

        self._mcp_client = MultiServerMCPClient(server_configs)
        self._tools = await self._mcp_client.get_tools()

        logger.info(
            f"Agent {self.agent_id} loaded {len(self._tools)} tools from {len(server_configs)} MCP servers"
        )

    async def _close_mcp_client(self) -> None:
        """Clean up MCP client reference."""
        self._mcp_client = None
        self._tools = None

    def get_balance(self) -> Decimal:
        return self.transaction_service.get_balance(self.agent_id)

    def _get_system_prompt(self) -> str:
        """Build the system prompt with agent context."""
        base_prompt = SYSTEM_PROMPT_PATH.read_text()

        context = f"""
## Your Identity

- **Agent ID**: {self.agent_id}
- **Principal ID**: {self.principal_id}
- **Current Balance**: ${self.get_balance()}
- **Model**: {self.model.name}
- **Model Provider**: {self.model.provider}
- **Model Description**: {self.model.description}
"""
        return base_prompt + context

    async def think_async(self) -> str:
        """Execute one autonomous thinking cycle (async version).

        Returns:
            The agent's final message content (reflection).
        """
        balance = self.transaction_service.get_balance(self.agent_id)
        logger.info(f"Agent {self.agent_id} starting think() with balance ${balance}")

        # Initialize MCP client and load tools
        await self._init_mcp_client()

        if not self._tools:
            logger.warning(f"Agent {self.agent_id} has no tools available")
            return "No tools available. Cannot perform any actions."

        # Create agent with middleware for usage tracking
        agent = create_agent(
            model=self.llm,
            tools=self._tools,
            system_prompt=self._get_system_prompt(),
            middleware=[
                ModelUsageMiddleware(),
                ToolUsageMiddleware(),
            ],
        )

        before_agent(self.agent_id)
        final_message = None

        try:
            # Invoke agent with context for middleware
            result = await agent.ainvoke(
                {"messages": [{"role": "user", "content": "Begin your autonomous execution cycle."}]},
                config={
                    "recursion_limit": 50,
                    "context": {
                        "agent_id": self.agent_id,
                        "model": self.model,
                    },
                },
            )

            messages = result.get("messages", [])
            logger.info(f"Agent {self.agent_id} completed with {len(messages)} messages")

            # Extract final message
            if messages:
                last_message = messages[-1]
                final_message = last_message.content if hasattr(last_message, "content") else str(last_message)
                logger.info(f"Agent {self.agent_id} final response: {final_message[:100]}...")

            return final_message or "Agent completed without output."

        except Exception as e:
            logger.error(f"Agent {self.agent_id} think() failed: {e}", exc_info=True)
            raise
        finally:
            after_agent(self.agent_id, final_message=final_message)
            await self._close_mcp_client()

    def think(self) -> str:
        """Execute one autonomous thinking cycle (sync wrapper)."""
        return asyncio.run(self.think_async())
