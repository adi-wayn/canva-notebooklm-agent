"""Unit tests for workflow engine and state machine.

Tests cover:
- Valid state transitions (SUBMITTED → QUEUED → PROCESSING → COMPLETED/FAILED)
- Error classification (transient vs permanent vs user)
- Progress tracking and artifact handling
- Event emission order and completeness
- Illegal transitions raising exceptions
"""

import pytest
from datetime import datetime

from src.orchestration import (
    WorkflowStatus,
    ErrorType,
    Workflow,
    WorkflowEvent,
    WorkflowEngine,
)
from src.utils.llm_exceptions import (
    LLMAPIError,
    TimeoutError as LLMTimeoutError,
    RateLimitError,
    InvalidResponseError,
    TokenCountError,
    FallbackActivatedError,
)


@pytest.mark.asyncio
class TestWorkflowStateTransitions:
    """Test valid and invalid state transitions."""

    def test_create_workflow(self):
        """Test workflow creation in SUBMITTED state."""
        engine = WorkflowEngine()
        workflow = engine.create_workflow(
            tenant_id="tenant_1",
            user_id="user_1",
            input_data={"source_id": "src_123"},
        )

        assert workflow.status == WorkflowStatus.SUBMITTED
        assert workflow.step == "submitted"
        assert workflow.progress_pct == 0
        assert workflow.tenant_id == "tenant_1"
        assert workflow.user_id == "user_1"
        assert workflow.error is None

    def test_queue_workflow(self):
        """Test transition from SUBMITTED to QUEUED."""
        engine = WorkflowEngine()
        workflow = engine.create_workflow("tenant_1", "user_1", {})

        engine.queue_workflow(workflow)

        assert workflow.status == WorkflowStatus.QUEUED
        assert workflow.step == "queued"
        assert workflow.progress_pct == 5

    def test_start_processing(self):
        """Test transition from QUEUED to PROCESSING."""
        engine = WorkflowEngine()
        workflow = engine.create_workflow("tenant_1", "user_1", {})
        engine.queue_workflow(workflow)

        engine.start_processing(workflow)

        assert workflow.status == WorkflowStatus.PROCESSING
        assert workflow.step == "initializing"
        assert workflow.progress_pct == 10

    def test_complete_workflow(self):
        """Test transition from PROCESSING to COMPLETED."""
        engine = WorkflowEngine()
        workflow = engine.create_workflow("tenant_1", "user_1", {})
        engine.queue_workflow(workflow)
        engine.start_processing(workflow)

        engine.complete_workflow(workflow)

        assert workflow.status == WorkflowStatus.COMPLETED
        assert workflow.step == "completed"
        assert workflow.progress_pct == 100
        assert workflow.error is None

    def test_fail_workflow_transient(self):
        """Test transition from PROCESSING to FAILED with transient error."""
        engine = WorkflowEngine()
        workflow = engine.create_workflow("tenant_1", "user_1", {})
        engine.queue_workflow(workflow)
        engine.start_processing(workflow)

        timeout_error = LLMTimeoutError("Request timed out", timeout_seconds=30)
        engine.fail_workflow(workflow, timeout_error)

        assert workflow.status == WorkflowStatus.FAILED
        assert workflow.error is not None
        assert workflow.error.type == ErrorType.TRANSIENT
        assert workflow.error.retryable is True
        assert "timed out" in workflow.error.message.lower()

    def test_fail_workflow_permanent(self):
        """Test transition from PROCESSING to FAILED with permanent error."""
        engine = WorkflowEngine()
        workflow = engine.create_workflow("tenant_1", "user_1", {})
        engine.queue_workflow(workflow)
        engine.start_processing(workflow)

        invalid_error = InvalidResponseError("Invalid JSON response")
        engine.fail_workflow(workflow, invalid_error)

        assert workflow.status == WorkflowStatus.FAILED
        assert workflow.error is not None
        assert workflow.error.type == ErrorType.PERMANENT
        assert workflow.error.retryable is False

    def test_illegal_transition_from_completed(self):
        """Test that illegal transitions raise ValueError."""
        engine = WorkflowEngine()
        workflow = engine.create_workflow("tenant_1", "user_1", {})
        engine.queue_workflow(workflow)
        engine.start_processing(workflow)
        engine.complete_workflow(workflow)

        # Cannot transition from COMPLETED to QUEUED
        with pytest.raises(ValueError, match="Cannot queue"):
            engine.queue_workflow(workflow)

    def test_illegal_transition_from_failed(self):
        """Test that cannot process failed workflow."""
        engine = WorkflowEngine()
        workflow = engine.create_workflow("tenant_1", "user_1", {})
        engine.queue_workflow(workflow)
        engine.start_processing(workflow)
        engine.fail_workflow(workflow, LLMTimeoutError("timeout", 10))

        # Cannot complete a failed workflow
        with pytest.raises(ValueError, match="Cannot complete"):
            engine.complete_workflow(workflow)

    def test_cannot_fail_non_processing_workflow(self):
        """Test that can only fail PROCESSING workflows."""
        engine = WorkflowEngine()
        workflow = engine.create_workflow("tenant_1", "user_1", {})

        with pytest.raises(ValueError, match="Cannot fail"):
            engine.fail_workflow(workflow, LLMTimeoutError("timeout", 10))


