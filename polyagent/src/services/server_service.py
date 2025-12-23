"""Service for managing MCP server configuration and agent grants."""

from uuid import UUID

from src.database import SessionLocal
from src.models import Agent, AgentServer, Server


class ServerService:
    """Service for managing MCP server discovery, registration, and agent access.

    Servers are MCP servers that provide tools to agents. Each server can contain
    multiple tools. Access is granted at the server level, not individual tools.

    Server types:
    - system: Built-in servers provided by the platform
    - custom: Servers created by agents
    """

    def __init__(self) -> None:
        pass

    def get_server(self, server_id: UUID | str) -> Server | None:
        """Get a server by ID."""
        session = SessionLocal()
        try:
            server = session.query(Server).filter(Server.id == server_id).first()
            if server:
                session.expunge(server)
            return server
        finally:
            session.close()

    def get_server_by_name(self, name: str) -> Server | None:
        """Get a server by name."""
        session = SessionLocal()
        try:
            server = session.query(Server).filter(Server.name == name).first()
            if server:
                session.expunge(server)
            return server
        finally:
            session.close()

    def list_servers(
        self, server_type: str | None = None, *, is_active: bool = True
    ) -> list[Server]:
        """List all servers, optionally filtered by type and active status."""
        session = SessionLocal()
        try:
            query = session.query(Server)
            if server_type:
                query = query.filter(Server.server_type == server_type)
            if is_active is not None:
                query = query.filter(Server.is_active == is_active)
            servers = query.all()
            for s in servers:
                session.expunge(s)
            return servers
        finally:
            session.close()

    def get_granted_server_names(self, agent_id: UUID | str) -> set[str]:
        """Get the set of server names granted to an agent."""
        session = SessionLocal()
        try:
            results = (
                session.query(Server.name)
                .join(AgentServer)
                .filter(AgentServer.agent_id == agent_id)
                .all()
            )
            return {r.name for r in results}
        finally:
            session.close()

    def get_servers_for_agent(self, agent_id: UUID | str) -> list[Server]:
        """Get all servers granted to an agent."""
        session = SessionLocal()
        try:
            servers = (
                session.query(Server)
                .join(AgentServer)
                .filter(AgentServer.agent_id == agent_id, Server.is_active.is_(True))
                .all()
            )
            for s in servers:
                session.expunge(s)
            return servers
        finally:
            session.close()

    def grant_server(self, agent_id: UUID | str, server_id: UUID | str) -> AgentServer:
        """Grant a server to an agent."""
        session = SessionLocal()
        try:
            existing = (
                session.query(AgentServer)
                .filter(AgentServer.agent_id == agent_id, AgentServer.server_id == server_id)
                .first()
            )
            if existing:
                session.expunge(existing)
                return existing

            agent_server = AgentServer(agent_id=agent_id, server_id=server_id)
            session.add(agent_server)
            session.commit()
            session.refresh(agent_server)
            session.expunge(agent_server)
            return agent_server
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def revoke_server(self, agent_id: UUID | str, server_id: UUID | str) -> bool:
        """Revoke a server from an agent. Returns True if revoked, False if not found."""
        session = SessionLocal()
        try:
            result = (
                session.query(AgentServer)
                .filter(AgentServer.agent_id == agent_id, AgentServer.server_id == server_id)
                .delete()
            )
            session.commit()
            return result > 0
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def grant_system_servers(self, agent_id: UUID | str) -> list[AgentServer]:
        """Grant all system servers to an agent."""
        session = SessionLocal()
        try:
            servers = (
                session.query(Server)
                .filter(Server.server_type == "system", Server.is_active.is_(True))
                .all()
            )
            granted = []
            for server in servers:
                existing = (
                    session.query(AgentServer)
                    .filter(AgentServer.agent_id == agent_id, AgentServer.server_id == server.id)
                    .first()
                )
                if existing:
                    granted.append(existing)
                else:
                    agent_server = AgentServer(agent_id=agent_id, server_id=server.id)
                    session.add(agent_server)
                    granted.append(agent_server)
            session.commit()
            for ag in granted:
                session.expunge(ag)
            return granted
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def create_server(  # noqa: PLR0913
        self,
        name: str,
        description: str,
        created_by_principal_id: UUID | str,
        command: str,
        args: list | None = None,
        env: dict | None = None,
        server_type: str = "custom",
        transport: str = "stdio",
    ) -> Server:
        """Create a new MCP server."""
        session = SessionLocal()
        try:
            server = Server(
                name=name,
                description=description,
                created_by_principal_id=created_by_principal_id,
                server_type=server_type,
                transport=transport,
                command=command,
                args=args,
                env=env,
                is_active=True,
            )
            session.add(server)
            session.commit()
            session.refresh(server)
            session.expunge(server)
            return server
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def delete_server(self, server_id: UUID | str) -> bool:
        """Delete a server (soft delete by setting is_active=False)."""
        session = SessionLocal()
        try:
            server = session.query(Server).filter(Server.id == server_id).first()
            if not server:
                return False
            server.is_active = False
            session.commit()
            return True
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_server_configs_for_agent(self, agent_id: UUID | str) -> list[dict]:
        """Get MCP server configurations for MultiServerMCPClient.

        Returns a list of server configs in the format expected by
        langchain-mcp-adapters MultiServerMCPClient.
        """
        servers = self.get_servers_for_agent(agent_id)

        # Get the agent's principal_id for injecting into server env
        session = SessionLocal()
        try:
            agent = session.query(Agent).filter(Agent.id == agent_id).first()
            principal_id = str(agent.principal_id) if agent else None
        finally:
            session.close()

        configs = []
        for server in servers:
            config = {
                "name": server.name,
                "transport": server.transport,
                "command": server.command,
            }
            if server.args:
                config["args"] = server.args

            # Merge server env with principal_id injection
            env = dict(server.env) if server.env else {}
            if principal_id:
                env["PRINCIPAL_ID"] = principal_id
            if env:
                config["env"] = env

            configs.append(config)

        return configs
