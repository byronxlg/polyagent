from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from src.agent.agent import Agent as AgentExecutor
from src.database import SessionLocal
from src.models import (
    Agent,
    AgentModelUsage,
    AgentServer,
    AgentTask,
    AgentToolUsage,
    AgentTrigger,
    AgentTriggerEvent,
    Message,
    Model,
    Principal,
    Simulation,
    SimulationConfig,
    Task,
    Transaction,
)
from src.schemas import (
    ActivityResponse,
    AgentBalanceResponse,
    AgentCreate,
    AgentModelUsageResponse,
    AgentResponse,
    AgentTaskResponse,
    AgentToolUsageResponse,
    AgentTriggerEventResponse,
    AgentTriggerResponse,
    AgentUpdate,
    MessageCreate,
    MessageResponse,
    ModelCreate,
    ModelResponse,
    PaginatedResponse,
    PrincipalCreate,
    PrincipalResponse,
    ServerResponse,
    SimulationConfigResponse,
    SimulationCreate,
    SimulationResponse,
    SimulationUpdate,
    TaskCreate,
    TaskResponse,
    TaskUpdate,
    TransactionResponse,
)
from src.services.activity_service import ActivityService
from src.services.message_service import MessageService
from src.services.server_service import ServerService
from src.services.task_service import TaskService
from src.services.transaction_service import TransactionService
from src.services.trigger_service import SimulationConfigService, TriggerService

DEFAULT_TRIGGER_SUBSCRIPTIONS = [
    # Notify when new tasks are created
    {"table_name": "tasks", "change_type": "INSERT", "conditions": None},
    # Notify when messages are sent to this agent (condition added dynamically)
    {"table_name": "messages", "change_type": "INSERT", "conditions": "SELF_MESSAGES"},
]

DEFAULT_LIMIT = 30

app = FastAPI(title="PolyAgent API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/health")
def health_check(db: Session = Depends(get_db)) -> dict:
    """Health check endpoint for container orchestration."""
    try:
        db.execute(text("SELECT 1"))
        return {"status": "healthy"}
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Database unavailable") from None


@app.on_event("startup")
def startup() -> None:
    """Grant system servers to all existing agents on startup.

    Server records are created via seed data migration.
    """
    server_service = ServerService()
    db = SessionLocal()
    try:
        # Grant system servers to all existing agents that don't have them
        agent_ids = [agent.id for agent in db.query(Agent).all()]
    finally:
        db.close()
    for agent_id in agent_ids:
        server_service.grant_system_servers(agent_id)


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "PolyAgent API", "version": "0.1.0"}


@app.post("/principals", response_model=PrincipalResponse, tags=["Principals"])
def create_principal(principal: PrincipalCreate, db: Session = Depends(get_db)) -> Principal:
    db_principal = Principal(
        username=principal.username,
        email=principal.email,
        principal_type=principal.principal_type,
    )
    db.add(db_principal)
    db.commit()
    db.refresh(db_principal)
    return db_principal


@app.get("/principals", response_model=PaginatedResponse[PrincipalResponse], tags=["Principals"])
def list_principals(limit: int = DEFAULT_LIMIT, offset: int = 0, db: Session = Depends(get_db)) -> dict:
    total = db.query(Principal).count()
    principals = db.query(Principal).order_by(Principal.id.desc()).limit(limit).offset(offset).all()
    return {
        "items": principals,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(principals) < total,
    }


@app.get("/principals/{principal_id}", response_model=PrincipalResponse, tags=["Principals"])
def get_principal(principal_id: UUID, db: Session = Depends(get_db)) -> Principal:
    principal = db.query(Principal).filter(Principal.id == principal_id).first()
    if not principal:
        raise HTTPException(status_code=404, detail="Principal not found")
    return principal


@app.post("/simulations", response_model=SimulationResponse, tags=["Simulations"])
def create_simulation(simulation: SimulationCreate, db: Session = Depends(get_db)) -> Simulation:
    db_simulation = Simulation(
        principal_id=simulation.principal_id,
        name=simulation.name,
        description=simulation.description,
        created_at=datetime.utcnow(),
    )
    db.add(db_simulation)
    db.commit()
    db.refresh(db_simulation)
    return db_simulation


