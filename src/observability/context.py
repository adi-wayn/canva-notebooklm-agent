"""Request context management using contextvars.

Provides thread-safe, async-aware context storage for request-scoped values:
- request_id: Unique identifier for request tracing
- tenant_id: Tenant identifier for multi-tenant isolation
- user_id: User identifier for audit logging (optional)

Usage:
    # In middleware:
    set_request_id("uuid-value")
    set_tenant_id("tenant-123")

    # In handlers/logging:
    request_id = get_request_id()
    tenant_id = get_tenant_id()

    # For async task spawning, preserve context:
    token = reset_context()  # Save current context
    # ... task execution ...
    restore_context(token)   # Restore after task
"""

from contextvars import ContextVar, Token
from typing import Optional
import uuid

# ContextVar declarations - thread-safe, async-aware
request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
tenant_id_var: ContextVar[Optional[str]] = ContextVar("tenant_id", default=None)
user_id_var: ContextVar[Optional[str]] = ContextVar("user_id", default=None)


def generate_request_id() -> str:
    """Generate a new request ID (UUID)."""
    return str(uuid.uuid4())


def set_request_id(request_id: str) -> Token[Optional[str]]:
    """Set the request ID in context. Returns token for restoration."""
    return request_id_var.set(request_id)


def get_request_id() -> Optional[str]:
    """Get the current request ID from context."""
    return request_id_var.get()


def set_tenant_id(tenant_id: str) -> Token[Optional[str]]:
    """Set the tenant ID in context. Returns token for restoration."""
    return tenant_id_var.set(tenant_id)


def get_tenant_id() -> Optional[str]:
    """Get the current tenant ID from context."""
    return tenant_id_var.get()


def set_user_id(user_id: str) -> Token[Optional[str]]:
    """Set the user ID in context. Returns token for restoration."""
    return user_id_var.set(user_id)


def get_user_id() -> Optional[str]:
    """Get the current user ID from context."""
    return user_id_var.get()


class ContextReset:
    """Manage context state for async task spawning.
    
    Saves and restores context across async boundaries.
    
    Usage:
        reset = ContextReset()
        # context is now cleared
        # ... spawn async task ...
        reset.restore()  # restore original context
    """

    def __init__(self) -> None:
        """Save current context state."""
        self._request_id_token: Optional[Token[Optional[str]]] = None
        self._tenant_id_token: Optional[Token[Optional[str]]] = None
        self._user_id_token: Optional[Token[Optional[str]]] = None

        # Save current values
        self._saved_request_id = get_request_id()
        self._saved_tenant_id = get_tenant_id()
        self._saved_user_id = get_user_id()

        # Clear context
        self.clear()

    def clear(self) -> None:
        """Clear all context variables."""
        request_id_var.set(None)
        tenant_id_var.set(None)
        user_id_var.set(None)

    def restore(self) -> None:
        """Restore previously saved context state."""
        if self._saved_request_id is not None:
            request_id_var.set(self._saved_request_id)
        if self._saved_tenant_id is not None:
            tenant_id_var.set(self._saved_tenant_id)
        if self._saved_user_id is not None:
            user_id_var.set(self._saved_user_id)


def get_context_dict() -> dict:
    """Get all context values as a dictionary (for logging/debugging)."""
    return {
        "request_id": get_request_id(),
        "tenant_id": get_tenant_id(),
        "user_id": get_user_id(),
    }
