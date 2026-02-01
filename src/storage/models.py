"""
SQLAlchemy ORM models for Canva-NotebookLM integration system.

All models are multi-tenant:
- Every table has tenant_id FK to Tenant
- All queries are tenant-scoped by default (see repository layer)
- Audit trail captures all state changes

Design:
- Async-native (no sync sessions)
- JSONB columns for flexible metadata
- Proper relationships and constraints
- Indexing for common queries (tenant_id, user_id, created_at, status)

See docs/DATABASE_SCHEMA.md for schema explanation.
"""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    JSON,
    TEXT,
    TIMESTAMP,
    BigInteger,
    ForeignKey,
    Index,
    Integer,
    String,
    event,
)
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    """Get current UTC datetime."""
    return datetime.now(timezone.utc)


class Base(AsyncAttrs, DeclarativeBase):
    """Base class for all ORM models."""

    pass


class WorkflowStatus(str, Enum):
    """Workflow execution status."""

    SUBMITTED = "submitted"  # Initial state
    QUEUED = "queued"  # Waiting for worker
    ANALYZING = "analyzing"  # NotebookLM analysis in progress
    PROCESSING = "processing"  # Canva design creation in progress
    COMPLETED = "completed"  # Successfully finished
    FAILED = "failed"  # Permanent failure
    CANCELLED = "cancelled"  # User cancelled


class WorkflowTaskStatus(str, Enum):
    """Individual task status within workflow."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


class AuditActionType(str, Enum):
    """Audit log action types."""

    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    STATE_TRANSITION = "state_transition"
    API_CALL = "api_call"
    ERROR = "error"


# ============================================================================
# Tenant & User Models
# ============================================================================


class Tenant(Base):
    """Organization or team (multi-tenancy root)."""

    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    tier: Mapped[str] = mapped_column(String(50), nullable=False, default="free")  # free, pro, enterprise
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    custom_metadata: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    # Relationships
    users: Mapped[List["User"]] = relationship("User", back_populates="tenant", cascade="all, delete-orphan")
    workflows: Mapped[List["Workflow"]] = relationship("Workflow", back_populates="tenant", cascade="all, delete-orphan")
    quota_usage: Mapped[List["QuotaUsage"]] = relationship(
        "QuotaUsage", back_populates="tenant", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Tenant(id={self.id}, name={self.name}, tier={self.tier})>"


class User(Base):
    """Person within a tenant."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    roles: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)  # [admin, user, viewer]
    custom_metadata: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="users")
    workflows: Mapped[List["Workflow"]] = relationship("Workflow", back_populates="created_by")

    # Indexes
    __table_args__ = (Index("idx_user_tenant_id", "tenant_id"), Index("idx_user_email", "email"))

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email}, tenant_id={self.tenant_id})>"


# ============================================================================
# Workflow & Task Models
# ============================================================================