@app.get("/simulations", response_model=PaginatedResponse[SimulationResponse], tags=["Simulations"])
def list_simulations(limit: int = DEFAULT_LIMIT, offset: int = 0, db: Session = Depends(get_db)) -> dict:
    total = db.query(Simulation).count()
    items = db.query(Simulation).offset(offset).limit(limit).all()
    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(items) < total,
    }


@app.get("/simulations/{simulation_id}", response_model=SimulationResponse, tags=["Simulations"])
def get_simulation(simulation_id: UUID, db: Session = Depends(get_db)) -> Simulation:
    simulation = db.query(Simulation).filter(Simulation.id == simulation_id).first()
    if not simulation:
        raise HTTPException(status_code=404, detail="Simulation not found")
    return simulation


@app.patch("/simulations/{simulation_id}", response_model=SimulationResponse, tags=["Simulations"])
def update_simulation(
    simulation_id: UUID, update: SimulationUpdate, db: Session = Depends(get_db)
) -> Simulation:
    simulation = db.query(Simulation).filter(Simulation.id == simulation_id).first()
    if not simulation:
        raise HTTPException(status_code=404, detail="Simulation not found")
    if update.name is not None:
        simulation.name = update.name
    if update.description is not None:
        simulation.description = update.description
    db.commit()
    db.refresh(simulation)
    return simulation


@app.delete("/simulations/{simulation_id}", tags=["Simulations"])
def delete_simulation(simulation_id: UUID, db: Session = Depends(get_db)) -> dict[str, str]:
    """Delete a simulation. Fails if agents or tasks exist in it."""
    simulation = db.query(Simulation).filter(Simulation.id == simulation_id).first()
    if not simulation:
        raise HTTPException(status_code=404, detail="Simulation not found")
    # Check if any agents exist in this simulation
    agent_count = db.query(Agent).filter(Agent.simulation_id == simulation_id).count()
    if agent_count > 0:
        raise HTTPException(
            status_code=400, detail=f"Cannot delete simulation: {agent_count} agents exist in it"
        )
    # Check if any tasks exist in this simulation
    task_count = db.query(Task).filter(Task.simulation_id == simulation_id).count()
    if task_count > 0:
        raise HTTPException(status_code=400, detail=f"Cannot delete simulation: {task_count} tasks exist in it")
    db.delete(simulation)
    db.commit()
    return {"message": "Simulation deleted"}


@app.post("/models", response_model=ModelResponse, tags=["Models"])
def create_model(model: ModelCreate, db: Session = Depends(get_db)) -> Model:
    db_model = Model(**model.model_dump())
    db.add(db_model)
    db.commit()
    db.refresh(db_model)
    return db_model


@app.get("/models", response_model=PaginatedResponse[ModelResponse], tags=["Models"])
def list_models(limit: int = DEFAULT_LIMIT, offset: int = 0, db: Session = Depends(get_db)) -> dict:
    total = db.query(Model).count()
    items = db.query(Model).offset(offset).limit(limit).all()
    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(items) < total,
    }


