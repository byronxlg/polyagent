"""Pytest fixtures for API testing."""

import contextlib
from collections.abc import Generator
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.database import DATABASE_URL, Base


class NonClosingSessionWrapper:
    """Wraps a session but ignores close() calls from services.

    Services create their own SessionLocal() instances and call close() on them.
    We need to prevent close() from actually closing the test session so that
    transaction rollback works at the end of each test.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def close(self) -> None:
        """Ignore close calls - we rollback at test end."""

    def __getattr__(self, name: str) -> Any:  # noqa: ANN401
        return getattr(self._session, name)


@pytest.fixture(scope="session")
def test_engine():
    """Create test database engine once per session."""
    engine = create_engine(DATABASE_URL, echo=False)
    Base.metadata.create_all(bind=engine)
    return engine


@pytest.fixture
def db_session(test_engine) -> Generator[Session, None, None]:
    """Create a fresh database session for each test with rollback.

    Uses a nested transaction pattern:
    1. Begin outer transaction on connection
    2. Test runs using this connection
    3. Rollback at end restores database state
    """
    connection = test_engine.connect()
    transaction = connection.begin()

    test_session_local = sessionmaker(autocommit=False, autoflush=False, bind=connection)
    session = test_session_local()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def override_session_local(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    """Override SessionLocal in all modules that import it.

    This ensures services use our test session instead of creating their own.
    """

    def get_wrapped_session() -> NonClosingSessionWrapper:
        return NonClosingSessionWrapper(db_session)

    # Patch SessionLocal in all modules that import it
    modules_to_patch = [
        "src.database",
        "src.api",
        "src.services.transaction_service",
        "src.services.task_service",
        "src.services.tool_service",
        "src.services.message_service",
        "src.services.agent_service",
        "src.services.activity_service",
        "src.services.principal_service",
        "src.services.usage_service",
    ]

    for module in modules_to_patch:
        with contextlib.suppress(AttributeError):
            monkeypatch.setattr(f"{module}.SessionLocal", get_wrapped_session)


@pytest.fixture
def client(
    db_session: Session, override_session_local: None
) -> Generator[TestClient, None, None]:
    """Create test client with overridden database session."""
    from src.api import app, get_db

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client

    app.dependency_overrides.clear()


# Entity fixtures


@pytest.fixture
def system_principal(db_session: Session):
    """Get or create system principal required for tool registration."""
    from src.models import Principal

    # Check if system principal already exists
    existing = (
        db_session.query(Principal)
        .filter(Principal.principal_type == "system")
        .first()
    )
    if existing:
        return existing

    principal = Principal(
        username="system",
        principal_type="system",
        email=None,
    )
    db_session.add(principal)
    db_session.flush()
    return principal


@pytest.fixture
def human_principal(db_session: Session):
    """Create a human principal for testing."""
    from src.models import Principal

    principal = Principal(
        username="test_human",
        principal_type="human",
        email="test@example.com",
    )
    db_session.add(principal)
    db_session.flush()
    return principal


@pytest.fixture
def simulation(db_session: Session, human_principal):
    """Create a test simulation."""
    from src.models import Simulation

    sim = Simulation(
        principal_id=human_principal.id,
        name="Test Simulation",
        description="A test simulation",
    )
    db_session.add(sim)
    db_session.flush()
    return sim


@pytest.fixture
def model(db_session: Session):
    """Create a test LLM model."""
    from src.models import Model

    m = Model(
        name="Test Model",
        provider_name="Test Provider",
        provider="test",
        provider_model_id="test-model-1",
        description="A test model",
        is_reasoning=False,
        input_cost_per_million=Decimal("1.00"),
        output_cost_per_million=Decimal("2.00"),
    )
    db_session.add(m)
    db_session.flush()
    return m


@pytest.fixture
def agent(db_session: Session, simulation, model, human_principal):
    """Create a test agent with its associated principal."""
    from src.models import Agent, Principal

    # Create agent's principal
    agent_principal = Principal(
        username="test_agent_principal",
        principal_type="ai_agent",
    )
    db_session.add(agent_principal)
    db_session.flush()

    agent = Agent(
        simulation_id=simulation.id,
        principal_id=agent_principal.id,
        model_id=model.id,
        created_by_principal_id=human_principal.id,
        name="Test Agent",
    )
    db_session.add(agent)
    db_session.flush()
    return agent


@pytest.fixture
def agent_with_balance(agent, db_session: Session):
    """Create an agent with initial balance via transaction."""
    from src.models import Transaction

    tx = Transaction(
        from_principal_id=None,
        to_principal_id=agent.principal_id,
        amount=Decimal("0.10"),
        reason="initial_balance",
    )
    db_session.add(tx)
    db_session.flush()
    return agent


@pytest.fixture
def task(db_session: Session, simulation, human_principal):
    """Create a test task."""
    from src.models import Task

    t = Task(
        simulation_id=simulation.id,
        created_by_principal_id=human_principal.id,
        description="Test task description",
        reward_dollars=Decimal("0.05"),
        deadline=datetime.utcnow() + timedelta(days=1),
    )
    db_session.add(t)
    db_session.flush()
    return t


@pytest.fixture
def expired_task(db_session: Session, simulation, human_principal):
    """Create an expired test task."""
    from src.models import Task

    t = Task(
        simulation_id=simulation.id,
        created_by_principal_id=human_principal.id,
        description="Expired task",
        reward_dollars=Decimal("0.05"),
        deadline=datetime.utcnow() - timedelta(days=1),
    )
    db_session.add(t)
    db_session.flush()
    return t
