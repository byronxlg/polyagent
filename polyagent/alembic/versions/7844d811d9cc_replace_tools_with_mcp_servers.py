"""replace tools with mcp servers

Revision ID: 7844d811d9cc
Revises: 21c11cad6787
Create Date: 2025-12-23 11:59:24.612898

"""
import json
from pathlib import Path
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '7844d811d9cc'
down_revision: Union[str, Sequence[str], None] = '21c11cad6787'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create new MCP server tables
    op.create_table('servers',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_by_principal_id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('server_type', sa.String(), nullable=False),
    sa.Column('transport', sa.String(), nullable=False),
    sa.Column('command', sa.String(), nullable=False),
    sa.Column('args', sa.JSON(), nullable=True),
    sa.Column('env', sa.JSON(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['created_by_principal_id'], ['principals.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_table('agent_servers',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('agent_id', sa.UUID(), nullable=False),
    sa.Column('server_id', sa.UUID(), nullable=False),
    sa.Column('granted_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ),
    sa.ForeignKeyConstraint(['server_id'], ['servers.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

    # Clear old tool usage data (clean break - no backwards compatibility)
    op.execute('TRUNCATE TABLE agent_tool_usage')

    # Modify agent_tool_usage first: remove tool_id FK before dropping tools table
    op.drop_constraint('agent_tool_usage_tool_id_fkey', 'agent_tool_usage', type_='foreignkey')
    op.drop_column('agent_tool_usage', 'tool_id')
    op.add_column('agent_tool_usage', sa.Column('server_name', sa.String(), nullable=False))
    op.add_column('agent_tool_usage', sa.Column('tool_name', sa.String(), nullable=False))

    # Now safe to drop old tool tables (agent_tools first due to FK to tools)
    op.drop_table('agent_tools')
    op.drop_table('tools')

    # Fix memory_json nullable (from previous migration that didn't apply correctly)
    op.alter_column('agents', 'memory_json',
               existing_type=postgresql.JSON(astext_type=sa.Text()),
               nullable=True)

    # Seed MCP servers from JSON file
    seed_data_dir = Path(__file__).parent.parent / "seed_data"
    servers_file = seed_data_dir / "servers.json"

    if servers_file.exists():
        conn = op.get_bind()

        with servers_file.open() as f:
            servers_data = json.load(f)

        # Check existing servers
        existing_servers = {row[0] for row in conn.execute(sa.text("SELECT name FROM servers"))}

        # Insert new servers
        for server_data in servers_data:
            if server_data['name'] not in existing_servers:
                conn.execute(
                    sa.text(
                        "INSERT INTO servers (name, description, server_type, transport, command, args, "
                        "created_by_principal_id, is_active, created_at) "
                        "VALUES (:name, :description, :server_type, :transport, :command, :args, "
                        ":created_by_principal_id, true, NOW())"
                    ),
                    {
                        "name": server_data["name"],
                        "description": server_data["description"],
                        "server_type": server_data["server_type"],
                        "transport": server_data["transport"],
                        "command": server_data["command"],
                        "args": json.dumps(server_data.get("args")),
                        "created_by_principal_id": server_data["created_by_principal_id"],
                    }
                )
        conn.commit()

        # Grant all system servers to all existing agents
        server_ids = conn.execute(
            sa.text("SELECT id FROM servers WHERE server_type = 'system'")
        ).fetchall()
        agent_ids = conn.execute(sa.text("SELECT id FROM agents")).fetchall()

        for agent_row in agent_ids:
            agent_id = agent_row[0]
            for server_row in server_ids:
                server_id = server_row[0]
                # Check if grant already exists
                exists = conn.execute(
                    sa.text(
                        "SELECT 1 FROM agent_servers WHERE agent_id = :agent_id AND server_id = :server_id"
                    ),
                    {"agent_id": agent_id, "server_id": server_id}
                ).fetchone()
                if not exists:
                    conn.execute(
                        sa.text(
                            "INSERT INTO agent_servers (agent_id, server_id, granted_at) "
                            "VALUES (:agent_id, :server_id, NOW())"
                        ),
                        {"agent_id": agent_id, "server_id": server_id}
                    )
        conn.commit()


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('agents', 'memory_json',
               existing_type=postgresql.JSON(astext_type=sa.Text()),
               nullable=False)
    op.add_column('agent_tool_usage', sa.Column('tool_id', sa.UUID(), autoincrement=False, nullable=False))
    op.create_foreign_key(op.f('agent_tool_usage_tool_id_fkey'), 'agent_tool_usage', 'tools', ['tool_id'], ['id'])
    op.drop_column('agent_tool_usage', 'tool_name')
    op.drop_column('agent_tool_usage', 'server_name')
    op.create_table('agent_tools',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), autoincrement=False, nullable=False),
    sa.Column('agent_id', sa.UUID(), autoincrement=False, nullable=False),
    sa.Column('tool_id', sa.UUID(), autoincrement=False, nullable=False),
    sa.Column('granted_at', postgresql.TIMESTAMP(), autoincrement=False, nullable=False),
    sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], name=op.f('agent_tools_agent_id_fkey')),
    sa.ForeignKeyConstraint(['tool_id'], ['tools.id'], name=op.f('agent_tools_tool_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('agent_tools_pkey'))
    )
    op.create_table('tools',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), autoincrement=False, nullable=False),
    sa.Column('created_by_principal_id', sa.UUID(), autoincrement=False, nullable=False),
    sa.Column('name', sa.VARCHAR(), autoincrement=False, nullable=False),
    sa.Column('description', sa.TEXT(), autoincrement=False, nullable=False),
    sa.Column('category', sa.VARCHAR(), autoincrement=False, nullable=True),
    sa.Column('scope', sa.VARCHAR(), autoincrement=False, nullable=False),
    sa.ForeignKeyConstraint(['created_by_principal_id'], ['principals.id'], name=op.f('tools_created_by_principal_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('tools_pkey')),
    sa.UniqueConstraint('name', name=op.f('tools_name_key'), postgresql_include=[], postgresql_nulls_not_distinct=False)
    )
    op.drop_table('agent_servers')
    op.drop_table('servers')
    # ### end Alembic commands ###
