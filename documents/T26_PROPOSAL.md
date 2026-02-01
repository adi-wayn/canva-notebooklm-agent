# T2.6 Proposal – Production Hardening (Persistence + Durable Events + Async SSE)

**Objective:** Replace in-memory storage with PostgreSQL persistence, add durable event stream, and implement proper async SSE tests with httpx.AsyncClient.

**Non-Negotiables:**
- WorkflowEngine remains read-only (deterministic, no behavior changes)
- API responses mirror T2.4 Workflow model (no field renames)
- No root artifacts; all docs in documents/
- All tests must complete without hanging (timeouts enforced)

---

## 1. File Structure (New & Modified)

### New Files (9 total)

**Database Layer:**
1. `src/db/__init__.py` (0 lines)
2. `src/db/session.py` (~40 lines) - SQLAlchemy session factory + engine initialization
3. `src/db/models.py` (~200 lines) - SQLAlchemy ORM models (Workflow, Artifact, Error, Event)
4. `src/persistence/__init__.py` (0 lines)
5. `src/persistence/workflow_repository.py` (~150 lines) - Data access layer (replaces src/api/store.py)

**Migrations:**
6. `alembic/versions/001_initial_schema.py` (~100 lines) - Create Workflow + Artifact + Error + Event tables

**Async SSE Tests:**
7. `tests/integration/test_workflow_sse.py` (~250 lines) - Async SSE tests with httpx.AsyncClient

**Event Streaming (Optional):**
8. `src/api/event_store.py` (~80 lines) - Event replay from DB (WorkflowEvent table)
9. `src/db/migrations/002_event_store.py` (included in 001 migration)

### Modified Files (4 total)

1. `src/main.py` - Add DB engine initialization, session middleware
2. `src/api/routes/workflows.py` - Replace store with repository, add event_id parameter to SSE endpoint
3. `src/api/broadcaster.py` - Rename to `src/api/event_publisher.py`, add DB event persistence
4. `src/workers/workflow_worker.py` - Update to persist state to DB via repository

---

## 2. Database Schema (PostgreSQL)

### Table: workflows
```sql
CREATE TABLE workflows (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id VARCHAR(255) NOT NULL,
  tenant_id VARCHAR(255) NOT NULL,
  status VARCHAR(50) NOT NULL DEFAULT 'SUBMITTED',
    -- ENUM values: SUBMITTED, QUEUED, IN_PROGRESS, COMPLETED, FAILED
  config JSONB NOT NULL,
  current_step VARCHAR(255),
  progress_pct INTEGER DEFAULT 0,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
  
  CONSTRAINT fk_tenant_workflow UNIQUE (tenant_id, id),
  INDEX idx_tenant_status (tenant_id, status),
  INDEX idx_user_id (user_id)
);
```

### Table: workflow_errors
```sql
CREATE TABLE workflow_errors (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workflow_id UUID NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
  type VARCHAR(50) NOT NULL,
    -- ENUM values: USER, TIMEOUT, INVALID_INPUT, PERMANENT
  message TEXT NOT NULL,
  retryable BOOLEAN NOT NULL DEFAULT false,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  
  INDEX idx_workflow_id (workflow_id)
);
```

### Table: workflow_artifacts
```sql
CREATE TABLE workflow_artifacts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workflow_id UUID NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
  name VARCHAR(255) NOT NULL,
  content_type VARCHAR(100),
  url VARCHAR(1024),
  data BYTEA,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  
  INDEX idx_workflow_id (workflow_id)
);
```

### Table: workflow_events (Durable Event Stream)
```sql
CREATE TABLE workflow_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workflow_id UUID NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
  event_type VARCHAR(100) NOT NULL,
    -- Values: progress, started, completed, error, artifact_created, etc.
  payload JSONB NOT NULL,
  sequence_number INTEGER NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  
  UNIQUE (workflow_id, sequence_number),
  INDEX idx_workflow_sequence (workflow_id, sequence_number)
);
```

### Indexes
- `idx_tenant_status(tenant_id, status)` - Fast tenant + status filtering
- `idx_user_id(user_id)` - User workflow lookup
- `idx_workflow_sequence(workflow_id, sequence_number)` - Event replay

---

## 3. Code Changes Summary

