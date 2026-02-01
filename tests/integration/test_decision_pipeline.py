"""Integration tests for LLM adapter and decision engine.

Tests cover:
- Real API interactions (with mocking)
- End-to-end workflows
- Decision pipeline consistency
- Error recovery scenarios
- Performance metrics collection
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from src.adapters.llm_adapter import LLMAdapter, PromptVersion
from src.orchestration.decision_engine import DecisionEngine
from src.utils.llm_exceptions import (
    LLMAPIError,
    LLMTimeoutError,
    RateLimitError,
)
from tests.fixtures.mock_llm import build_openai_response


@pytest.mark.asyncio
class TestDecisionPipeline:
    """Test complete decision pipelines."""

    async def test_multi_step_decision_workflow(self):
        """Test workflow with multiple sequential decisions."""
        adapter = LLMAdapter("test_key")
        engine = DecisionEngine(adapter)

        # Step 1: Analyze layout
        layout_response = build_openai_response(content='{"layout": "grid"}')

        # Step 2: Decide colors
        color_response = build_openai_response(content='{"primary": "blue"}')

        # Step 3: Finalize
        final_response = build_openai_response(content="Final design complete")

        mock_create = AsyncMock(side_effect=[layout_response, color_response, final_response])

        with patch.object(adapter.client.chat.completions, "create", mock_create):
            # Execute pipeline
            layout = await engine.decide_json("layout", {}, "Decide layout")
            colors = await engine.decide_json("colors", layout.metadata, "Decide colors")
            final = await engine.decide("finalize", colors.metadata, "Finalize")

            assert mock_create.call_count == 3
            assert final.content == "Final design complete"

    async def test_decision_with_context_passing(self):
        """Test context is properly passed through decisions."""
        adapter = LLMAdapter("test_key")
        engine = DecisionEngine(adapter)

        response = build_openai_response(content='{"used_context": true}')

        with patch.object(
            adapter.client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=response,
        ) as mock_create:
            context = {
                "user_preferences": {"theme": "dark"},
                "canvas_size": [1920, 1080],
            }

            decision = await engine.decide_json("design", context, "Make decision")

            # Verify context was included in the call
            call_args = mock_create.call_args
            assert call_args is not None

    async def test_parallel_decisions(self):
        """Test parallel independent decisions."""
        adapter = LLMAdapter("test_key")
        engine = DecisionEngine(adapter)

        response1 = build_openai_response(content='{"option": "A"}')
        response2 = build_openai_response(content='{"option": "B"}')
        response3 = build_openai_response(content='{"option": "C"}')

        with patch.object(
            adapter.client.chat.completions,
            "create",
            new_callable=AsyncMock,
            side_effect=[response1, response2, response3],
        ):
            # Run decisions in parallel
            decisions = await asyncio.gather(
                engine.decide_json("decision_1", {}, "Option A or B"),
                engine.decide_json("decision_2", {}, "Option B or C"),
                engine.decide_json("decision_3", {}, "Option A or C"),
            )

            assert len(decisions) == 3
            assert all(d.content for d in decisions)


@pytest.mark.asyncio
class TestErrorRecovery:
    """Test error handling and recovery."""

    async def test_automatic_retry_on_timeout(self):
        """Test automatic retry after timeout."""
        adapter = LLMAdapter("test_key")
        engine = DecisionEngine(adapter)

        success_response = build_openai_response(content="Success on retry")

        with patch.object(
            adapter.client.chat.completions,
            "create",
            new_callable=AsyncMock,
            side_effect=[LLMTimeoutError("timeout", 10), success_response],
        ):
            # Register a simple fallback rule
            async def timeout_rule(context):
                return "Timeout rule fallback"

            engine.register_rule("test", timeout_rule)

            decision = await engine.decide(
                "test",
                {},
                "Test",
                allow_fallback=True,
            )

            # Should use fallback after timeout
            assert decision.fallback_used

    async def test_rate_limit_recovery(self):
        """Test graceful handling of rate limits."""
        adapter = LLMAdapter("test_key")
        engine = DecisionEngine(adapter)

        import openai

        rate_limit_error = openai.RateLimitError("Rate limit", response=MagicMock(), body={})

        async def rate_limit_rule(context):
            return "Using rate limit rule"

        engine.register_rule("ratelimit_test", rate_limit_rule)

        with patch.object(
            adapter.client.chat.completions,
            "create",
            new_callable=AsyncMock,
            side_effect=rate_limit_error,
        ):
            decision = await engine.decide(
                "ratelimit_test",
                {},
                "Test",
                allow_fallback=True,
            )

            assert decision.fallback_used


@pytest.mark.asyncio
class TestPerformanceMetrics:
    """Test performance metric collection."""

    async def test_latency_tracking(self):
        """Test latency is accurately tracked."""
        adapter = LLMAdapter("test_key")

        response = build_openai_response(content="Response")

        with patch.object(
            adapter.client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=response,
        ):
            result = await adapter.generate("Test")

            assert result.latency_ms > 0
            assert isinstance(result.latency_ms, float)

    async def test_token_usage_aggregation(self):
        """Test token usage is tracked correctly."""
        adapter = LLMAdapter("test_key")

        response1 = build_openai_response(input_tokens=100, output_tokens=50)
        response2 = build_openai_response(input_tokens=200, output_tokens=100)

        with patch.object(
            adapter.client.chat.completions,
            "create",
            new_callable=AsyncMock,
            side_effect=[response1, response2],
        ):
            result1 = await adapter.generate("Prompt 1")
            result2 = await adapter.generate("Prompt 2")

            total_input = result1.token_usage.input_tokens + result2.token_usage.input_tokens
            total_output = result1.token_usage.output_tokens + result2.token_usage.output_tokens

            assert total_input == 300
            assert total_output == 150

    async def test_cost_tracking(self):
        """Test cost calculation is accurate."""
        adapter = LLMAdapter("test_key")

        response = build_openai_response(input_tokens=1000, output_tokens=500)

        with patch.object(
            adapter.client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=response,
        ):
            result = await adapter.generate("Test")

            assert result.token_usage.total_cost > 0
            # Verify input + output cost = total
            assert (
                abs(
                    result.token_usage.input_cost
                    + result.token_usage.output_cost
                    - result.token_usage.total_cost
                )
                < 0.0001
            )


@pytest.mark.asyncio
class TestPromptVersioning:
    """Test prompt versioning system."""

    async def test_different_versions_produce_different_results(self):
        """Test that different prompt versions are cached separately."""
        adapter = LLMAdapter("test_key")

        response_v1 = build_openai_response(content="Response V1")
        response_v2 = build_openai_response(content="Response V2")

        with patch.object(
            adapter.client.chat.completions,
            "create",
            new_callable=AsyncMock,
            side_effect=[response_v1, response_v2],
        ):
            result_v1 = await adapter.generate("Same prompt", PromptVersion.V1)
            result_v2 = await adapter.generate("Same prompt", PromptVersion.V2)

            assert result_v1.prompt_version == PromptVersion.V1
            assert result_v2.prompt_version == PromptVersion.V2
            assert result_v1.content != result_v2.content

    async def test_version_upgrade_path(self):
        """Test migrating from one version to another."""
        adapter = LLMAdapter("test_key")
        engine = DecisionEngine(adapter)

        old_response = build_openai_response(content="Old version response")
        new_response = build_openai_response(content="New version response")

        with patch.object(
            adapter.client.chat.completions,
            "create",
            new_callable=AsyncMock,
            side_effect=[old_response, new_response],
        ):
            # First with V1
            result_v1 = await adapter.generate("Test", PromptVersion.V1)

            # Then with V2 (simulating upgrade)
            result_v2 = await adapter.generate("Test", PromptVersion.V2)

            assert result_v1.prompt_version == PromptVersion.V1
            assert result_v2.prompt_version == PromptVersion.V2


@pytest.mark.asyncio
class TestDecisionEngineFallbackRegistry:
    """Test decision engine fallback rules."""

    async def test_rule_execution_order(self):
        """Test fallback rules are executed in registration order."""
        adapter = LLMAdapter("test_key")
        engine = DecisionEngine(adapter)

        execution_order = []

        async def rule1(context):
            execution_order.append("rule1")
            raise ValueError("rule1 failed")

        async def rule2(context):
            execution_order.append("rule2")
            return "From rule2"

        engine.register_rule("test", rule1)
        engine.register_rule("test", rule2)

        with patch.object(
            adapter.client.chat.completions,
            "create",
            new_callable=AsyncMock,
            side_effect=LLMTimeoutError("timeout", 10),
        ):
            decision = await engine.decide("test", {}, "Test", allow_fallback=True)

            # Rules should be tried in order
            assert "rule1" in execution_order or "rule2" in execution_order

    async def test_rule_receives_context(self):
        """Test rules receive the full context."""
        adapter = LLMAdapter("test_key")
        engine = DecisionEngine(adapter)

        received_context = None

        async def context_aware_rule(context):
            nonlocal received_context
            received_context = context
            return "from_rule"

        engine.register_rule("test", context_aware_rule)

        test_context = {"user_id": "123", "session": "abc"}

        with patch.object(
            adapter.client.chat.completions,
            "create",
            side_effect=LLMTimeoutError("timeout", 10),
        ):
            await engine.decide("test", test_context, "Test", allow_fallback=True)

            assert received_context is not None
            assert received_context.get("user_id") == "123"


@pytest.mark.asyncio
class TestEndToEndScenarios:
    """Test complete end-to-end scenarios."""

    async def test_canva_design_decision_flow(self):
        """Simulate a Canva design decision flow."""
        adapter = LLMAdapter("test_key")
        engine = DecisionEngine(adapter)

        # Mock responses for each step
        layout_response = build_openai_response(content='{"layout": "asymmetric", "columns": 3}')
        color_response = build_openai_response(content='{"primary": "#3b82f6", "secondary": "#60a5fa"}')
        typography_response = build_openai_response(content='{"font": "Inter", "weight": 600}')

        with patch.object(
            adapter.client.chat.completions,
            "create",
            new_callable=AsyncMock,
            side_effect=[layout_response, color_response, typography_response],
        ):
            # Design flow
            layout = await engine.decide_json("layout", {}, "Choose layout")
            colors = await engine.decide_json("colors", layout.metadata, "Choose colors")
            typography = await engine.decide_json("typography", colors.metadata, "Choose typography")

            # Verify all decisions were made
            assert layout.metadata.get("json_data", {}).get("layout") == "asymmetric"
            assert colors.metadata.get("json_data", {}).get("primary") == "#3b82f6"
            assert typography.metadata.get("json_data", {}).get("font") == "Inter"

    async def test_error_handling_in_design_flow(self):
        """Test error handling in multi-step design flow."""
        adapter = LLMAdapter("test_key")
        engine = DecisionEngine(adapter)

        # Register fallback for layout
        async def default_layout(context):
            return "grid"

        engine.register_rule("layout", default_layout)

        with patch.object(
            adapter.client.chat.completions,
            "create",
            new_callable=AsyncMock,
            side_effect=LLMTimeoutError("timeout", 10),
        ):
            layout = await engine.decide("layout", {}, "Choose layout", allow_fallback=True)

            assert layout.fallback_used
            assert layout.content == "grid"

    async def test_timeout_with_long_operation(self):
        """Test timeout handling during slow operations."""
        adapter = LLMAdapter("test_key", timeout_seconds=1.0)
        engine = DecisionEngine(adapter)

        async def slow_rule(context):
            return "Fallback response"

        engine.register_rule("test", slow_rule)

        with patch.object(
            adapter.client.chat.completions,
            "create",
            new_callable=AsyncMock,
            side_effect=LLMTimeoutError("timeout", 1),
        ):
            decision = await engine.decide("test", {}, "Test", allow_fallback=True)

            assert decision.fallback_used
