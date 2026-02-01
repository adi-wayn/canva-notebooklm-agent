"""Custom exception hierarchy for LLM adapter.

Mirrors the structure of canva_exceptions.py and notebooklm_exceptions.py.
"""


class LLMAPIError(Exception):
    """Base exception for all LLM API errors.

    Attributes:
        message: Human-readable error message
        error_code: Error code (e.g., INVALID_JSON, TIMEOUT, RATE_LIMIT)
        details: Additional error details (dict)
    """

    def __init__(self, message: str, error_code: str = None, details: dict = None):
        """Initialize LLM API error."""
        self.message = message
        self.error_code = error_code or "UNKNOWN_ERROR"
        self.details = details or {}
        super().__init__(self.message)

    def __repr__(self):
        return f"{self.__class__.__name__}(message={self.message!r}, error_code={self.error_code!r})"


class InvalidResponseError(LLMAPIError):
    """Raised when LLM response is invalid or unparseable."""

    def __init__(self, message: str, error_code: str = None, details: dict = None):
        """Initialize invalid response error."""
        super().__init__(
            message=message,
            error_code=error_code or "INVALID_RESPONSE",
            details=details,
        )


class TokenCountError(LLMAPIError):
    """Raised when token count cannot be calculated or exceeds limit."""

    def __init__(self, message: str, error_code: str = None, details: dict = None):
        """Initialize token count error."""
        super().__init__(
            message=message,
            error_code=error_code or "TOKEN_COUNT_ERROR",
            details=details,
        )


class TimeoutError(LLMAPIError):
    """Raised when LLM request times out."""

    def __init__(self, message: str, timeout_seconds: float = None, error_code: str = None, details: dict = None):
        """Initialize timeout error."""
        super().__init__(
            message=message,
            error_code=error_code or "TIMEOUT",
            details=details,
        )
        self.timeout_seconds = timeout_seconds


class RateLimitError(LLMAPIError):
    """Raised when LLM API rate limit is exceeded."""

    def __init__(self, message: str, retry_after: int = 60, error_code: str = None, details: dict = None):
        """Initialize rate limit error."""
        super().__init__(
            message=message,
            error_code=error_code or "RATE_LIMIT_EXCEEDED",
            details=details,
        )
        self.retry_after = retry_after


class FallbackActivatedError(LLMAPIError):
    """Raised when fallback logic is activated due to LLM failure.

    This is informational (not necessarily a failure condition).
    """

    def __init__(self, message: str, original_error: Exception = None, error_code: str = None, details: dict = None):
        """Initialize fallback activated error."""
        super().__init__(
            message=message,
            error_code=error_code or "FALLBACK_ACTIVATED",
            details=details,
        )
        self.original_error = original_error


class LLMTimeoutError(TimeoutError):
    """Backward-compatible alias for TimeoutError."""

    pass
