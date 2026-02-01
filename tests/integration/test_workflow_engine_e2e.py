"""Integration tests for workflow engine with mocked adapters.

Tests cover:
- End-to-end happy path (SUBMITTED → COMPLETED)
- Workflow with decision engine calls
- Multi-step processing with progress updates
- Error handling and retry scenarios
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.orchestration import (
    WorkflowStatus,
    ErrorType,
    WorkflowEngine,
)
from src.utils.llm_exceptions import (
    LLMTimeoutError,
    InvalidResponseError,
)


@pytest.mark.asyncio
class TestWorkflowHappyPath:
    """Test complete workflow happy path."""

    async def test_complete_workflow_lifecycle(self):
        """Test workflow from creation to completion."""
        engine = WorkflowEngine()
        events = []
        engine.register_event_callback(lambda e: events.append(e))

        # Step 1: Create workflow
        workflow = engine.create_workflow(
            tenant_id="tenant_1",
            user_id="user_1",
            input_data={"source_id": "src_123", "title": "Q4 Strategy"},
        )
        assert workflow.status == WorkflowStatus.SUBMITTED

        # Step 2: Queue
        engine.queue_workflow(workflow)
        assert workflow.status == WorkflowStatus.QUEUED

        # Step 3: Start processing
        engine.start_processing(workflow)
        assert workflow.status == WorkflowStatus.PROCESSING

        # Step 4: Progress through steps
        engine.update_progress(workflow, "analyzing_content", 20)
        engine.add_artifact(
            workflow,
            "content_analysis",
            "application/json",
            data={"slides": 10, "topics": 5},
        )

        engine.update_progress(workflow, "generating_layout", 40)
        engine.add_artifact(
            workflow,
            "layout_decision",
            "application/json",
            data={"template": "grid", "colors": ["#000", "#fff"]},
        )

        engine.update_progress(workflow, "creating_design", 60)
        engine.update_progress(workflow, "populating_content", 80)
        engine.add_artifact(
            workflow,
            "design_export",
            "application/pdf",
            url="https://example.com/design.pdf",
        )

        engine.update_progress(workflow, "finalizing", 95)

        # Step 5: Complete
        engine.complete_workflow(workflow)
        assert workflow.status == WorkflowStatus.COMPLETED

        # Verify artifacts
        assert len(workflow.artifacts) == 3
        assert workflow.artifacts[0].name == "content_analysis"
        assert workflow.artifacts[1].name == "layout_decision"
        assert workflow.artifacts[2].name == "design_export"

        # Verify events
        status_changes = [e for e in events if e.event_type == "status_changed"]
        progress_updates = [e for e in events if e.event_type == "step_progressed"]
        artifact_creates = [e for e in events if e.event_type == "artifact_created"]

        assert len(status_changes) == 3  # SUBMITTED→QUEUED, QUEUED→PROCESSING, PROCESSING→COMPLETED
        assert len(progress_updates) == 5  # 5 progress updates
        assert len(artifact_creates) == 3

    async def test_workflow_with_decision_engine_calls(self):
        """Test workflow that calls decision engine (mocked)."""
        from src.adapters.llm_adapter import LLMAdapter
        from src.orchestration.decision_engine import DecisionEngine

        engine = WorkflowEngine()

        workflow = engine.create_workflow(
            tenant_id="tenant_1",
            user_id="user_1",
            input_data={"source_id": "src_123"},
        )

        engine.queue_workflow(workflow)
        engine.start_processing(workflow)

        # Mock the decision engine
        with patch("src.orchestration.decision_engine.LLMAdapter") as mock_adapter_class:
            mock_adapter = AsyncMock()
            mock_adapter_class.return_value = mock_adapter

            # Mock decision result
            mock_decision = MagicMock()
            mock_decision.content = '{"layout": "grid", "colors": ["#000", "#fff"]}'
            mock_decision.metadata = {"json_data": {"layout": "grid", "colors": ["#000", "#fff"]}}
            mock_adapter.generate_json = AsyncMock(return_value=mock_decision)

            # Simulate decision call
            decision_engine = DecisionEngine(mock_adapter)
            result = await decision_engine.decide_json(
                decision_type="layout",
                context={},
                prompt_template="Choose layout",
            )

            engine.add_artifact(
                workflow,
                "layout_decision",
                "application/json",
                data={"layout": "grid", "colors": ["#000", "#fff"]},
            )

        engine.update_progress(workflow, "design_creation", 60)
        engine.add_artifact(
            workflow,
            "design",
            "application/pdf",
            url="https://example.com/design.pdf",
        )

        engine.complete_workflow(workflow)

        assert workflow.status == WorkflowStatus.COMPLETED
        assert len(workflow.artifacts) == 2
        assert workflow.artifacts[0].name == "layout_decision"
        assert workflow.artifacts[0].data["layout"] == "grid"


@pytest.mark.asyncio
class TestWorkflowErrorRecovery:
    """Test error handling and recovery scenarios."""

    async def test_transient_error_failure(self):
        """Test workflow failing with transient error (retryable)."""
        engine = WorkflowEngine()
        events = []
        engine.register_event_callback(lambda e: events.append(e))

        workflow = engine.create_workflow("tenant_1", "user_1", {})
        engine.queue_workflow(workflow)
        engine.start_processing(workflow)

        engine.update_progress(workflow, "analyzing", 30)

        # Simulate transient failure
        timeout_error = LLMTimeoutError("Request timeout", timeout_seconds=30)
        engine.fail_workflow(workflow, timeout_error, step="analyzing")

        assert workflow.status == WorkflowStatus.FAILED
        assert workflow.error.type == ErrorType.TRANSIENT
        assert workflow.error.retryable is True

        # Verify failure event
        failure_events = [e for e in events if e.event_type == "failed"]
        assert len(failure_events) == 1
        assert failure_events[0].error.retryable is True

    async def test_permanent_error_failure(self):
        """Test workflow failing with permanent error (not retryable)."""
        engine = WorkflowEngine()
        events = []
        engine.register_event_callback(lambda e: events.append(e))

        workflow = engine.create_workflow("tenant_1", "user_1", {})
        engine.queue_workflow(workflow)
        engine.start_processing(workflow)

        engine.update_progress(workflow, "parsing", 40)

        # Simulate permanent failure
        parse_error = InvalidResponseError("Invalid JSON in response")
        engine.fail_workflow(workflow, parse_error, step="parsing")

        assert workflow.status == WorkflowStatus.FAILED
        assert workflow.error.type == ErrorType.PERMANENT
        assert workflow.error.retryable is False

        # Verify failure event
        failure_events = [e for e in events if e.event_type == "failed"]
        assert len(failure_events) == 1
        assert failure_events[0].error.retryable is False

    async def test_partial_progress_before_failure(self):
        """Test workflow preserves progress state before failure."""
        engine = WorkflowEngine()

        workflow = engine.create_workflow("tenant_1", "user_1", {})
        engine.queue_workflow(workflow)
        engine.start_processing(workflow)

        # Partial progress
        engine.update_progress(workflow, "step_1", 25)
        engine.add_artifact(workflow, "artifact_1", "application/json", data={"key": "value"})
        engine.update_progress(workflow, "step_2", 50)

        # Failure
        error = LLMTimeoutError("timeout", 30)
        engine.fail_workflow(workflow, error)

        # Verify partial state is preserved
        assert workflow.progress_pct == 50
        assert workflow.step == "step_2"
        assert len(workflow.artifacts) == 1


@pytest.mark.asyncio
class TestWorkflowEventStream:
    """Test event streaming interface."""

    async def test_event_stream_basic(self):
        """Test basic event streaming (async generator)."""
        engine = WorkflowEngine()

        # Create workflow and generate events in background
        workflow = engine.create_workflow("tenant_1", "user_1", {})
        engine.queue_workflow(workflow)
        engine.start_processing(workflow)
        engine.update_progress(workflow, "step_1", 50)
        engine.complete_workflow(workflow)

        # Collect events from stream
        events = []
        async for event in engine.event_stream(workflow.id):
            events.append(event)
            # Stop after completion
            if event.event_type == "status_changed" and event.new_status == WorkflowStatus.COMPLETED:
                break

        # Verify we got all events
        assert len(events) >= 4
        assert events[0].event_type == "status_changed"
        assert events[0].new_status == WorkflowStatus.QUEUED

    async def test_event_stream_for_failed_workflow(self):
        """Test event stream for failing workflow."""
        engine = WorkflowEngine()

        workflow = engine.create_workflow("tenant_1", "user_1", {})
        engine.queue_workflow(workflow)
        engine.start_processing(workflow)
        engine.fail_workflow(workflow, LLMTimeoutError("timeout", 30))

        # Collect events
        events = []
        async for event in engine.event_stream(workflow.id):
            events.append(event)
            if event.event_type == "failed":
                break

        # Verify failure event is in stream
        failure_events = [e for e in events if e.event_type == "failed"]
        assert len(failure_events) == 1
        assert failure_events[0].error.retryable is True


@pytest.mark.asyncio
class TestMultiTenantIsolation:
    """Test multi-tenant safety in workflows."""

    async def test_workflows_isolated_by_tenant(self):
        """Test workflows from different tenants are tracked separately."""
        engine = WorkflowEngine()

        # Create workflows for different tenants
        wf_tenant1 = engine.create_workflow("tenant_1", "user_1", {"data": "tenant1"})
        wf_tenant2 = engine.create_workflow("tenant_2", "user_2", {"data": "tenant2"})

        assert wf_tenant1.tenant_id == "tenant_1"
        assert wf_tenant2.tenant_id == "tenant_2"

        # Both should be retrievable
        assert engine.get_workflow(wf_tenant1.id) is not None
        assert engine.get_workflow(wf_tenant2.id) is not None

        # Transition one
        engine.queue_workflow(wf_tenant1)
        assert wf_tenant1.status == WorkflowStatus.QUEUED
        assert wf_tenant2.status == WorkflowStatus.SUBMITTED

    async def test_events_include_tenant_id(self):
        """Test all events include tenant_id."""
        engine = WorkflowEngine()
        events = []
        engine.register_event_callback(lambda e: events.append(e))

        workflow = engine.create_workflow("tenant_xyz", "user_1", {})
        engine.queue_workflow(workflow)
        engine.start_processing(workflow)
        engine.complete_workflow(workflow)

        for event in events:
            assert event.tenant_id == "tenant_xyz"


@pytest.mark.asyncio
class TestWorkflowSerializationE2E:
    """Test workflow serialization in realistic scenarios."""

    async def test_completed_workflow_api_response(self):
        """Test completed workflow serializes for API response."""
        engine = WorkflowEngine()

        workflow = engine.create_workflow(
            tenant_id="tenant_1",
            user_id="user_1",
            input_data={"source_id": "src_123"},
        )
        engine.queue_workflow(workflow)
        engine.start_processing(workflow)
        engine.update_progress(workflow, "processing", 50)
        engine.add_artifact(
            workflow,
            "result",
            "application/json",
            url="https://example.com/result.json",
        )
        engine.complete_workflow(workflow)

        # Serialize for API
        data = workflow.to_dict()

        assert data["status"] == "COMPLETED"
        assert data["progress_pct"] == 100
        assert len(data["artifacts"]) == 1
        assert data["artifacts"][0]["name"] == "result"
        assert data["artifacts"][0]["url"] == "https://example.com/result.json"
        assert data["error"] is None

    async def test_failed_workflow_api_response(self):
        """Test failed workflow serializes with error details."""
        engine = WorkflowEngine()

        workflow = engine.create_workflow("tenant_1", "user_1", {})
        engine.queue_workflow(workflow)
        engine.start_processing(workflow)
        engine.update_progress(workflow, "step", 30)

        error = LLMTimeoutError("API timeout after 30s", timeout_seconds=30)
        engine.fail_workflow(workflow, error)

        # Serialize for API
        data = workflow.to_dict()

        assert data["status"] == "FAILED"
        assert data["step"] == "step"
        assert data["progress_pct"] == 30
        assert data["error"] is not None
        assert data["error"]["type"] == "TRANSIENT"
        assert data["error"]["retryable"] is True
        assert "timeout" in data["error"]["message"].lower()
