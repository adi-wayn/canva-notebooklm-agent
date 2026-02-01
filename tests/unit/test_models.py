"""
Unit tests for ORM models.

Tests model definitions, relationships, and constraints.
"""

import pytest
from uuid import uuid4

from src.storage.models import (
    Tenant,
    User,
    Workflow,
    WorkflowStatus,
    WorkflowTask,
    WorkflowTaskStatus,
    Design,
    AuditLog,
    QuotaUsage,
    AuditActionType,
)


class TestTenantModel:
    """Test Tenant model."""

    def test_tenant_creation(self):
        """Test creating a tenant."""
        tenant = Tenant(name="test-org", tier="pro")
        assert tenant.name == "test-org"
        assert tenant.tier == "pro"
        assert tenant.is_active is True
        assert tenant.metadata == {}

    def test_tenant_defaults(self):
        """Test tenant defaults."""
        tenant = Tenant(name="default-org")
        assert tenant.tier == "free"  # Default tier
        assert tenant.is_active is True
        assert tenant.id is not None  # UUID generated


class TestUserModel:
    """Test User model."""

    def test_user_creation(self):
        """Test creating a user."""
        tenant_id = str(uuid4())
        user = User(
            tenant_id=tenant_id,
            email="user@example.com",
            display_name="John Doe",
            roles=["user"],
        )
        assert user.email == "user@example.com"
        assert user.display_name == "John Doe"
        assert user.roles == ["user"]
        assert user.is_active is True

    def test_user_defaults(self):
        """Test user defaults."""
        tenant_id = str(uuid4())
        user = User(
            tenant_id=tenant_id,
            email="user@example.com",
            display_name="Test",
        )
        assert user.is_active is True
        assert user.roles == []
        assert user.metadata == {}


class TestWorkflowModel:
    """Test Workflow model."""

    def test_workflow_creation(self):
        """Test creating a workflow."""
        tenant_id = str(uuid4())
        user_id = str(uuid4())
        workflow = Workflow(
            tenant_id=tenant_id,
            user_id=user_id,
            status=WorkflowStatus.SUBMITTED.value,
        )
        assert workflow.status == "submitted"
        assert workflow.tenant_id == tenant_id
        assert workflow.user_id == user_id

    def test_workflow_defaults(self):
        """Test workflow defaults."""
        tenant_id = str(uuid4())
        user_id = str(uuid4())
        workflow = Workflow(
            tenant_id=tenant_id,
            user_id=user_id,
        )
        assert workflow.status == WorkflowStatus.SUBMITTED.value
        assert workflow.input_config == {}
        assert workflow.output_artifacts == {}
        assert workflow.error_log == []

    def test_workflow_status_enum(self):
        """Test workflow status enum values."""
        assert WorkflowStatus.SUBMITTED.value == "submitted"
        assert WorkflowStatus.QUEUED.value == "queued"
        assert WorkflowStatus.ANALYZING.value == "analyzing"
        assert WorkflowStatus.PROCESSING.value == "processing"
        assert WorkflowStatus.COMPLETED.value == "completed"
        assert WorkflowStatus.FAILED.value == "failed"
        assert WorkflowStatus.CANCELLED.value == "cancelled"


class TestWorkflowTaskModel:
    """Test WorkflowTask model."""

    def test_task_creation(self):
        """Test creating a task."""
        workflow_id = str(uuid4())
        task = WorkflowTask(
            workflow_id=workflow_id,
            task_name="analyze_content",
            operation_type="notebooklm",
            status=WorkflowTaskStatus.PENDING.value,
        )
        assert task.task_name == "analyze_content"
        assert task.operation_type == "notebooklm"
        assert task.status == "pending"

    def test_task_defaults(self):
        """Test task defaults."""
        workflow_id = str(uuid4())
        task = WorkflowTask(
            workflow_id=workflow_id,
            task_name="test_task",
            operation_type="test",
        )
        assert task.status == WorkflowTaskStatus.PENDING.value
        assert task.retry_count == 0
        assert task.input_data == {}
        assert task.output_data == {}


class TestDesignModel:
    """Test Design model."""

    def test_design_creation(self):
        """Test creating a design."""
        tenant_id = str(uuid4())
        workflow_id = str(uuid4())
        design = Design(
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            canva_design_id="design_abc123",
            title="My Design",
        )
        assert design.canva_design_id == "design_abc123"
        assert design.title == "My Design"

    def test_design_defaults(self):
        """Test design defaults."""
        tenant_id = str(uuid4())
        workflow_id = str(uuid4())
        design = Design(
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            canva_design_id="design_abc",
            title="Test",
        )
        assert design.design_metadata == {}
        assert design.export_formats == {}


class TestAuditLogModel:
    """Test AuditLog model."""

    def test_audit_log_creation(self):
        """Test creating an audit log."""
        tenant_id = str(uuid4())
        user_id = str(uuid4())
        log = AuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            action=AuditActionType.CREATE.value,
            resource_type="workflow",
            resource_id=str(uuid4()),
            new_state={"status": "submitted"},
        )
        assert log.action == "create"
        assert log.resource_type == "workflow"
        assert log.new_state == {"status": "submitted"}

    def test_audit_log_defaults(self):
        """Test audit log defaults."""
        tenant_id = str(uuid4())
        log = AuditLog(
            tenant_id=tenant_id,
            action="test_action",
            resource_type="test",
            resource_id="test_id",
        )
        assert log.previous_state is None
        assert log.new_state == {}
        assert log.metadata == {}


class TestQuotaUsageModel:
    """Test QuotaUsage model."""

    def test_quota_creation(self):
        """Test creating quota usage entry."""
        from datetime import datetime, timezone, timedelta

        tenant_id = str(uuid4())
        reset_time = datetime.now(timezone.utc) + timedelta(days=1)
        quota = QuotaUsage(
            tenant_id=tenant_id,
            service="canva",
            metric="designs_created",
            current_usage=5,
            limit_value=100,
            reset_at=reset_time,
        )
        assert quota.service == "canva"
        assert quota.current_usage == 5
        assert quota.limit_value == 100

    def test_quota_defaults(self):
        """Test quota defaults."""
        from datetime import datetime, timezone, timedelta

        tenant_id = str(uuid4())
        reset_time = datetime.now(timezone.utc) + timedelta(days=1)
        quota = QuotaUsage(
            tenant_id=tenant_id,
            service="test",
            metric="test_metric",
            limit_value=-1,  # Unlimited
            reset_at=reset_time,
        )
        assert quota.current_usage == 0
        assert quota.limit_value == -1  # Unlimited
        assert quota.metadata == {}


class TestModelEnums:
    """Test model enums."""

    def test_audit_action_type_enum(self):
        """Test AuditActionType enum."""
        assert AuditActionType.CREATE.value == "create"
        assert AuditActionType.UPDATE.value == "update"
        assert AuditActionType.DELETE.value == "delete"
        assert AuditActionType.STATE_TRANSITION.value == "state_transition"
        assert AuditActionType.API_CALL.value == "api_call"
        assert AuditActionType.ERROR.value == "error"

    def test_workflow_status_values(self):
        """Test all workflow status values exist."""
        statuses = {e.value for e in WorkflowStatus}
        expected = {
            "submitted", "queued", "analyzing", "processing",
            "completed", "failed", "cancelled"
        }
        assert statuses == expected

    def test_workflow_task_status_values(self):
        """Test all workflow task status values exist."""
        statuses = {e.value for e in WorkflowTaskStatus}
        expected = {"pending", "running", "completed", "failed", "retrying"}
        assert statuses == expected
