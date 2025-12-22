"""Custom ReAct agent for autonomous event-driven execution.

This agent builds a LangGraph StateGraph directly rather than using the
chat-oriented create_agent function. The agent runs autonomously until
it decides it has completed its current objective, rather than waiting
for user input.
"""

import logging
import time
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal
from uuid import UUID

from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool as tool_decorator
from langchain_litellm import ChatLiteLLM
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode
from litellm.exceptions import (
    APIConnectionError,
    APIError,
    InternalServerError,
    RateLimitError,
    ServiceUnavailableError,
    Timeout,
)

from src.agent.middleware import after_agent, before_agent
from src.agent.state import AgentState
from src.database import SessionLocal
from src.models import Agent as AgentModel
from src.models import AgentModelUsage, AgentToolUsage, Model, Principal, Tool
from src.services.tool_service import ToolService
from src.services.transaction_service import TransactionService

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_PATH = Path(__file__).parent / "prompts" / "system.md"


class Agent:
    """Autonomous ReAct agent using custom LangGraph StateGraph.

    Unlike the chat-oriented create_agent, this agent:
    - Runs autonomously until it has no more actions to take (no user interaction)
    - Ends when the LLM produces no tool calls (natural completion)
    - Final text output is captured to memory as reflection for the next run
    - Tracks model and tool usage inline within the graph nodes
    """

    def __init__(self, agent_id: UUID | str) -> None:
        self.agent_id = agent_id
        self.transaction_service = TransactionService()

        # Load agent and model data
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
        self.system_prompt = self._get_system_prompt()

        # Load tools
        tool_service = ToolService()
        self.tools = tool_service.get_tools_for_agent(agent_id)

        # Bind tools to the LLM
        self.llm_with_tools = self.llm.bind_tools(self.tools)

        # Build the graph
        self.graph = self._build_graph()

    def get_balance(self) -> Decimal:
        return self.transaction_service.get_balance(self.agent_id)

    def think(self) -> str:
        """Execute one autonomous thinking cycle.

        The agent will continue calling tools until it has no more actions to take.
        When done, it should provide a reflection that will be saved to memory.

        Returns:
            The agent's final message content (reflection).
        """
        balance = self.transaction_service.get_balance(self.agent_id)
        logger.info(f"Agent {self.agent_id} starting think() with balance ${balance}")

        before_agent(self.agent_id)
        try:
            response = self.graph.invoke(
                {
                    "messages": [SystemMessage(content=self.system_prompt)],
                    "current_agent_task_id": None,
                },
                config={"recursion_limit": 50},
            )

            messages = response["messages"]
            logger.info(f"Agent {self.agent_id} completed with {len(messages)} messages")

            # Log tool calls
            tool_calls = [msg for msg in messages if hasattr(msg, "tool_calls") and msg.tool_calls]
            if tool_calls:
                for msg in tool_calls:
                    for tool_call in msg.tool_calls:
                        logger.info(f"Agent {self.agent_id} called tool: {tool_call.get('name', 'unknown')}")
            else:
                logger.warning(f"Agent {self.agent_id} made NO tool calls")

            last_message = messages[-1]
            content = last_message.content if hasattr(last_message, "content") else str(last_message)
            logger.info(f"Agent {self.agent_id} final response: {content[:100]}...")

            # Capture final message for memory
            final_message_for_memory = content

            return content

        except (APIConnectionError, InternalServerError, ServiceUnavailableError, Timeout) as e:
            error_msg = f"Network or server error: {type(e).__name__}"
            logger.error(f"Agent {self.agent_id} failed due to connection issues: {e}", exc_info=True)
            final_message_for_memory = None
            raise RuntimeError(error_msg) from e
        except RateLimitError as e:
            error_msg = "Rate limit exceeded. Please try again later."
            logger.error(f"Agent {self.agent_id} hit rate limit: {e}")
            final_message_for_memory = None
            raise RuntimeError(error_msg) from e
        except ValueError as e:
            logger.error(f"Agent {self.agent_id} validation error: {e}")
            final_message_for_memory = None
            raise
        except Exception as e:
            logger.error(f"Agent {self.agent_id} think() failed with unexpected error: {e}", exc_info=True)
            final_message_for_memory = None
            raise
        finally:
            after_agent(self.agent_id, final_message=final_message_for_memory)

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

    def _build_graph(self) -> StateGraph:
        """Build the ReAct agent graph."""
        workflow = StateGraph(AgentState)

        # Add nodes
        workflow.add_node("agent", self._call_model)
        workflow.add_node("tools", self._create_tool_node())

        # Set entry point
        workflow.set_entry_point("agent")

        # Add conditional edge: agent decides whether to use tools or end
        workflow.add_conditional_edges(
            "agent",
            self._should_continue,
            {"continue": "tools", "end": END},
        )

        # Tools always return to agent
        workflow.add_edge("tools", "agent")

        return workflow.compile()

    def _call_model_with_retry(self, messages: list, max_retries: int = 3) -> AIMessage:
        """Call the model with retry logic for transient errors.

        Args:
            messages: Message history to send to the model
            max_retries: Maximum number of retry attempts

        Returns:
            AIMessage response from the model

        Raises:
            Various exceptions if all retries fail
        """
        last_exception = None
        for attempt in range(max_retries):
            try:
                return self.llm_with_tools.invoke(messages)
            except (APIConnectionError, InternalServerError, ServiceUnavailableError, Timeout) as e:
                last_exception = e
                is_final_attempt = attempt == max_retries - 1

                if is_final_attempt:
                    logger.error(
                        f"Agent {self.agent_id} model call failed after {max_retries} attempts: "
                        f"{type(e).__name__}: {e}"
                    )
                    raise

                wait_time = 2**attempt
                logger.warning(
                    f"Agent {self.agent_id} model call failed (attempt {attempt + 1}/{max_retries}): "
                    f"{type(e).__name__}: {e}. Retrying in {wait_time}s..."
                )
                time.sleep(wait_time)
            except RateLimitError as e:
                logger.error(f"Agent {self.agent_id} hit rate limit: {e}")
                raise
            except APIError as e:
                logger.error(f"Agent {self.agent_id} API error (non-retryable): {e}")
                raise
            except Exception as e:
                logger.error(f"Agent {self.agent_id} unexpected error: {type(e).__name__}: {e}", exc_info=True)
                raise

        if last_exception:
            raise last_exception
        msg = "Unexpected: no response and no exception"
        raise RuntimeError(msg)

    def _call_model(self, state: AgentState) -> dict:
        """Call the LLM with current state and track usage."""
        messages = state["messages"]
        agent_task_id = state.get("current_agent_task_id")

        # Check balance before call
        balance = self.transaction_service.get_balance(self.agent_id)
        if balance < 0:
            msg = f"Agent {self.agent_id} is in debt (${balance}) and cannot make model calls"
            logger.warning(msg)
            raise ValueError(msg)

        # Build input context for logging
        model_input = self._build_model_input_context(messages)

        # Call the model with retry logic
        response = self._call_model_with_retry(messages)

        # Extract usage and calculate cost
        input_tokens = 0
        output_tokens = 0
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            input_tokens = response.usage_metadata.get("input_tokens", 0)
            output_tokens = response.usage_metadata.get("output_tokens", 0)

        input_cost = (Decimal(input_tokens) / Decimal(1_000_000)) * self.model.input_cost_per_million
        output_cost = (Decimal(output_tokens) / Decimal(1_000_000)) * self.model.output_cost_per_million
        total_cost = input_cost + output_cost

        logger.info(
            f"Agent {self.agent_id} model call: {input_tokens} input, "
            f"{output_tokens} output tokens, cost ${total_cost:.6f}"
        )

        # Build output for logging
        output_parts = []
        if response.content:
            output_parts.append(response.content)
        if hasattr(response, "tool_calls") and response.tool_calls:
            output_parts.append(f"Tool calls: {response.tool_calls}")
        output = "\n".join(output_parts) or "(no output)"

        # Record usage
        session = SessionLocal()
        try:
            usage = AgentModelUsage(
                agent_id=self.agent_id,
                model_id=self.model.id,
                agent_task_id=agent_task_id,
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
            self.transaction_service.deduct_dollars(
                from_agent_id=self.agent_id,
                amount=total_cost,
                reason="model_usage",
                reference_id=usage_id,
            )

        return {"messages": [response]}

    def _create_tool_node(self) -> ToolNode:
        """Create a ToolNode that tracks usage."""
        # We use LangGraph's ToolNode but wrap tools to track usage
        tracked_tools = [self._wrap_tool_for_tracking(tool) for tool in self.tools]
        return ToolNode(tracked_tools)

    def _wrap_tool_for_tracking(self, tool):  # noqa: ANN001, ANN202
        """Wrap a tool to track its usage in the database."""
        original_func = tool.func

        def tracked_wrapper(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
            # Get current task from state (not available here, will be None)
            # Tool tracking for agent_task_id requires accessing state differently
            tool_input = str(kwargs) if kwargs else str(args)

            # Execute original tool
            result = original_func(*args, **kwargs)

            # Record usage
            session = SessionLocal()
            try:
                # Look up or create the Tool record
                db_tool = session.query(Tool).filter(Tool.name == tool.name).first()
                if not db_tool:
                    system_principal = (
                        session.query(Principal).filter(Principal.principal_type == "system").first()
                    )
                    if not system_principal:
                        msg = "No system principal found"
                        raise ValueError(msg)

                    db_tool = Tool(
                        name=tool.name,
                        description=f"Auto-created: {tool.name}",
                        created_by_principal_id=system_principal.id,
                        scope="local",
                    )
                    session.add(db_tool)
                    session.flush()

                usage = AgentToolUsage(
                    agent_id=self.agent_id,
                    tool_id=db_tool.id,
                    agent_task_id=None,  # Cannot access state from here
                    input=tool_input[:500],
                    output=str(result)[:500],
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

        # Create new tool with tracked wrapper
        @tool_decorator(tool.name, description=tool.description)
        def tracked_tool(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
            return tracked_wrapper(*args, **kwargs)

        # Copy over the schema if it exists
        if hasattr(tool, "args_schema"):
            tracked_tool.args_schema = tool.args_schema

        return tracked_tool

    def _should_continue(self, state: AgentState) -> Literal["continue", "end"]:
        """Determine if agent should continue with tools or end.

        The agent ends when it has no more tool calls to make.
        This is the LLM's natural way of signaling completion.
        """
        messages = state["messages"]
        last_message = messages[-1]

        # Check if agent has made tool calls
        if not (hasattr(last_message, "tool_calls") and last_message.tool_calls):
            # No tool calls - agent is done and will provide reflection
            logger.info(f"Agent {self.agent_id} completed execution (no more tool calls)")
            return "end"

        # Agent made tool calls - continue execution
        return "continue"

    def _build_model_input_context(self, messages: list) -> str:
        """Build a summary of recent messages for logging."""
        input_parts = []
        for msg in reversed(messages):
            msg_type = type(msg).__name__
            if isinstance(msg, ToolMessage):
                input_parts.insert(0, f"[Tool Result] {msg.content}")
            elif isinstance(msg, AIMessage) and hasattr(msg, "tool_calls") and msg.tool_calls:
                tool_names = [tc.get("name", "unknown") for tc in msg.tool_calls]
                input_parts.insert(0, f"[AI Tool Call] {', '.join(tool_names)}")
                break
            elif msg_type in ("SystemMessage", "HumanMessage"):
                content = msg.content if hasattr(msg, "content") else str(msg)
                input_parts.insert(0, f"[{msg_type}] {content[:200]}")
                break
        return "\n".join(input_parts) if input_parts else ""
