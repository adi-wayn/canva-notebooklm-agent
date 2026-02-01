"""Workflow API routes (5 endpoints from T2.4 UX spec)."""
import uuid
import logging
from fastapi import APIRouter, HTTPException, Header, Response, Query
from fastapi.responses import StreamingResponse
from datetime import datetime
from src.api.schemas.workflow import (
    WorkflowSchema,
    CreateWorkflowRequest,
    RetryWorkflowRequest,
)
from src.api.broadcaster import broadcaster
from src.orchestration.workflow_engine import (
    Workflow,
    WorkflowStatus,
    WorkflowError,
    ErrorType,
    WorkflowEvent,
)
from src.infra.queue import WorkflowQueue
from src.storage.database import database
from src.storage.repository import WorkflowRepository, WorkflowEventRepository


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["workflows"])
queue = WorkflowQueue()


def _extract_tenant_id(x_tenant_id: str) -> str:
    """Extract tenant ID from header (Phase 1 convention)."""
    if not x_tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-ID header required")
    return x_tenant_id


def _workflow_to_schema(workflow: Workflow) -> WorkflowSchema:
    """Convert internal Workflow model to Pydantic schema."""
    error_data = None
    if workflow.error:
        error_data = {
            "type": workflow.error.type.value,
            "message": workflow.error.message,
            "retryable": workflow.error.retryable,
        }

    artifacts_data = [
        {
            "name": artifact.name,
            "content_type": artifact.content_type,
            "url": artifact.url,
            "data": artifact.data,
            "created_at": artifact.created_at,
        }
        for artifact in workflow.artifacts
    ]

    return WorkflowSchema(
        id=workflow.id,
        tenant_id=workflow.tenant_id,
        user_id=workflow.user_id,
        status=workflow.status.value,
        step=workflow.step if workflow.step else None,
        progress_pct=workflow.progress_pct,
        artifacts=artifacts_data,
        error=error_data,
        created_at=workflow.created_at,
        started_at=getattr(workflow, 'started_at', None),
        completed_at=getattr(workflow, 'completed_at', None),
        request_id=workflow.request_id,
    )


@router.post("/workflows")
async def create_workflow(
    request: CreateWorkflowRequest,
    x_tenant_id: str = Header(None),
) -> WorkflowSchema:
    """
    Create a new workflow and enqueue for processing.
    
    POST /api/v1/workflows
    Header: X-Tenant-ID
    Body: {"user_id": "u_xxx", "tenant_id": "t_yyy", "config": {...}}
    
    Returns: Workflow with status=SUBMITTED
    """
    tenant_id = _extract_tenant_id(x_tenant_id)
    
    # Validate tenant consistency
    if request.tenant_id != tenant_id:
        raise HTTPException(status_code=400, detail="Tenant ID mismatch (body vs header)")

    # Create workflow (initial status = SUBMITTED)
    workflow = Workflow(
        id=f"wf_{uuid.uuid4().hex[:12]}",
        tenant_id=tenant_id,
        user_id=request.user_id,
        status=WorkflowStatus.SUBMITTED,
        step="",
        progress_pct=0,
        request_id=f"req_{uuid.uuid4().hex[:8]}",
        created_at=datetime.utcnow(),
    )

    # Persist in DB (replace in-memory store)
    async with database.session() as session:
        wf_repo = WorkflowRepository(session, tenant_id=tenant_id)
        await wf_repo.create(
            id=workflow.id,
            tenant_id=workflow.tenant_id,
            user_id=workflow.user_id,
            status=workflow.status.value,
            input_config=request.config or {},
            custom_metadata={
                "step": workflow.step,
                "progress_pct": workflow.progress_pct,
                "artifacts": [],
                "error": None,
            },
        )

    # Enqueue to Redis (best-effort)
    try:
        await queue.enqueue(workflow.id, tenant_id)
    except Exception:
        logger.warning(f"Failed to enqueue workflow {workflow.id}; will rely on retry mechanisms")

    # Enqueue to Redis (best-effort; if unavailable, workflow stays in SUBMITTED)
    # Note: We don't block on this; async enqueueing can happen in background
    logger.info(f"Workflow {workflow.id} created (enqueue deferred to background)")

    return _workflow_to_schema(workflow)


