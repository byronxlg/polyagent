"""MCP server for custom server creation and management tools."""

import ast
import importlib
import re
from pathlib import Path

from fastmcp import FastMCP

from src.database import SessionLocal
from src.models import Agent, Server
from src.services.server_service import ServerService

mcp = FastMCP("tooling")

CUSTOM_SERVERS_DIR = Path(__file__).parent.parent / "custom"
EXAMPLES_DIR = Path(__file__).parent.parent / "examples"


def _get_agent_id(principal_id: str) -> str | None:
    """Get agent_id from principal_id."""
    session = SessionLocal()
    try:
        agent = session.query(Agent).filter(Agent.principal_id == principal_id).first()
        return str(agent.id) if agent else None
    finally:
        session.close()


def _sanitize_server_name(name: str) -> str:
    """Sanitize server name to be a valid Python identifier."""
    name = re.sub(r"[\s-]+", "_", name)
    name = re.sub(r"[^a-zA-Z0-9_]", "", name)
    if name and not name[0].isalpha():
        name = "server_" + name
    return name.lower()


def _validate_server_code(code: str) -> tuple[bool, str]:
    """Validate that the code is syntactically correct and has required structure."""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return False, (
            f"Syntax error: {e}. "
            "Use get_server_template to see the required structure."
        )

    # Check for mcp = FastMCP(...) pattern
    has_mcp_init = False
    has_tool = False

    for node in ast.walk(tree):
        # Check for mcp = FastMCP(...)
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "mcp":
                    if isinstance(node.value, ast.Call):
                        if isinstance(node.value.func, ast.Name) and node.value.func.id == "FastMCP":
                            has_mcp_init = True

        # Check for @mcp.tool() decorator
        if isinstance(node, ast.FunctionDef):
            for decorator in node.decorator_list:
                if isinstance(decorator, ast.Call):
                    if isinstance(decorator.func, ast.Attribute):
                        if decorator.func.attr == "tool":
                            has_tool = True

    if not has_mcp_init:
        return False, (
            "Code must create mcp = FastMCP('server_name'). "
            "Use get_server_template to see the required structure."
        )

    if not has_tool:
        return False, (
            "Code must define at least one tool with @mcp.tool() decorator. "
            "Use get_server_template to see the required structure."
        )

    return True, ""


def _load_and_validate_module(module_path: str, file_path: Path) -> tuple[bool, str | None]:
    """Load module and validate it has mcp object. Returns (success, error)."""
    try:
        module = importlib.import_module(module_path)
        if not hasattr(module, "mcp"):
            file_path.unlink()
            return False, (
                "Module must export 'mcp' object. "
                "Use get_server_template to see the required structure."
            )
        return True, None
    except (ImportError, AttributeError, TypeError) as e:
        file_path.unlink()
        return False, (
            f"Failed to load server: {e}. "
            "Use get_server_template to see the required structure."
        )


@mcp.tool()
def get_server_template(principal_id: str) -> dict:
    """Get the template for creating custom MCP servers.

    Args:
        principal_id: Your principal ID (injected by agent)
    """
    template_path = EXAMPLES_DIR / "server_template.py"
    if not template_path.exists():
        # Return inline template if file doesn't exist
        template = '''"""
Custom MCP Server Template.

This file shows the required structure for custom MCP servers.
All custom servers must:
1. Import FastMCP from fastmcp
2. Create an mcp instance with FastMCP('server_name')
3. Define at least one tool with @mcp.tool() decorator
4. All tools must accept principal_id: str as first parameter
"""

from fastmcp import FastMCP

mcp = FastMCP("my_server")


@mcp.tool()
def my_tool(principal_id: str, param1: str) -> dict:
    """Description of what this tool does.

    Args:
        principal_id: Your principal ID (injected by agent)
        param1: Description of parameter
    """
    # Tool implementation here
    return {"success": True, "result": f"Processed: {param1}"}


@mcp.tool()
def another_tool(principal_id: str, value: int) -> dict:
    """Another example tool.

    Args:
        principal_id: Your principal ID (injected by agent)
        value: A numeric value to process
    """
    return {"success": True, "doubled": value * 2}


if __name__ == "__main__":
    mcp.run()
'''
        return {"success": True, "template": template}

    return {"success": True, "template": template_path.read_text()}


@mcp.tool()
def list_server_examples(principal_id: str) -> dict:
    """List available MCP server examples.

    Args:
        principal_id: Your principal ID (injected by agent)
    """
    if not EXAMPLES_DIR.exists():
        return {"success": True, "examples": [], "count": 0}

    examples = [
        {"name": file_path.stem, "filename": file_path.name}
        for file_path in EXAMPLES_DIR.glob("example_*_server.py")
    ]

    return {"success": True, "examples": examples, "count": len(examples)}


@mcp.tool()
def get_server_example(principal_id: str, example_name: str) -> dict:
    """Get the code for a specific server example.

    Args:
        principal_id: Your principal ID (injected by agent)
        example_name: Name of the example (e.g., 'calculator' or 'example_calculator_server')
    """
    if not example_name.startswith("example_"):
        example_name = f"example_{example_name}"
    if not example_name.endswith("_server.py"):
        if example_name.endswith(".py"):
            example_name = example_name[:-3] + "_server.py"
        else:
            example_name = f"{example_name}_server.py"

    example_path = EXAMPLES_DIR / example_name
    if not example_path.exists():
        return {"success": False, "error": f"Example '{example_name}' not found"}

    return {"success": True, "name": example_name, "code": example_path.read_text()}


