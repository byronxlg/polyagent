"""make memory_json nullable with default

Revision ID: 21c11cad6787
Revises: 3178b8f950b1
Create Date: 2025-12-22 15:42:31.051275

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '21c11cad6787'
down_revision: Union[str, Sequence[str], None] = '3178b8f950b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Update all NULL memory_json values to empty JSON object
    op.execute("UPDATE agents SET memory_json = '{}' WHERE memory_json IS NULL")

    # Add server default for future inserts
    op.alter_column('agents', 'memory_json',
                    nullable=True,
                    server_default=sa.text("'{}'"))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove server default
    op.alter_column('agents', 'memory_json',
                    nullable=False,
                    server_default=None)
