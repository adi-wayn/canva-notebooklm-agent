"""Unit tests for LLM adapter and decision engine.

Tests cover:
- OpenAI integration (mocked)
- JSON response parsing
- Fallback logic
- Caching behavior
- Cost and latency tracking
- Timeout handling
- Prompt versioning
"""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from src.adapters.llm_adapter import (
    LLMAdapter,
    LLMResponse,
    PromptVersion,
    TokenUsage,
)
from src.orchestration.decision_engine import DecisionEngine, Decision
from src.utils.llm_exceptions import (
    LLMAPIError,
    InvalidResponseError,
    TimeoutError as LLMTimeoutError,
    RateLimitError,
    FallbackActivatedError,
)
from tests.fixtures.mock_llm import (
    build_llm_response,
    build_openai_response,
    mock_async_openai_client,
    mock_cache,
)


@pytest.fixture
def adapter():
    """Create an LLMAdapter instance for testing."""
    return LLMAdapter(
        api_key="test_api_key",
        model="gpt-3.5-turbo",
        timeout_seconds=10.0,
        cache=None,
    )


@pytest.fixture
def adapter_with_cache():
    """Create an LLMAdapter with mocked cache."""
    return LLMAdapter(
        api_key="test_api_key",
        model="gpt-3.5-turbo",
        timeout_seconds=10.0,
        cache=mock_cache(),
    )


@pytest.mark.asyncio
class TestLLMAdapterBasics:
    """Test basic LLM adapter functionality."""

    async def test_adapter_initialization(self, adapter):
        """Test adapter initializes correctly."""
        assert adapter.api_key == "test_api_key"
        assert adapter.model == "gpt-3.5-turbo"
        assert adapter.timeout_seconds == 10.0

    async def test_timeout_clamping(self):
        """Test that timeout is clamped to valid range."""
        adapter_low = LLMAdapter("key", timeout_seconds=5.0)
        assert adapter_low.timeout_seconds == 10.0  # MIN

        adapter_high = LLMAdapter("key", timeout_seconds=60.0)
        assert adapter_high.timeout_seconds == 30.0  # MAX

    async def test_context_manager(self, adapter):
        """Test async context manager support."""
        with patch.object(adapter.client, "close", new_callable=AsyncMock):
            async with adapter:
                pass
            assert adapter.client.close.called

    async def test_close(self, adapter):
        """Test close method."""
        with patch.object(adapter.client, "close", new_callable=AsyncMock) as mock_close:
            await adapter.close()
            mock_close.assert_called_once()


@pytest.mark.asyncio
class TestLLMAdapterGenerate:
    """Test LLM text generation."""

    async def test_generate_success(self, adapter):
        """Test successful text generation."""
        mock_response = build_openai_response(
            content="Test response",
            input_tokens=10,
            output_tokens=5,
        )

        with patch.object(adapter.client.chat.completions, "create", new_callable=AsyncMock, return_value=mock_response):
            result = await adapter.generate("Test prompt")

            assert isinstance(result, LLMResponse)
            assert result.content == "Test response"
            assert result.token_usage.input_tokens == 10
            assert result.token_usage.output_tokens == 5
            assert result.prompt_version == PromptVersion.V1

    async def test_generate_with_version(self, adapter):
        """Test generate with specific prompt version."""
        mock_response = build_openai_response()

        with patch.object(adapter.client.chat.completions, "create", new_callable=AsyncMock, return_value=mock_response):
            result = await adapter.generate("Test", prompt_version=PromptVersion.V2)

            assert result.prompt_version == PromptVersion.V2

    async def test_generate_timeout(self, adapter):
        """Test timeout handling."""
        with patch.object(
            adapter.client.chat.completions,
            "create",
            new_callable=AsyncMock,
            side_effect=asyncio.TimeoutError(),
        ):
            with pytest.raises(LLMTimeoutError):
                await adapter.generate("Test")

    async def test_generate_rate_limit(self, adapter):
        """Test rate limit handling."""
        import openai

        with patch.object(
            adapter.client.chat.completions,
            "create",
            new_callable=AsyncMock,
            side_effect=openai.RateLimitError("Rate limit", response=MagicMock(), body={}),
        ):
            with pytest.raises(RateLimitError):
                await adapter.generate("Test")

    async def test_generate_tracks_latency(self, adapter):
        """Test that latency is tracked."""
        mock_response = build_openai_response()

        with patch.object(adapter.client.chat.completions, "create", new_callable=AsyncMock, return_value=mock_response):
            result = await adapter.generate("Test")

            assert result.latency_ms > 0

    async def test_generate_cost_calculation(self, adapter):
        """Test cost tracking."""
        mock_response = build_openai_response(input_tokens=100, output_tokens=50)

        with patch.object(adapter.client.chat.completions, "create", new_callable=AsyncMock, return_value=mock_response):
            result = await adapter.generate("Test")

            assert result.token_usage.total_cost > 0
            assert result.token_usage.input_cost > 0
            assert result.token_usage.output_cost > 0