class TestProgressTracking:
    """Test progress and step tracking during PROCESSING."""

    def test_update_progress(self):
        """Test progress updates during processing."""
        engine = WorkflowEngine()
        workflow = engine.create_workflow("tenant_1", "user_1", {})
        engine.queue_workflow(workflow)
        engine.start_processing(workflow)

        engine.update_progress(workflow, "analyzing_content", 25)

        assert workflow.step == "analyzing_content"
        assert workflow.progress_pct == 25

    def test_progress_validation(self):
        """Test progress percentage bounds validation."""
        engine = WorkflowEngine()
        workflow = engine.create_workflow("tenant_1", "user_1", {})
        engine.queue_workflow(workflow)
        engine.start_processing(workflow)

        with pytest.raises(ValueError, match="must be 0-100"):
            engine.update_progress(workflow, "step", 101)

        with pytest.raises(ValueError, match="must be 0-100"):
            engine.update_progress(workflow, "step", -1)

    def test_cannot_update_progress_non_processing(self):
        """Test that can only update progress during PROCESSING."""
        engine = WorkflowEngine()
        workflow = engine.create_workflow("tenant_1", "user_1", {})

        with pytest.raises(ValueError, match="Cannot update progress"):
            engine.update_progress(workflow, "step", 50)


class TestArtifactHandling:
    """Test artifact (output) creation and storage."""

    def test_add_artifact_with_url(self):
        """Test adding artifact with URL."""
        engine = WorkflowEngine()
        workflow = engine.create_workflow("tenant_1", "user_1", {})

        engine.add_artifact(
            workflow,
            name="design_export",
            content_type="application/pdf",
            url="https://example.com/design.pdf",
        )

        assert len(workflow.artifacts) == 1
        assert workflow.artifacts[0].name == "design_export"
        assert workflow.artifacts[0].url == "https://example.com/design.pdf"

    def test_add_artifact_with_data(self):
        """Test adding artifact with structured data."""
        engine = WorkflowEngine()
        workflow = engine.create_workflow("tenant_1", "user_1", {})

        data = {"layout": "grid", "columns": 3}
        engine.add_artifact(
            workflow,
            name="layout_decision",
            content_type="application/json",
            data=data,
        )

        assert len(workflow.artifacts) == 1
        assert workflow.artifacts[0].data == data

    def test_multiple_artifacts(self):
        """Test adding multiple artifacts."""
        engine = WorkflowEngine()
        workflow = engine.create_workflow("tenant_1", "user_1", {})

        engine.add_artifact(workflow, "design", "application/pdf", url="https://example.com/1.pdf")
        engine.add_artifact(workflow, "data", "application/json", data={"key": "value"})
        engine.add_artifact(workflow, "export", "image/png", url="https://example.com/design.png")

        assert len(workflow.artifacts) == 3


