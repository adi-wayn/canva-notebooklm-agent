"""
Core exception definitions for the system.

All custom exceptions inherit from AppException and include:
- Error code (for API responses)
- Category (transient, permanent, user)
- Recovery suggestions
"""

from enum import Enum
from typing import Any, Dict, Optional


class ErrorCategory(str, Enum):
    """Error categorization for handling strategy."""

    TRANSIENT = "transient"  # Retry with backoff
    PERMANENT = "permanent"  # Fail immediately
    USER = "user"  # Return to user for action


class AppException(Exception):
    """Base exception for all application errors."""

    code: str = "INTERNAL_ERROR"
    category: ErrorCategory = ErrorCategory.PERMANENT
    status_code: int = 500
    message: str = "An unexpected error occurred"

    def __init__(
        self,
        message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
    ):
        """Initialize exception."""
        self.message = message or self.message
        self.details = details or {}
        self.cause = cause
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to API response dict."""
        return {
            "error_id": id(self),
            "code": self.code,
            "message": self.message,
            "category": self.category.value,
            "details": self.details,
        }


# API & HTTP Errors


class APIError(AppException):
    """Base class for API errors."""

    code = "API_ERROR"
    status_code = 500


class BadRequestError(AppException):
    """Invalid request (400)."""

    code = "BAD_REQUEST"
    status_code = 400
    category = ErrorCategory.USER


class AuthenticationError(AppException):
    """Authentication failed (401)."""

    code = "AUTHENTICATION_ERROR"
    status_code = 401
    category = ErrorCategory.USER


class AuthorizationError(AppException):
    """Insufficient permissions (403)."""

    code = "AUTHORIZATION_ERROR"
    status_code = 403
    category = ErrorCategory.USER


class NotFoundError(AppException):
    """Resource not found (404)."""

    code = "NOT_FOUND"
    status_code = 404
    category = ErrorCategory.USER


class ConflictError(AppException):
    """Resource conflict (409)."""

    code = "CONFLICT"
    status_code = 409
    category = ErrorCategory.USER


class RateLimitError(AppException):
    """Rate limit exceeded (429)."""

    code = "RATE_LIMIT_EXCEEDED"
    status_code = 429
    category = ErrorCategory.TRANSIENT


# External Service Errors


class ExternalServiceError(AppException):
    """Base for external API failures."""

    code = "EXTERNAL_SERVICE_ERROR"
    status_code = 502
    category = ErrorCategory.TRANSIENT


class CanvaAPIError(ExternalServiceError):
    """Canva API error."""

    code = "CANVA_API_ERROR"


class NotebookLMAPIError(ExternalServiceError):
    """NotebookLM API error."""

    code = "NOTEBOOKLM_API_ERROR"


class LLMAPIError(ExternalServiceError):
    """LLM API error."""

    code = "LLM_API_ERROR"


# Database & Storage Errors


class DatabaseError(AppException):
    """Database operation failure."""

    code = "DATABASE_ERROR"
    status_code = 500
    category = ErrorCategory.TRANSIENT


class DataIntegrityError(DatabaseError):
    """Data integrity violation."""

    code = "DATA_INTEGRITY_ERROR"
    category = ErrorCategory.PERMANENT


# Workflow & Orchestration Errors


class WorkflowError(AppException):
    """Workflow execution error."""

    code = "WORKFLOW_ERROR"


class InvalidStateTransition(WorkflowError):
    """Invalid state transition attempted."""

    code = "INVALID_STATE_TRANSITION"
    category = ErrorCategory.PERMANENT


class TaskExecutionError(WorkflowError):
    """Task execution failure."""

    code = "TASK_EXECUTION_ERROR"


class CircuitBreakerOpen(AppException):
    """Circuit breaker is open (service failing)."""

    code = "CIRCUIT_BREAKER_OPEN"
    status_code = 503
    category = ErrorCategory.TRANSIENT


# Configuration Errors


class ConfigurationError(AppException):
    """Configuration error."""

    code = "CONFIGURATION_ERROR"
    status_code = 500
    category = ErrorCategory.PERMANENT