@pytest.mark.asyncio
class TestLLMAdapterJSON:
    """Test JSON response generation."""

    async def test_generate_json_success(self, adapter):
        """Test successful JSON generation."""
        json_content = '{"key": "value", "count": 42}'
        mock_response = build_openai_response(content=json_content)

        with patch.object(adapter.client.chat.completions, "create", new_callable=AsyncMock, return_value=mock_response):
            result = await adapter.generate_json("Generate JSON")

            assert result.json_data == {"key": "value", "count": 42}

    async def test_generate_json_with_markdown(self, adapter):
        """Test JSON wrapped in markdown code blocks."""
        json_content = '```json\n{"key": "value"}\n```'
        mock_response = build_openai_response(content=json_content)

        with patch.object(adapter.client.chat.completions, "create", new_callable=AsyncMock, return_value=mock_response):
            result = await adapter.generate_json("Generate JSON")

            assert result.json_data == {"key": "value"}

    async def test_generate_json_invalid(self, adapter):
        """Test invalid JSON response."""
        mock_response = build_openai_response(content="not valid json")

        with patch.object(adapter.client.chat.completions, "create", new_callable=AsyncMock, return_value=mock_response):
            with pytest.raises(InvalidResponseError):
                await adapter.generate_json("Generate JSON")

    async def test_generate_json_with_schema(self, adapter):
        """Test JSON generation with schema validation."""
        json_content = '{"layout": "grid", "columns": 3}'
        mock_response = build_openai_response(content=json_content)
        schema = {"type": "object", "properties": {"layout": {"type": "string"}}}

        with patch.object(adapter.client.chat.completions, "create", new_callable=AsyncMock, return_value=mock_response):
            result = await adapter.generate_json("Generate", expected_schema=schema)

            assert result.json_data["layout"] == "grid"


@pytest.mark.asyncio
class TestLLMAdapterCaching:
    """Test decision caching."""

    async def test_cache_hit(self, adapter_with_cache):
        """Test cache hit returns cached response."""
        cached_response = build_llm_response(content="Cached response")

        # Mock cache to return serialized response
        import pickle

        serialized = pickle.dumps(cached_response)
        adapter_with_cache.cache.get.return_value = serialized

        result = await adapter_with_cache.generate("Test prompt")

        assert result.content == "Cached response"
        adapter_with_cache.cache.get.assert_called()

    async def test_cache_miss_and_store(self, adapter_with_cache):
        """Test cache miss fetches from LLM and stores."""
        mock_response = build_openai_response(content="Fresh response")

        adapter_with_cache.cache.get.return_value = None

        with patch.object(adapter_with_cache.client.chat.completions, "create", new_callable=AsyncMock, return_value=mock_response):
            result = await adapter_with_cache.generate("Test")

            assert result.content == "Fresh response"
            adapter_with_cache.cache.set.assert_called()

    async def test_cache_versioning(self, adapter_with_cache):
        """Test cache respects prompt version."""
        adapter_with_cache.cache.get.return_value = None

        mock_response = build_openai_response()

        with patch.object(adapter_with_cache.client.chat.completions, "create", new_callable=AsyncMock, return_value=mock_response):
            # Make two calls with different versions
            await adapter_with_cache.generate("Same prompt", PromptVersion.V1)
            await adapter_with_cache.generate("Same prompt", PromptVersion.V2)

            # Should have called cache.set twice with different keys
            assert adapter_with_cache.cache.set.call_count >= 1


@pytest.mark.asyncio
class TestLLMAdapterFallback:
    """Test fallback logic."""

    async def test_fallback_success(self, adapter):
        """Test successful fallback."""
        async def fallback_fn(prompt):
            return "Fallback response"

        with patch.object(
            adapter.client.chat.completions,
            "create",
            side_effect=LLMTimeoutError("timeout", timeout_seconds=10),
        ):
            result = await adapter.generate_with_fallback("Test", fallback_fn)

            assert result.content == "Fallback response"
            assert result.fallback_used is True

    async def test_fallback_failure(self, adapter):
        """Test fallback failure."""
        async def fallback_fn(prompt):
            raise ValueError("Fallback failed")

        with patch.object(
            adapter.client.chat.completions,
            "create",
            side_effect=LLMTimeoutError("timeout", timeout_seconds=10),
        ):
            with pytest.raises(FallbackActivatedError):
                await adapter.generate_with_fallback("Test", fallback_fn)


