"""Deterministic workflow engine for orchestrating Canva + NotebookLM + LLM decisions.

State machine: SUBMITTED → QUEUED → PROCESSING → COMPLETED | FAILED
No LLM-driven state changes; all transitions explicit and deterministic.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, AsyncIterator
import uuid
import logging

from src.utils.llm_exceptions import (
    LLMAPIError,
    InvalidResponseError,
    TokenCountError,
    TimeoutError,
    RateLimitError,
    FallbackActivatedError,
)


logger = logging.getLogger(__name__)


class WorkflowStatus(Enum):
    """Deterministic workflow status states."""
    SUBMITTED = "SUBMITTED"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ErrorType(Enum):
    """Error classification for failure states."""
    TRANSIENT = "TRANSIENT"      # Retryable (rate limit, timeout, temporary outage)
    PERMANENT = "PERMANENT"      # Not retryable (invalid input, auth, 404)
    USER = "USER"                # User error (bad input, quota exceeded)


@dataclass
class WorkflowError:
    """Structured error representation for workflow failures."""
    type: ErrorType
    message: str
    retryable: bool = False

    def __post_init__(self):
        """Validate retryable flag matches error type."""
        if self.type == ErrorType.TRANSIENT and not self.retryable:
            self.retryable = True
        elif self.type == ErrorType.PERMANENT and self.retryable:
            self.retryable = False


@dataclass
class WorkflowArtifact:
    """Artifact (output) produced during workflow execution."""
    name: str
    content_type: str
    url: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Workflow:
    """Persistent workflow entity representing a single integration task."""
    id: str
    tenant_id: str
    user_id: str
    status: WorkflowStatus
    step: str  # Current step (e.g., "analyzing_content", "generating_layout")
    progress_pct: int  # 0-100
    artifacts: List[WorkflowArtifact] = field(default_factory=list)
    error: Optional[WorkflowError] = None
    input_data: Dict[str, Any] = field(default_factory=dict)
    output_data: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for API responses."""
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "status": self.status.value,
            "step": self.step,
            "progress_pct": self.progress_pct,
            "artifacts": [
                {
                    "name": a.name,
                    "content_type": a.content_type,
                    "url": a.url,
                    "created_at": a.created_at.isoformat(),
                }
                for a in self.artifacts
            ],
            "error": {
                "type": self.error.type.value,
                "message": self.error.message,
                "retryable": self.error.retryable,
            } if self.error else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "request_id": self.request_id,
        }