class TestErrorClassification:
    """Test error type classification for retryability."""

    def test_classify_timeout_as_transient(self):
        """Test timeout errors are classified as transient."""
        engine = WorkflowEngine()
        workflow = engine.create_workflow("tenant_1", "user_1", {})
        engine.queue_workflow(workflow)
        engine.start_processing(workflow)

        error = LLMTimeoutError("Request timed out", timeout_seconds=30)
        engine.fail_workflow(workflow, error)

        assert workflow.error.type == ErrorType.TRANSIENT
        assert workflow.error.retryable is True

    def test_classify_rate_limit_as_transient(self):
        """Test rate limit errors are classified as transient."""
        engine = WorkflowEngine()
        workflow = engine.create_workflow("tenant_1", "user_1", {})
        engine.queue_workflow(workflow)
        engine.start_processing(workflow)

        error = RateLimitError("Rate limited", retry_after=60)
        engine.fail_workflow(workflow, error)

        assert workflow.error.type == ErrorType.TRANSIENT
        assert workflow.error.retryable is True

    def test_classify_invalid_response_as_permanent(self):
        """Test invalid response errors are classified as permanent."""
        engine = WorkflowEngine()
        workflow = engine.create_workflow("tenant_1", "user_1", {})
        engine.queue_workflow(workflow)
        engine.start_processing(workflow)

        error = InvalidResponseError("JSON parsing failed")
        engine.fail_workflow(workflow, error)

        assert workflow.error.type == ErrorType.PERMANENT
        assert workflow.error.retryable is False

    def test_classify_token_count_as_permanent(self):
        """Test token count errors are classified as permanent."""
        engine = WorkflowEngine()
        workflow = engine.create_workflow("tenant_1", "user_1", {})
        engine.queue_workflow(workflow)
        engine.start_processing(workflow)

        error = TokenCountError("Token count exceeded")
        engine.fail_workflow(workflow, error)

        assert workflow.error.type == ErrorType.PERMANENT
        assert workflow.error.retryable is False

    def test_classify_fallback_as_user_error(self):
        """Test fallback activation is classified as user error."""
        engine = WorkflowEngine()
        workflow = engine.create_workflow("tenant_1", "user_1", {})
        engine.queue_workflow(workflow)
        engine.start_processing(workflow)

        error = FallbackActivatedError("No fallback rule", original_error=LLMTimeoutError("timeout", 10))
        engine.fail_workflow(workflow, error)

        assert workflow.error.type == ErrorType.USER
        assert workflow.error.retryable is False

    def test_classify_generic_llm_api_error_as_transient(self):
        """Test generic LLM API errors default to transient."""
        engine = WorkflowEngine()
        workflow = engine.create_workflow("tenant_1", "user_1", {})
        engine.queue_workflow(workflow)
        engine.start_processing(workflow)

        error = LLMAPIError("Unknown API error")
        engine.fail_workflow(workflow, error)

        assert workflow.error.type == ErrorType.TRANSIENT
        assert workflow.error.retryable is True


class TestEventEmission:
    """Test event emission and ordering."""

    def test_events_emitted_on_transitions(self):
        """Test events are emitted on state transitions."""
        engine = WorkflowEngine()
        events = []
        engine.register_event_callback(lambda e: events.append(e))

        workflow = engine.create_workflow("tenant_1", "user_1", {})
        engine.queue_workflow(workflow)
        engine.start_processing(workflow)
        engine.complete_workflow(workflow)

        # Should have 3 transition events
        assert len(events) == 3
        assert events[0].event_type == "status_changed"
        assert events[0].old_status == WorkflowStatus.SUBMITTED
        assert events[0].new_status == WorkflowStatus.QUEUED

        assert events[1].event_type == "status_changed"
        assert events[1].old_status == WorkflowStatus.QUEUED
        assert events[1].new_status == WorkflowStatus.PROCESSING

        assert events[2].event_type == "status_changed"
        assert events[2].old_status == WorkflowStatus.PROCESSING
        assert events[2].new_status == WorkflowStatus.COMPLETED

    def test_events_include_metadata(self):
        """Test events include required metadata."""
        engine = WorkflowEngine()
        events = []
        engine.register_event_callback(lambda e: events.append(e))

        workflow = engine.create_workflow("tenant_1", "user_1", {})
        engine.queue_workflow(workflow)

        event = events[0]
        assert event.workflow_id == workflow.id
        assert event.tenant_id == "tenant_1"
        assert event.request_id == workflow.request_id
        assert event.timestamp is not None

    def test_progress_events(self):
        """Test progress events are emitted."""
        engine = WorkflowEngine()
        events = []
        engine.register_event_callback(lambda e: events.append(e))

        workflow = engine.create_workflow("tenant_1", "user_1", {})
        engine.queue_workflow(workflow)
        engine.start_processing(workflow)
        engine.update_progress(workflow, "analyzing", 25)
        engine.update_progress(workflow, "generating", 50)

        # 3 status + 2 progress events
        progress_events = [e for e in events if e.event_type == "step_progressed"]
        assert len(progress_events) == 2
        assert progress_events[0].step == "analyzing"
        assert progress_events[0].progress_pct == 25
        assert progress_events[1].step == "generating"
        assert progress_events[1].progress_pct == 50

    def test_artifact_events(self):
        """Test artifact creation events are emitted."""
        engine = WorkflowEngine()
        events = []
        engine.register_event_callback(lambda e: events.append(e))

        workflow = engine.create_workflow("tenant_1", "user_1", {})
        engine.add_artifact(workflow, "design", "application/pdf", url="https://example.com/design.pdf")

        artifact_events = [e for e in events if e.event_type == "artifact_created"]
        assert len(artifact_events) == 1

    def test_failure_event_includes_error(self):
        """Test failure events include error details."""
        engine = WorkflowEngine()
        events = []
        engine.register_event_callback(lambda e: events.append(e))

        workflow = engine.create_workflow("tenant_1", "user_1", {})
        engine.queue_workflow(workflow)
        engine.start_processing(workflow)

        error = LLMTimeoutError("Request timeout", timeout_seconds=30)
        engine.fail_workflow(workflow, error, step="analyzing")

        failure_events = [e for e in events if e.event_type == "failed"]
        assert len(failure_events) == 1
        assert failure_events[0].error is not None
        assert failure_events[0].error.type == ErrorType.TRANSIENT
        assert failure_events[0].error.retryable is True
        assert failure_events[0].step == "analyzing"

    def test_event_ordering(self):
        """Test events are emitted in correct order."""
        engine = WorkflowEngine()
        events = []
        engine.register_event_callback(lambda e: events.append(e))

        workflow = engine.create_workflow("tenant_1", "user_1", {})
        engine.queue_workflow(workflow)
        engine.start_processing(workflow)
        engine.update_progress(workflow, "step_1", 30)
        engine.add_artifact(workflow, "artifact_1", "application/json", data={})
        engine.update_progress(workflow, "step_2", 60)
        engine.complete_workflow(workflow)

        # Verify order: queue, start, progress, artifact, progress, complete
        assert events[0].event_type == "status_changed"  # SUBMITTED -> QUEUED
        assert events[1].event_type == "status_changed"  # QUEUED -> PROCESSING
        assert events[2].event_type == "step_progressed"  # progress 30
        assert events[3].event_type == "artifact_created"  # artifact
        assert events[4].event_type == "step_progressed"  # progress 60
        assert events[5].event_type == "status_changed"  # PROCESSING -> COMPLETED


