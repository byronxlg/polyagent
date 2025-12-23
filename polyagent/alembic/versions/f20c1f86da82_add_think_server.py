"""add think server

Revision ID: f20c1f86da82
Revises: 0d9538be39e0
Create Date: 2025-12-23 22:32:15.875703

"""

import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f20c1f86da82"
down_revision: Union[str, Sequence[str], None] = "0d9538be39e0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# System principal UUID (used for system servers)
SYSTEM_PRINCIPAL_ID = "a603702c-1e2f-4324-bd98-3c8e3232b477"


def upgrade() -> None:
    """Add think server to the servers table."""
    conn = op.get_bind()

    # Check if think server already exists
    result = conn.execute(sa.text("SELECT id FROM servers WHERE name = 'think'"))
    if result.fetchone():
        return  # Already exists

    # Insert think server
    conn.execute(
        sa.text(
            "INSERT INTO servers (name, description, server_type, transport, command, args, "
            "created_by_principal_id, is_active, created_at) "
            "VALUES (:name, :description, :server_type, :transport, :command, :args, "
            ":created_by_principal_id, true, NOW())"
        ),
        {
            "name": "think",
            "description": "Internal reasoning tool: think through problems step by step without executing actions.",
            "server_type": "system",
            "transport": "stdio",
            "command": "uv",
            "args": json.dumps(["run", "python", "-m", "src.mcp_servers.servers.think_server"]),
            "created_by_principal_id": SYSTEM_PRINCIPAL_ID,
        },
    )

    # Grant think server to all existing agents
    conn.execute(
        sa.text(
            """
            INSERT INTO agent_servers (agent_id, server_id, granted_at)
            SELECT a.id, s.id, NOW()
            FROM agents a
            CROSS JOIN servers s
            WHERE s.name = 'think'
            AND NOT EXISTS (
                SELECT 1 FROM agent_servers ags
                WHERE ags.agent_id = a.id AND ags.server_id = s.id
            )
            """
        )
    )


def downgrade() -> None:
    """Remove think server."""
    conn = op.get_bind()

    # Remove agent_servers grants for think server
    conn.execute(
        sa.text(
            "DELETE FROM agent_servers WHERE server_id = (SELECT id FROM servers WHERE name = 'think')"
        )
    )

    # Remove think server
    conn.execute(sa.text("DELETE FROM servers WHERE name = 'think'"))
