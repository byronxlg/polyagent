"""Tests for PrincipalService."""

from uuid import uuid4

from sqlalchemy.orm import Session

from src.models import Principal
from src.services.principal_service import PrincipalService


def test_get_principals(db_session: Session, override_session_local, system_principal):
    """Test getting all principals."""
    service = PrincipalService()
    principals = service.get_principals()

    # Should have at least the system principal (created by fixture)
    assert len(principals) >= 1
    assert all(isinstance(p, Principal) for p in principals)


def test_get_principals_filter_by_type(db_session: Session, override_session_local, system_principal):
    """Test filtering principals by type."""
    # Create principals of different types
    human = Principal(username="test_human", principal_type="human")
    agent_principal = Principal(username="test_agent", principal_type="ai_agent")
    db_session.add_all([human, agent_principal])
    db_session.flush()

    service = PrincipalService()

    # Get only humans
    humans = service.get_principals(principal_type="human")
    assert len(humans) >= 1
    assert all(p.principal_type == "human" for p in humans)

    # Get only agents
    agents = service.get_principals(principal_type="ai_agent")
    assert len(agents) >= 1
    assert all(p.principal_type == "ai_agent" for p in agents)

    # Get system principals (system_principal fixture ensures at least one exists)
    systems = service.get_principals(principal_type="system")
    assert len(systems) >= 1
    assert all(p.principal_type == "system" for p in systems)


def test_get_principal(db_session: Session, override_session_local):
    """Test getting a specific principal by ID."""
    # Create a principal
    principal = Principal(username="test_principal", principal_type="human")
    db_session.add(principal)
    db_session.flush()

    service = PrincipalService()
    result = service.get_principal(principal.id)

    assert result is not None
    assert result.id == principal.id
    assert result.username == "test_principal"
    assert result.principal_type == "human"


def test_get_principal_not_found(db_session: Session, override_session_local):
    """Test getting non-existent principal returns None."""
    service = PrincipalService()
    result = service.get_principal(uuid4())

    assert result is None