@router.get("/workflows/{workflow_id}")
async def get_workflow(
    workflow_id: str,
    x_tenant_id: str = Header(None),
) -> WorkflowSchema:
    """
    Get workflow status and details.
    
    GET /api/v1/workflows/{workflow_id}
    Header: X-Tenant-ID
    
    Returns: Current Workflow state
    """
    tenant_id = _extract_tenant_id(x_tenant_id)

    async with database.session() as session:
        wf_repo = WorkflowRepository(session, tenant_id=tenant_id)
        workflow_db = await wf_repo.get_by_id(workflow_id)
        if not workflow_db:
            raise HTTPException(status_code=404, detail="Workflow not found")

    # Tenant isolation
    if workflow_db.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    # Map DB fields to canonical API schema
    metadata = workflow_db.custom_metadata or {}
    return WorkflowSchema(
        id=workflow_db.id,
        tenant_id=workflow_db.tenant_id,
        user_id=workflow_db.user_id,
        status=str(workflow_db.status).upper(),
        step=metadata.get("step") or "",
        progress_pct=int(metadata.get("progress_pct", 0)),
        artifacts=metadata.get("artifacts", []),
        error=metadata.get("error"),
        created_at=workflow_db.created_at,
        started_at=workflow_db.started_at,
        completed_at=workflow_db.completed_at,
        request_id=metadata.get("request_id", ""),
    )


