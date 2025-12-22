import logging
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from langchain.agents import create_agent
from langchain_core.messages import SystemMessage
from langchain_litellm import ChatLiteLLM

from src.agent.middleware import after_agent, before_agent, model_usage_tracker, tool_usage_tracker
from src.agent.state import AgentState
from src.database import SessionLocal
from src.models import Agent as AgentModel
from src.models import Model
from src.services.tool_service import ToolService
from src.services.transaction_service import TransactionService

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_PATH = Path(__file__).parent / "prompts" / "system.md"


class Agent:
    def __init__(self, agent_id: UUID | str) -> None:
        self.agent_id = agent_id
        self.transaction_service = TransactionService()

        # Load agent and model data in a temporary session
        session = SessionLocal()
        try:
            agent_model = session.query(AgentModel).filter(AgentModel.id == agent_id).first()
            if not agent_model:
                msg = f"Agent {agent_id} not found"
                raise ValueError(msg)

            model = session.query(Model).filter(Model.id == agent_model.model_id).first()
            if not model:
                msg = f"Model {agent_model.model_id} not found"
                raise ValueError(msg)

            # Store model data needed for context (detached from session)
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
        self.system_prompt = self._get_system_prompt()

        tool_service = ToolService()
        tools = tool_service.get_tools_for_agent(agent_id)

        self.agent = create_agent(
            self.llm,
            tools,
            middleware=[model_usage_tracker, tool_usage_tracker],
            state_schema=AgentState,
        )

    def get_balance(self) -> Decimal:
        return self.transaction_service.get_balance(self.agent_id)

    def think(self) -> str:
        balance = self.transaction_service.get_balance(self.agent_id)
        logger.info(f"Agent {self.agent_id} starting think() with balance ${balance}")

        before_agent(self.agent_id)
        try:
            response = self.agent.invoke(
                {
                    "messages": [SystemMessage(content=self.system_prompt)],
                    "current_agent_task_id": None,
                },
                config={"max_concurrency": 1},
                context={"agent_id": self.agent_id, "model": self.model},
            )

            messages = response["messages"]
            logger.info(f"Agent {self.agent_id} completed with {len(messages)} messages in conversation")

            # Log all tool calls
            tool_calls = [msg for msg in messages if hasattr(msg, "tool_calls") and msg.tool_calls]
            if tool_calls:
                for msg in tool_calls:
                    for tool_call in msg.tool_calls:
                        logger.info(f"Agent {self.agent_id} called tool: {tool_call.get('name', 'unknown')}")
            else:
                logger.warning(f"Agent {self.agent_id} made NO tool calls")

            last_message = messages[-1]
            logger.info(f"Agent {self.agent_id} final response: {last_message.content[:100]}...")
            return last_message.content

        except Exception as e:
            logger.error(f"Agent {self.agent_id} think() failed: {e}", exc_info=True)
            raise
        finally:
            after_agent(self.agent_id)

    def _get_system_prompt(self) -> str:
        base_prompt = SYSTEM_PROMPT_PATH.read_text()

        context = f"""
            ## Your Identity

            - **Agent ID**: {self.agent_id}
            - **Current Balance**: ${self.get_balance()}
            - **Model**: {self.model.name}
            - **Model Provider**: {self.model.provider}
            - **Model Description**: {self.model.description}
        """
        return base_prompt + context
