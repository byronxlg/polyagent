from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response wrapper."""

    items: list[T]
    total: int
    limit: int
    offset: int
    has_more: bool


class PrincipalCreate(BaseModel):
    username: str
    principal_type: str  # 'human', 'ai_agent', 'system'
    email: str | None = None


class PrincipalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    principal_type: str
    email: str | None
    created_at: datetime

    @field_serializer("created_at")
    def serialize_created_at(self, dt: datetime) -> str:
        return dt.isoformat() + "Z" if dt else None


class SimulationCreate(BaseModel):
    principal_id: UUID
    name: str
    description: str | None = None


class SimulationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    principal_id: UUID
    name: str
    description: str | None
    created_at: datetime

    @field_serializer("created_at")
    def serialize_created_at(self, dt: datetime) -> str:
        return dt.isoformat() + "Z" if dt else None


class SimulationUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class TaskStatus(str, Enum):
    AVAILABLE = "available"
    CLOSED = "closed"
    EXPIRED = "expired"

    @property
    def description(self) -> str:
        return _TASK_STATUS_INFO[self.value]["description"]


_TASK_STATUS_INFO = {
    "available": {"description": "Not completed and deadline not passed"},
    "closed": {"description": "Task completed"},
    "expired": {"description": "Not completed and deadline passed"},
}


class AgentTaskStatus(str, Enum):
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    DENIED = "denied"
    NOT_SELECTED = "not_selected"
    ABANDONED = "abandoned"
    LATE = "late"

    @property
    def description(self) -> str:
        return _AGENT_TASK_STATUS_INFO[self.value]["description"]

    @property
    def is_terminal(self) -> bool:
        """Whether this status is final (no further state changes possible)."""
        return _AGENT_TASK_STATUS_INFO[self.value]["terminal"]


_AGENT_TASK_STATUS_INFO = {
    "in_progress": {"description": "Currently working on task", "terminal": False},
    "submitted": {"description": "Work submitted, awaiting evaluation", "terminal": False},
    "accepted": {"description": "Submission accepted, reward paid", "terminal": True},
    "denied": {"description": "Submission explicitly rejected by evaluator", "terminal": True},
    "not_selected": {"description": "Another agent's submission was accepted", "terminal": True},
    "abandoned": {"description": "Agent gave up on task", "terminal": True},
    "late": {"description": "Submitted after deadline", "terminal": True},
}


class ModelCreate(BaseModel):
    name: str
    provider_name: str
    provider: str
    provider_model_id: str
    description: str
    is_reasoning: bool = False
    input_cost_per_million: Decimal
    output_cost_per_million: Decimal


class ModelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    provider_name: str
    provider: str
    provider_model_id: str
    description: str
    is_reasoning: bool
    input_cost_per_million: Decimal
    output_cost_per_million: Decimal


class AgentCreate(BaseModel):
    simulation_id: UUID
    model_id: UUID
    created_by_principal_id: UUID
    name: str | None = None
    initial_balance: Decimal = Decimal("0.10")
    memory_json: dict = Field(default_factory=dict)
    memory_text: str | None = None


class AgentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    simulation_id: UUID
    principal_id: UUID
    model_id: UUID
    created_by_principal_id: UUID
    name: str | None = None
    public_profile: str | None = None
    memory_json: dict | None = None
    memory_text: str | None = None
    is_running: bool
    created_at: datetime

    @field_serializer("created_at")
    def serialize_created_at(self, dt: datetime) -> str:
        return dt.isoformat() + "Z" if dt else None

    @field_serializer("memory_json")
    def serialize_memory_json(self, memory: dict | None) -> dict:
        return memory if memory is not None else {}


class AgentUpdate(BaseModel):
    name: str | None = None
    public_profile: str | None = None


class AgentBalanceResponse(BaseModel):
    agent_id: UUID
    balance: Decimal


class TaskCreate(BaseModel):
    simulation_id: UUID
    created_by_principal_id: UUID
    description: str
    reward_dollars: Decimal
    deadline: datetime


class TaskUpdate(BaseModel):
    deadline: datetime | None = None
    status: TaskStatus | None = None


class AgentTaskSummary(BaseModel):
    """Summary of an AgentTask for embedding in TaskResponse."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agent_id: UUID
    status: AgentTaskStatus
    created_at: datetime
    submitted_at: datetime | None = None

    @field_serializer("created_at", "submitted_at")
    def serialize_dt(self, dt: datetime | None) -> str | None:
        return dt.isoformat() + "Z" if dt else None


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    simulation_id: UUID
    created_by_principal_id: UUID
    description: str
    reward_dollars: Decimal
    deadline: datetime
    status: TaskStatus
    created_at: datetime
    closed_at: datetime | None = None
    agent_tasks: list[AgentTaskSummary] = []

    @field_serializer("deadline", "created_at", "closed_at")
    def serialize_dt(self, dt: datetime | None) -> str | None:
        return dt.isoformat() + "Z" if dt else None


