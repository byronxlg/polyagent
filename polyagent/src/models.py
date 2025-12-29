from datetime import datetime
from decimal import Decimal
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base


class Principal(Base):
    __tablename__ = "principals"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
    )
    username: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    principal_type: Mapped[str] = mapped_column(String, nullable=False)  # 'human', 'ai_agent', 'system'
    email: Mapped[str | None] = mapped_column(String, nullable=True, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    agent: Mapped["Agent | None"] = relationship(
        back_populates="principal", foreign_keys="Agent.principal_id", uselist=False
    )
    created_agents: Mapped[list["Agent"]] = relationship(
        back_populates="created_by", foreign_keys="Agent.created_by_principal_id"
    )
    simulations: Mapped[list["Simulation"]] = relationship(back_populates="principal")
    created_tasks: Mapped[list["Task"]] = relationship(back_populates="created_by")
    servers: Mapped[list["Server"]] = relationship(back_populates="created_by")
    sent_messages: Mapped[list["Message"]] = relationship(
        back_populates="sender", foreign_keys="Message.from_principal_id"
    )
    received_messages: Mapped[list["Message"]] = relationship(
        back_populates="recipient", foreign_keys="Message.to_principal_id"
    )
    sent_transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="sender", foreign_keys="Transaction.from_principal_id"
    )
    received_transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="recipient", foreign_keys="Transaction.to_principal_id"
    )


class Simulation(Base):
    __tablename__ = "simulations"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
    )
    principal_id: Mapped[UUID] = mapped_column(ForeignKey("principals.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    principal: Mapped["Principal"] = relationship(back_populates="simulations")
    agents: Mapped[list["Agent"]] = relationship(back_populates="simulation")
    tasks: Mapped[list["Task"]] = relationship(back_populates="simulation")
    triggers: Mapped[list["AgentTrigger"]] = relationship(back_populates="simulation")
    config: Mapped["SimulationConfig | None"] = relationship(back_populates="simulation", uselist=False)


class Model(Base):
    __tablename__ = "models"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(String, nullable=False)  # Human readable name
    provider_name: Mapped[str] = mapped_column(String, nullable=False)  # Human readable provider
    provider: Mapped[str] = mapped_column(String, nullable=False)  # Provider identifier (e.g., "openai")
    provider_model_id: Mapped[str] = mapped_column(String, nullable=False)  # Model ID for API calls
    description: Mapped[str] = mapped_column(Text, nullable=False)
    is_reasoning: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    input_cost_per_million: Mapped[Decimal] = mapped_column(Numeric(precision=20, scale=10), nullable=False)
    output_cost_per_million: Mapped[Decimal] = mapped_column(Numeric(precision=20, scale=10), nullable=False)

    agents: Mapped[list["Agent"]] = relationship(back_populates="model")
    usage_records: Mapped[list["AgentModelUsage"]] = relationship(back_populates="model")


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
    )
    principal_id: Mapped[UUID] = mapped_column(ForeignKey("principals.id"), nullable=False, unique=True)
    simulation_id: Mapped[UUID] = mapped_column(ForeignKey("simulations.id"), nullable=False)
    model_id: Mapped[UUID] = mapped_column(ForeignKey("models.id"), nullable=False)
    created_by_principal_id: Mapped[UUID] = mapped_column(ForeignKey("principals.id"), nullable=False)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    public_profile: Mapped[str | None] = mapped_column(Text, nullable=True)
    memory_json: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, default=dict, server_default=sa.text("'{}'")
    )
    memory_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_running: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    principal: Mapped["Principal"] = relationship(back_populates="agent", foreign_keys=[principal_id])
    simulation: Mapped["Simulation"] = relationship(back_populates="agents")
    model: Mapped["Model"] = relationship(back_populates="agents")
    created_by: Mapped["Principal"] = relationship(
        back_populates="created_agents", foreign_keys=[created_by_principal_id]
    )
    agent_tasks: Mapped[list["AgentTask"]] = relationship(back_populates="agent")
    servers: Mapped[list["AgentServer"]] = relationship(back_populates="agent")
    model_usage: Mapped[list["AgentModelUsage"]] = relationship(back_populates="agent")
    tool_usage: Mapped[list["AgentToolUsage"]] = relationship(back_populates="agent")
    triggers: Mapped[list["AgentTrigger"]] = relationship(back_populates="agent")


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
    )
    simulation_id: Mapped[UUID] = mapped_column(ForeignKey("simulations.id"), nullable=False)
    created_by_principal_id: Mapped[UUID] = mapped_column(ForeignKey("principals.id"), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    reward_dollars: Mapped[Decimal] = mapped_column(Numeric(precision=20, scale=10), nullable=False)
    deadline: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    is_completed: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    simulation: Mapped["Simulation"] = relationship(back_populates="tasks")
    created_by: Mapped["Principal"] = relationship()
    agent_tasks: Mapped[list["AgentTask"]] = relationship(back_populates="task")

    @property
    def status(self) -> str:
        """Computed status based on is_completed and deadline."""
        if self.is_completed:
            return "closed"
        if datetime.utcnow() > self.deadline:
            return "expired"
        return "available"


class AgentTask(Base):
    __tablename__ = "agent_tasks"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
    )
    task_id: Mapped[UUID] = mapped_column(ForeignKey("tasks.id"), nullable=False)
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id"), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="in_progress")
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    task: Mapped["Task"] = relationship(back_populates="agent_tasks")
    agent: Mapped["Agent"] = relationship(back_populates="agent_tasks")
    model_usage: Mapped[list["AgentModelUsage"]] = relationship(back_populates="agent_task")
    tool_usage: Mapped[list["AgentToolUsage"]] = relationship(back_populates="agent_task")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
    )
    from_principal_id: Mapped[UUID] = mapped_column(ForeignKey("principals.id"), nullable=False)
    to_principal_id: Mapped[UUID] = mapped_column(ForeignKey("principals.id"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    received_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    sender: Mapped["Principal"] = relationship(back_populates="sent_messages", foreign_keys=[from_principal_id])
    recipient: Mapped["Principal"] = relationship(
        back_populates="received_messages", foreign_keys=[to_principal_id]
    )


class Server(Base):
    """MCP server configuration."""

    __tablename__ = "servers"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
    )
    created_by_principal_id: Mapped[UUID] = mapped_column(ForeignKey("principals.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    server_type: Mapped[str] = mapped_column(String, nullable=False)  # "system" or "custom"
    transport: Mapped[str] = mapped_column(String, nullable=False, default="stdio")  # "stdio" or "http"
    command: Mapped[str] = mapped_column(String, nullable=False)  # Command to run server
    args: Mapped[list | None] = mapped_column(JSON, nullable=True)  # Command arguments
    env: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # Environment variables
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    created_by: Mapped["Principal"] = relationship(back_populates="servers")
    agent_servers: Mapped[list["AgentServer"]] = relationship(back_populates="server")


class AgentServer(Base):
    """Junction table for agent-to-MCP server grants."""

    __tablename__ = "agent_servers"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
    )
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id"), nullable=False)
    server_id: Mapped[UUID] = mapped_column(ForeignKey("servers.id"), nullable=False)
    granted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    agent: Mapped["Agent"] = relationship(back_populates="servers")
    server: Mapped["Server"] = relationship(back_populates="agent_servers")


class AgentModelUsage(Base):
    __tablename__ = "agent_model_usage"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
    )
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id"), nullable=False)
    model_id: Mapped[UUID] = mapped_column(ForeignKey("models.id"), nullable=False)
    agent_task_id: Mapped[UUID | None] = mapped_column(ForeignKey("agent_tasks.id"), nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    total_cost: Mapped[Decimal] = mapped_column(Numeric(precision=20, scale=10), nullable=False)
    input: Mapped[str] = mapped_column(Text, nullable=False)
    output: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    agent: Mapped["Agent"] = relationship(back_populates="model_usage")
    model: Mapped["Model"] = relationship(back_populates="usage_records")
    agent_task: Mapped["AgentTask | None"] = relationship(back_populates="model_usage")


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
    )
    from_principal_id: Mapped[UUID | None] = mapped_column(ForeignKey("principals.id"), nullable=True)
    to_principal_id: Mapped[UUID | None] = mapped_column(ForeignKey("principals.id"), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(precision=20, scale=10), nullable=False)
    reason: Mapped[str] = mapped_column(String, nullable=False)
    reference_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    sender: Mapped["Principal | None"] = relationship(
        back_populates="sent_transactions", foreign_keys=[from_principal_id]
    )
    recipient: Mapped["Principal | None"] = relationship(
        back_populates="received_transactions", foreign_keys=[to_principal_id]
    )


class AgentToolUsage(Base):
    __tablename__ = "agent_tool_usage"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
    )
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id"), nullable=False)
    server_name: Mapped[str] = mapped_column(String, nullable=False)  # MCP server name
    tool_name: Mapped[str] = mapped_column(String, nullable=False)  # Tool name within server
    agent_task_id: Mapped[UUID | None] = mapped_column(ForeignKey("agent_tasks.id"), nullable=True)
    input: Mapped[str] = mapped_column(Text, nullable=False)
    output: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    agent: Mapped["Agent"] = relationship(back_populates="tool_usage")
    agent_task: Mapped["AgentTask | None"] = relationship(back_populates="tool_usage")


