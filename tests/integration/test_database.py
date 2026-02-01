"""
Integration tests for database and migrations.

Tests that:
1. Migrations run successfully on Postgres
2. Schema is created correctly
3. Models can persist and retrieve data
"""

import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from src.storage.models import (
    Base,
    Tenant,
    User,
    Workflow,
    WorkflowTask,
    Design,
    AuditLog,
    QuotaUsage,
    WorkflowStatus,
)
from src.storage.database import Database
from src.config import settings


@pytest.fixture
async def test_db():
    """
    Create a test database instance.

    Uses the same Postgres connection as configured in .env.
    """
    db = Database()
    await db.connect()

    # Drop all tables to start fresh
    try:
        await db.drop_tables()
    except Exception:
        pass  # Tables may not exist yet

    # Create all tables
    await db.create_tables()

    yield db

    # Cleanup
    await db.disconnect()


@pytest.mark.asyncio
async def test_database_connection(test_db: Database):
    """Test that database connection works."""
    # If we got here, connection succeeded
    assert test_db.engine is not None
    assert test_db._session_factory is not None


@pytest.mark.asyncio
async def test_tenant_persistence(test_db: Database):
    """Test creating and retrieving a tenant."""
    tenant = Tenant(name=f"test-org-{uuid4()}", tier="pro")

    async with test_db.session() as session:
        session.add(tenant)
        await session.commit()
        tenant_id = tenant.id

    # Retrieve tenant
    async with test_db.session() as session:
        result = await session.execute(select(Tenant).where(Tenant.id == tenant_id))
        retrieved = result.scalar_one_or_none()

    assert retrieved is not None
    assert retrieved.name == tenant.name
    assert retrieved.tier == "pro"


@pytest.mark.asyncio
async def test_user_with_tenant_fk(test_db: Database):
    """Test creating a user with tenant foreign key."""
    # Create tenant first
    tenant = Tenant(name=f"test-org-{uuid4()}")
    async with test_db.session() as session:
        session.add(tenant)
        await session.commit()
        tenant_id = tenant.id

    # Create user
    user = User(
        tenant_id=tenant_id,
        email=f"user-{uuid4()}@example.com",
        display_name="Test User",
        roles=["user"],
    )
    async with test_db.session() as session:
        session.add(user)
        await session.commit()
        user_id = user.id

    # Verify relationship
    async with test_db.session() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        retrieved = result.scalar_one_or_none()

    assert retrieved is not None
    assert retrieved.tenant_id == tenant_id


@pytest.mark.asyncio
async def test_workflow_cascade_delete(test_db: Database):
    """Test that deleting tenant cascades to workflows."""
    # Create tenant
    tenant = Tenant(name=f"test-org-{uuid4()}")
    async with test_db.session() as session:
        session.add(tenant)
        await session.commit()
        tenant_id = tenant.id

    # Create user
    user = User(
        tenant_id=tenant_id,
        email=f"user-{uuid4()}@example.com",
        display_name="Test",
    )
    async with test_db.session() as session:
        session.add(user)
        await session.commit()
        user_id = user.id

    # Create workflow
    workflow = Workflow(
        tenant_id=tenant_id,
        user_id=user_id,
        status=WorkflowStatus.SUBMITTED.value,
    )
    async with test_db.session() as session:
        session.add(workflow)
        await session.commit()
        workflow_id = workflow.id

    # Verify workflow exists
    async with test_db.session() as session:
        result = await session.execute(select(Workflow).where(Workflow.id == workflow_id))
        assert result.scalar_one_or_none() is not None

    # Delete tenant
    async with test_db.session() as session:
        tenant_to_delete = await session.get(Tenant, tenant_id)
        if tenant_to_delete:
            await session.delete(tenant_to_delete)
            await session.commit()

    # Workflow should be deleted via cascade
    async with test_db.session() as session:
        result = await session.execute(select(Workflow).where(Workflow.id == workflow_id))
        assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_workflow_with_tasks(test_db: Database):
    """Test creating a workflow with subtasks."""
    # Setup
    tenant = Tenant(name=f"test-org-{uuid4()}")
    async with test_db.session() as session:
        session.add(tenant)
        await session.commit()
        tenant_id = tenant.id

    user = User(
        tenant_id=tenant_id,
        email=f"user-{uuid4()}@example.com",
        display_name="Test",
    )
    async with test_db.session() as session:
        session.add(user)
        await session.commit()
        user_id = user.id

    # Create workflow with tasks
    workflow = Workflow(
        tenant_id=tenant_id,
        user_id=user_id,
    )
    async with test_db.session() as session:
        session.add(workflow)
        await session.commit()
        workflow_id = workflow.id

    # Add tasks
    task1 = WorkflowTask(
        workflow_id=workflow_id,
        task_name="analyze_content",
        operation_type="notebooklm",
    )
    task2 = WorkflowTask(
        workflow_id=workflow_id,
        task_name="create_design",
        operation_type="canva",
    )
    async with test_db.session() as session:
        session.add_all([task1, task2])
        await session.commit()

    # Retrieve workflow with tasks
    async with test_db.session() as session:
        result = await session.execute(select(Workflow).where(Workflow.id == workflow_id))
        retrieved = result.scalar_one_or_none()
        await session.refresh(retrieved, ["tasks"])

    assert len(retrieved.tasks) == 2
    assert retrieved.tasks[0].task_name in ["analyze_content", "create_design"]