@dataclass
class WorkflowEvent:
    """Event emitted on workflow state/progress changes."""
    workflow_id: str
    tenant_id: str
    request_id: str
    event_type: str  # "status_changed", "step_progressed", "artifact_created", "failed"
    old_status: Optional[WorkflowStatus] = None
    new_status: Optional[WorkflowStatus] = None
    step: Optional[str] = None
    progress_pct: Optional[int] = None
    error: Optional[WorkflowError] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dict for streaming."""
        return {
            "workflow_id": self.workflow_id,
            "tenant_id": self.tenant_id,
            "request_id": self.request_id,
            "event_type": self.event_type,
            "old_status": self.old_status.value if self.old_status else None,
            "new_status": self.new_status.value if self.new_status else None,
            "step": self.step,
            "progress_pct": self.progress_pct,
            "error": {
                "type": self.error.type.value,
                "message": self.error.message,
                "retryable": self.error.retryable,
            } if self.error else None,
            "timestamp": self.timestamp.isoformat(),
        }


class WorkflowEngine:
    """Orchestration engine managing deterministic workflow execution."""

    def __init__(self):
        """Initialize engine with event queue."""
        self._event_queue: List[WorkflowEvent] = []
        self._event_callbacks: List[Callable[[WorkflowEvent], Any]] = []
        self._workflows: Dict[str, Workflow] = {}  # In-memory storage for MVP

    def create_workflow(
        self,
        tenant_id: str,
        user_id: str,
        input_data: Dict[str, Any],
    ) -> Workflow:
        """Create and submit a new workflow.

        Args:
            tenant_id: Tenant identifier
            user_id: User identifier
            input_data: Workflow input (source_id, title, etc.)

        Returns:
            Workflow in SUBMITTED state
        """
        workflow = Workflow(
            id=f"wf_{uuid.uuid4().hex[:12]}",
            tenant_id=tenant_id,
            user_id=user_id,
            status=WorkflowStatus.SUBMITTED,
            step="submitted",
            progress_pct=0,
            input_data=input_data,
            request_id=str(uuid.uuid4()),
        )
        self._workflows[workflow.id] = workflow
        logger.info(
            "Workflow created",
            extra={
                "workflow_id": workflow.id,
                "tenant_id": tenant_id,
                "request_id": workflow.request_id,
            },
        )
        return workflow

    def queue_workflow(self, workflow: Workflow) -> None:
        """Transition workflow from SUBMITTED to QUEUED.

        Args:
            workflow: Workflow to queue

        Raises:
            ValueError: If workflow is not in SUBMITTED state
        """
        if workflow.status != WorkflowStatus.SUBMITTED:
            raise ValueError(
                f"Cannot queue workflow in {workflow.status.value} state; "
                f"expected {WorkflowStatus.SUBMITTED.value}"
            )

        old_status = workflow.status
        workflow.status = WorkflowStatus.QUEUED
        workflow.step = "queued"
        workflow.progress_pct = 5
        workflow.updated_at = datetime.utcnow()

        event = WorkflowEvent(
            workflow_id=workflow.id,
            tenant_id=workflow.tenant_id,
            request_id=workflow.request_id,
            event_type="status_changed",
            old_status=old_status,
            new_status=workflow.status,
            step=workflow.step,
            progress_pct=workflow.progress_pct,
        )
        self._emit_event(event)

    def start_processing(self, workflow: Workflow) -> None:
        """Transition workflow from QUEUED to PROCESSING.

        Args:
            workflow: Workflow to start processing

        Raises:
            ValueError: If workflow is not in QUEUED state
        """
        if workflow.status != WorkflowStatus.QUEUED:
            raise ValueError(
                f"Cannot start processing workflow in {workflow.status.value} state; "
                f"expected {WorkflowStatus.QUEUED.value}"
            )

        old_status = workflow.status
        workflow.status = WorkflowStatus.PROCESSING
        workflow.step = "initializing"
        workflow.progress_pct = 10
        workflow.updated_at = datetime.utcnow()

        event = WorkflowEvent(
            workflow_id=workflow.id,
            tenant_id=workflow.tenant_id,
            request_id=workflow.request_id,
            event_type="status_changed",
            old_status=old_status,
            new_status=workflow.status,
            step=workflow.step,
            progress_pct=workflow.progress_pct,
        )
        self._emit_event(event)

    def update_progress(
        self,
        workflow: Workflow,
        step: str,
        progress_pct: int,
    ) -> None:
        """Update workflow progress during PROCESSING.

        Args:
            workflow: Workflow to update
            step: Current step name
            progress_pct: Progress percentage (0-100)

        Raises:
            ValueError: If workflow is not in PROCESSING state or progress is invalid
        """
        if workflow.status != WorkflowStatus.PROCESSING:
            raise ValueError(
                f"Cannot update progress for workflow in {workflow.status.value} state; "
                f"expected {WorkflowStatus.PROCESSING.value}"
            )

        if not 0 <= progress_pct <= 100:
            raise ValueError(f"Progress must be 0-100, got {progress_pct}")

        workflow.step = step
        workflow.progress_pct = progress_pct
        workflow.updated_at = datetime.utcnow()

        event = WorkflowEvent(
            workflow_id=workflow.id,
            tenant_id=workflow.tenant_id,
            request_id=workflow.request_id,
            event_type="step_progressed",
            step=step,
            progress_pct=progress_pct,
        )
        self._emit_event(event)

    def add_artifact(
        self,
        workflow: Workflow,
        name: str,
        content_type: str,
        url: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add artifact (output) to workflow.

        Args:
            workflow: Workflow to update
            name: Artifact name (e.g., "design_export")
            content_type: MIME type (e.g., "application/pdf")
            url: Optional URL to artifact
            data: Optional structured data
        """
        artifact = WorkflowArtifact(
            name=name,
            content_type=content_type,
            url=url,
            data=data,
        )
        workflow.artifacts.append(artifact)
        workflow.updated_at = datetime.utcnow()

        event = WorkflowEvent(
            workflow_id=workflow.id,
            tenant_id=workflow.tenant_id,
            request_id=workflow.request_id,
            event_type="artifact_created",
            step=workflow.step,
            progress_pct=workflow.progress_pct,
        )
        self._emit_event(event)

    def complete_workflow(self, workflow: Workflow) -> None:
        """Transition workflow from PROCESSING to COMPLETED.

        Args:
            workflow: Workflow to complete

        Raises:
            ValueError: If workflow is not in PROCESSING state
        """
        if workflow.status != WorkflowStatus.PROCESSING:
            raise ValueError(
                f"Cannot complete workflow in {workflow.status.value} state; "
                f"expected {WorkflowStatus.PROCESSING.value}"
            )

        old_status = workflow.status
        workflow.status = WorkflowStatus.COMPLETED
        workflow.step = "completed"
        workflow.progress_pct = 100
        workflow.error = None
        workflow.updated_at = datetime.utcnow()

        event = WorkflowEvent(
            workflow_id=workflow.id,
            tenant_id=workflow.tenant_id,
            request_id=workflow.request_id,
            event_type="status_changed",
            old_status=old_status,
            new_status=workflow.status,
            step=workflow.step,
            progress_pct=workflow.progress_pct,
        )
        self._emit_event(event)

        logger.info(
            "Workflow completed",
            extra={
                "workflow_id": workflow.id,
                "tenant_id": workflow.tenant_id,
                "request_id": workflow.request_id,
            },
        )

    def fail_workflow(
        self,
        workflow: Workflow,
        error: WorkflowError,
        step: Optional[str] = None,
    ) -> None:
        """Transition workflow from PROCESSING to FAILED.

        Args:
            workflow: Workflow to fail
            error: WorkflowError with classification and retryable flag
            step: Optional step where failure occurred
        """
        if workflow.status != WorkflowStatus.PROCESSING:
            raise ValueError(
                f"Cannot fail workflow in {workflow.status.value} state; "
                f"expected {WorkflowStatus.PROCESSING.value}"
            )

        old_status = workflow.status
        workflow.status = WorkflowStatus.FAILED
        workflow.step = step or workflow.step
        workflow.error = error
        workflow.updated_at = datetime.utcnow()

        event = WorkflowEvent(
            workflow_id=workflow.id,
            tenant_id=workflow.tenant_id,
            request_id=workflow.request_id,
            event_type="failed",
            old_status=old_status,
            new_status=workflow.status,
            step=workflow.step,
            error=workflow.error,
        )
        self._emit_event(event)

        logger.warning(
            "Workflow failed: %s",
            error.message,
            extra={
                "workflow_id": workflow.id,
                "tenant_id": workflow.tenant_id,
                "request_id": workflow.request_id,
                "error_type": error.type.value,
                "retryable": error.retryable,
            },
        )

    def register_event_callback(
        self,
        callback: Callable[[WorkflowEvent], Any],
    ) -> None:
        """Register callback for workflow events.

        Args:
            callback: Callable(event: WorkflowEvent) -> Any
        """
        self._event_callbacks.append(callback)

    async def event_stream(
        self,
        workflow_id: str,
    ) -> AsyncIterator[WorkflowEvent]:
        """Stream events for a workflow (async generator).

        Args:
            workflow_id: Workflow to stream events for

        Yields:
            WorkflowEvent for each event
        """
        # In a real implementation, this would read from a queue/database
        # For testing, we just yield from the in-memory queue
        idx = 0
        while True:
            # Check if we have new events
            if idx < len(self._event_queue):
                event = self._event_queue[idx]
                if event.workflow_id == workflow_id:
                    idx += 1
                    yield event
            else:
                # No more events yet; sleep briefly and check again
                import asyncio
                await asyncio.sleep(0.1)

            # Stop streaming if workflow is completed or failed
            if workflow_id in self._workflows:
                workflow = self._workflows[workflow_id]
                if workflow.status in (WorkflowStatus.COMPLETED, WorkflowStatus.FAILED):
                    # Return remaining events
                    while idx < len(self._event_queue):
                        event = self._event_queue[idx]
                        if event.workflow_id == workflow_id:
                            idx += 1
                            yield event
                        else:
                            idx += 1
                    break

    def get_workflow(self, workflow_id: str) -> Optional[Workflow]:
        """Retrieve workflow by ID.

        Args:
            workflow_id: Workflow identifier

        Returns:
            Workflow or None if not found
        """
        return self._workflows.get(workflow_id)

    def _emit_event(self, event: WorkflowEvent) -> None:
        """Emit event to all registered callbacks and queue.

        Args:
            event: WorkflowEvent to emit
        """
        self._event_queue.append(event)

        for callback in self._event_callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.exception(
                    "Error in event callback",
                    extra={"workflow_id": event.workflow_id},
                )

    def _classify_error(
        self,
        exception: Exception,
    ) -> tuple[ErrorType, bool, str]:
        """Classify exception as transient, permanent, or user error.

        Args:
            exception: Exception to classify

        Returns:
            (ErrorType, retryable, message)
        """
        # Transient errors (retryable)
        if isinstance(exception, (TimeoutError, RateLimitError)):
            return (ErrorType.TRANSIENT, True, str(exception))

        # Permanent errors (not retryable)
        if isinstance(exception, (InvalidResponseError, TokenCountError)):
            return (ErrorType.PERMANENT, False, str(exception))

        # LLM fallback (user-facing, may be retryable)
        if isinstance(exception, FallbackActivatedError):
            return (ErrorType.USER, False, str(exception))

        # Generic LLM API error (default to transient)
        if isinstance(exception, LLMAPIError):
            return (ErrorType.TRANSIENT, True, str(exception))

        # Unknown (default to permanent)
        return (ErrorType.PERMANENT, False, str(exception))
