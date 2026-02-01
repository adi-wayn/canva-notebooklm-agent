"""add workflow_events table

Revision ID: 002_add_workflow_events
Revises: 001_initial_schema
Create Date: 2026-01-17
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "002_add_workflow_events"

# Point to the previous revision in your history
down_revision = "001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workflow_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("workflow_id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # Foreign keys
    op.create_foreign_key(
        "fk_workflow_events_workflow",
        "workflow_events",
        "workflows",
        ["workflow_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_workflow_events_tenant",
        "workflow_events",
        "tenants",
        ["tenant_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # Indexes for replay and tenant scoping
    op.create_index(
        "idx_workflow_events_workflow_id",
        "workflow_events",
        ["workflow_id"],
    )
    op.create_index(
        "idx_workflow_events_tenant_id",
        "workflow_events",
        ["tenant_id"],
    )
    op.create_index(
        "idx_workflow_events_created_at",
        "workflow_events",
        ["created_at"],
    )
    op.create_index(
        "idx_workflow_events_workflow_id_id",
        "workflow_events",
        ["workflow_id", "id"],
    )


def downgrade() -> None:
    op.drop_index("idx_workflow_events_workflow_id_id", table_name="workflow_events")
    op.drop_index("idx_workflow_events_created_at", table_name="workflow_events")
    op.drop_index("idx_workflow_events_tenant_id", table_name="workflow_events")
    op.drop_index("idx_workflow_events_workflow_id", table_name="workflow_events")
    op.drop_constraint("fk_workflow_events_tenant", "workflow_events", type_="foreignkey")
    op.drop_constraint("fk_workflow_events_workflow", "workflow_events", type_="foreignkey")
    op.drop_table("workflow_events")
