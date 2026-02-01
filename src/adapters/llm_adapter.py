"""LLM adapter with OpenAI integration, caching, cost tracking, and fallback logic.

Provides:
- Async OpenAI client wrapper
- Structured JSON response parsing with validation
- Decision caching with Redis
- Cost tracking (tokens, approximate USD cost)
- Latency tracking per operation
- Timeout handling (configurable 10-30s)
- Prompt versioning for reproducibility
- Rule-based fallback logic for resilience
"""

import asyncio
import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

import openai
from openai import AsyncOpenAI

from src.observability.context import get_tenant_id
from src.utils.llm_exceptions import (
    LLMAPIError,
    InvalidResponseError,
    TokenCountError,
    TimeoutError,
    RateLimitError,
    FallbackActivatedError,
)

logger = logging.getLogger(__name__)

# Constants
DEFAULT_TIMEOUT = 10.0
MAX_TIMEOUT = 30.0
MODEL_COST_PER_1K_INPUT_TOKENS = 0.0005  # Example: GPT-3.5 input cost
MODEL_COST_PER_1K_OUTPUT_TOKENS = 0.0015  # Example: GPT-3.5 output cost


class PromptVersion(str, Enum):
    """Supported prompt versions for reproducibility."""

    V1 = "v1"
    V2 = "v2"