@app.get("/models/{model_id}", response_model=ModelResponse, tags=["Models"])
def get_model(model_id: UUID, db: Session = Depends(get_db)) -> Model:
    model = db.query(Model).filter(Model.id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    return model


@app.delete("/models/{model_id}", tags=["Models"])
def delete_model(model_id: UUID, db: Session = Depends(get_db)) -> dict[str, str]:
    """Delete a model. Fails if agents are using it."""
    model = db.query(Model).filter(Model.id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    # Check if any agents use this model
    agent_count = db.query(Agent).filter(Agent.model_id == model_id).count()
    if agent_count > 0:
        raise HTTPException(status_code=400, detail=f"Cannot delete model: {agent_count} agents are using it")
    db.delete(model)
    db.commit()
    return {"message": "Model deleted"}


@app.post("/agents", response_model=AgentResponse, tags=["Agents"])
def create_agent(agent: AgentCreate, db: Session = Depends(get_db)) -> Agent:
    # Create a Principal for this AI agent with unique username
    # Use agent name as base, append UUID to ensure uniqueness
    base_name = agent.name or "Agent"
    unique_username = f"{base_name}_{uuid4().hex[:8]}"

    principal = Principal(
        username=unique_username,
        principal_type="ai_agent",
        email=None,
        created_at=datetime.utcnow(),
    )
    db.add(principal)
    db.flush()  # Get the principal ID without committing yet

    # Create the Agent record linked to the Principal
    db_agent = Agent(
        simulation_id=agent.simulation_id,
        principal_id=principal.id,
        model_id=agent.model_id,
        created_by_principal_id=agent.created_by_principal_id,
        name=agent.name,
        memory_json=agent.memory_json,
        memory_text=agent.memory_text,
        created_at=datetime.utcnow(),
    )
    db.add(db_agent)
    db.commit()
    db.refresh(db_agent)

    # Grant initial balance via transaction ledger (uses its own session)
    if agent.initial_balance > 0:
        transaction_service = TransactionService()
        transaction_service.grant_dollars(
            to_agent_id=db_agent.id,
            amount=agent.initial_balance,
            reason="initial_balance",
        )

    # Grant system servers (uses its own session)
    server_service = ServerService()
    server_service.grant_system_servers(db_agent.id)

    # Create default trigger subscriptions
    trigger_service = TriggerService()
    for trigger_config in DEFAULT_TRIGGER_SUBSCRIPTIONS:
        conditions = trigger_config["conditions"]
        # Handle special marker for self-referencing conditions
        if conditions == "SELF_MESSAGES":
            conditions = {"to_principal_id": str(principal.id)}
        trigger_service.create_subscription(
            agent_id=db_agent.id,
            table_name=trigger_config["table_name"],
            change_type=trigger_config["change_type"],
            conditions=conditions,
        )

    return db_agent


@app.get("/agents", response_model=PaginatedResponse[AgentResponse], tags=["Agents"])
def list_agents(limit: int = DEFAULT_LIMIT, offset: int = 0, db: Session = Depends(get_db)) -> dict:
    total = db.query(Agent).count()
    items = db.query(Agent).offset(offset).limit(limit).all()
    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(items) < total,
    }


@app.get("/agents/{agent_id}", response_model=AgentResponse, tags=["Agents"])
def get_agent(agent_id: UUID, db: Session = Depends(get_db)) -> Agent:
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@app.patch("/agents/{agent_id}", response_model=AgentResponse, tags=["Agents"])
def update_agent(agent_id: UUID, update: AgentUpdate, db: Session = Depends(get_db)) -> Agent:
    """Update an agent's profile (name and/or public_profile)."""
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    if update.name is not None:
        agent.name = update.name
    if update.public_profile is not None:
        agent.public_profile = update.public_profile
    db.commit()
    db.refresh(agent)
    return agent


@app.delete("/agents/{agent_id}", tags=["Agents"])
def delete_agent(agent_id: UUID, db: Session = Depends(get_db)) -> dict[str, str]:
    """Delete an agent and all related data."""
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    # Delete related data in order (respecting foreign key constraints)
    db.query(AgentToolUsage).filter(AgentToolUsage.agent_id == agent_id).delete()
    db.query(AgentModelUsage).filter(AgentModelUsage.agent_id == agent_id).delete()
    # For Transaction and Message, convert agent_id to principal_id for filtering
    db.query(Transaction).filter(
        (Transaction.from_principal_id == agent.principal_id)
        | (Transaction.to_principal_id == agent.principal_id)
    ).delete(synchronize_session=False)
    db.query(Message).filter(
        (Message.from_principal_id == agent.principal_id) | (Message.to_principal_id == agent.principal_id)
    ).delete(synchronize_session=False)
    db.query(AgentTask).filter(AgentTask.agent_id == agent_id).delete()
    db.query(AgentServer).filter(AgentServer.agent_id == agent_id).delete()
    # Delete trigger events first (references agent_triggers), then triggers
    db.query(AgentTriggerEvent).filter(AgentTriggerEvent.agent_id == agent_id).delete()
    db.query(AgentTrigger).filter(AgentTrigger.agent_id == agent_id).delete()
    db.delete(agent)
    db.commit()
    return {"message": "Agent deleted"}


@app.get("/agents/{agent_id}/balance", response_model=AgentBalanceResponse, tags=["Agents"])
def get_agent_balance(agent_id: UUID) -> dict[str, UUID | Decimal]:
    transaction_service = TransactionService()
    balance = transaction_service.get_balance(agent_id)
    return {"agent_id": agent_id, "balance": balance}


@app.get("/agents/{agent_id}/servers", response_model=list[ServerResponse], tags=["Agents"])
def get_agent_servers(agent_id: UUID, db: Session = Depends(get_db)) -> list:
    """Get all MCP servers granted to an agent."""
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    server_service = ServerService()
    return server_service.get_servers_for_agent(agent_id)


def _execute_single_agent(agent_id: UUID) -> dict[str, str | UUID]:
    """Execute a single agent autonomously.

    This function is designed to be called from a thread pool for parallel execution.
    Each agent manages its own database sessions internally.
    """
    try:
        executor = AgentExecutor(agent_id)
        balance = executor.get_balance()

        if balance < 0:
            return {"agent_id": agent_id, "status": "skipped", "message": "Agent is in debt"}

        result = executor.think()

        max_result_length = 100
        truncated_result = result[:max_result_length] + "..." if len(result) > max_result_length else result
        return {"agent_id": agent_id, "status": "success", "result": truncated_result}
    except Exception as e:  # noqa: BLE001
        return {"agent_id": agent_id, "status": "error", "message": str(e)}


def trigger_all_agents() -> None:
    """Background task to trigger all agents to think in parallel."""
    db = SessionLocal()
    try:
        agent_ids = [agent.id for agent in db.query(Agent).all()]
    finally:
        db.close()

    if not agent_ids:
        return

    # Execute all agents in parallel using a thread pool
    with ThreadPoolExecutor(max_workers=len(agent_ids)) as executor:
        futures = [executor.submit(_execute_single_agent, agent_id) for agent_id in agent_ids]
        # Wait for all to complete (results are discarded in background task)
        for future in as_completed(futures):
            future.result()  # This will re-raise any exception from the thread


@app.post("/tasks", response_model=TaskResponse, tags=["Tasks"])
def create_task(task: TaskCreate) -> Task:
    task_service = TaskService()
    return task_service.create_task(
        simulation_id=task.simulation_id,
        created_by_principal_id=task.created_by_principal_id,
        description=task.description,
        reward_dollars=task.reward_dollars,
        deadline=task.deadline,
    )


@app.get("/tasks", response_model=PaginatedResponse[TaskResponse], tags=["Tasks"])
def list_tasks(
    *,
    available_only: bool = False,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> dict:
    query = db.query(Task).options(selectinload(Task.agent_tasks))
    if available_only:
        now = datetime.utcnow()
        query = query.filter(Task.is_completed == False, Task.deadline > now)  # noqa: E712
    total = query.count()
    items = query.offset(offset).limit(limit).all()
    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(items) < total,
    }


@app.get("/tasks/{task_id}", response_model=TaskResponse, tags=["Tasks"])
def get_task(task_id: UUID, db: Session = Depends(get_db)) -> Task:
    task = db.query(Task).options(selectinload(Task.agent_tasks)).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.patch("/tasks/{task_id}", response_model=TaskResponse, tags=["Tasks"])
def update_task(task_id: UUID, task_update: TaskUpdate, db: Session = Depends(get_db)) -> Task:
    task = db.query(Task).options(selectinload(Task.agent_tasks)).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task_update.deadline is not None:
        task.deadline = task_update.deadline

    if task_update.status is not None:
        if task_update.status.value == "closed":
            task.is_completed = True
            task.closed_at = datetime.utcnow()
        elif task_update.status.value == "available":
            task.is_completed = False
            task.closed_at = None

    db.commit()
    db.refresh(task)
    return task


@app.get("/agent-tasks", response_model=PaginatedResponse[AgentTaskResponse], tags=["Agent Tasks"])
def list_agent_tasks(
    agent_id: UUID | None = None,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> dict:
    query = db.query(AgentTask)
    if agent_id:
        query = query.filter(AgentTask.agent_id == agent_id)
    total = query.count()
    items = query.offset(offset).limit(limit).all()
    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(items) < total,
    }


@app.get("/agent-tasks/{agent_task_id}", response_model=AgentTaskResponse, tags=["Agent Tasks"])
def get_agent_task(agent_task_id: UUID, db: Session = Depends(get_db)) -> AgentTask:
    agent_task = db.query(AgentTask).filter(AgentTask.id == agent_task_id).first()
    if not agent_task:
        raise HTTPException(status_code=404, detail="AgentTask not found")
    return agent_task


@app.post("/agent-tasks/{agent_task_id}/accept", response_model=AgentTaskResponse, tags=["Agent Tasks"])
def accept_submission(agent_task_id: UUID) -> AgentTask:
    """Accept an agent's task submission and award them the reward."""
    task_service = TaskService()
    try:
        return task_service.accept_submission(agent_task_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.post("/agent-tasks/{agent_task_id}/deny", response_model=AgentTaskResponse, tags=["Agent Tasks"])
def deny_submission(agent_task_id: UUID) -> AgentTask:
    """Deny an agent's task submission."""
    task_service = TaskService()
    try:
        return task_service.deny_submission(agent_task_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.get("/transactions", response_model=PaginatedResponse[TransactionResponse], tags=["Transactions"])
def list_transactions(
    agent_id: UUID | None = None,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> dict:
    query = db.query(Transaction)
    if agent_id:
        # Convert agent_id to principal_id for filtering
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        query = query.filter(
            (Transaction.from_principal_id == agent.principal_id)
            | (Transaction.to_principal_id == agent.principal_id)
        )
    total = query.count()
    items = query.order_by(Transaction.timestamp.desc()).offset(offset).limit(limit).all()
    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(items) < total,
    }


@app.get("/messages", response_model=PaginatedResponse[MessageResponse], tags=["Messages"])
def list_messages(
    agent_id: UUID | None = None,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> dict:
    query = db.query(Message)
    if agent_id:
        # Convert agent_id to principal_id for filtering
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        query = query.filter(
            (Message.from_principal_id == agent.principal_id) | (Message.to_principal_id == agent.principal_id)
        )
    total = query.count()
    items = query.order_by(Message.sent_at.desc()).offset(offset).limit(limit).all()
    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(items) < total,
    }


@app.get("/agents/{agent_id}/inbox", response_model=list[MessageResponse], tags=["Messages"])
def get_inbox(agent_id: UUID, db: Session = Depends(get_db)) -> list[Message]:
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    message_service = MessageService()
    return message_service.get_inbox(agent.principal_id)


@app.post("/messages", response_model=MessageResponse, tags=["Messages"])
def send_message(message: MessageCreate) -> Message:
    """Send a message from one principal to another."""
    message_service = MessageService()
    return message_service.send_message(
        from_principal_id=message.from_principal_id,
        to_principal_id=message.to_principal_id,
        content=message.content,
    )


@app.post("/agents/{agent_id}/tick", tags=["Agent Execution"])
def agent_tick(agent_id: UUID, db: Session = Depends(get_db)) -> dict[str, str]:
    """Trigger an agent to think and take action autonomously."""
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    try:
        executor = AgentExecutor(agent_id)
        result = executor.think()
        return {"message": "Agent executed successfully", "result": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent execution failed: {e!s}") from e


@app.post("/agents/tick-all-background", tags=["Agent Execution"])
def tick_all_agents_background(background_tasks: BackgroundTasks) -> dict[str, str]:
    """Trigger all agents to think in the background. Returns immediately."""
    background_tasks.add_task(trigger_all_agents)
    return {"message": "All agents triggered in background"}


@app.post("/agents/tick-all", tags=["Agent Execution"])
def tick_all_agents(db: Session = Depends(get_db)) -> dict[str, list[dict[str, str | UUID]]]:
    """Trigger all agents to think and take action autonomously in parallel."""
    agent_ids = [agent.id for agent in db.query(Agent).all()]

    if not agent_ids:
        return {"results": []}

    # Execute all agents in parallel using a thread pool
    with ThreadPoolExecutor(max_workers=len(agent_ids)) as executor:
        futures = [executor.submit(_execute_single_agent, agent_id) for agent_id in agent_ids]
        results = [future.result() for future in as_completed(futures)]

    # Sort results by agent_id for consistent ordering
    results.sort(key=lambda x: x["agent_id"])
    return {"results": results}


@app.get("/agent-tool-usage", response_model=PaginatedResponse[AgentToolUsageResponse], tags=["Usage"])
def list_agent_tool_usage(
    agent_id: UUID | None = None,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> dict:
    query = db.query(AgentToolUsage)
    if agent_id:
        query = query.filter(AgentToolUsage.agent_id == agent_id)

    total = query.count()
    items = query.order_by(AgentToolUsage.timestamp.desc()).offset(offset).limit(limit).all()

    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(items) < total,
    }


@app.get("/agent-model-usage", response_model=PaginatedResponse[AgentModelUsageResponse], tags=["Usage"])
def list_agent_model_usage(
    agent_id: UUID | None = None,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> dict:
    query = db.query(AgentModelUsage)
    if agent_id:
        query = query.filter(AgentModelUsage.agent_id == agent_id)
    total = query.count()
    items = query.order_by(AgentModelUsage.timestamp.desc()).offset(offset).limit(limit).all()
    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(items) < total,
    }


@app.delete("/reset", tags=["Simulation"])
def reset_simulation(db: Session = Depends(get_db)) -> dict[str, str]:
    """Reset simulation data while preserving servers and models."""
    # Delete in order to respect foreign key constraints
    db.query(AgentToolUsage).delete()
    db.query(AgentModelUsage).delete()
    db.query(Transaction).delete()
    db.query(Message).delete()
    db.query(AgentTask).delete()
    db.query(AgentServer).delete()
    db.query(Agent).delete()
    db.query(Task).delete()
    db.commit()
    return {"message": "Simulation reset successfully"}


@app.get("/activity", response_model=ActivityResponse, tags=["Activity"])
def get_activity(
    agent_id: UUID | None = None,
    types: str | None = None,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> dict:
    """Get unified activity feed combining all activity types."""
    type_list = types.split(",") if types else None
    activity_service = ActivityService(db)
    items, total = activity_service.get_activity(
        limit=limit,
        offset=offset,
        agent_id=agent_id,
        types=type_list,
    )
    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(items) < total,
    }


# Trigger System Endpoints


@app.get("/simulations/{simulation_id}/config", response_model=SimulationConfigResponse, tags=["Triggers"])
def get_simulation_config(simulation_id: UUID, _db: Session = Depends(get_db)) -> SimulationConfig:
    """Get simulation configuration including pause state."""
    config_service = SimulationConfigService()
    return config_service.get_or_create_config(simulation_id)


@app.post("/simulations/{simulation_id}/pause", response_model=SimulationConfigResponse, tags=["Triggers"])
def pause_simulation(simulation_id: UUID, db: Session = Depends(get_db)) -> SimulationConfig:
    """Pause automatic agent triggering for a simulation.

    When paused, the trigger worker will not execute agents in this simulation,
    even if their trigger conditions are met.
    """
    # Verify simulation exists
    simulation = db.query(Simulation).filter(Simulation.id == simulation_id).first()
    if not simulation:
        raise HTTPException(status_code=404, detail="Simulation not found")

    config_service = SimulationConfigService()
    return config_service.pause_simulation(simulation_id)


@app.post("/simulations/{simulation_id}/resume", response_model=SimulationConfigResponse, tags=["Triggers"])
def resume_simulation(simulation_id: UUID, db: Session = Depends(get_db)) -> SimulationConfig:
    """Resume automatic agent triggering for a simulation."""
    # Verify simulation exists
    simulation = db.query(Simulation).filter(Simulation.id == simulation_id).first()
    if not simulation:
        raise HTTPException(status_code=404, detail="Simulation not found")

    config_service = SimulationConfigService()
    return config_service.resume_simulation(simulation_id)


@app.get("/agents/{agent_id}/triggers", response_model=list[AgentTriggerResponse], tags=["Triggers"])
def list_agent_triggers(
    agent_id: UUID,
    db: Session = Depends(get_db),
    *,
    include_inactive: bool = Query(default=False),
) -> list[AgentTrigger]:
    """List an agent's trigger subscriptions."""
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    trigger_service = TriggerService()
    is_active = None if include_inactive else True
    return trigger_service.list_subscriptions(agent_id=agent_id, is_active=is_active)


@app.get(
    "/trigger-events",
    response_model=PaginatedResponse[AgentTriggerEventResponse],
    tags=["Triggers"],
)
def list_trigger_events(
    agent_id: UUID | None = None,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> dict:
    """List recent trigger events for debugging and monitoring."""
    query = db.query(AgentTriggerEvent)
    if agent_id:
        query = query.filter(AgentTriggerEvent.agent_id == agent_id)

    total = query.count()
    items = query.order_by(AgentTriggerEvent.created_at.desc()).offset(offset).limit(limit).all()

    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(items) < total,
    }