class TestWorkflowRetrieval:
    """Test workflow storage and retrieval."""

    def test_get_workflow(self):
        """Test retrieving workflow by ID."""
        engine = WorkflowEngine()
        workflow = engine.create_workflow("tenant_1", "user_1", {"key": "value"})

        retrieved = engine.get_workflow(workflow.id)

        assert retrieved is not None
        assert retrieved.id == workflow.id
        assert retrieved.input_data == {"key": "value"}

    def test_get_nonexistent_workflow(self):
        """Test getting nonexistent workflow returns None."""
        engine = WorkflowEngine()
        retrieved = engine.get_workflow("nonexistent")
        assert retrieved is None


class TestWorkflowSerialization:
    """Test workflow serialization for API responses."""

    def test_workflow_to_dict(self):
        """Test workflow serialization."""
        engine = WorkflowEngine()
        workflow = engine.create_workflow("tenant_1", "user_1", {})
        engine.queue_workflow(workflow)

        data = workflow.to_dict()

        assert data["id"] == workflow.id
        assert data["tenant_id"] == "tenant_1"
        assert data["user_id"] == "user_1"
        assert data["status"] == "QUEUED"
        assert data["step"] == "queued"
        assert data["progress_pct"] == 5

    def test_workflow_with_error_serialization(self):
        """Test workflow with error serialization."""
        engine = WorkflowEngine()
        workflow = engine.create_workflow("tenant_1", "user_1", {})
        engine.queue_workflow(workflow)
        engine.start_processing(workflow)
        engine.fail_workflow(workflow, LLMTimeoutError("timeout", 30))

        data = workflow.to_dict()

        assert data["status"] == "FAILED"
        assert data["error"] is not None
        assert data["error"]["type"] == "TRANSIENT"
        assert data["error"]["retryable"] is True

    def test_workflow_with_artifacts_serialization(self):
        """Test workflow with artifacts serialization."""
        engine = WorkflowEngine()
        workflow = engine.create_workflow("tenant_1", "user_1", {})
        engine.add_artifact(workflow, "design", "application/pdf", url="https://example.com/design.pdf")

        data = workflow.to_dict()

        assert len(data["artifacts"]) == 1
        assert data["artifacts"][0]["name"] == "design"
        assert data["artifacts"][0]["content_type"] == "application/pdf"
