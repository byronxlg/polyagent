"""Autonomous agent using LangChain's create_agent.

This agent uses create_agent() to build a ReAct agent that runs autonomously
until it decides it has completed its objective. Tools are loaded from MCP
servers via langchain-mcp-adapters.
"""

import asyncio
import logging
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

from langchain.agents import create_agent
from langchain_litellm import ChatLiteLLM

from src.agent.middleware import MIDDLEWARE
from src.database import SessionLocal
from src.models import Agent as AgentModel
from src.models import Model
from src.services.server_service import ServerService
from src.services.transaction_service import TransactionService

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_PATH = Path(__file__).parent / "prompts" / "system.md"


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

        # Create agent with middleware for usage tracking and lifecycle
        agent = create_agent(
            model=self.llm,
            tools=self._tools,
            system_prompt=self._get_system_prompt(),
            middleware=MIDDLEWARE,
        )

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
            final_message = None
            if messages:
                last_message = messages[-1]
                final_message = last_message.content if hasattr(last_message, "content") else str(last_message)
                logger.info(f"Agent {self.agent_id} final response: {final_message[:100]}...")

            return final_message or "Agent completed without output."

        except Exception as e:
            logger.error(f"Agent {self.agent_id} think() failed: {e}", exc_info=True)
            raise
        finally:
            await self._close_mcp_client()

    def think(self) -> str:
        """Execute one autonomous thinking cycle (sync wrapper)."""
        return asyncio.run(self.think_async())
