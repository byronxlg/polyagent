import importlib
from uuid import UUID

from src.database import SessionLocal
from src.models import Agent, AgentTool, Principal, Tool


class ToolService:
    """Service for managing tool discovery, registration, and agent access.

    Tool loading is determined by scope:
    - local: File-based tools loaded from system/ or custom/ directories
    - internal/external: API-based tools (not yet implemented)

    For local tools, the module path is derived from:
    - System tools (created by system principal): src.agent.tools.system.{category}_tool
    - Custom tools (created by agents): src.agent.tools.custom.{created_by_principal_id}.{category}_tool

    Tool metadata (name, description, category, created_by_principal_id) is stored in the database and
    loaded from seed data at migration time.
    """

    def __init__(self) -> None:
        pass

    def get_granted_tool_names(self, agent_id: UUID | str) -> set[str]:
        """Get the set of tool names granted to an agent."""
        session = SessionLocal()
        try:
            results = session.query(Tool.name).join(AgentTool).filter(AgentTool.agent_id == agent_id).all()
            return {r.name for r in results}
        finally:
            session.close()

    def get_tools_for_agent(self, agent_id: UUID | str) -> list:
        """Discover all tools and return only those granted to the agent.

        Gets the agent's principal_id and uses it to discover tools.
        """
        session = SessionLocal()
        try:
            agent = session.query(Agent).filter(Agent.id == agent_id).first()
            if not agent:
                return []
            principal_id = agent.principal_id
        finally:
            session.close()

        all_tools = self._discover_all_tools(principal_id)
        granted_names = self.get_granted_tool_names(agent_id)
        return [t for t in all_tools if t.name in granted_names]

    def grant_tool(self, agent_id: UUID | str, tool_id: UUID | str) -> AgentTool:
        """Grant a tool to an agent."""
        session = SessionLocal()
        try:
            existing = (
                session.query(AgentTool)
                .filter(AgentTool.agent_id == agent_id, AgentTool.tool_id == tool_id)
                .first()
            )
            if existing:
                session.expunge(existing)
                return existing

            agent_tool = AgentTool(agent_id=agent_id, tool_id=tool_id)
            session.add(agent_tool)
            session.commit()
            session.refresh(agent_tool)
            session.expunge(agent_tool)
            return agent_tool
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def revoke_tool(self, agent_id: UUID | str, tool_id: UUID | str) -> bool:
        """Revoke a tool from an agent. Returns True if revoked, False if not found."""
        session = SessionLocal()
        try:
            result = (
                session.query(AgentTool)
                .filter(AgentTool.agent_id == agent_id, AgentTool.tool_id == tool_id)
                .delete()
            )
            session.commit()
            return result > 0
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def grant_all_tools(self, agent_id: UUID | str) -> list[AgentTool]:
        """Grant all available tools to an agent."""
        session = SessionLocal()
        try:
            tools = session.query(Tool).all()
            granted = []
            for tool in tools:
                existing = (
                    session.query(AgentTool)
                    .filter(AgentTool.agent_id == agent_id, AgentTool.tool_id == tool.id)
                    .first()
                )
                if existing:
                    granted.append(existing)
                else:
                    agent_tool = AgentTool(agent_id=agent_id, tool_id=tool.id)
                    session.add(agent_tool)
                    granted.append(agent_tool)
            session.commit()
            for at in granted:
                session.expunge(at)
            return granted
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def grant_system_tools(self, agent_id: UUID | str) -> list[AgentTool]:
        """Grant all system tools (created by system user) to an agent."""
        session = SessionLocal()
        try:
            # Get system principal ID
            system_principal = session.query(Principal).filter(Principal.principal_type == "system").first()
            if not system_principal:
                msg = "No system principal found in database"
                raise ValueError(msg)

            # System tools are created by the system principal
            tools = session.query(Tool).filter(Tool.created_by_principal_id == system_principal.id).all()
            granted = []
            for tool in tools:
                existing = (
                    session.query(AgentTool)
                    .filter(AgentTool.agent_id == agent_id, AgentTool.tool_id == tool.id)
                    .first()
                )
                if existing:
                    granted.append(existing)
                else:
                    agent_tool = AgentTool(agent_id=agent_id, tool_id=tool.id)
                    session.add(agent_tool)
                    granted.append(agent_tool)
            session.commit()
            for at in granted:
                session.expunge(at)
            return granted
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def _discover_all_tools(self, principal_id: UUID | str) -> list:
        """Load and instantiate all local-scoped tools based on database records.

        Tools are loaded from database records (seeded from tools.json).
        For each tool record:
        - System tools: src/agent/tools/system/{category}_tool.py
          Category: {sanitized_name} (e.g., "agent")
          Module: src.agent.tools.system.agent_tool

        - Custom tools: src/agent/tools/custom/{creator_principal_id}/{category}_tool.py
          Category: {sanitized_name} (e.g., "my_tool")
          Module: src.agent.tools.custom.{creator_principal_id}.{category}_tool
          Uses created_by_principal_id to determine directory path

        Non-local tools (internal/external scope) would be loaded via API calls
        and are not yet implemented.
        """
        session = SessionLocal()
        try:
            # Get system principal to identify system vs custom tools
            system_principal = session.query(Principal).filter(Principal.principal_type == "system").first()
            if not system_principal:
                msg = "No system principal found in database"
                raise ValueError(msg)

            # Query all local-scope tools
            db_tools = session.query(Tool).filter(Tool.scope == "local").all()

            # Group tools by (directory, creator_principal_id, category) to minimize module loads
            tools_by_module: dict[tuple[str, str | None, str], list] = {}
            for db_tool in db_tools:
                # Determine directory based on creator
                is_system = db_tool.created_by_principal_id == system_principal.id
                directory = "system" if is_system else "custom"
                creator_id = None if is_system else str(db_tool.created_by_principal_id)
                key = (directory, creator_id, db_tool.category)
                if key not in tools_by_module:
                    tools_by_module[key] = []
                tools_by_module[key].append(db_tool)

            # Load tools from modules
            all_tools = []
            for directory, creator_id, category in tools_by_module:
                module_name = f"{category}_tool"
                if directory == "custom" and creator_id:
                    # Custom tool path: src.agent.tools.custom.{creator_principal_id}.{category}_tool
                    module_path = f"src.agent.tools.custom.{creator_id}.{module_name}"
                else:
                    # System tool path: src.agent.tools.system.{category}_tool
                    module_path = f"src.agent.tools.system.{module_name}"
                try:
                    module = importlib.import_module(module_path)
                    all_tools.extend(module.create_tools(principal_id))
                except ModuleNotFoundError:
                    # Tool file doesn't exist yet (e.g., custom tool being created)
                    continue

            return all_tools

        finally:
            session.close()
