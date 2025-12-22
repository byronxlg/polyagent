import ast
import importlib
import re
from pathlib import Path

from langchain_core.tools import tool

from src.database import SessionLocal
from src.models import Agent, AgentTool, Principal, Tool

CUSTOM_TOOLS_DIR = Path(__file__).parent.parent / "custom"
EXAMPLES_DIR = Path(__file__).parent.parent / "examples"


def _validate_tool_code(code: str) -> tuple[bool, str]:
    """Validate that the code is syntactically correct and has create_tools function."""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return False, (
            f"Syntax error: {e}. "
            "Use get_tool_template to see the required structure or get_tool_example to see working examples."
        )

    has_create_tools = any(
        isinstance(node, ast.FunctionDef) and node.name == "create_tools" for node in ast.walk(tree)
    )
    if not has_create_tools:
        return False, (
            "Code must define a create_tools(agent_id: int) function. "
            "Use get_tool_template to see the required structure or get_tool_example to see working examples."
        )

    return True, ""


def _sanitize_tool_name(name: str) -> str:
    """Sanitize tool name to be a valid Python identifier."""
    name = re.sub(r"[\s-]+", "_", name)
    name = re.sub(r"[^a-zA-Z0-9_]", "", name)
    if name and not name[0].isalpha():
        name = "tool_" + name
    return name.lower()


def _register_tools_in_db(tools: list, category: str, principal_id: str, agent_id: int) -> None:
    """Register tools in database and grant to creating agent.

    Args:
        tools: List of LangChain tool objects to register
        category: The sanitized tool name (used to derive module filename)
        principal_id: The principal_id of the creating agent (determines directory)
        agent_id: The agent_id to grant the tools to

    Module path for custom tools: src.agent.tools.custom.{principal_id}.{category}_tool
    """
    session = SessionLocal()
    try:
        for t in tools:
            existing = session.query(Tool).filter(Tool.name == t.name).first()
            if not existing:
                new_tool = Tool(
                    name=t.name,
                    description=t.description,
                    category=category,
                    scope="local",
                    created_by_principal_id=principal_id,
                )
                session.add(new_tool)
        session.commit()

        for t in tools:
            db_tool = session.query(Tool).filter(Tool.name == t.name).first()
            if db_tool:
                exists = (
                    session.query(AgentTool)
                    .filter(AgentTool.agent_id == agent_id, AgentTool.tool_id == db_tool.id)
                    .first()
                )
                if not exists:
                    session.add(AgentTool(agent_id=agent_id, tool_id=db_tool.id))
        session.commit()
    finally:
        session.close()


def _load_and_validate_module(module_path: str, file_path: Path) -> tuple[list, str | None]:
    """Load module and validate it returns tools. Returns (tools, error)."""
    try:
        module = importlib.import_module(module_path)
        tools = module.create_tools(0)
        if not tools:
            file_path.unlink()
            return [], (
                "create_tools() returned no tools. "
                "Use get_tool_template to see the required structure or "
                "get_tool_example to see working examples."
            )

        # Validate that each tool is a proper LangChain tool object with name/description
        for t in tools:
            if not hasattr(t, "name") or not hasattr(t, "description"):
                file_path.unlink()
                return [], (
                    "create_tools() must return LangChain tool objects with .name and .description. "
                    "Use @tool decorator from langchain_core.tools. "
                    "Use get_tool_template to see the required structure or "
                    "get_tool_example to see working examples."
                )

        return tools, None
    except (ImportError, AttributeError, TypeError) as e:
        file_path.unlink()
        return [], (
            f"Failed to load tool: {e}. "
            "Use get_tool_template to see the required structure or get_tool_example to see working examples."
        )


