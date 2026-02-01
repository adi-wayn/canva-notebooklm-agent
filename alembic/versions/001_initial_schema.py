"""Initial schema creation - all models

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-01-17 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_initial_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create tenants table
    op.create_table(
        'tenants',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('tier', sa.String(50), nullable=False, server_default='free'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('custom_metadata', postgresql.JSON(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )
    op.create_index('ix_tenants_name', 'tenants', ['name'])

    # Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('tenant_id', sa.String(36), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('display_name', sa.String(255), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('roles', postgresql.JSON(), nullable=False, server_default='[]'),
        sa.Column('custom_metadata', postgresql.JSON(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
    )
    op.create_index('idx_user_tenant_id', 'users', ['tenant_id'])
    op.create_index('idx_user_email', 'users', ['email'])
    op.create_index('ix_users_email', 'users', ['email'])

    # Create workflows table
    op.create_table(
        'workflows',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('tenant_id', sa.String(36), nullable=False),
        sa.Column('user_id', sa.String(36), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='submitted'),
        sa.Column('current_task_id', sa.String(36), nullable=True),
        sa.Column('input_config', postgresql.JSON(), nullable=False, server_default='{}'),
        sa.Column('output_artifacts', postgresql.JSON(), nullable=False, server_default='{}'),
        sa.Column('error_log', postgresql.JSON(), nullable=False, server_default='[]'),
        sa.Column('custom_metadata', postgresql.JSON(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('started_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('completed_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_workflow_tenant_id', 'workflows', ['tenant_id'])
    op.create_index('idx_workflow_user_id', 'workflows', ['user_id'])
    op.create_index('idx_workflow_status', 'workflows', ['status'])
    op.create_index('idx_workflow_created_at', 'workflows', ['created_at'])
    op.create_index('idx_workflow_tenant_created', 'workflows', ['tenant_id', 'created_at'])

    # Create workflow_tasks table
    op.create_table(
        'workflow_tasks',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('workflow_id', sa.String(36), nullable=False),
        sa.Column('task_name', sa.String(100), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('operation_type', sa.String(50), nullable=False),
        sa.Column('input_data', postgresql.JSON(), nullable=False, server_default='{}'),
        sa.Column('output_data', postgresql.JSON(), nullable=False, server_default='{}'),
        sa.Column('error', postgresql.JSON(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('started_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('completed_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['workflow_id'], ['workflows.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_workflow_task_workflow_id', 'workflow_tasks', ['workflow_id'])
    op.create_index('idx_workflow_task_status', 'workflow_tasks', ['status'])
    op.create_index('idx_workflow_task_created_at', 'workflow_tasks', ['created_at'])

    # Create designs table
    op.create_table(
        'designs',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('tenant_id', sa.String(36), nullable=False),
        sa.Column('workflow_id', sa.String(36), nullable=False),
        sa.Column('canva_design_id', sa.String(255), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('design_url', sa.Text(), nullable=True),
        sa.Column('design_metadata', postgresql.JSON(), nullable=False, server_default='{}'),
        sa.Column('export_formats', postgresql.JSON(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['workflow_id'], ['workflows.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('canva_design_id'),
    )
    op.create_index('idx_design_tenant_id', 'designs', ['tenant_id'])
    op.create_index('idx_design_workflow_id', 'designs', ['workflow_id'])
    op.create_index('idx_design_created_at', 'designs', ['created_at'])

    # Create audit_logs table
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('tenant_id', sa.String(36), nullable=False),
        sa.Column('user_id', sa.String(36), nullable=True),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('resource_type', sa.String(50), nullable=False),
        sa.Column('resource_id', sa.String(36), nullable=False),
        sa.Column('previous_state', postgresql.JSON(), nullable=True),
        sa.Column('new_state', postgresql.JSON(), nullable=False, server_default='{}'),
        sa.Column('custom_metadata', postgresql.JSON(), nullable=False, server_default='{}'),
        sa.Column('timestamp', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_audit_tenant_id', 'audit_logs', ['tenant_id'])
    op.create_index('idx_audit_resource_type_id', 'audit_logs', ['resource_type', 'resource_id'])
    op.create_index('idx_audit_timestamp', 'audit_logs', ['timestamp'])

    # Create quota_usage table
    op.create_table(
        'quota_usage',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('tenant_id', sa.String(36), nullable=False),
        sa.Column('service', sa.String(50), nullable=False),
        sa.Column('metric', sa.String(50), nullable=False),
        sa.Column('current_usage', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('limit_value', sa.Integer(), nullable=False),
        sa.Column('reset_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('custom_metadata', postgresql.JSON(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_quota_tenant_service', 'quota_usage', ['tenant_id', 'service'])
    op.create_index('idx_quota_reset_at', 'quota_usage', ['reset_at'])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_index('idx_quota_reset_at', table_name='quota_usage')
    op.drop_index('idx_quota_tenant_service', table_name='quota_usage')
    op.drop_table('quota_usage')

    op.drop_index('idx_audit_timestamp', table_name='audit_logs')
    op.drop_index('idx_audit_resource_type_id', table_name='audit_logs')
    op.drop_index('idx_audit_tenant_id', table_name='audit_logs')
    op.drop_table('audit_logs')

    op.drop_index('idx_design_created_at', table_name='designs')
    op.drop_index('idx_design_workflow_id', table_name='designs')
    op.drop_index('idx_design_tenant_id', table_name='designs')
    op.drop_table('designs')

    op.drop_index('idx_workflow_task_created_at', table_name='workflow_tasks')
    op.drop_index('idx_workflow_task_status', table_name='workflow_tasks')
    op.drop_index('idx_workflow_task_workflow_id', table_name='workflow_tasks')
    op.drop_table('workflow_tasks')

    op.drop_index('idx_workflow_tenant_created', table_name='workflows')
    op.drop_index('idx_workflow_created_at', table_name='workflows')
    op.drop_index('idx_workflow_status', table_name='workflows')
    op.drop_index('idx_workflow_user_id', table_name='workflows')
    op.drop_index('idx_workflow_tenant_id', table_name='workflows')
    op.drop_table('workflows')

    op.drop_index('ix_users_email', table_name='users')
    op.drop_index('idx_user_email', table_name='users')
    op.drop_index('idx_user_tenant_id', table_name='users')
    op.drop_table('users')

    op.drop_index('ix_tenants_name', table_name='tenants')
    op.drop_table('tenants')
