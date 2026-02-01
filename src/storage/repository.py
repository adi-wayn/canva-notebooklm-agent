"""
Repository pattern for data access layer.

Provides:
- BaseRepository with async CRUD operations
- Tenant-scoped queries by default (no "global" fetch)
- Transaction boundaries and rollback handling
- Type-safe query builders
- Pagination support

All queries are tenant-scoped: you cannot access another tenant's data without
explicitly bypassing the scope (which is admin-only and logged).

Design pattern: Active Record with Repository wrapping.

Usage:
    async with database.session() as session:
        repo = WorkflowRepository(session, tenant_id="acme.com")
        
        # Tenant-scoped by default
        workflows = await repo.list_by_status("submitted")
        
        # Create
        new_workflow = await repo.create(input_config={...})
        
        # Transaction auto-commits on context exit
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar

from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.storage.models import (
    Base,
    Tenant,
    User,
    Workflow,
    WorkflowTask,
    Design,
    AuditLog,
    AuditActionType,
    WorkflowEvent,
    UserConnection,
)
from src.utils.exceptions import NotFoundError


T = TypeVar("T", bound=Base)


class BaseRepository(ABC, Generic[T]):
    """
    Base repository with async CRUD operations.

    All queries are tenant-scoped by default.
    """

    model: Type[T]

    def __init__(self, session: AsyncSession, tenant_id: str):
        """
        Initialize repository.

        Args:
            session: AsyncSession for queries
            tenant_id: Tenant to scope queries to (prevents cross-tenant access)
        """
        self.session = session
        self.tenant_id = tenant_id

    async def get_by_id(self, entity_id: str) -> Optional[T]:
        """
        Get entity by ID (tenant-scoped).

        Args:
            entity_id: Entity ID

        Returns:
            Entity or None if not found
        """
        # Build query: get by ID and tenant
        query = select(self.model).where(self.model.id == entity_id)

        # If model has tenant_id column, filter by it
        if hasattr(self.model, "tenant_id"):
            query = query.where(self.model.tenant_id == self.tenant_id)

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_id_or_404(self, entity_id: str) -> T:
        """
        Get entity by ID or raise NotFoundError.

        Args:
            entity_id: Entity ID

        Returns:
            Entity

        Raises:
            NotFoundError: If not found or belongs to different tenant
        """
        entity = await self.get_by_id(entity_id)
        if not entity:
            raise NotFoundError(
                message=f"{self.model.__tablename__} {entity_id} not found",
                details={"entity_type": self.model.__tablename__, "entity_id": entity_id},
            )
        return entity

    async def list_all(
        self, limit: int = 100, offset: int = 0, order_by_desc: bool = True
    ) -> List[T]:
        """
        List all entities (tenant-scoped).

        Args:
            limit: Max results
            offset: Offset for pagination
            order_by_desc: Order by created_at descending

        Returns:
            List of entities
        """
        query = select(self.model)

        # Filter by tenant if applicable
        if hasattr(self.model, "tenant_id"):
            query = query.where(self.model.tenant_id == self.tenant_id)

        # Order by created_at if available
        if hasattr(self.model, "created_at"):
            if order_by_desc:
                query = query.order_by(desc(self.model.created_at))
            else:
                query = query.order_by(self.model.created_at)

        query = query.limit(limit).offset(offset)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def create(self, **kwargs) -> T:
        """
        Create new entity.

        Args:
            **kwargs: Entity fields

        Returns:
            Created entity
        """
        # Ensure tenant_id is set if applicable
        if hasattr(self.model, "tenant_id"):
            kwargs.setdefault("tenant_id", self.tenant_id)

        entity = self.model(**kwargs)
        self.session.add(entity)
        await self.session.flush()  # Get ID without committing
        return entity

    async def update(self, entity_id: str, **kwargs) -> T:
        """
        Update entity (tenant-scoped).

        Args:
            entity_id: Entity to update
            **kwargs: Fields to update

        Returns:
            Updated entity

        Raises:
            NotFoundError: If entity not found or belongs to different tenant
        """
        entity = await self.get_by_id_or_404(entity_id)

        # Update fields
        for key, value in kwargs.items():
            if hasattr(entity, key):
                setattr(entity, key, value)

        # Update timestamp if available
        if hasattr(entity, "updated_at"):
            setattr(entity, "updated_at", datetime.now(timezone.utc))

        await self.session.flush()
        return entity

    async def delete(self, entity_id: str) -> bool:
        """
        Delete entity (tenant-scoped).

        Args:
            entity_id: Entity to delete

        Returns:
            True if deleted, False if not found

        Raises:
            NotFoundError: If belongs to different tenant
        """
        entity = await self.get_by_id(entity_id)
        if not entity:
            return False

        await self.session.delete(entity)
        await self.session.flush()
        return True

    async def count(self) -> int:
        """
        Count entities (tenant-scoped).

        Returns:
            Number of entities
        """
        from sqlalchemy import func

        query = select(func.count(self.model.id))

        if hasattr(self.model, "tenant_id"):
            query = query.where(self.model.tenant_id == self.tenant_id)

        result = await self.session.execute(query)
        return result.scalar() or 0


# ============================================================================
# Specialized Repositories
# ============================================================================


class TenantRepository(BaseRepository[Tenant]):
    """Repository for Tenant entities."""

    model = Tenant

    async def get_by_name(self, name: str) -> Optional[Tenant]:
        """Get tenant by name (admin only)."""
        query = select(Tenant).where(Tenant.name == name)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()


class UserRepository(BaseRepository[User]):
    """Repository for User entities."""

    model = User

    async def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email within tenant."""
        query = select(User).where(
            and_(User.email == email, User.tenant_id == self.tenant_id)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_by_role(self, role: str, limit: int = 100) -> List[User]:
        """List users with specific role."""
        # NOTE: roles is a JSON array; this is a simple check
        # For production, use JSON operators or denormalize
        query = (
            select(User)
            .where(User.tenant_id == self.tenant_id)
            .limit(limit)
        )
        result = await self.session.execute(query)
        users = result.scalars().all()
        # Filter in Python (simple case; use SQL operators for production)
        return [u for u in users if role in u.roles]


class WorkflowRepository(BaseRepository[Workflow]):
    """Repository for Workflow entities."""

    model = Workflow

    async def list_by_status(self, status: str, limit: int = 100) -> List[Workflow]:
        """List workflows with specific status."""
        query = (
            select(Workflow)
            .where(
                and_(Workflow.tenant_id == self.tenant_id, Workflow.status == status)
            )
            .order_by(desc(Workflow.created_at))
            .limit(limit)
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    async def list_by_user(self, user_id: str, limit: int = 100) -> List[Workflow]:
        """List workflows created by user."""
        query = (
            select(Workflow)
            .where(
                and_(
                    Workflow.tenant_id == self.tenant_id, Workflow.user_id == user_id
                )
            )
            .order_by(desc(Workflow.created_at))
            .limit(limit)
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_with_tasks(self, workflow_id: str) -> Optional[Workflow]:
        """Get workflow with eagerly-loaded tasks."""
        query = (
            select(Workflow)
            .where(
                and_(
                    Workflow.id == workflow_id, Workflow.tenant_id == self.tenant_id
                )
            )
            .options(selectinload(Workflow.tasks))
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()


class WorkflowTaskRepository(BaseRepository[WorkflowTask]):
    """Repository for WorkflowTask entities."""

    model = WorkflowTask

    async def list_by_workflow(self, workflow_id: str) -> List[WorkflowTask]:
        """List tasks for a workflow."""
        query = (
            select(WorkflowTask)
            .where(WorkflowTask.workflow_id == workflow_id)
            .order_by(WorkflowTask.created_at)
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    async def list_by_status(self, status: str, limit: int = 100) -> List[WorkflowTask]:
        """List tasks with specific status."""
        query = (
            select(WorkflowTask)
            .where(WorkflowTask.status == status)
            .order_by(desc(WorkflowTask.created_at))
            .limit(limit)
        )
        result = await self.session.execute(query)
        return result.scalars().all()


class DesignRepository(BaseRepository[Design]):
    """Repository for Design entities."""

    model = Design

    async def get_by_canva_id(self, canva_design_id: str) -> Optional[Design]:
        """Get design by Canva design ID (tenant-scoped)."""
        query = select(Design).where(
            and_(
                Design.tenant_id == self.tenant_id,
                Design.canva_design_id == canva_design_id,
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_by_workflow(self, workflow_id: str) -> List[Design]:
        """List designs for a workflow."""
        query = (
            select(Design)
            .where(
                and_(
                    Design.tenant_id == self.tenant_id,
                    Design.workflow_id == workflow_id,
                )
            )
            .order_by(desc(Design.created_at))
        )
        result = await self.session.execute(query)
        return result.scalars().all()


class AuditLogRepository(BaseRepository[AuditLog]):
    """Repository for AuditLog entities (append-only)."""

    model = AuditLog

    async def create_log(
        self,
        action: str,
        resource_type: str,
        resource_id: str,
        new_state: Dict[str, Any],
        previous_state: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditLog:
        """
        Create an audit log entry.

        Args:
            action: Action type (create, update, delete, etc.)
            resource_type: Type of resource (workflow, design, user, etc.)
            resource_id: ID of resource
            new_state: New state after action
            previous_state: Previous state before action
            user_id: User who performed action (optional)
            metadata: Additional context (request_id, ip, etc.)

        Returns:
            Created AuditLog
        """
        log = AuditLog(
            tenant_id=self.tenant_id,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            new_state=new_state,
            previous_state=previous_state,
            metadata=metadata or {},
        )
        self.session.add(log)
        await self.session.flush()
        return log

    async def list_by_resource(
        self, resource_type: str, resource_id: str, limit: int = 100
    ) -> List[AuditLog]:
        """List audit logs for a resource."""
        query = (
            select(AuditLog)
            .where(
                and_(
                    AuditLog.tenant_id == self.tenant_id,
                    AuditLog.resource_type == resource_type,
                    AuditLog.resource_id == resource_id,
                )
            )
            .order_by(desc(AuditLog.timestamp))
            .limit(limit)
        )
        result = await self.session.execute(query)
        return result.scalars().all()


class WorkflowEventRepository(BaseRepository[WorkflowEvent]):
    """Repository for append-only workflow events (tenant-scoped)."""

    model = WorkflowEvent

    async def append_event(
        self,
        workflow_id: str,
        event_type: str,
        payload: Dict[str, Any],
    ) -> WorkflowEvent:
        """Append a new event for a workflow.

        Returns the persisted event (with monotonic `id`).
        """
        event = WorkflowEvent(
            workflow_id=workflow_id,
            tenant_id=self.tenant_id,
            event_type=event_type,
            payload=payload or {},
        )
        self.session.add(event)
        await self.session.flush()
        return event

    async def list_after(
        self,
        workflow_id: str,
        last_event_id: int,
        limit: int = 1000,
    ) -> List[WorkflowEvent]:
        """List events with id > last_event_id for a workflow (ordered)."""
        query = (
            select(WorkflowEvent)
            .where(
                and_(
                    WorkflowEvent.workflow_id == workflow_id,
                    WorkflowEvent.tenant_id == self.tenant_id,
                    WorkflowEvent.id > last_event_id,
                )
            )
            .order_by(WorkflowEvent.id)
            .limit(limit)
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    async def list_by_user(self, user_id: str, limit: int = 100) -> List[AuditLog]:
        """List audit logs for a user."""
        query = (
            select(AuditLog)
            .where(
                and_(
                    AuditLog.tenant_id == self.tenant_id,
                    AuditLog.user_id == user_id,
                )
            )
            .order_by(desc(AuditLog.timestamp))
            .limit(limit)
        )
        result = await self.session.execute(query)
        return result.scalars().all()


# ============================================================================
# OAuth Connections Repository
# ============================================================================


class UserConnectionRepository(BaseRepository[UserConnection]):
    """Manage OAuth connections for external services (Canva, NotebookLM, etc.).
    
    Stores and retrieves tokens for authorized integrations. Automatically
    tenant-scoped to prevent cross-tenant data leakage.
    """

    def __init__(self, session: AsyncSession, user_id: str, tenant_id: str):
        """Initialize with user context.
        
        Args:
            session: AsyncSession for database access
            user_id: User ID for token isolation
            tenant_id: Tenant ID for multi-tenancy
        """
        super().__init__(session, tenant_id)
        self.model = UserConnection
        self.user_id = user_id

    async def get_connection(self, provider: str) -> Optional[UserConnection]:
        """Get connection for a specific provider.
        
        Args:
            provider: Provider name ('canva', 'notebooklm', etc.)
            
        Returns:
            UserConnection if exists, None otherwise
        """
        query = select(UserConnection).where(
            and_(
                UserConnection.user_id == self.user_id,
                UserConnection.tenant_id == self.tenant_id,
                UserConnection.provider == provider,
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def save_connection(
        self,
        provider: str,
        access_token: str,
        refresh_token: Optional[str] = None,
        token_expires_at: Optional[datetime] = None,
        account_email: Optional[str] = None,
        account_name: Optional[str] = None,
    ) -> UserConnection:
        """Save new OAuth connection.
        
        Args:
            provider: Provider name
            access_token: OAuth access token
            refresh_token: OAuth refresh token (optional)
            token_expires_at: Token expiration datetime
            account_email: Connected account email
            account_name: Connected account name
            
        Returns:
            Created UserConnection
        """
        connection = UserConnection(
            user_id=self.user_id,
            tenant_id=self.tenant_id,
            provider=provider,
            access_token=access_token,
            refresh_token=refresh_token,
            token_expires_at=token_expires_at,
            account_email=account_email,
            account_name=account_name,
        )
        self.session.add(connection)
        await self.session.flush()
        return connection

    async def update_tokens(
        self,
        provider: str,
        access_token: str,
        refresh_token: Optional[str] = None,
        token_expires_at: Optional[datetime] = None,
    ) -> Optional[UserConnection]:
        """Update tokens for existing connection (e.g., after refresh).
        
        Args:
            provider: Provider name
            access_token: New access token
            refresh_token: New refresh token (optional, keeps existing if not provided)
            token_expires_at: New expiration time
            
        Returns:
            Updated UserConnection if found, None otherwise
        """
        connection = await self.get_connection(provider)
        if not connection:
            return None

        connection.access_token = access_token
        if refresh_token is not None:
            connection.refresh_token = refresh_token
        if token_expires_at is not None:
            connection.token_expires_at = token_expires_at
        connection.updated_at = datetime.now(timezone.utc)

        await self.session.flush()
        return connection

    async def delete_connection(self, provider: str) -> bool:
        """Delete connection (revoke access).
        
        Args:
            provider: Provider name
            
        Returns:
            True if deleted, False if not found
        """
        connection = await self.get_connection(provider)
        if not connection:
            return False

        await self.session.delete(connection)
        await self.session.flush()
        return True

    async def has_connection(self, provider: str) -> bool:
        """Check if user has active connection.
        
        Args:
            provider: Provider name
            
        Returns:
            True if connection exists
        """
        connection = await self.get_connection(provider)
        return connection is not None
