"""Custom exception hierarchy for NotebookLM API client.

Mirrors the structure of canva_exceptions.py for consistency.
"""


class NotebookLMAPIError(Exception):
    """Base exception for all NotebookLM API errors.

    Attributes:
        message: Human-readable error message
        status_code: HTTP status code (if applicable)
        error_code: API-specific error code
        details: Additional error details (dict)
    """

    def __init__(self, message: str, status_code: int = None, error_code: str = None, details: dict = None):
        """Initialize NotebookLM API error."""
        self.message = message
        self.status_code = status_code
        self.error_code = error_code or "UNKNOWN_ERROR"
        self.details = details or {}
        super().__init__(self.message)

    def __repr__(self):
        return f"{self.__class__.__name__}(message={self.message!r}, status_code={self.status_code}, error_code={self.error_code!r})"


class TokenRefreshError(NotebookLMAPIError):
    """Raised when OAuth token refresh fails."""

    def __init__(self, message: str, status_code: int = None, error_code: str = None, details: dict = None):
        """Initialize token refresh error."""
        super().__init__(
            message=message,
            status_code=status_code or 401,
            error_code=error_code or "TOKEN_REFRESH_FAILED",
            details=details,
        )


class RateLimitError(NotebookLMAPIError):
    """Raised when API rate limit is exceeded.

    Attributes:
        retry_after: Recommended wait time in seconds before retrying
    """

    def __init__(self, message: str, retry_after: int = 60, status_code: int = None, error_code: str = None, details: dict = None):
        """Initialize rate limit error."""
        super().__init__(
            message=message,
            status_code=status_code or 429,
            error_code=error_code or "RATE_LIMIT_EXCEEDED",
            details=details,
        )
        self.retry_after = retry_after


class TransientError(NotebookLMAPIError):
    """Raised for transient errors (5xx, timeouts) that should be retried."""

    def __init__(self, message: str, status_code: int = None, error_code: str = None, details: dict = None):
        """Initialize transient error."""
        super().__init__(
            message=message,
            status_code=status_code,
            error_code=error_code or "TRANSIENT_ERROR",
            details=details,
        )


class ValidationError(NotebookLMAPIError):
    """Raised for validation errors (4xx responses, excluding 401/429)."""

    def __init__(self, message: str, status_code: int = None, error_code: str = None, details: dict = None):
        """Initialize validation error."""
        super().__init__(
            message=message,
            status_code=status_code or 400,
            error_code=error_code or "VALIDATION_ERROR",
            details=details,
        )


class AuthenticationError(NotebookLMAPIError):
    """Raised when authentication fails after token refresh attempt."""

    def __init__(self, message: str, status_code: int = None, error_code: str = None, details: dict = None):
        """Initialize authentication error."""
        super().__init__(
            message=message,
            status_code=status_code or 401,
            error_code=error_code or "AUTHENTICATION_FAILED",
            details=details,
        )