class AgentTaskCreate(BaseModel):
    task_id: UUID
    agent_id: UUID


class AgentTaskSubmit(BaseModel):
    result: str


class AgentTaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    task_id: UUID
    agent_id: UUID
    status: AgentTaskStatus
    result: str | None = None
    created_at: datetime
    submitted_at: datetime | None = None

    @field_serializer("created_at", "submitted_at")
    def serialize_dt(self, dt: datetime | None) -> str | None:
        return dt.isoformat() + "Z" if dt else None


class TransactionCreate(BaseModel):
    from_principal_id: UUID | None = None
    to_principal_id: UUID | None = None
    amount: Decimal
    reason: str
    reference_id: UUID | None = None


class TransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    from_principal_id: UUID | None
    to_principal_id: UUID | None
    amount: Decimal
    reason: str
    reference_id: UUID | None
    timestamp: datetime

    @field_serializer("timestamp")
    def serialize_timestamp(self, dt: datetime) -> str:
        return dt.isoformat() + "Z" if dt else None


class MessageCreate(BaseModel):
    from_principal_id: UUID
    to_principal_id: UUID
    content: str


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    from_principal_id: UUID
    to_principal_id: UUID
    content: str
    sent_at: datetime
    received_at: datetime | None = None

    @field_serializer("sent_at", "received_at")
    def serialize_dt(self, dt: datetime | None) -> str | None:
        return dt.isoformat() + "Z" if dt else None


class SimulationSetup(BaseModel):
    num_agents: int = 3
    starting_balance: Decimal = Decimal("0.10")
    model_name: str = "gpt-5-mini"
    task_description: str = "Write a haiku about artificial intelligence"
    task_reward: Decimal = Decimal("0.05")


class SimulationStatus(BaseModel):
    agents_count: int
    tasks_count: int
    pending_submissions: int
    total_transactions: int


class AgentToolUsageCreate(BaseModel):
    agent_id: UUID
    tool_id: UUID
    input: str
    output: str


class AgentToolUsageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agent_id: UUID
    tool_id: UUID
    agent_task_id: UUID | None = None
    tool_name: str
    input: str
    output: str
    timestamp: datetime

    @field_serializer("timestamp")
    def serialize_timestamp(self, dt: datetime) -> str:
        return dt.isoformat() + "Z" if dt else None


class AgentModelUsageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agent_id: UUID
    model_id: UUID
    agent_task_id: UUID | None = None
    input_tokens: int
    output_tokens: int
    total_cost: Decimal
    input: str
    output: str
    timestamp: datetime

    @field_serializer("timestamp")
    def serialize_timestamp(self, dt: datetime) -> str:
        return dt.isoformat() + "Z" if dt else None


class ToolResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str
    category: str | None
    scope: str  # local, internal, external
    created_by_principal_id: UUID


class ActivityType(str, Enum):
    AGENT_TASK = "agent_task"
    MESSAGE = "message"
    TRANSACTION = "transaction"
    TOOL_USAGE = "tool_usage"
    MODEL_USAGE = "model_usage"


class ActivityItem(BaseModel):
    """A single activity item in the unified feed."""

    id: str  # Prefixed with type, e.g. "at-1", "msg-2"
    type: ActivityType
    timestamp: str
    agent_id: UUID | None
    data: dict  # Full entity data


class ActivityResponse(BaseModel):
    """Paginated activity feed response."""

    items: list[ActivityItem]
    total: int
    limit: int
    offset: int
    has_more: bool