@mcp.tool()
def create_mcp_server(principal_id: str, name: str, description: str, code: str) -> dict:
    """Create a new custom MCP server from provided code.

    The server will be saved as a Python file and registered in the database.
    You will automatically be granted access to use the server.

    Args:
        principal_id: Your principal ID (injected by agent)
        name: Display name for the server
        description: Brief description of what the server does
        code: Python code for the server (use get_server_template for structure)
    """
    agent_id = _get_agent_id(principal_id)
    if not agent_id:
        return {"success": False, "error": "Agent not found"}

    sanitized_name = _sanitize_server_name(name)
    if not sanitized_name:
        return {
            "success": False,
            "error": "Invalid server name. Use get_server_template for guidance.",
        }

    is_valid, error = _validate_server_code(code)
    if not is_valid:
        return {"success": False, "error": error}

    # Create principal-specific subdirectory
    principal_dir = CUSTOM_SERVERS_DIR / principal_id
    principal_dir.mkdir(parents=True, exist_ok=True)

    # Create __init__.py if it doesn't exist
    init_file = principal_dir / "__init__.py"
    if not init_file.exists():
        init_file.write_text('"""Custom MCP servers for this principal."""\n')

    file_path = principal_dir / f"{sanitized_name}_server.py"
    if file_path.exists():
        return {"success": False, "error": f"Server '{sanitized_name}' already exists"}

    file_path.write_text(code)

    # Validate the module can be loaded
    module_path = f"src.mcp_servers.custom.{principal_id}.{sanitized_name}_server"
    success, load_error = _load_and_validate_module(module_path, file_path)
    if not success:
        return {"success": False, "error": load_error}

    # Register server in database
    server_service = ServerService()
    try:
        server = server_service.create_server(
            name=sanitized_name,
            description=description,
            created_by_principal_id=principal_id,
            command="uv",
            args=["run", "python", "-m", module_path],
            server_type="custom",
            transport="stdio",
        )

        # Grant access to creating agent
        server_service.grant_server(agent_id, server.id)

        return {
            "success": True,
            "message": f"Server '{sanitized_name}' created",
            "server_id": str(server.id),
            "server_name": server.name,
        }
    except Exception as e:
        # Clean up file if database registration fails
        file_path.unlink()
        return {"success": False, "error": f"Failed to register server: {e}"}


@mcp.tool()
def list_custom_servers(principal_id: str) -> dict:
    """List all custom MCP servers (not system servers).

    Args:
        principal_id: Your principal ID (injected by agent)
    """
    server_service = ServerService()
    servers = server_service.list_servers(server_type="custom")
    return {
        "success": True,
        "count": len(servers),
        "servers": [
            {
                "id": str(s.id),
                "name": s.name,
                "description": s.description,
                "is_active": s.is_active,
            }
            for s in servers
        ],
    }


@mcp.tool()
def delete_server(principal_id: str, server_name: str) -> dict:
    """Delete a custom MCP server by name.

    Only works for custom servers, not system servers.
    This also removes the server file and revokes access from all agents.

    Args:
        principal_id: Your principal ID (injected by agent)
        server_name: Name of the server to delete
    """
    session = SessionLocal()
    try:
        server = session.query(Server).filter(Server.name == server_name).first()
        if not server:
            return {"success": False, "error": f"Server '{server_name}' not found"}

        if server.server_type == "system":
            return {"success": False, "error": "Cannot delete system servers"}

        # Delete the file for custom servers
        creator_id = str(server.created_by_principal_id)
        file_path = CUSTOM_SERVERS_DIR / creator_id / f"{server_name}_server.py"
        if file_path.exists():
            file_path.unlink()

        # Soft delete the server
        server_service = ServerService()
        server_service.delete_server(server.id)

        return {"success": True, "message": f"Server '{server_name}' deleted"}
    finally:
        session.close()


@mcp.tool()
def grant_server_access(principal_id: str, server_name: str, target_agent_id: str) -> dict:
    """Grant a server to another agent so they can use its tools.

    Args:
        principal_id: Your principal ID (injected by agent)
        server_name: Name of the server to grant
        target_agent_id: ID of the agent to grant access to
    """
    server_service = ServerService()
    server = server_service.get_server_by_name(server_name)
    if not server:
        return {"success": False, "error": f"Server '{server_name}' not found"}

    try:
        server_service.grant_server(target_agent_id, server.id)
        return {"success": True, "message": f"Granted '{server_name}' to agent {target_agent_id}"}
    except Exception as e:
        return {"success": False, "error": f"Failed to grant server: {e}"}


@mcp.tool()
def list_my_servers(principal_id: str) -> dict:
    """List all MCP servers you have access to.

    Args:
        principal_id: Your principal ID (injected by agent)
    """
    agent_id = _get_agent_id(principal_id)
    if not agent_id:
        return {"success": False, "error": "Agent not found"}

    server_service = ServerService()
    servers = server_service.get_servers_for_agent(agent_id)
    return {
        "success": True,
        "count": len(servers),
        "servers": [
            {
                "id": str(s.id),
                "name": s.name,
                "description": s.description,
                "server_type": s.server_type,
            }
            for s in servers
        ],
    }


if __name__ == "__main__":
    mcp.run()