def _do_create_tool(name: str, code: str, agent_id: int) -> dict:
    """Create a new custom tool from provided code.

    Tools are organized by principal_id in subdirectories:
    File path: src/agent/tools/custom/{principal_id}/{sanitized_name}_tool.py
    Module path: src.agent.tools.custom.{principal_id}.{sanitized_name}_tool

    The category field stores just the sanitized_name.
    The created_by_principal_id field is used to determine the directory.
    """
    session = SessionLocal()
    try:
        # Get the agent's principal_id
        agent = session.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            return {"success": False, "error": "Agent not found"}
        principal_id = str(agent.principal_id)
    finally:
        session.close()

    sanitized_name = _sanitize_tool_name(name)
    if not sanitized_name:
        return {
            "success": False,
            "error": (
                "Invalid tool name. "
                "Use get_tool_template to see the required structure or "
                "get_tool_example to see working examples."
            ),
        }

    is_valid, error = _validate_tool_code(code)
    if not is_valid:
        return {"success": False, "error": error}

    # Create principal-specific subdirectory
    principal_dir = CUSTOM_TOOLS_DIR / principal_id
    principal_dir.mkdir(parents=True, exist_ok=True)

    # Create __init__.py if it doesn't exist
    init_file = principal_dir / "__init__.py"
    if not init_file.exists():
        init_file.write_text("")

    file_path = principal_dir / f"{sanitized_name}_tool.py"
    if file_path.exists():
        return {"success": False, "error": f"Tool '{sanitized_name}' already exists"}

    file_path.write_text(code)

    module_path = f"src.agent.tools.custom.{principal_id}.{sanitized_name}_tool"
    tools, load_error = _load_and_validate_module(module_path, file_path)
    if load_error:
        return {"success": False, "error": load_error}

    # Register with category = sanitized_name
    # The created_by_principal_id field is used to determine the directory
    _register_tools_in_db(tools, sanitized_name, principal_id, agent_id)

    return {"success": True, "message": f"Tool '{sanitized_name}' created", "tools": [t.name for t in tools]}


def _do_list_custom_tools() -> dict:
    """List all non-system tools from the database."""
    session = SessionLocal()
    try:
        # Get the system principal
        system_principal = session.query(Principal).filter(Principal.principal_type == "system").first()
        if not system_principal:
            return {"success": False, "error": "System principal not found"}

        # Non-system tools are created by principals other than the system principal
        tools = session.query(Tool).filter(Tool.created_by_principal_id != system_principal.id).all()
        return {
            "success": True,
            "count": len(tools),
            "tools": [{"id": str(t.id), "name": t.name, "description": t.description} for t in tools],
        }
    finally:
        session.close()


def _do_delete_tool(tool_name: str) -> dict:
    """Delete a custom tool by name.

    For local-scoped custom tools, the file path is derived from:
    - created_by_principal_id (determines the directory)
    - category (the sanitized tool name)

    File path: src/agent/tools/custom/{created_by_principal_id}/{category}_tool.py
    """
    session = SessionLocal()
    try:
        db_tool = session.query(Tool).filter(Tool.name == tool_name).first()
        if not db_tool:
            return {"success": False, "error": f"Tool '{tool_name}' not found"}

        # Get the system principal to check if this is a system tool
        system_principal = session.query(Principal).filter(Principal.principal_type == "system").first()
        if system_principal and db_tool.created_by_principal_id == system_principal.id:
            return {"success": False, "error": "Cannot delete system tools"}

        # Delete the file for local-scoped custom tools
        if db_tool.scope == "local" and db_tool.category:
            principal_id = str(db_tool.created_by_principal_id)
            file_path = CUSTOM_TOOLS_DIR / principal_id / f"{db_tool.category}_tool.py"
            if file_path.exists():
                file_path.unlink()

        session.query(AgentTool).filter(AgentTool.tool_id == db_tool.id).delete()
        session.delete(db_tool)
        session.commit()
        return {"success": True, "message": f"Tool '{tool_name}' deleted"}
    finally:
        session.close()