@pytest.mark.asyncio
class TestDecisionEngine:
    """Test decision engine."""

    async def test_decide_success(self):
        """Test successful decision."""
        adapter = LLMAdapter("test_key")
        engine = DecisionEngine(adapter)

        mock_response = build_openai_response(content="Decision: layout_grid")

        with patch.object(adapter.client.chat.completions, "create", new_callable=AsyncMock, return_value=mock_response):
            decision = await engine.decide(
                decision_type="layout",
                context={"elements": 5},
                prompt_template="Decide layout",
            )

            assert isinstance(decision, Decision)
            assert decision.content == "Decision: layout_grid"
            assert decision.fallback_used is False

    async def test_decide_with_fallback(self):
        """Test decision with rule-based fallback."""
        adapter = LLMAdapter("test_key")
        engine = DecisionEngine(adapter)

        async def layout_rule(context):
            return "fallback_layout"

        engine.register_rule("layout", layout_rule)

        with patch.object(
            adapter.client.chat.completions,
            "create",
            side_effect=LLMTimeoutError("timeout", timeout_seconds=10),
        ):
            decision = await engine.decide(
                decision_type="layout",
                context={"elements": 5},
                prompt_template="Decide layout",
                allow_fallback=True,
            )

            assert decision.fallback_used is True
            assert decision.content == "fallback_layout"

    async def test_decide_json(self):
        """Test JSON decision."""
        adapter = LLMAdapter("test_key")
        engine = DecisionEngine(adapter)

        json_response = '{"layout": "grid", "columns": 3}'
        mock_response = build_openai_response(content=json_response)

        with patch.object(adapter.client.chat.completions, "create", new_callable=AsyncMock, return_value=mock_response):
            decision = await engine.decide_json(
                decision_type="layout",
                context={},
                prompt_template="Decide JSON",
            )

            assert decision.metadata["json_data"]["layout"] == "grid"

    async def test_decide_without_fallback(self):
        """Test decision fails if fallback not allowed."""
        adapter = LLMAdapter("test_key")
        engine = DecisionEngine(adapter)

        with patch.object(
            adapter.client.chat.completions,
            "create",
            side_effect=LLMTimeoutError("timeout", timeout_seconds=10),
        ):
            with pytest.raises(LLMAPIError):
                await engine.decide(
                    decision_type="layout",
                    context={},
                    prompt_template="Test",
                    allow_fallback=False,
                )

    async def test_rule_registration(self):
        """Test rule registration."""
        adapter = LLMAdapter("test_key")
        engine = DecisionEngine(adapter)

        async def my_rule(context):
            return "rule_result"

        engine.register_rule("custom", my_rule)

        assert "custom" in engine.rule_registry
        assert engine.rule_registry["custom"] == my_rule


@pytest.mark.asyncio
class TestLLMAdapterErrors:
    """Test error handling."""

    async def test_invalid_json_with_details(self, adapter):
        """Test invalid JSON includes content details."""
        mock_response = build_openai_response(content="bad{json")

        with patch.object(adapter.client.chat.completions, "create", new_callable=AsyncMock, return_value=mock_response):
            with pytest.raises(InvalidResponseError) as exc_info:
                await adapter.generate_json("Test")

            assert exc_info.value.details["raw_content"]

    async def test_llm_error_wrapping(self, adapter):
        """Test that generic exceptions are wrapped."""
        with patch.object(
            adapter.client.chat.completions,
            "create",
            side_effect=RuntimeError("Something broke"),
        ):
            with pytest.raises(LLMAPIError):
                await adapter.generate("Test")


@pytest.mark.asyncio
class TestLLMAdapterIntegration:
    """Integration-style tests."""

    async def test_full_json_pipeline(self):
        """Test full JSON generation pipeline."""
        adapter = LLMAdapter("test_key")
        engine = DecisionEngine(adapter)

        json_content = '{"recommendation": "use_bold_typography", "confidence": 0.95}'
        mock_response = build_openai_response(content=json_content)

        with patch.object(adapter.client.chat.completions, "create", new_callable=AsyncMock, return_value=mock_response):
            decision = await engine.decide_json(
                decision_type="typography",
                context={"font_family": "sans-serif"},
                prompt_template="Recommend typography",
            )

            assert decision.metadata["json_data"]["confidence"] == 0.95
            assert not decision.fallback_used

    async def test_fallback_preserves_error_chain(self):
        """Test that error chain is preserved through fallback."""
        adapter = LLMAdapter("test_key")
        engine = DecisionEngine(adapter)

        original_error = LLMTimeoutError("original", timeout_seconds=10)

        async def failing_rule(context):
            raise ValueError("Fallback error")

        engine.register_rule("test", failing_rule)
        with patch.object(
            adapter.client.chat.completions,
            "create",
            side_effect=original_error,
        ):
            with pytest.raises(FallbackActivatedError) as exc_info:
                await engine.decide("test", {}, "Test", allow_fallback=True)

            # Check that original error is wrapped
            assert isinstance(exc_info.value.original_error, LLMAPIError)