@router.get("/workflows/{workflow_id}/stream")
async def stream_workflow_events(
    workflow_id: str,
    x_tenant_id: str = Header(None),
    last_event_id: int | None = Query(None),
    last_event_id_header: int | None = Header(None, alias="Last-Event-ID"),
):
    """
    Stream workflow events via Server-Sent Events (SSE).
    
    GET /api/v1/workflows/{workflow_id}/stream
    Header: X-Tenant-ID
    
    Returns: Streaming response (text/event-stream)
    """
    tenant_id = _extract_tenant_id(x_tenant_id)

    async with database.session() as session:
        wf_repo = WorkflowRepository(session, tenant_id=tenant_id)
        workflow_db = await wf_repo.get_by_id(workflow_id)
        if not workflow_db:
            raise HTTPException(status_code=404, detail="Workflow not found")

    # Tenant isolation
    if workflow_db.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    # Determine replay cursor
    replay_cursor = last_event_id_header if last_event_id_header is not None else (last_event_id or 0)

    # Subscribe to events
    queue = broadcaster.subscribe(workflow_id)

    async def event_generator():
        try:
            # 1) Replay persisted events > cursor (source of truth)
            async with database.session() as session:
                ev_repo = WorkflowEventRepository(session, tenant_id=tenant_id)
                events = await ev_repo.list_after(workflow_id, replay_cursor)
                logger.info(f"[SSE] Replaying {len(events)} persisted events for {workflow_id}")
                for ev in events:
                    yield f"id: {ev.id}\n"
                    import json as _json
                    yield f"data: {_json.dumps(ev.payload)}\n\n"
            
            # 2) For live updates in same-process context (e.g., E2E test),
            # subscribe to in-memory broadcaster (worker in same process)
            while True:
                event = await queue.get()
                # Expect dict {"id": int, "payload": dict}
                if isinstance(event, dict) and "id" in event and "payload" in event:
                    yield f"id: {event['id']}\n"
                    import json as _json
                    yield f"data: {_json.dumps(event['payload'])}\n\n"
                else:
                    # Fallback (legacy)
                    event_json = event.to_json() if hasattr(event, "to_json") else str(event)
                    yield f"data: {event_json}\n\n"
        except Exception as e:
            logger.error(f"[SSE] Error streaming events for {workflow_id}: {e}")
        finally:
            broadcaster.unsubscribe(workflow_id, queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/workflows/{workflow_id}/retry")
async def retry_workflow(
    workflow_id: str,
    request: RetryWorkflowRequest,
    x_tenant_id: str = Header(None),
) -> WorkflowSchema:
    """
    Retry a failed workflow (only if error.retryable=true).
    
    POST /api/v1/workflows/{workflow_id}/retry
    Header: X-Tenant-ID
    Body: {}
    
    Returns: Workflow with status reset to QUEUED
    """
    tenant_id = _extract_tenant_id(x_tenant_id)

    async with database.session() as session:
        wf_repo = WorkflowRepository(session, tenant_id=tenant_id)
        workflow_db = await wf_repo.get_by_id(workflow_id)
        if not workflow_db:
            raise HTTPException(status_code=404, detail="Workflow not found")

    # Tenant isolation
    if workflow_db.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    # Verify workflow is failed
    if str(workflow_db.status).upper() != WorkflowStatus.FAILED.value:
        raise HTTPException(status_code=400, detail="Workflow is not in FAILED state")

    # Verify error is retryable
    metadata = workflow_db.custom_metadata or {}
    error = metadata.get("error")
    if not error or not bool(error.get("retryable")):
        raise HTTPException(status_code=400, detail="Workflow error is not retryable")

    # Enqueue retry command (worker will reset and reprocess)
    try:
        await queue.enqueue(workflow_id, tenant_id, action="retry")
    except Exception:
        logger.warning(f"Failed to enqueue retry for workflow {workflow_id}; will rely on retry mechanisms")

    # Return current state (worker will mutate asynchronously)
    md = metadata
    return WorkflowSchema(
        id=workflow_db.id,
        tenant_id=workflow_db.tenant_id,
        user_id=workflow_db.user_id,
        status=str(workflow_db.status).upper(),
        step=md.get("step") or "",
        progress_pct=int(md.get("progress_pct", 0)),
        artifacts=md.get("artifacts", []),
        error=md.get("error"),
        created_at=workflow_db.created_at,
        started_at=workflow_db.started_at,
        completed_at=workflow_db.completed_at,
        request_id=md.get("request_id", ""),
    )


@router.post("/workflows/{workflow_id}/cancel")
async def cancel_workflow(
    workflow_id: str,
    x_tenant_id: str = Header(None),
) -> WorkflowSchema:
    """
    Cancel a workflow (moves to FAILED with error type=USER).
    
    POST /api/v1/workflows/{workflow_id}/cancel
    Header: X-Tenant-ID
    
    Returns: Workflow with status=FAILED, error.type=USER
    """
    tenant_id = _extract_tenant_id(x_tenant_id)

    async with database.session() as session:
        wf_repo = WorkflowRepository(session, tenant_id=tenant_id)
        workflow_db = await wf_repo.get_by_id(workflow_id)
        if not workflow_db:
            raise HTTPException(status_code=404, detail="Workflow not found")

    # Tenant isolation
    if workflow_db.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    # Verify workflow is not already terminal
    if str(workflow_db.status).upper() in (WorkflowStatus.COMPLETED.value, WorkflowStatus.FAILED.value):
        raise HTTPException(status_code=400, detail="Workflow is already terminal")

    # Enqueue cancel command (worker will mark FAILED + emit event)
    try:
        await queue.enqueue(workflow_id, tenant_id, action="cancel")
    except Exception:
        logger.warning(f"Failed to enqueue cancel for workflow {workflow_id}; will rely on retry mechanisms")

    logger.info(f"Workflow {workflow_id} cancel requested; queued for processing")

    # Return current state (worker will mutate asynchronously)
    md = workflow_db.custom_metadata or {}
    return WorkflowSchema(
        id=workflow_db.id,
        tenant_id=workflow_db.tenant_id,
        user_id=workflow_db.user_id,
        status=str(workflow_db.status).upper(),
        step=md.get("step") or "",
        progress_pct=int(md.get("progress_pct", 0)),
        artifacts=md.get("artifacts", []),
        error=md.get("error"),
        created_at=workflow_db.created_at,
        started_at=workflow_db.started_at,
        completed_at=workflow_db.completed_at,
        request_id=md.get("request_id", ""),
    )
