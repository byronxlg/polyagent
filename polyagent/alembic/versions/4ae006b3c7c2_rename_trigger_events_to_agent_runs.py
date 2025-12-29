"""Rename trigger_events to agent_runs.

Revision ID: 4ae006b3c7c2
Revises: f20c1f86da82
Create Date: 2025-01-01

Changes:
- Rename table agent_trigger_events -> agent_runs
- Rename columns:
  - execution_started_at -> started_at
  - execution_completed_at -> completed_at
  - execution_error -> error
- Make nullable:
  - trigger_id
  - table_name
  - record_id
  - change_type
- Add column:
  - final_response (JSONB, nullable)
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = "4ae006b3c7c2"
down_revision = "f20c1f86da82"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Rename table
    op.rename_table("agent_trigger_events", "agent_runs")

    # Rename columns
    op.alter_column("agent_runs", "execution_started_at", new_column_name="started_at")
    op.alter_column("agent_runs", "execution_completed_at", new_column_name="completed_at")
    op.alter_column("agent_runs", "execution_error", new_column_name="error")

    # Make columns nullable
    op.alter_column("agent_runs", "trigger_id", existing_type=sa.UUID(), nullable=True)
    op.alter_column("agent_runs", "table_name", existing_type=sa.String(), nullable=True)
    op.alter_column("agent_runs", "record_id", existing_type=sa.UUID(), nullable=True)
    op.alter_column("agent_runs", "change_type", existing_type=sa.String(), nullable=True)

    # Add final_response column
    op.add_column("agent_runs", sa.Column("final_response", JSONB, nullable=True))

    # Rename index if it exists
    op.execute("ALTER INDEX IF EXISTS ix_agent_trigger_events_created_at RENAME TO ix_agent_runs_created_at")
    op.execute("ALTER INDEX IF EXISTS ix_agent_trigger_events_trigger_id RENAME TO ix_agent_runs_trigger_id")
    op.execute("ALTER INDEX IF EXISTS ix_agent_trigger_events_agent_id RENAME TO ix_agent_runs_agent_id")


def downgrade() -> None:
    # Remove final_response column
    op.drop_column("agent_runs", "final_response")

    # Make columns not nullable (with default values for existing nulls)
    op.execute("UPDATE agent_runs SET trigger_id = '00000000-0000-0000-0000-000000000000' WHERE trigger_id IS NULL")
    op.execute("UPDATE agent_runs SET table_name = 'unknown' WHERE table_name IS NULL")
    op.execute("UPDATE agent_runs SET record_id = '00000000-0000-0000-0000-000000000000' WHERE record_id IS NULL")
    op.execute("UPDATE agent_runs SET change_type = 'unknown' WHERE change_type IS NULL")

    op.alter_column("agent_runs", "trigger_id", existing_type=sa.UUID(), nullable=False)
    op.alter_column("agent_runs", "table_name", existing_type=sa.String(), nullable=False)
    op.alter_column("agent_runs", "record_id", existing_type=sa.UUID(), nullable=False)
    op.alter_column("agent_runs", "change_type", existing_type=sa.String(), nullable=False)

    # Rename columns back
    op.alter_column("agent_runs", "started_at", new_column_name="execution_started_at")
    op.alter_column("agent_runs", "completed_at", new_column_name="execution_completed_at")
    op.alter_column("agent_runs", "error", new_column_name="execution_error")

    # Rename indexes back
    op.execute("ALTER INDEX IF EXISTS ix_agent_runs_created_at RENAME TO ix_agent_trigger_events_created_at")
    op.execute("ALTER INDEX IF EXISTS ix_agent_runs_trigger_id RENAME TO ix_agent_trigger_events_trigger_id")
    op.execute("ALTER INDEX IF EXISTS ix_agent_runs_agent_id RENAME TO ix_agent_trigger_events_agent_id")

    # Rename table back
    op.rename_table("agent_runs", "agent_trigger_events")