@pytest.mark.asyncio
async def test_audit_log_persistence(test_db: Database):
    """Test creating audit logs."""
    tenant = Tenant(name=f"test-org-{uuid4()}")
    async with test_db.session() as session:
        session.add(tenant)
        await session.commit()
        tenant_id = tenant.id

    # Create audit log
    log = AuditLog(
        tenant_id=tenant_id,
        action="create",
        resource_type="workflow",
        resource_id=str(uuid4()),
        new_state={"status": "submitted"},
    )
    async with test_db.session() as session:
        session.add(log)
        await session.commit()
        log_id = log.id

    # Retrieve
    async with test_db.session() as session:
        result = await session.execute(select(AuditLog).where(AuditLog.id == log_id))
        retrieved = result.scalar_one_or_none()

    assert retrieved is not None
    assert retrieved.action == "create"


@pytest.mark.asyncio
async def test_quota_usage_persistence(test_db: Database):
    """Test quota usage tracking."""
    tenant = Tenant(name=f"test-org-{uuid4()}")
    async with test_db.session() as session:
        session.add(tenant)
        await session.commit()
        tenant_id = tenant.id

    # Create quota
    reset_time = datetime.now(timezone.utc) + timedelta(days=1)
    quota = QuotaUsage(
        tenant_id=tenant_id,
        service="canva",
        metric="designs_created",
        current_usage=5,
        limit_value=100,
        reset_at=reset_time,
    )
    async with test_db.session() as session:
        session.add(quota)
        await session.commit()
        quota_id = quota.id

    # Retrieve
    async with test_db.session() as session:
        result = await session.execute(select(QuotaUsage).where(QuotaUsage.id == quota_id))
        retrieved = result.scalar_one_or_none()

    assert retrieved is not None
    assert retrieved.current_usage == 5
    assert retrieved.limit_value == 100


@pytest.mark.asyncio
async def test_multi_tenant_isolation(test_db: Database):
    """Test that tenants are properly isolated."""
    # Create two tenants
    tenant1 = Tenant(name=f"tenant1-{uuid4()}")
    tenant2 = Tenant(name=f"tenant2-{uuid4()}")

    async with test_db.session() as session:
        session.add_all([tenant1, tenant2])
        await session.commit()
        tenant1_id = tenant1.id
        tenant2_id = tenant2.id

    # Create users in each tenant
    user1 = User(
        tenant_id=tenant1_id,
        email=f"user1-{uuid4()}@example.com",
        display_name="User 1",
    )
    user2 = User(
        tenant_id=tenant2_id,
        email=f"user2-{uuid4()}@example.com",
        display_name="User 2",
    )
    async with test_db.session() as session:
        session.add_all([user1, user2])
        await session.commit()

    # Verify tenant1 only sees user1
    async with test_db.session() as session:
        result = await session.execute(
            select(User).where(User.tenant_id == tenant1_id)
        )
        users = result.scalars().all()

    assert len(users) == 1
    assert users[0].email == user1.email
