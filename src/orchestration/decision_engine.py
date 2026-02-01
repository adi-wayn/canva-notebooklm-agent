"""Decision engine with rule-based fallback logic.

Provides the decision layer for semantic actions, combining LLM outputs
with rule-based fallbacks for robustness.
"""

import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from src.adapters.llm_adapter import LLMAdapter, LLMResponse, PromptVersion
from src.utils.llm_exceptions import LLMAPIError, FallbackActivatedError

logger = logging.getLogger(__name__)


@dataclass
class Decision:
    """Represents a semantic decision from the decision engine."""

    decision_id: str
    content: str
    reasoning: Optional[str] = None
    fallback_used: bool = False
    metadata: Dict[str, Any] = None
    llm_response: Optional[LLMResponse] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "decision_id": self.decision_id,
            "content": self.content,
            "reasoning": self.reasoning,
            "fallback_used": self.fallback_used,
            "metadata": self.metadata or {},
            "llm_response": self.llm_response.to_dict() if self.llm_response else None,
        }


class DecisionEngine:
    """Decision engine combining LLM with rule-based fallback.

    The engine attempts to make decisions using LLM reasoning, and falls back
    to rule-based logic if the LLM fails or returns invalid responses.
    """

    def __init__(
        self,
        llm_adapter: LLMAdapter,
        rule_registry: Optional[Dict[str, Callable]] = None,
    ):
        """Initialize decision engine.

        Args:
            llm_adapter: LLM adapter instance
            rule_registry: Dict mapping decision type to fallback rule function
        """
        self.llm_adapter = llm_adapter
        self.rule_registry = rule_registry or {}

    def register_rule(self, decision_type: str, rule_fn: Callable) -> None:
        """Register a fallback rule for a decision type.

        Args:
            decision_type: Type of decision (e.g., 'layout', 'content_strategy')
            rule_fn: Async callable that takes input and returns decision
        """
        self.rule_registry[decision_type] = rule_fn

    async def decide(
        self,
        decision_type: str,
        context: Dict[str, Any],
        prompt_template: str,
        prompt_version: PromptVersion = PromptVersion.V1,
        allow_fallback: bool = True,
    ) -> Decision:
        """Make a semantic decision.

        Attempts LLM-based reasoning first, falls back to rules if needed.

        Args:
            decision_type: Type of decision being made
            context: Context data for the decision
            prompt_template: Template to use for LLM prompt
            prompt_version: Version of prompt template
            allow_fallback: Whether to fall back to rules on LLM failure

        Returns:
            Decision object with content and metadata

        Raises:
            LLMAPIError: If LLM fails and fallback not allowed
            FallbackActivatedError: If both LLM and fallback fail
        """
        import uuid

        decision_id = str(uuid.uuid4())

        # Try LLM first
        try:
            llm_response = await self.llm_adapter.generate(
                prompt=prompt_template,
                prompt_version=prompt_version,
            )

            return Decision(
                decision_id=decision_id,
                content=llm_response.content,
                reasoning=llm_response.content,
                fallback_used=False,
                metadata={
                    "decision_type": decision_type,
                    "cost": llm_response.token_usage.total_cost,
                    "latency_ms": llm_response.latency_ms,
                },
                llm_response=llm_response,
            )

        except LLMAPIError as e:
            logger.warning(f"LLM decision failed ({e.error_code}): {e.message}")

            if not allow_fallback:
                raise

            # Try rule-based fallback
            rule_fn = self.rule_registry.get(decision_type)
            if rule_fn is None:
                raise FallbackActivatedError(
                    message=f"No fallback rule registered for decision type: {decision_type}",
                    original_error=e,
                ) from e

            try:
                fallback_content = await rule_fn(context)

                return Decision(
                    decision_id=decision_id,
                    content=fallback_content,
                    reasoning=f"Fallback rule ({decision_type})",
                    fallback_used=True,
                    metadata={
                        "decision_type": decision_type,
                        "fallback_reason": e.error_code,
                    },
                )

            except Exception as fallback_error:
                logger.error(f"Fallback rule also failed: {fallback_error}")
                raise FallbackActivatedError(
                    message=f"LLM failed and fallback rule failed: {str(fallback_error)}",
                    original_error=e,
                ) from fallback_error

    async def decide_json(
        self,
        decision_type: str,
        context: Dict[str, Any],
        prompt_template: str,
        expected_schema: Optional[Dict[str, Any]] = None,
        prompt_version: PromptVersion = PromptVersion.V1,
        allow_fallback: bool = True,
    ) -> Decision:
        """Make a semantic decision with structured JSON output.

        Args:
            decision_type: Type of decision being made
            context: Context data for the decision
            prompt_template: Template to use for LLM prompt
            expected_schema: Optional JSON schema for validation
            prompt_version: Version of prompt template
            allow_fallback: Whether to fall back to rules on LLM failure

        Returns:
            Decision object with json_data

        Raises:
            Similar to decide()
        """
        import uuid

        decision_id = str(uuid.uuid4())

        try:
            llm_response = await self.llm_adapter.generate_json(
                prompt=prompt_template,
                expected_schema=expected_schema,
                prompt_version=prompt_version,
            )

            return Decision(
                decision_id=decision_id,
                content=str(llm_response.json_data),
                reasoning=llm_response.content,
                fallback_used=False,
                metadata={
                    "decision_type": decision_type,
                    "cost": llm_response.token_usage.total_cost,
                    "latency_ms": llm_response.latency_ms,
                    "json_data": llm_response.json_data,
                },
                llm_response=llm_response,
            )

        except LLMAPIError as e:
            logger.warning(f"LLM JSON decision failed ({e.error_code}): {e.message}")

            if not allow_fallback:
                raise

            rule_fn = self.rule_registry.get(decision_type)
            if rule_fn is None:
                raise FallbackActivatedError(
                    message=f"No fallback rule registered for decision type: {decision_type}",
                    original_error=e,
                ) from e

            try:
                fallback_result = await rule_fn(context)
                fallback_json = fallback_result if isinstance(fallback_result, dict) else {"result": fallback_result}

                return Decision(
                    decision_id=decision_id,
                    content=str(fallback_json),
                    reasoning=f"Fallback rule ({decision_type})",
                    fallback_used=True,
                    metadata={
                        "decision_type": decision_type,
                        "fallback_reason": e.error_code,
                        "json_data": fallback_json,
                    },
                )

            except Exception as fallback_error:
                logger.error(f"Fallback rule also failed: {fallback_error}")
                raise FallbackActivatedError(
                    message=f"LLM failed and fallback rule failed: {str(fallback_error)}",
                    original_error=e,
                ) from fallback_error