class Workflow(Base):
    """Main workflow orchestration record."""

    __tablename__ = "workflows"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default=WorkflowStatus.SUBMITTED.value, index=True)
    current_task_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)  # Currently executing task
    input_config: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)  # User's input
    output_artifacts: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)  # Generated outputs
    error_log: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)  # Error history
    custom_metadata: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)  # Additional context
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=utc_now)
    started_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="workflows")
    created_by: Mapped["User"] = relationship("User", back_populates="workflows")
    tasks: Mapped[List["WorkflowTask"]] = relationship("WorkflowTask", back_populates="workflow", cascade="all, delete-orphan")
    designs: Mapped[List["Design"]] = relationship("Design", back_populates="workflow", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index("idx_workflow_tenant_id", "tenant_id"),
        Index("idx_workflow_user_id", "user_id"),
        Index("idx_workflow_status", "status"),
        Index("idx_workflow_created_at", "created_at"),
        Index("idx_workflow_tenant_created", "tenant_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Workflow(id={self.id}, tenant_id={self.tenant_id}, status={self.status})>"


class WorkflowTask(Base):
    """Subtask within a workflow."""

    __tablename__ = "workflow_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workflow_id: Mapped[str] = mapped_column(String(36), ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False)
    task_name: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g., "analyze_content", "create_design"
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=WorkflowTaskStatus.PENDING.value, index=True
    )
    operation_type: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g., "notebooklm", "canva", "llm"
    input_data: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    output_data: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    error: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    retry_count: Mapped[int] = mapped_column(nullable=False, default=0)
    duration_ms: Mapped[Optional[int]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=utc_now)
    started_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    # Relationships
    workflow: Mapped["Workflow"] = relationship("Workflow", back_populates="tasks")

    # Indexes
    __table_args__ = (
        Index("idx_workflow_task_workflow_id", "workflow_id"),
        Index("idx_workflow_task_status", "status"),
        Index("idx_workflow_task_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<WorkflowTask(id={self.id}, workflow_id={self.workflow_id}, status={self.status})>"


# ============================================================================
# Design Model
# ============================================================================


class Design(Base):
    """Canva design generated for a workflow."""

    __tablename__ = "designs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    workflow_id: Mapped[str] = mapped_column(String(36), ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False)
    canva_design_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)  # Canva API ID
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    design_url: Mapped[Optional[str]] = mapped_column(TEXT, nullable=True)  # Canva edit URL
    design_metadata: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)  # Width, height, etc.
    export_formats: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)  # {png: url, pdf: url, ...}
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", foreign_keys=[tenant_id])
    workflow: Mapped["Workflow"] = relationship("Workflow", back_populates="designs")

    # Indexes
    __table_args__ = (
        Index("idx_design_tenant_id", "tenant_id"),
        Index("idx_design_workflow_id", "workflow_id"),
        Index("idx_design_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Design(id={self.id}, workflow_id={self.workflow_id}, canva_design_id={self.canva_design_id})>"


# ============================================================================
# Audit & Quota Models
# ============================================================================


class AuditLog(Base):
    """Immutable audit trail of all state changes."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)  # see AuditActionType
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g., "workflow", "design", "user"
    resource_id: Mapped[str] = mapped_column(String(36), nullable=False)
    previous_state: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    new_state: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    custom_metadata: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)  # request_id, ip, etc.
    timestamp: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=utc_now, index=True)

    # Relationships (lightweight: no cascade)
    tenant: Mapped["Tenant"] = relationship("Tenant", foreign_keys=[tenant_id])
    user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[user_id])

    # Indexes
    __table_args__ = (
        Index("idx_audit_tenant_id", "tenant_id"),
        Index("idx_audit_resource_type_id", "resource_type", "resource_id"),
        Index("idx_audit_timestamp", "timestamp"),
    )

    def __repr__(self) -> str:
        return f"<AuditLog(id={self.id}, tenant_id={self.tenant_id}, action={self.action})>"


class QuotaUsage(Base):
    """Per-tenant quota tracking."""

    __tablename__ = "quota_usage"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    service: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g., "canva", "notebooklm", "llm", "api_calls"
    metric: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g., "designs_created", "api_requests"
    current_usage: Mapped[int] = mapped_column(nullable=False, default=0)
    limit_value: Mapped[int] = mapped_column(nullable=False)  # -1 = unlimited
    reset_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    custom_metadata: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="quota_usage")

    # Indexes
    __table_args__ = (
        Index("idx_quota_tenant_service", "tenant_id", "service"),
        Index("idx_quota_reset_at", "reset_at"),
    )

    def __repr__(self) -> str:
        return f"<QuotaUsage(id={self.id}, tenant_id={self.tenant_id}, service={self.service}, metric={self.metric})>"


# ============================================================================
# Workflow Events (Append-only, ordered for SSE replay)
# ============================================================================


class WorkflowEvent(Base):
    """Durable event log for workflows (append-only).

    Enables SSE replay via monotonic global `id` and tenant-scoped queries.
    """

    __tablename__ = "workflow_events"

    # Use Integer for SQLite compatibility (supports AUTOINCREMENT)
    # Postgres will handle this as serial/bigserial automatically
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workflow_id: Mapped[str] = mapped_column(String(36), ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=utc_now)

    # Relationships
    # Lightweight relations to avoid heavy joins
    # (we primarily query by workflow/tenant for replay)

    __table_args__ = (
        Index("idx_workflow_events_workflow_id", "workflow_id"),
        Index("idx_workflow_events_tenant_id", "tenant_id"),
        Index("idx_workflow_events_created_at", "created_at"),
        Index("idx_workflow_events_workflow_id_id", "workflow_id", "id"),
    )

    def __repr__(self) -> str:
        return (
            f"<WorkflowEvent(id={self.id}, workflow_id={self.workflow_id}, "
            f"tenant_id={self.tenant_id}, event_type={self.event_type})>"
        )


# ============================================================================
# OAuth & Connections
# ============================================================================


class UserConnection(Base):
    """OAuth connection for external services (Canva, NotebookLM, etc.).
    
    Stores access tokens, refresh tokens, and connection metadata for
    external service integrations. Supports token refresh and revocation.
    """

    __tablename__ = "user_connections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)  # 'canva', 'notebooklm', etc.
    access_token: Mapped[Optional[str]] = mapped_column(TEXT, nullable=True)
    refresh_token: Mapped[Optional[str]] = mapped_column(TEXT, nullable=True)
    token_expires_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    account_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    account_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    __table_args__ = (
        Index("idx_user_connections_user_tenant", "user_id", "tenant_id"),
        Index("idx_user_connections_user_tenant_provider", "user_id", "tenant_id", "provider", unique=True),
        Index("idx_user_connections_provider", "provider"),
    )

    def __repr__(self) -> str:
        return (
            f"<UserConnection(user_id={self.user_id}, provider={self.provider}, "
            f"account_email={self.account_email})>"
        )