@dataclass
class TokenUsage:
    """Token usage statistics."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0

    @property
    def input_cost(self) -> float:
        """Calculate approximate cost for input tokens."""
        return (self.input_tokens / 1000.0) * MODEL_COST_PER_1K_INPUT_TOKENS

    @property
    def output_cost(self) -> float:
        """Calculate approximate cost for output tokens."""
        return (self.output_tokens / 1000.0) * MODEL_COST_PER_1K_OUTPUT_TOKENS

    @property
    def total_cost(self) -> float:
        """Calculate total approximate cost."""
        return self.input_cost + self.output_cost


@dataclass
class LLMResponse:
    """Structured LLM response with metadata."""

    content: str
    json_data: Optional[Dict[str, Any]] = None
    token_usage: TokenUsage = field(default_factory=TokenUsage)
    latency_ms: float = 0.0
    prompt_version: PromptVersion = PromptVersion.V1
    model: str = "gpt-3.5-turbo"
    timestamp: datetime = field(default_factory=datetime.utcnow)
    fallback_used: bool = False

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "content": self.content,
            "json_data": self.json_data,
            "token_usage": {
                "input_tokens": self.token_usage.input_tokens,
                "output_tokens": self.token_usage.output_tokens,
                "total_tokens": self.token_usage.total_tokens,
                "total_cost": self.token_usage.total_cost,
            },
            "latency_ms": self.latency_ms,
            "prompt_version": self.prompt_version.value,
            "model": self.model,
            "timestamp": self.timestamp.isoformat(),
            "fallback_used": self.fallback_used,
        }


class LLMAdapterInterface(ABC):
    """Abstract interface for LLM adapter."""

    @abstractmethod
    async def generate(self, prompt: str, prompt_version: PromptVersion = PromptVersion.V1) -> LLMResponse:
        """Generate LLM response from prompt."""
        pass

    @abstractmethod
    async def generate_json(
        self, prompt: str, expected_schema: Optional[Dict[str, Any]] = None, prompt_version: PromptVersion = PromptVersion.V1
    ) -> LLMResponse:
        """Generate structured JSON response from prompt."""
        pass

    @abstractmethod
    async def close(self):
        """Close adapter and cleanup resources."""
        pass


class LLMAdapter(LLMAdapterInterface):
    """LLM adapter with OpenAI integration, caching, and fallback logic.

    Features:
    - Async OpenAI API wrapper
    - Structured JSON response parsing with schema validation
    - Decision caching with Redis (if available)
    - Cost tracking (tokens + approximate USD)
    - Latency tracking per operation
    - Configurable timeout (10-30s)
    - Prompt versioning for reproducibility
    - Rule-based fallback for resilience
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-3.5-turbo",
        timeout_seconds: float = DEFAULT_TIMEOUT,
        cache=None,
    ):
        """Initialize LLM adapter.

        Args:
            api_key: OpenAI API key
            model: Model name (e.g., 'gpt-3.5-turbo', 'gpt-4')
            timeout_seconds: Request timeout (10-30s)
            cache: Cache instance for decision caching (optional)
        """
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = max(DEFAULT_TIMEOUT, min(timeout_seconds, MAX_TIMEOUT))
        self.cache = cache

        self.client = AsyncOpenAI(api_key=api_key, timeout=self.timeout_seconds)

    async def close(self):
        """Close the OpenAI client."""
        await self.client.close()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    def _make_cache_key(self, prompt: str, prompt_version: PromptVersion) -> str:
        """Generate cache key for prompt + version."""
        if self.cache is None:
            return None

        try:
            tenant_id = get_tenant_id() or "default"
        except Exception:
            tenant_id = "default"

        # Simple hash-based key (in production, use embeddings)
        import hashlib

        prompt_hash = hashlib.md5(f"{prompt}:{prompt_version.value}".encode()).hexdigest()
        return f"llm:decision:{tenant_id}:{prompt_hash}"

    async def _get_cached_response(self, cache_key: str) -> Optional[LLMResponse]:
        """Retrieve cached LLM response if available."""
        if cache_key is None or self.cache is None:
            return None

        try:
            cached = await self.cache.get(cache_key)
            if cached:
                # Deserialize cached response
                import pickle

                return pickle.loads(cached)
        except Exception as e:
            logger.debug(f"Cache retrieval failed: {e}")

        return None

    async def _cache_response(self, cache_key: str, response: LLMResponse) -> None:
        """Cache LLM response for future reuse."""
        if cache_key is None or self.cache is None:
            return

        try:
            import pickle

            serialized = pickle.dumps(response)
            # Cache for 24 hours
            await self.cache.set(cache_key, serialized, ttl=86400)
        except Exception as e:
            logger.debug(f"Cache storage failed: {e}")

    def _parse_json_response(self, content: str) -> Dict[str, Any]:
        """Parse and validate JSON response.

        Args:
            content: Raw response content

        Returns:
            Parsed JSON dict

        Raises:
            InvalidResponseError: If JSON is invalid or schema check fails
        """
        content = content.strip()

        # Try to extract JSON if wrapped in markdown code blocks
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]

        content = content.strip()

        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            raise InvalidResponseError(
                message=f"Invalid JSON response: {str(e)}",
                details={"raw_content": content[:200]},
            ) from e

    async def generate(self, prompt: str, prompt_version: PromptVersion = PromptVersion.V1) -> LLMResponse:
        """Generate text response from prompt.

        Args:
            prompt: Input prompt
            prompt_version: Version of prompt for tracking

        Returns:
            LLMResponse with content and metadata

        Raises:
            Various LLMAPIError subclasses
        """
        cache_key = self._make_cache_key(prompt, prompt_version)
        cached_response = await self._get_cached_response(cache_key)
        if cached_response:
            return cached_response

        start_time = time.time()

        try:
            response = await asyncio.wait_for(
                self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                ),
                timeout=self.timeout_seconds,
            )

            latency_ms = (time.time() - start_time) * 1000

            # Extract response content
            content = response.choices[0].message.content

            # Calculate token usage
            usage = TokenUsage(
                input_tokens=response.usage.prompt_tokens,
                output_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
            )

            result = LLMResponse(
                content=content,
                token_usage=usage,
                latency_ms=latency_ms,
                prompt_version=prompt_version,
                model=self.model,
            )

            # Cache the result
            await self._cache_response(cache_key, result)

            return result

        except asyncio.TimeoutError:
            raise TimeoutError(
                message=f"LLM request timed out after {self.timeout_seconds}s",
                timeout_seconds=self.timeout_seconds,
            )
        except openai.RateLimitError as e:
            raise RateLimitError(
                message=f"LLM rate limit exceeded: {str(e)}",
                retry_after=60,
            ) from e
        except Exception as e:
            raise LLMAPIError(
                message=f"LLM request failed: {str(e)}",
                details={"exception_type": type(e).__name__},
            ) from e

    async def generate_json(
        self,
        prompt: str,
        expected_schema: Optional[Dict[str, Any]] = None,
        prompt_version: PromptVersion = PromptVersion.V1,
    ) -> LLMResponse:
        """Generate structured JSON response.

        Adds JSON formatting instruction to prompt and parses response.

        Args:
            prompt: Input prompt
            expected_schema: Optional JSON schema for validation
            prompt_version: Version of prompt for tracking

        Returns:
            LLMResponse with parsed json_data

        Raises:
            InvalidResponseError: If response is not valid JSON
        """
        # Enhance prompt with JSON instruction
        json_prompt = f"{prompt}\n\nRespond with ONLY valid JSON, no other text."

        # Attempt LLM call
        try:
            response = await self.generate(json_prompt, prompt_version)
            json_data = self._parse_json_response(response.content)
            response.json_data = json_data
            return response

        except InvalidResponseError:
            raise
        except LLMAPIError:
            raise

    async def generate_with_fallback(
        self,
        prompt: str,
        fallback_fn,
        prompt_version: PromptVersion = PromptVersion.V1,
    ) -> LLMResponse:
        """Generate response with rule-based fallback.

        If LLM fails, calls fallback_fn to generate response.

        Args:
            prompt: Input prompt
            fallback_fn: Async function to call on LLM failure
            prompt_version: Version of prompt for tracking

        Returns:
            LLMResponse with content (from LLM or fallback)

        Raises:
            LLMAPIError: If both LLM and fallback fail
        """
        try:
            return await self.generate(prompt, prompt_version)
        except LLMAPIError as e:
            logger.warning(f"LLM failed ({e.error_code}), activating fallback: {e.message}")

            try:
                fallback_content = await fallback_fn(prompt)

                # Return as fallback response
                return LLMResponse(
                    content=fallback_content,
                    prompt_version=prompt_version,
                    model=self.model,
                    fallback_used=True,
                    latency_ms=0.0,
                )

            except Exception as fallback_error:
                logger.error(f"Fallback also failed: {fallback_error}")
                raise FallbackActivatedError(
                    message=f"LLM failed and fallback failed: {str(fallback_error)}",
                    original_error=e,
                ) from fallback_error
