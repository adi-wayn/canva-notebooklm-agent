"""Custom exceptions for Canva API adapter."""

from typing import Optional, Dict, Any


class CanvaAPIError(Exception):
    """Base exception for Canva API errors."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """Initialize Canva API error.

        Args:
            message: Human-readable error message
            status_code: HTTP status code (if applicable)
            error_code: Canva-specific error code
            details: Additional error details from API
        """
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details or {}
        super().__init__(message)


class TokenRefreshError(CanvaAPIError):
    """Raised when token refresh fails."""

    pass


class RateLimitError(CanvaAPIError):
    """Raised when rate limit is exceeded."""

    def __init__(
        self,
        message: str,
        retry_after: Optional[int] = None,
        **kwargs,
    ):
        """Initialize rate limit error.

        Args:
            message: Error message
            retry_after: Seconds to wait before retrying
            **kwargs: Additional arguments for CanvaAPIError
        """
        super().__init__(message, **kwargs)
        self.retry_after = retry_after


class TransientError(CanvaAPIError):
    """Raised for transient errors (5xx, timeouts) that can be retried."""

    pass


class ValidationError(CanvaAPIError):
    """Raised for validation errors (4xx, not 401/429)."""

    pass


class AuthenticationError(CanvaAPIError):
    """Raised for authentication/authorization errors (401, 403)."""

    pass
