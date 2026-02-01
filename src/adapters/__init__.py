"""
Adapters module.

Provides provider-agnostic interfaces for external APIs:
- Canva (design generation, content insertion, export)
- NotebookLM (content analysis, insight generation)
- LLM (OpenAI, Claude, self-hosted)
- Rate limiting and circuit breaker utilities
"""
from src.adapters.canva_adapter import CanvaAdapter, CanvaAdapterInterface
from src.adapters.notebooklm_adapter import NotebookLMAdapter, NotebookLMAdapterInterface
from src.utils.canva_exceptions import (
    CanvaAPIError,
    TokenRefreshError as CanvaTokenRefreshError,
    RateLimitError as CanvaRateLimitError,
    TransientError as CanvaTransientError,
    ValidationError as CanvaValidationError,
    AuthenticationError as CanvaAuthenticationError,
)
from src.utils.notebooklm_exceptions import (
    NotebookLMAPIError,
    TokenRefreshError as NotebookLMTokenRefreshError,
    RateLimitError as NotebookLMRateLimitError,
    TransientError as NotebookLMTransientError,
    ValidationError as NotebookLMValidationError,
    AuthenticationError as NotebookLMAuthenticationError,
)

__all__ = [
    # Canva
    "CanvaAdapter",
    "CanvaAdapterInterface",
    "CanvaAPIError",
    "CanvaTokenRefreshError",
    "CanvaRateLimitError",
    "CanvaTransientError",
    "CanvaValidationError",
    "CanvaAuthenticationError",
    # NotebookLM
    "NotebookLMAdapter",
    "NotebookLMAdapterInterface",
    "NotebookLMAPIError",
    "NotebookLMTokenRefreshError",
    "NotebookLMRateLimitError",
    "NotebookLMTransientError",
    "NotebookLMValidationError",
    "NotebookLMAuthenticationError",
]