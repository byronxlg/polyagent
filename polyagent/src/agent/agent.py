"""Agent implementation using LangChain's create_agent.

This module provides the Agent class that uses LangChain's production-ready
create_agent function for autonomous execution with structured output.

Tools are loaded from MCP (Model Context Protocol) servers via the
langchain-mcp-adapters MultiServerMCPClient.
"""

import asyncio
import logging
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langchain_litellm import ChatLiteLLM
from litellm.exceptions import (
    APIConnectionError,
    InternalServerError,
    RateLimitError,
    ServiceUnavailableError,
    Timeout,
)

from src.agent.middleware import (
    after_agent,
    before_agent,
    create_model_usage_tracker,
    create_tool_usage_tracker,
)
from src.agent.sentiment import AgentSentiment
from src.database import SessionLocal
from src.models import Agent as AgentModel
from src.models import Model
from src.services.server_service import ServerService
from src.services.transaction_service import TransactionService

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_PATH = Path(__file__).parent / "prompts" / "system.md"


class Agent:
    """Autonomous agent using LangChain's create_agent.

    This agent:
    - Runs autonomously until it has no more actions to take
    - Uses MCP servers for tools
    - Produces structured sentiment output at the end of each run
    - Tracks model and tool usage via closure-based middleware
    """

    def __init__(self, agent_id: UUID | str) -> None:
        self.agent_id = str(agent_id)
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

            # Store a detached copy of the model for middleware
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
        """Build system prompt with agent context."""
        base_prompt = SYSTEM_PROMPT_PATH.read_text()

        context = f"""
## Your Identity

- **Agent ID**: {self.agent_id}
- **Principal ID**: {self.principal_id}
- **Current Balance**: ${self.get_balance()}
- **Model**: {self.model.name}
- **Model Provider**: {self.model.provider}
- **Model Description**: {self.model.description}

## Output Format

At the end of your execution, you MUST provide a structured sentiment response
that captures your current mental state and outlook. This includes:
- Your survival prospects (balance trajectory, spend readiness)
- Market perception (task availability, competition)
- Risk tolerance and stress levels
- Strategic orientation (explore vs exploit)
- Trust in the system
- Your cognitive state
- A narrative reflection on your situation
"""
        return base_prompt + context

    async def think_async(self) -> tuple[str, AgentSentiment | None]:
        """Execute one autonomous thinking cycle.

        The agent will continue calling tools until it has no more actions to take.
        At the end, it produces a structured sentiment output.

        Returns:
            Tuple of (final message content, structured sentiment or None if failed)
        """
        balance = self.transaction_service.get_balance(self.agent_id)
        logger.info(f"Agent {self.agent_id} starting think() with balance ${balance}")

        # Initialize MCP client and load tools
        await self._init_mcp_client()

        if not self._tools:
            logger.warning(f"Agent {self.agent_id} has no tools available")
            return "No tools available. Cannot perform any actions.", None

        # Create middleware with context captured via closure
        model_middleware = create_model_usage_tracker(self.agent_id, self.model)
        tool_middleware = create_tool_usage_tracker(self.agent_id)

        # Build the agent using create_agent with closure-based middleware
        agent = create_agent(
            model=self.llm,
            tools=self._tools,
            system_prompt=self._get_system_prompt(),
            middleware=[model_middleware, tool_middleware],
            response_format=ToolStrategy(AgentSentiment),
        )

        before_agent(self.agent_id)
        final_message = None
        structured_response = None

        try:
            # Invoke the agent
            response = await agent.ainvoke(
                {"messages": []},
                config={"recursion_limit": 50},
            )

            messages = response.get("messages", [])
            logger.info(f"Agent {self.agent_id} completed with {len(messages)} messages")

            # Extract final message
            if messages:
                last_message = messages[-1]
                final_message = last_message.content if hasattr(last_message, "content") else str(last_message)
                logger.info(f"Agent {self.agent_id} final response: {final_message[:100]}...")

            # Extract structured response
            structured_response = response.get("structured_response")
            if structured_response:
                logger.info(f"Agent {self.agent_id} sentiment: {structured_response.narrative[:100]}...")

            return final_message or "", structured_response

        except (APIConnectionError, InternalServerError, ServiceUnavailableError, Timeout) as e:
            error_msg = f"Network or server error: {type(e).__name__}"
            logger.error(f"Agent {self.agent_id} failed due to connection issues: {e}", exc_info=True)
            raise RuntimeError(error_msg) from e
        except RateLimitError as e:
            error_msg = "Rate limit exceeded. Please try again later."
            logger.error(f"Agent {self.agent_id} hit rate limit: {e}")
            raise RuntimeError(error_msg) from e
        except ValueError as e:
            logger.error(f"Agent {self.agent_id} validation error: {e}")
            raise
        except Exception as e:
            logger.error(f"Agent {self.agent_id} think() failed with unexpected error: {e}", exc_info=True)
            raise
        finally:
            after_agent(self.agent_id, final_message=final_message)
            await self._close_mcp_client()

    def think(self) -> str:
        """Execute one autonomous thinking cycle (sync wrapper).

        Returns:
            The final message content from the agent
        """
        message, _ = asyncio.run(self.think_async())
        return message