### src/main.py
```python
# NEW CODE:
from src.db.session import engine, SessionLocal
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app):
    # Startup: Initialize DB engine
    from alembic.config import Config
    from alembic.runtime.migration import MigrationContext
    from alembic.operations import Operations
    
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: MigrationContext.configure(c))
    
    yield
    
    # Shutdown: Close DB
    await engine.dispose()

app = FastAPI(lifespan=lifespan)
```

### src/api/routes/workflows.py
```python
# CHANGES:
# 1. Replace: from src.api.store import store → from src.persistence.workflow_repository import repository
# 2. Update all endpoints to use repository instead of store
# 3. Stream endpoint: accept optional query parameter `last_event_id`
#    - If provided, replay events from DB starting after that ID
#    - Otherwise, start fresh
#
# Example:
@router.get("/workflows/{workflow_id}/stream")
async def stream_workflow_events(
    workflow_id: str,
    x_tenant_id: str = Header(None),
    last_event_id: Optional[str] = Query(None),
):
    # ... tenant validation ...
    
    async def event_generator():
        # If last_event_id provided, replay from DB first
        if last_event_id:
            events = await repository.get_events_after(workflow_id, last_event_id)
            for event in events:
                yield f"data: {event.to_json()}\nid: {event.id}\n\n"
        
        # Then subscribe to live events
        queue = event_publisher.subscribe(workflow_id)
        try:
            while True:
                event = await queue.get()
                yield f"data: {event.to_json()}\nid: {event.id}\n\n"
        finally:
            event_publisher.unsubscribe(workflow_id, queue)
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

### src/persistence/workflow_repository.py (New)
```python
# NEW FILE: Data access layer replacing src/api/store.py
# Methods:
# - create(workflow) → Workflow
# - get(workflow_id) → Workflow
# - update(workflow) → Workflow
# - list_by_tenant(tenant_id) → List[Workflow]
# - get_events_after(workflow_id, event_id) → List[WorkflowEvent]
# - save_event(workflow_id, event) → WorkflowEvent
# - get_error(workflow_id) → WorkflowError
# - save_error(workflow_id, error) → WorkflowError

# Thread-safe using async SQLAlchemy
```

### src/api/event_publisher.py (Renamed from broadcaster.py)
```python
# CHANGES:
# 1. Rename broadcaster → event_publisher
# 2. Add method: async def publish(workflow_id, event)
#    - Inserts event into DB (workflow_events table)
#    - Gets next sequence_number from max(sequence_number) + 1
#    - Publishes to in-memory queue for SSE subscribers
#
# 3. Keep asyncio.Queue for live subscribers (in-memory)
# 4. DB provides durability + replay capability
```

### src/workers/workflow_worker.py
```python
# CHANGES:
# 1. Replace store → repository
# 2. Replace broadcaster.publish → event_publisher.publish
# 3. Update workflow state in DB:
#    - After queue_workflow(): status=QUEUED
#    - After start_processing(): status=IN_PROGRESS, publish event
#    - After progress update: save_event(progress)
#    - After complete_workflow(): status=COMPLETED, save artifacts, publish event
#    - After error: status=FAILED, save_error(), publish event
#
# 4. Idempotency check (AT-LEAST-ONCE):
#    - Before executing workflow, check if already executed (status != QUEUED)
#    - If yes, skip execution, ack message, continue
#    - If no, execute and update status atomically
```

---

## 4. Test Plan (test_workflow_sse.py)

### Test Class: TestWorkflowSSEAsync
**Framework:** pytest + httpx.AsyncClient + pytest-asyncio

```python
@pytest.mark.asyncio
class TestWorkflowSSEAsync:
    """Async SSE tests with httpx.AsyncClient and proper event streaming."""
    
    async def test_sse_stream_receives_progress_events(self):
        """Open SSE stream, trigger workflow, assert progress events arrive."""
        # 1. Create workflow
        async with httpx.AsyncClient(app=app, base_url="http://test") as client:
            create_resp = await client.post(...)
            workflow_id = create_resp.json()["id"]
        
        # 2. Open SSE stream (non-blocking, background task)
        async def consume_stream(client, workflow_id):
            events = []
            async with client.stream("GET", f"/api/v1/workflows/{workflow_id}/stream", ...) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        events.append(json.loads(line[6:]))
            return events
        
        # 3. Concurrently: consume stream + trigger worker execution
        task = asyncio.create_task(consume_stream(client, workflow_id))
        
        # Trigger workflow execution via Redis queue
        await enqueue_workflow(workflow_id)
        
        # Wait for stream with timeout
        try:
            events = await asyncio.wait_for(task, timeout=10.0)
        except asyncio.TimeoutError:
            pytest.fail("SSE stream timeout")
        
        # 4. Assert events
        assert len(events) >= 1
        assert events[0]["type"] == "progress" or events[0]["type"] == "started"
        assert events[-1]["type"] in ("completed", "error")
    
    async def test_sse_stream_terminates_on_completion(self):
        """Assert SSE stream terminates when workflow completes."""
        # ... similar setup ...
        # Assert no more events after terminal event
        # Assert connection closes gracefully
    
    async def test_sse_replay_from_event_id(self):
        """Test optional event_id parameter replays past events."""
        # 1. Create + complete workflow (events: start, progress, complete)
        # 2. Reconnect with last_event_id=<first_progress_event_id>
        # 3. Assert replay delivers progress + complete events
        # 4. Assert no start event (already past)
    
    async def test_sse_tenant_isolation_async(self):
        """Async version of tenant isolation test."""
        # ... verify 403 on cross-tenant access ...
    
    async def test_sse_stream_no_hang_on_disconnect(self):
        """Assert stream closes properly when client disconnects."""
        # ... open stream, close immediately, assert no resource leak ...