class AgentTrigger(Base):
    """Agent subscriptions to database change events."""

    __tablename__ = "agent_triggers"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
    )
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id"), nullable=False, index=True)
    simulation_id: Mapped[UUID] = mapped_column(ForeignKey("simulations.id"), nullable=False, index=True)
    table_name: Mapped[str] = mapped_column(String, nullable=False)  # "tasks", "messages", "agent_tasks"
    change_type: Mapped[str] = mapped_column(String, nullable=False)  # "INSERT", "UPDATE", "DELETE"
    conditions: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # {"column": "value"} filters
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    last_triggered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    agent: Mapped["Agent"] = relationship(back_populates="triggers")
    simulation: Mapped["Simulation"] = relationship(back_populates="triggers")
    trigger_events: Mapped[list["AgentTriggerEvent"]] = relationship(back_populates="trigger")


class AgentTriggerEvent(Base):
    """Audit log of trigger activations."""

    __tablename__ = "agent_trigger_events"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
    )
    trigger_id: Mapped[UUID] = mapped_column(ForeignKey("agent_triggers.id"), nullable=False, index=True)
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id"), nullable=False, index=True)
    table_name: Mapped[str] = mapped_column(String, nullable=False)
    record_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    change_type: Mapped[str] = mapped_column(String, nullable=False)
    matched_conditions: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    agent_executed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    execution_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    execution_completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    execution_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    trigger: Mapped["AgentTrigger"] = relationship(back_populates="trigger_events")
    agent: Mapped["Agent"] = relationship()


class SimulationConfig(Base):
    """Simulation-level configuration including pause state."""

    __tablename__ = "simulation_configs"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
    )
    simulation_id: Mapped[UUID] = mapped_column(ForeignKey("simulations.id"), nullable=False, unique=True)
    is_paused: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    config_json: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    simulation: Mapped["Simulation"] = relationship(back_populates="config")
