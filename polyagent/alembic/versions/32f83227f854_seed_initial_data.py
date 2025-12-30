"""seed initial data

Revision ID: 32f83227f854
Revises: 2c5949726cdc
Create Date: 2025-12-30 18:25:04.969517

"""
import json
from decimal import Decimal
from pathlib import Path
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import table, column, String, Numeric, Boolean, Text


# revision identifiers, used by Alembic.
revision: str = '32f83227f854'
down_revision: Union[str, Sequence[str], None] = '2c5949726cdc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Load seed data from JSON files."""
    # Path to seed data files
    seed_data_dir = Path(__file__).parent.parent / "seed_data"

    # Get connection
    conn = op.get_bind()

    # Seed principals
    principals_file = seed_data_dir / "principals.json"
    if principals_file.exists():
        with principals_file.open() as f:
            principals_data = json.load(f)

        # Check existing principals
        existing_principals = {row[0] for row in conn.execute(sa.text("SELECT username FROM principals"))}

        # Insert new principals
        for principal_data in principals_data:
            if principal_data['username'] not in existing_principals:
                conn.execute(
                    sa.text(
                        "INSERT INTO principals (id, username, email, principal_type, created_at) "
                        "VALUES (:id, :username, :email, :principal_type, NOW())"
                    ),
                    principal_data
                )
        conn.commit()

    # Seed models
    models_file = seed_data_dir / "models.json"
    if models_file.exists():
        with models_file.open() as f:
            models_data = json.load(f)

        # Define models table structure
        models_table = table('models',
            column('name', String),
            column('provider_name', String),
            column('provider', String),
            column('provider_model_id', String),
            column('description', Text),
            column('is_reasoning', Boolean),
            column('input_cost_per_million', Numeric(20, 10)),
            column('output_cost_per_million', Numeric(20, 10)),
        )

        # Check existing models
        existing_models = {row[0] for row in conn.execute(sa.text("SELECT name FROM models"))}

        # Insert new models
        for model_data in models_data:
            if model_data['name'] not in existing_models:
                # Convert string costs to Decimal
                model_data['input_cost_per_million'] = Decimal(model_data['input_cost_per_million'])
                model_data['output_cost_per_million'] = Decimal(model_data['output_cost_per_million'])
                conn.execute(models_table.insert().values(model_data))
        conn.commit()

    # Seed MCP servers
    servers_file = seed_data_dir / "servers.json"
    if servers_file.exists():
        with servers_file.open() as f:
            servers_data = json.load(f)

        # Check existing servers
        existing_servers = {row[0] for row in conn.execute(sa.text("SELECT name FROM mcp_servers"))}

        # Insert new servers
        for server_data in servers_data:
            if server_data['name'] not in existing_servers:
                conn.execute(
                    sa.text(
                        "INSERT INTO mcp_servers (name, description, server_type, transport, command, args, "
                        "created_by_principal_id, is_active, created_at) "
                        "VALUES (:name, :description, :server_type, :transport, :command, CAST(:args AS jsonb), "
                        ":created_by_principal_id, true, NOW())"
                    ),
                    {
                        'name': server_data['name'],
                        'description': server_data['description'],
                        'server_type': server_data['server_type'],
                        'transport': server_data['transport'],
                        'command': server_data['command'],
                        'args': json.dumps(server_data.get('args')),
                        'created_by_principal_id': server_data['created_by_principal_id'],
                    }
                )
        conn.commit()


def downgrade() -> None:
    """Remove seed data."""
    # Path to seed data files
    seed_data_dir = Path(__file__).parent.parent / "seed_data"

    # Get connection
    conn = op.get_bind()

    # Remove MCP servers
    servers_file = seed_data_dir / "servers.json"
    if servers_file.exists():
        with servers_file.open() as f:
            servers_data = json.load(f)

        for server_data in servers_data:
            conn.execute(sa.text("DELETE FROM mcp_servers WHERE name = :name"), {"name": server_data['name']})

    # Remove models
    models_file = seed_data_dir / "models.json"
    if models_file.exists():
        with models_file.open() as f:
            models_data = json.load(f)

        for model_data in models_data:
            conn.execute(sa.text("DELETE FROM models WHERE name = :name"), {"name": model_data['name']})

    # Remove principals
    principals_file = seed_data_dir / "principals.json"
    if principals_file.exists():
        with principals_file.open() as f:
            principals_data = json.load(f)

        for principal_data in principals_data:
            conn.execute(sa.text("DELETE FROM principals WHERE username = :username"), {"username": principal_data['username']})