def _do_grant_tool(tool_name: str, target_agent_id: str) -> dict:
    """Grant a tool to another agent."""
    session = SessionLocal()
    try:
        db_tool = session.query(Tool).filter(Tool.name == tool_name).first()
        if not db_tool:
            return {"success": False, "error": f"Tool '{tool_name}' not found"}

        exists = (
            session.query(AgentTool)
            .filter(AgentTool.agent_id == target_agent_id, AgentTool.tool_id == db_tool.id)
            .first()
        )
        if exists:
            return {"success": True, "message": f"Agent {target_agent_id} already has '{tool_name}'"}

        session.add(AgentTool(agent_id=target_agent_id, tool_id=db_tool.id))
        session.commit()
        return {"success": True, "message": f"Granted '{tool_name}' to agent {target_agent_id}"}
    finally:
        session.close()


def _do_get_tool_template() -> dict:
    """Get the tool creation template."""
    template_path = EXAMPLES_DIR / "template.py"
    if not template_path.exists():
        return {"success": False, "error": "Template file not found"}

    return {"success": True, "template": template_path.read_text()}


def _do_list_tool_examples() -> dict:
    """List available tool examples."""
    if not EXAMPLES_DIR.exists():
        return {"success": True, "examples": []}

    examples = [
        {"name": file_path.stem, "filename": file_path.name} for file_path in EXAMPLES_DIR.glob("example_*.py")
    ]

    return {"success": True, "examples": examples, "count": len(examples)}


def _do_get_tool_example(example_name: str) -> dict:
    """Get the code for a specific example."""
    if not example_name.startswith("example_"):
        example_name = f"example_{example_name}"
    if not example_name.endswith(".py"):
        example_name = f"{example_name}.py"

    example_path = EXAMPLES_DIR / example_name
    if not example_path.exists():
        return {"success": False, "error": f"Example '{example_name}' not found"}

    return {"success": True, "name": example_name, "code": example_path.read_text()}


def create_tools(principal_id: str) -> list:
    """Create tooling tools for a principal.

    Args:
        principal_id: The principal_id of the agent using these tools
    """
    # Get agent_id from principal_id for operations that need it
    session = SessionLocal()
    try:
        agent = session.query(Agent).filter(Agent.principal_id == principal_id).first()
        agent_id = agent.id if agent else None
    finally:
        session.close()

    @tool("get_tool_template", description="Get the template for creating custom tools")
    def get_tool_template() -> dict:
        """Get the tool creation template with required structure."""
        return _do_get_tool_template()

    @tool("list_tool_examples", description="List available tool examples")
    def list_tool_examples() -> dict:
        """List all available tool examples."""
        return _do_list_tool_examples()

    @tool("get_tool_example", description="Get the code for a specific tool example")
    def get_tool_example(example_name: str) -> dict:
        """Get the code for a specific example.

        Args:
            example_name: Name of the example (e.g., 'calculator' or 'example_calculator')
        """
        return _do_get_tool_example(example_name)

    @tool("create_tool", description="Create a new custom tool. Provide the tool name and Python code.")
    def create_tool(name: str, code: str) -> dict:
        """Create a new custom tool."""
        if not agent_id:
            return {"success": False, "error": "Agent not found for this principal"}
        return _do_create_tool(name, code, agent_id)

    @tool("list_custom_tools", description="List all available custom tools created by agents.")
    def list_custom_tools() -> dict:
        """List all custom tools."""
        return _do_list_custom_tools()

    @tool("delete_tool", description="Delete a custom tool. Only works for non-system tools.")
    def delete_tool(tool_name: str) -> dict:
        """Delete a custom tool by name."""
        return _do_delete_tool(tool_name)

    @tool("grant_tool", description="Grant a tool to another agent so they can use it.")
    def grant_tool(tool_name: str, target_agent_id: str) -> dict:
        """Grant a tool to another agent."""
        return _do_grant_tool(tool_name, target_agent_id)

    return [
        get_tool_template,
        list_tool_examples,
        get_tool_example,
        create_tool,
        list_custom_tools,
        delete_tool,
        grant_tool,
    ]
