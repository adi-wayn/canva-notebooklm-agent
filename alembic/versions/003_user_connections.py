"""003_user_connections.py

Create user_connections table for storing OAuth tokens securely.

Revision ID: 003_user_connections
Revises: 002_add_workflow_events
Create Date: 2026-01-18

"""
from alembic import op
import sqlalchemy as sa


revision = '003_user_connections'
down_revision = '002_add_workflow_events'
branch_labels = None
depends_on = None


def upgrade():
    """Add user_connections table for OAuth token storage."""
    op.create_table(
        'user_connections',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('provider', sa.String(), nullable=False),  # 'canva', 'notebooklm'
        sa.Column('access_token', sa.String(), nullable=True),
        sa.Column('refresh_token', sa.String(), nullable=True),
        sa.Column('token_expires_at', sa.DateTime(), nullable=True),
        sa.Column('account_email', sa.String(), nullable=True),
        sa.Column('account_name', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'tenant_id', 'provider', name='uq_user_tenant_provider')
    )
    
    # Create index for quick lookups
    op.create_index('ix_user_connections_user_tenant', 'user_connections', ['user_id', 'tenant_id'])
    op.create_index('ix_user_connections_provider', 'user_connections', ['provider'])


def downgrade():
    """Remove user_connections table."""
    op.drop_index('ix_user_connections_provider', table_name='user_connections')
    op.drop_index('ix_user_connections_user_tenant', table_name='user_connections')
    op.drop_table('user_connections')
