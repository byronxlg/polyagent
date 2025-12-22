"""Tests for ToolService."""

import pytest
from sqlalchemy.orm import Session

from src.models import Agent, AgentTool, Principal, Tool
from src.services.tool_service import ToolService


def test_get_granted_tool_names_empty(db_session: Session, agent, override_session_local):
    """Test getting granted tools when none are granted."""
    service = ToolService()
    tool_names = service.get_granted_tool_names(agent.id)

    assert tool_names == set()


def test_get_granted_tool_names(db_session: Session, agent, system_principal, override_session_local):
    """Test getting granted tool names."""
    # Create a tool
    tool = Tool(
        name="test_tool",
        description="A test tool",
        category="test",
        scope="local",
        created_by_principal_id=system_principal.id,
    )
    db_session.add(tool)
    db_session.flush()

    # Grant the tool to the agent
    agent_tool = AgentTool(agent_id=agent.id, tool_id=tool.id)
    db_session.add(agent_tool)
    db_session.flush()

    service = ToolService()
    tool_names = service.get_granted_tool_names(agent.id)

    assert "test_tool" in tool_names


def test_grant_tool(db_session: Session, agent, system_principal, override_session_local):
    """Test granting a tool to an agent."""
    # Create a tool
    tool = Tool(
        name="test_tool",
        description="A test tool",
        category="test",
        scope="local",
        created_by_principal_id=system_principal.id,
    )
    db_session.add(tool)
    db_session.flush()

    service = ToolService()
    agent_tool = service.grant_tool(agent.id, tool.id)

    assert agent_tool.agent_id == agent.id
    assert agent_tool.tool_id == tool.id

    # Verify it's now granted
    tool_names = service.get_granted_tool_names(agent.id)
    assert "test_tool" in tool_names


def test_grant_tool_idempotent(db_session: Session, agent, system_principal, override_session_local):
    """Test granting the same tool twice is idempotent."""
    # Create a tool
    tool = Tool(
        name="test_tool",
        description="A test tool",
        category="test",
        scope="local",
        created_by_principal_id=system_principal.id,
    )
    db_session.add(tool)
    db_session.flush()

    service = ToolService()

    # Grant twice
    agent_tool1 = service.grant_tool(agent.id, tool.id)
    agent_tool2 = service.grant_tool(agent.id, tool.id)

    # Should return the same grant
    assert agent_tool1.id == agent_tool2.id


def test_revoke_tool(db_session: Session, agent, system_principal, override_session_local):
    """Test revoking a tool from an agent."""
    # Create and grant a tool
    tool = Tool(
        name="test_tool",
        description="A test tool",
        category="test",
        scope="local",
        created_by_principal_id=system_principal.id,
    )
    db_session.add(tool)
    db_session.flush()

    agent_tool = AgentTool(agent_id=agent.id, tool_id=tool.id)
    db_session.add(agent_tool)
    db_session.flush()

    service = ToolService()

    # Verify it's granted
    assert "test_tool" in service.get_granted_tool_names(agent.id)

    # Revoke
    result = service.revoke_tool(agent.id, tool.id)
    assert result is True

    # Verify it's no longer granted
    assert "test_tool" not in service.get_granted_tool_names(agent.id)


def test_revoke_tool_not_granted(db_session: Session, agent, system_principal, override_session_local):
    """Test revoking a tool that wasn't granted returns False."""
    # Create a tool but don't grant it
    tool = Tool(
        name="test_tool",
        description="A test tool",
        category="test",
        scope="local",
        created_by_principal_id=system_principal.id,
    )
    db_session.add(tool)
    db_session.flush()

    service = ToolService()
    result = service.revoke_tool(agent.id, tool.id)

    assert result is False


def test_grant_all_tools(db_session: Session, agent, system_principal, override_session_local):
    """Test granting all available tools to an agent."""
    # Create multiple tools
    tool1 = Tool(
        name="tool1",
        description="Tool 1",
        category="test",
        scope="local",
        created_by_principal_id=system_principal.id,
    )
    tool2 = Tool(
        name="tool2",
        description="Tool 2",
        category="test",
        scope="local",
        created_by_principal_id=system_principal.id,
    )
    db_session.add_all([tool1, tool2])
    db_session.flush()

    service = ToolService()
    granted = service.grant_all_tools(agent.id)

    assert len(granted) >= 2
    tool_names = service.get_granted_tool_names(agent.id)
    assert "tool1" in tool_names
    assert "tool2" in tool_names


def test_grant_system_tools(db_session: Session, agent, system_principal, override_session_local):
    """Test granting only system tools to an agent."""
    # Create a system tool (owned by system principal)
    system_tool = Tool(
        name="system_tool",
        description="A system tool",
        category="system",
        scope="local",
        created_by_principal_id=system_principal.id,
    )
    db_session.add(system_tool)
    db_session.flush()

    # Create a human principal and their tool
    human = Principal(username="human_user", principal_type="human")
    db_session.add(human)
    db_session.flush()

    user_tool = Tool(
        name="user_tool",
        description="A user-created tool",
        category="custom",
        scope="local",
        created_by_principal_id=human.id,
    )
    db_session.add(user_tool)
    db_session.flush()

    service = ToolService()
    granted = service.grant_system_tools(agent.id)

    tool_names = service.get_granted_tool_names(agent.id)

    # System tool should be granted
    assert "system_tool" in tool_names
    # User tool should NOT be granted
    assert "user_tool" not in tool_names


def test_grant_system_tools_requires_system_principal(db_session: Session, agent, system_principal, override_session_local):
    """Test grant_system_tools requires a system principal to exist.

    Note: We use the system_principal fixture to ensure one exists.
    In a fresh database without a system principal, this would raise ValueError.
    """
    # Create a system tool
    tool = Tool(
        name="required_system_tool",
        description="A system tool",
        category="test",
        scope="local",
        created_by_principal_id=system_principal.id,
    )
    db_session.add(tool)
    db_session.flush()

    service = ToolService()
    # This should work when system principal exists
    granted = service.grant_system_tools(agent.id)

    # Should have granted our tool
    tool_names = service.get_granted_tool_names(agent.id)
    assert "required_system_tool" in tool_names
