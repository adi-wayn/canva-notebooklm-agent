"""Test fixtures and mock helpers for LLM testing.

Provides:
- Mock OpenAI responses
- Mock cache implementation
- Response builders
- Mock async clients
"""

from datetime import datetime
from typing import Optional
from unittest.mock import AsyncMock, MagicMock

from src.adapters.llm_adapter import LLMResponse, PromptVersion, TokenUsage


def build_token_usage(
    input_tokens: int = 100,
    output_tokens: int = 50,
) -> TokenUsage:
    """Build a TokenUsage object for testing."""
    return TokenUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
    )


def build_llm_response(
    content: str = "Test response",
    json_data: dict = None,
    input_tokens: int = 50,
    output_tokens: int = 30,
    latency_ms: float = 100.0,
    prompt_version: PromptVersion = PromptVersion.V1,
    fallback_used: bool = False,
) -> LLMResponse:
    """Build a mock LLMResponse."""
    return LLMResponse(
        content=content,
        json_data=json_data,
        token_usage=TokenUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
        ),
        latency_ms=latency_ms,
        timestamp=datetime.now(),
        prompt_version=prompt_version,
        fallback_used=fallback_used,
    )


def build_openai_response(
    content: str = "Test response",
    input_tokens: int = 50,
    output_tokens: int = 30,
) -> MagicMock:
    """Build a mock OpenAI API response."""
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = content
    response.usage.prompt_tokens = input_tokens
    response.usage.completion_tokens = output_tokens
    response.usage.total_tokens = input_tokens + output_tokens
    return response


def mock_async_openai_client() -> AsyncMock:
    """Create a mock AsyncOpenAI client."""
    client = AsyncMock()
    client.chat.completions.create = AsyncMock()
    client.close = AsyncMock()
    return client


def mock_cache() -> AsyncMock:
    """Create a mock cache instance."""
    cache = AsyncMock()
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock()
    return cache
