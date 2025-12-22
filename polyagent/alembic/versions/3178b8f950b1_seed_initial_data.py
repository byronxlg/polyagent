"""seed initial data

Revision ID: 3178b8f950b1
Revises: 8e04ff2c6804
Create Date: 2025-12-21 16:47:33.444027

"""
import json
from decimal import Decimal
from pathlib import Path
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import table, column, String, Numeric, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = '3178b8f950b1'
down_revision: Union[str, Sequence[str], None] = '8e04ff2c6804'
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

    # Seed tools
    tools_file = seed_data_dir / "tools.json"
    if tools_file.exists():
        with tools_file.open() as f:
            tools_data = json.load(f)

        # Check existing tools
        existing_tools = {row[0] for row in conn.execute(sa.text("SELECT name FROM tools"))}

        # Insert new tools
        for tool_data in tools_data:
            if tool_data['name'] not in existing_tools:
                conn.execute(
                    sa.text(
                        "INSERT INTO tools (name, description, category, scope, created_by_principal_id) "
                        "VALUES (:name, :description, :category, :scope, :created_by_principal_id)"
                    ),
                    tool_data
                )
        conn.commit()


def downgrade() -> None:
    """Remove seed data."""
    # Path to seed data files
    seed_data_dir = Path(__file__).parent.parent / "seed_data"

    # Get connection
    conn = op.get_bind()

    # Remove tools
    tools_file = seed_data_dir / "tools.json"
    if tools_file.exists():
        with tools_file.open() as f:
            tools_data = json.load(f)

        for tool_data in tools_data:
            conn.execute(sa.text("DELETE FROM tools WHERE name = :name"), {"name": tool_data['name']})

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