```

### Test Fixtures
```python
@pytest.fixture
async def async_client():
    """Async HTTP client for SSE tests."""
    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        yield client

@pytest.fixture
async def redis_queue():
    """Redis Streams queue for test workflows."""
    queue = RedisQueue()
    await queue.initialize()
    yield queue
    await queue.cleanup()

@pytest.fixture
async def db_session():
    """Test database session."""
    async with SessionLocal() as session:
        async with session.begin():
            # Create test tables
            await session.run_sync(Base.metadata.create_all)
        yield session
```

---

## 5. Implementation Sequence

**Phase 1: Database Layer (Est. 2-3 hours)**
1. Create SQLAlchemy models (src/db/models.py)
2. Create migration (001_initial_schema.py)
3. Create repository layer (src/persistence/workflow_repository.py)
4. Update main.py for DB initialization

**Phase 2: Event Persistence (Est. 1-2 hours)**
1. Rename broadcaster → event_publisher
2. Add event save logic to event_publisher
3. Update workflow_worker to save events

**Phase 3: Async SSE Tests (Est. 2-3 hours)**
1. Create test_workflow_sse.py with async fixtures
2. Implement 4+ async test cases
3. Verify no hanging tests, enforce timeouts

**Phase 4: Integration & Verification (Est. 1-2 hours)**
1. Update existing integration tests to use repository
2. Run all gates:
   - `pytest tests/integration/test_workflow_api.py -q`
   - `pytest tests/integration/test_workflow_sse.py -q`
   - `make smoke-test`
3. Verify no regressions

**Total Est. Time:** 6-10 hours

---

## 6. Verification Gates

```bash
# T2.6 API tests (existing)
pytest tests/integration/test_workflow_api.py -q
Expected: 13 PASSED

# T2.6 SSE tests (new)
pytest tests/integration/test_workflow_sse.py -q
Expected: 4+ PASSED, no timeouts

# Phase 1 smoke tests
make smoke-test
Expected: 52 PASSED (unchanged)
```

---

## 7. Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| DB migration fails on existing data | Test on clean DB; keep src/api/store.py as fallback initially |
| SSE streaming hangs in async tests | Enforce 10s timeout on all stream operations; use asyncio.wait_for |
| Event ordering issues in DB | Use sequence_number column with unique constraint; order by in queries |
| Idempotency failures | Check status in DB before executing; atomic status update in worker |
| Cross-tenant data leaks | All repository queries filter by tenant_id; add DB constraint |

---

## 8. Acceptance Criteria

- ✅ PostgreSQL persistence fully functional
- ✅ All 4+ async SSE tests pass without hanging
- ✅ Event replay works (last_event_id parameter)
- ✅ Tenant isolation enforced at DB level
- ✅ Worker idempotency verified
- ✅ No Phase 1 regressions (smoke tests pass)
- ✅ No root artifacts; docs only in documents/
- ✅ WorkflowEngine unchanged (read-only)

---

**Ready to Implement?** Confirm scope, then proceed with Phase 1 (Database Layer).
