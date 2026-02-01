"""Stateless workflow worker loop (consumes queue, executes engine, publishes events)."""
import asyncio
import logging
from typing import Optional
from src.infra.queue import WorkflowQueue
from src.api.broadcaster import broadcaster
from src.orchestration.workflow_engine import (
    WorkflowEngine,
    WorkflowStatus,
    WorkflowEvent,
    WorkflowError,
    ErrorType,
)
from src.utils.llm_exceptions import RateLimitError, InvalidResponseError
from src.storage.database import database
from src.storage.repository import WorkflowRepository, WorkflowEventRepository, UserConnectionRepository
from src.adapters.canva_adapter import create_canva_adapter_from_db


logger = logging.getLogger(__name__)


class WorkflowWorker:
    """Stateless worker that processes workflow tasks from Redis Streams."""

    def __init__(self, worker_id: str = "worker-1", redis_url: Optional[str] = None):
        self.worker_id = worker_id
        self.queue = WorkflowQueue(redis_url)
        self.engine = WorkflowEngine()
        self.should_stop = False

    async def start(self, poll_interval_ms: int = 1000) -> None:
        """
        Start the worker loop (polls Redis, executes workflows, streams events).
        
        Blocks until should_stop=True or exception.
        """
        await self.queue.initialize()
        logger.info(f"🚀 [{self.worker_id}] Worker started, polling every {poll_interval_ms}ms")

        try:
            while not self.should_stop:
                try:
                    # 1. Poll Redis Stream (blocks until task or timeout)
                    result = await self.queue.dequeue(self.worker_id, timeout_ms=poll_interval_ms)
                    
                    if not result:
                        # Timeout, no task available
                        continue
                    
                    entry_id, task_data = result
                    workflow_id = task_data.get("workflow_id")
                    tenant_id = task_data.get("tenant_id")
                    action = task_data.get("action", "process")

                    logger.info(f"🔄 [{self.worker_id}] PROCESSING START: workflow_id={workflow_id}, tenant_id={tenant_id}, entry_id={entry_id}")

                    # 2. Fetch workflow from DB (tenant-scoped)
                    async with database.session() as session:
                        wf_repo = WorkflowRepository(session, tenant_id=tenant_id)
                        workflow_db = await wf_repo.get_by_id(workflow_id)
                        if not workflow_db:
                            logger.warning(f"⚠️ [{self.worker_id}] Workflow {workflow_id} NOT FOUND in DB, acking and skipping")
                            await self.queue.ack(entry_id)
                            continue
                        
                        logger.debug(f"[{self.worker_id}] Loaded workflow from DB: status={workflow_db.status}, metadata={workflow_db.custom_metadata}")
                        
                        # Build engine Workflow object from DB state (canonical fields only)
                        from src.orchestration.workflow_engine import Workflow as EngineWorkflow
                        engine_workflow = EngineWorkflow(
                            id=workflow_db.id,
                            tenant_id=workflow_db.tenant_id,
                            user_id=workflow_db.user_id,
                            status=WorkflowStatus(workflow_db.status.upper()),
                            step=(workflow_db.custom_metadata.get("step") or ""),
                            progress_pct=int(workflow_db.custom_metadata.get("progress_pct", 0)),
                            artifacts=[],
                            error=None,
                            input_data=workflow_db.input_config or {},
                            output_data={},
                        )

                    # 3. Handle actions and idempotency
                    # If already terminal, skip regardless of action
                    if engine_workflow.status in (WorkflowStatus.COMPLETED, WorkflowStatus.FAILED) and action != "retry":
                        logger.info(f"✅ [{self.worker_id}] Workflow {workflow_id} already TERMINAL ({engine_workflow.status.value}), acking and skipping")
                        await self.queue.ack(entry_id)
                        continue

                    # Handle cancel action: mark FAILED with user error and persist
                    if action == "cancel":
                        logger.info(f"🛑 [{self.worker_id}] Cancel requested for {workflow_id}")
                        try:
                            # Ensure in-process state for correct transition
                            if engine_workflow.status == WorkflowStatus.SUBMITTED:
                                self.engine.queue_workflow(engine_workflow)
                                self.engine.start_processing(engine_workflow)
                            elif engine_workflow.status == WorkflowStatus.QUEUED:
                                self.engine.start_processing(engine_workflow)

                            # Fail workflow with USER error
                            user_error = WorkflowError(type=ErrorType.USER, message="Cancelled by user", retryable=False)
                            self.engine.fail_workflow(engine_workflow, user_error)

                            # Persist state
                            async with database.session() as session:
                                wf_repo = WorkflowRepository(session, tenant_id=tenant_id)
                                metadata = workflow_db.custom_metadata or {}
                                metadata.update({
                                    "step": engine_workflow.step,
                                    "progress_pct": engine_workflow.progress_pct,
                                    "artifacts": [
                                        {
                                            "name": a.name,
                                            "content_type": a.content_type,
                                            "url": a.url,
                                            "created_at": a.created_at.isoformat(),
                                        } for a in engine_workflow.artifacts
                                    ],
                                    "error": {
                                        "type": user_error.type.value,
                                        "message": user_error.message,
                                        "retryable": user_error.retryable,
                                    },
                                })
                                await wf_repo.update(
                                    workflow_id,
                                    status=engine_workflow.status.value,
                                    custom_metadata=metadata,
                                )

                            await self.queue.ack(entry_id)
                            logger.info(f"✅ [{self.worker_id}] Cancel processed and acked for {workflow_id}")
                        except Exception as e:
                            logger.exception(f"❌ [{self.worker_id}] Error processing cancel: {e}")
                            await asyncio.sleep(0.1)
                        continue

                    # Handle retry action: reset to SUBMITTED and proceed
                    if action == "retry":
                        logger.info(f"🔁 [{self.worker_id}] Retry requested for {workflow_id}")
                        # Reset to SUBMITTED to allow engine transitions
                        old_status = engine_workflow.status
                        engine_workflow.status = WorkflowStatus.SUBMITTED
                        engine_workflow.step = "retrying"
                        engine_workflow.progress_pct = 0
                        # Emit status_changed event
                        evt = WorkflowEvent(
                            workflow_id=engine_workflow.id,
                            tenant_id=engine_workflow.tenant_id,
                            request_id=engine_workflow.request_id,
                            event_type="status_changed",
                            old_status=old_status,
                            new_status=engine_workflow.status,
                            step=engine_workflow.step,
                            progress_pct=engine_workflow.progress_pct,
                        )
                        try:
                            # Emit via engine to ensure callbacks run
                            self.engine._emit_event(evt)
                        except Exception:
                            logger.debug("Failed to emit retry status_changed event")

                    # 4. Register event callback to stream via broadcaster
                    # Collect async tasks for event persistence
                    event_tasks = []
                    
                    def on_event(event):
                        """Synchronous callback that schedules async event persistence."""
                        logger.info(f"🔔 [{self.worker_id}] Event emitted: type={event.event_type}, workflow={workflow_id}")
                        async def persist_and_broadcast():
                            # Persist event then broadcast with DB id for SSE
                            async with database.session() as session:
                                ev_repo = WorkflowEventRepository(session, tenant_id=tenant_id)
                                persisted = await ev_repo.append_event(
                                    workflow_id=workflow_id,
                                    event_type=event.event_type,
                                    payload=event.to_dict(),
                                )
                                logger.info(
                                    f"💾 [{self.worker_id}] Event persisted: event_type={event.event_type}, event_id={persisted.id}, workflow={workflow_id}"
                                )
                            # Broadcast a minimal dict containing id and payload JSON for SSE
                            await broadcaster.publish(
                                workflow_id,
                                {"id": persisted.id, "payload": persisted.payload}
                            )
                            logger.info(f"📡 [{self.worker_id}] Event broadcast: event_id={persisted.id}, workflow={workflow_id}")
                        
                        # Schedule task and keep reference
                        task = asyncio.create_task(persist_and_broadcast())
                        event_tasks.append(task)

                    self.engine.register_event_callback(on_event)

                    # 5. Execute workflow via engine (deterministic state machine)
                    try:
                        logger.info(f"🎯 [{self.worker_id}] Executing workflow engine for {workflow_id}")
                        self.engine.queue_workflow(engine_workflow)
                        self.engine.start_processing(engine_workflow)

                        # Simulated failure (for integration tests) - only once per workflow
                        simulate_flag = (engine_workflow.input_data or {}).get("simulate_failure")
                        simulate_consumed_local = (workflow_db.custom_metadata or {}).get("simulate_failure_consumed")
                        if simulate_flag and not simulate_consumed_local:
                            # Mark consumed in metadata on persist
                            if simulate_flag == "transient_once":
                                raise RateLimitError("forced transient failure")
                            if simulate_flag == "permanent_once":
                                raise InvalidResponseError("forced permanent failure")

                        # Run decision engine calls (mocked for now, real in T2.7)
                        # This is where the orchestration happens
                        self.engine.update_progress(engine_workflow, "analyzing", 25)
                        await asyncio.sleep(0.1)  # Small delay to allow event streaming
                        self.engine.update_progress(engine_workflow, "generating", 50)
                        await asyncio.sleep(0.1)
                        self.engine.update_progress(engine_workflow, "creating", 75)
                        await asyncio.sleep(0.1)
                        self.engine.update_progress(engine_workflow, "finalizing", 95)
                        await asyncio.sleep(0.1)

                        # Create real Canva design if connected
                        try:
                            # Check if user has Canva connection
                            async with database.session() as session:
                                conn_repo = UserConnectionRepository(
                                    session, 
                                    user_id=engine_workflow.user_id,
                                    tenant_id=engine_workflow.tenant_id
                                )
                                has_canva = await conn_repo.has_connection("canva")
                            
                            if has_canva:
                                # Get Canva adapter from database tokens
                                adapter = await create_canva_adapter_from_db(
                                    user_id=engine_workflow.user_id,
                                    tenant_id=engine_workflow.tenant_id
                                )
                                
                                if adapter:
                                    # Create a real design with title from input
                                    title = engine_workflow.input_data.get("description", "Generated Design")
                                    design = await adapter.create_presentation(title=title)
                                    
                                    # Add artifact with design ID and resolvable URL
                                    design_url = f"https://www.canva.com/design/{design.design_id}/edit"
                                    self.engine.add_artifact(
                                        engine_workflow,
                                        name=f"Design: {title}",
                                        content_type="canva_design",
                                        url=design_url,
                                        data={
                                            "design_id": design.design_id,
                                            "title": design.title,
                                            "created_at": design.created_at.isoformat() if design.created_at else None,
                                        }
                                    )
                                    logger.info(f"✅ [{self.worker_id}] Created real Canva design: {design.design_id}")
                                    await adapter.close()
                                else:
                                    logger.warning(f"⚠️ [{self.worker_id}] Canva adapter creation failed (token expired?)")
                                    self.engine.add_artifact(
                                        engine_workflow,
                                        name="Error: Canva token expired",
                                        content_type="text",
                                        data={"message": "Please reconnect to Canva"}
                                    )
                            else:
                                # Canva not connected - add placeholder artifact
                                logger.info(f"ℹ️ [{self.worker_id}] Canva not connected, skipping design creation")
                                self.engine.add_artifact(
                                    engine_workflow,
                                    name="Connect Canva to create designs",
                                    content_type="text",
                                    data={"message": "Click 'Connect Canva' in the app to authorize design creation"}
                                )
                        except Exception as e:
                            logger.error(f"❌ [{self.worker_id}] Failed to create Canva design: {e}")
                            self.engine.add_artifact(
                                engine_workflow,
                                name="Error creating design",
                                content_type="text",
                                data={"error": str(e)}
                            )

                        # Complete workflow
                        self.engine.complete_workflow(engine_workflow)
                        logger.info(f"✅ [{self.worker_id}] Workflow {workflow_id} execution completed successfully")

                    except Exception as e:
                        # Workflow engine classifies error and fails workflow
                        logger.exception(f"❌ [{self.worker_id}] Workflow {workflow_id} FAILED with {type(e).__name__}: {str(e)}")
                        error_type, retryable, message = self.engine._classify_error(e)
                        error = WorkflowError(type=error_type, message=message, retryable=retryable)
                        self.engine.fail_workflow(engine_workflow, error)

                    # 5.5. Wait for all event persistence tasks to complete
                    if event_tasks:
                        logger.debug(f"[{self.worker_id}] Waiting for {len(event_tasks)} event persistence tasks")
                        await asyncio.gather(*event_tasks)

                    # 6. Persist workflow terminal/non-terminal state in DB and commit
                    logger.info(f"💾 [{self.worker_id}] Persisting final state: workflow_id={workflow_id}, status={engine_workflow.status.value}, progress={engine_workflow.progress_pct}%")
                    async with database.session() as session:
                        wf_repo = WorkflowRepository(session, tenant_id=tenant_id)
                        # Update canonical fields inside JSONB metadata to preserve schema
                        metadata = workflow_db.custom_metadata or {}
                        metadata.update({
                            "step": engine_workflow.step,
                            "progress_pct": engine_workflow.progress_pct,
                            "artifacts": [
                                {
                                    "name": a.name,
                                    "content_type": a.content_type,
                                    "url": a.url,
                                    "created_at": a.created_at.isoformat(),
                                } for a in engine_workflow.artifacts
                            ],
                            "error": (
                                {
                                    "type": engine_workflow.error.type.value,
                                    "message": engine_workflow.error.message,
                                    "retryable": engine_workflow.error.retryable,
                                } if engine_workflow.error else None
                            ),
                            # Track simulate flag consumption for integration tests
                            "simulate_failure_consumed": True if (engine_workflow.input_data or {}).get("simulate_failure") else metadata.get("simulate_failure_consumed", False),
                        })
                        await wf_repo.update(
                            workflow_id,
                            status=engine_workflow.status.value,
                            custom_metadata=metadata,
                        )
                        logger.info(f"✅ [{self.worker_id}] DB state committed: workflow_id={workflow_id}")

                    # 7. Ack in Redis (only after DB commit confirms)
                    await self.queue.ack(entry_id)
                    logger.info(f"✅ [{self.worker_id}] PROCESSING COMPLETE: workflow_id={workflow_id}, final_status={engine_workflow.status.value}")

                except Exception as e:
                    logger.exception(f"💥 [{self.worker_id}] CRITICAL ERROR in worker loop: {type(e).__name__}: {str(e)}")
                    # Continue loop on error
                    await asyncio.sleep(0.1)

        finally:
            await self.queue.close()
            logger.info(f"🛑 [{self.worker_id}] Worker stopped")

    def stop(self) -> None:
        """Signal worker to stop polling."""
        self.should_stop = True

    async def process_once(self, timeout_ms: int = 5000) -> bool:
        """
        Process exactly one workflow task from the queue (for testing).
        
        Returns:
            True if a task was processed, False if queue was empty.
        """
        await self.queue.initialize()
        
        # 1. Poll Redis Stream (blocks until task or timeout)
        result = await self.queue.dequeue(self.worker_id, timeout_ms=timeout_ms)
        
        if not result:
            # Timeout, no task available
            return False
        
        entry_id, task_data = result
        workflow_id = task_data.get("workflow_id")
        tenant_id = task_data.get("tenant_id")
        action = task_data.get("action", "process")

        logger.info(f"[{self.worker_id}] Processing workflow {workflow_id}")

        # 2. Fetch workflow from DB (tenant-scoped)
        async with database.session() as session:
            wf_repo = WorkflowRepository(session, tenant_id=tenant_id)
            workflow_db = await wf_repo.get_by_id(workflow_id)
            if not workflow_db:
                logger.warning(f"[{self.worker_id}] Workflow {workflow_id} not found in DB")
                await self.queue.ack(entry_id)
                return True

            metadata = workflow_db.custom_metadata or {}

            # Build engine Workflow object from DB state (canonical fields only)
            from src.orchestration.workflow_engine import Workflow as EngineWorkflow
            engine_workflow = EngineWorkflow(
                id=workflow_db.id,
                tenant_id=workflow_db.tenant_id,
                user_id=workflow_db.user_id,
                status=WorkflowStatus(workflow_db.status.upper()),
                step=(metadata.get("step") or ""),
                progress_pct=int(metadata.get("progress_pct", 0)),
                artifacts=[],
                error=None,
                input_data=workflow_db.input_config or {},
                output_data={},
            )

        # 3. Idempotency / command gating
        if action == "process" and engine_workflow.status in (WorkflowStatus.COMPLETED, WorkflowStatus.FAILED):
            logger.info(f"[{self.worker_id}] Workflow {workflow_id} already terminal, skipping")
            await self.queue.ack(entry_id)
            return True

        # 3.a Retry validation
        if action == "retry":
            if engine_workflow.status != WorkflowStatus.FAILED:
                logger.info(f"[{self.worker_id}] Retry ignored; workflow {workflow_id} not FAILED")
                await self.queue.ack(entry_id)
                return True
            error_meta = (metadata or {}).get("error") or {}
            if not error_meta.get("retryable"):
                logger.info(f"[{self.worker_id}] Retry ignored; error not retryable for {workflow_id}")
                await self.queue.ack(entry_id)
                return True
            # Reset engine state to allow re-queueing
            engine_workflow.status = WorkflowStatus.SUBMITTED
            engine_workflow.step = ""
            engine_workflow.progress_pct = 0
            engine_workflow.error = None
            metadata["error"] = None

        # 3.b Cancel handling (short-circuit, no engine run)
        if action == "cancel":
            if engine_workflow.status in (WorkflowStatus.COMPLETED, WorkflowStatus.FAILED):
                logger.info(f"[{self.worker_id}] Cancel ignored; workflow {workflow_id} already terminal")
                await self.queue.ack(entry_id)
                return True

            # Persist cancel event immediately
            cancel_error = WorkflowError(type=ErrorType.USER, message="Workflow cancelled by user", retryable=False)
            cancel_event = WorkflowEvent(
                workflow_id=workflow_id,
                tenant_id=tenant_id,
                request_id=engine_workflow.request_id,
                event_type="failed",
                old_status=engine_workflow.status,
                new_status=WorkflowStatus.FAILED,
                step="cancelled",
                error=cancel_error,
            )

            async def persist_cancel_event():
                async with database.session() as session:
                    ev_repo = WorkflowEventRepository(session, tenant_id=tenant_id)
                    persisted = await ev_repo.append_event(
                        workflow_id=workflow_id,
                        event_type=cancel_event.event_type,
                        payload=cancel_event.to_dict(),
                    )
                await broadcaster.publish(workflow_id, {"id": persisted.id, "payload": persisted.payload})

            await asyncio.gather(asyncio.create_task(persist_cancel_event()))

            # Update workflow state to FAILED (user-cancelled)
            metadata.update({
                "step": "cancelled",
                "progress_pct": 100,
                "error": {
                    "type": cancel_error.type.value,
                    "message": cancel_error.message,
                    "retryable": cancel_error.retryable,
                },
            })

            async with database.session() as session:
                wf_repo = WorkflowRepository(session, tenant_id=tenant_id)
                await wf_repo.update(
                    workflow_id,
                    status=WorkflowStatus.FAILED.value,
                    custom_metadata=metadata,
                )

            await self.queue.ack(entry_id)
            logger.info(f"[{self.worker_id}] Workflow {workflow_id} cancelled and acked")
            return True

        # 4. Register event callback to stream via broadcaster
        # Collect async tasks for event persistence
        event_tasks: list[asyncio.Task] = []
        
        def on_event(event):
            """Synchronous callback that schedules async event persistence."""
            async def persist_and_broadcast():
                # Persist event then broadcast with DB id for SSE
                async with database.session() as session:
                    ev_repo = WorkflowEventRepository(session, tenant_id=tenant_id)
                    persisted = await ev_repo.append_event(
                        workflow_id=workflow_id,
                        event_type=event.event_type,
                        payload=event.to_dict(),
                    )
                # Broadcast a minimal dict containing id and payload JSON for SSE
                await broadcaster.publish(workflow_id, {"id": persisted.id, "payload": persisted.payload})
            
            # Schedule task and keep reference
            task = asyncio.create_task(persist_and_broadcast())
            event_tasks.append(task)

        self.engine.register_event_callback(on_event)

        # 5. Execute workflow via engine (deterministic state machine)
        try:
            self.engine.queue_workflow(engine_workflow)
            self.engine.start_processing(engine_workflow)

            # Simulated failure (for integration tests) - only once per workflow
            simulate_flag = (engine_workflow.input_data or {}).get("simulate_failure")
            if simulate_flag and not metadata.get("simulate_failure_consumed"):
                metadata["simulate_failure_consumed"] = True
                if simulate_flag == "transient_once":
                    raise RateLimitError("forced transient failure")
                if simulate_flag == "permanent_once":
                    raise InvalidResponseError("forced permanent failure")

            # Run decision engine calls (mocked for now, real in T2.7)
            # This is where the orchestration happens
            self.engine.update_progress(engine_workflow, "analyzing", 25)
            self.engine.update_progress(engine_workflow, "generating", 50)
            self.engine.update_progress(engine_workflow, "creating", 75)
            self.engine.update_progress(engine_workflow, "finalizing", 95)

            # Add sample artifacts
            self.engine.add_artifact(engine_workflow, "result.json", "application/json", url="s3://...")

            # Complete workflow
            self.engine.complete_workflow(engine_workflow)

        except Exception as e:
            # Workflow engine classifies error and fails workflow
            logger.exception(f"[{self.worker_id}] Workflow {workflow_id} failed with {type(e).__name__}")
            error_type, retryable, message = self.engine._classify_error(e)
            error = WorkflowError(type=error_type, message=message, retryable=retryable)
            self.engine.fail_workflow(engine_workflow, error)

        # 5.5. Wait for all event persistence tasks to complete
        if event_tasks:
            await asyncio.gather(*event_tasks)

        # 6. Persist workflow terminal/non-terminal state in DB and commit
        async with database.session() as session:
            wf_repo = WorkflowRepository(session, tenant_id=tenant_id)
            # Update canonical fields inside JSONB metadata to preserve schema
            metadata.update({
                "step": engine_workflow.step,
                "progress_pct": engine_workflow.progress_pct,
                "artifacts": [
                    {
                        "name": a.name,
                        "content_type": a.content_type,
                        "url": a.url,
                        "created_at": a.created_at.isoformat(),
                    } for a in engine_workflow.artifacts
                ],
                "error": (
                    {
                        "type": engine_workflow.error.type.value,
                        "message": engine_workflow.error.message,
                        "retryable": engine_workflow.error.retryable,
                    } if engine_workflow.error else None
                ),
            })
            await wf_repo.update(
                workflow_id,
                status=engine_workflow.status.value,
                custom_metadata=metadata,
            )

        # 7. Ack in Redis (only after DB commit confirms)
        await self.queue.ack(entry_id)
        logger.info(f"[{self.worker_id}] Workflow {workflow_id} completed and acked")
        
        return True


async def run_worker_loop(worker_id: str = "worker-1", redis_url: Optional[str] = None) -> None:
    """Convenience function to run a worker loop until stopped."""
    # Initialize database connection (required for all DB operations)
    await database.connect()
    
    # Create tables if they don't exist (for dev/test; prod uses migrations)
    try:
        await database.create_tables()
    except Exception:
        # Tables may already exist or migrations manage schema
        pass
    
    worker = WorkflowWorker(worker_id, redis_url)
    try:
        await worker.start()
    finally:
        await database.disconnect()
