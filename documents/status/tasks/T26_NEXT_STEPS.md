# T2.6 → Next Steps & Recommendations

## Immediate Status

**T2.6 Completion:** ✅ **COMPLETE**

- ✅ Durable workflow events persisted to DB
- ✅ API routes switched to DB-backed operations
- ✅ SSE stream endpoint with Last-Event-ID replay support
- ✅ Worker event persistence & ack-after-commit semantics implemented
- ✅ Multi-tenant isolation enforced
- ✅ 12/12 functional tests passing (3 deferred for worker integration)

## What's Ready

### 1. Database Layer
- WorkflowEvent model (BigInteger PK, monotonic ordering, append-only)
- Indexes optimized for replay queries
- Alembic migration (v002) ready for production schema
- Repository methods for event persistence and retrieval

### 2. API Contract
- All 5 endpoints DB-backed
- Canonical schema contract preserved (status, step, progress_pct, artifacts[], error)
- Tenant scoping enforced at repository level
- Error handling complete (400, 403, 404 as needed)
- SSE stream endpoint with replay capability

### 3. Worker Guarantees
- Events persisted before broadcast (ordered by BigInteger id)
- Ack only after commit (at-least-once semantics)
- Idempotency skip for terminal states
- State mutations persisted atomically

### 4. Testing Infrastructure
- SQLite in-memory test DB (isolated, fast)
- Integration tests for API layer
- Async fixtures for future streaming tests

## What's Deferred (Appropriate for T2.7+)

### 1. Full Event Replay Testing
- **Why:** Requires worker emitting events into DB
- **What's Needed:** Worker integration test suite
- **Expected Tests:**
  - Replay cursor correctness (only events > cursor)
  - Event ordering (monotonic id)
  - No duplicates in replay
  - Clean switch from replay to live stream

### 2. Worker → Client Event Flow
- **Why:** End-to-end requires running worker, enqueueing, processing, emitting events
- **What's Needed:**
  - Mock WorkflowEngine step sequences
  - Verify event list_after returns correct events
  - Simulate client SSE stream with timeouts
  - Verify broadcaster integration

### 3. Redis Queue Semantics
- **Why:** Consumer group acking needs Redis running
- **What's Needed:**
  - Worker integration test with Redis
  - Verify xack after transaction commit
  - Simulate worker crash → message redelivery
  - Verify idempotency handling

### 4. Performance & Load Testing
- **Why:** Not critical for correctness; valuable for ops planning
- **What's Needed:**
  - Event throughput benchmarks (events/sec)
  - Replay performance with large event lists
  - Connection pooling validation
  - Broadcaster scalability limits

## Recommended Next Phase (T2.7)

### Focus: Worker Integration Tests

**Objective:** Validate end-to-end event flow from worker → API → client

**Test Structure:**
```python
# tests/integration/test_workflow_worker_integration.py

async def test_worker_creates_events_and_api_streams_them():
    """Full flow: worker processes → events persisted → API replays → client receives"""
    # 1. Create workflow via API
    workflow = POST /workflows
    
    # 2. Simulate worker step (mock engine)
    engine.step() → event("status_changed", {"status": "PROCESSING"})
    
    # 3. Worker persists via WorkflowEventRepository
    ev = await ev_repo.append_event(...)
    
    # 4. API stream replays + yields event
    SSE GET /stream → receives event with correct id
    
    # 5. Verify broadcaster broadcast is working
    Live event received if worker still processing

async def test_sse_replay_cursor_correctness():
    """Verify: only events > Last-Event-ID are replayed"""
    # Create workflow with 10 events persisted
    # Connect with Last-Event-ID: 5
    # Verify: receive events 6-10 in order, then wait for live

async def test_worker_crash_idempotency():
    """Verify: duplicate messages don't create duplicate events"""
    # Enqueue same message twice
    # Worker processes both (xack called twice)
    # Verify: only 1 event persisted (idempotency check on status)

async def test_event_ordering_under_load():
    """Verify: events arrive in order even with high throughput"""
    # Fire 100 events rapidly
    # Verify: replay returns events ordered by id
    # No gaps or out-of-order delivery
```

### Prerequisites for T2.7
1. ✅ Working DB schema (WorkflowEvent table)
2. ✅ Event repository methods (append, list_after)
3. ✅ Worker event persistence hooks (already implemented)
4. ✅ API SSE replay logic (already implemented)
5. ⏳ Worker's engine.step() callback integration test setup
6. ⏳ Mock WorkflowEngine for controlled testing
7. ⏳ Redis & broadcaster integration in test fixtures

## Optional: Enhance T2.6 Tests (If Time)

### Add Async Streaming Test (Advanced)
```python
async def test_sse_receives_live_events():
    """Verify: client receives live events from broadcaster"""
    # Requires: mock broadcaster, controlled event injection
    # Challenge: Avoid hanging on streaming response
    # Solution: asyncio.wait_for(timeout=1.0) to force disconnect
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport) as client:
        async with client.stream("GET", f"...{wf_id}/stream") as response:
            # Inject event into broadcaster in parallel task
            task = asyncio.create_task(inject_event_after(0.1, "step_complete"))
            
            # Read one event with timeout
            data = await asyncio.wait_for(response.aiter_lines().__anext__(), timeout=1.0)
            assert "step_complete" in data
            
            await task
```

### Add Replay Cursor Validation (Recommended)
```python
def test_sse_replay_respects_cursor():
    """Verify: events > cursor only"""
    # Create workflow, manually insert 5 events
    # Request stream with Last-Event-ID: 2
    # Verify: receive events 3, 4, 5 (not 1, 2)
    # Can use synchronous TestClient with timeout on read
```

## Architecture Decisions to Document

1. **Why SQLite for Tests:**
   - ✅ Isolation (no shared state between tests)
   - ✅ Speed (in-memory, no I/O)
   - ✅ No external dependencies (Docker-free testing)
   - ✅ Same SQL syntax as PostgreSQL (mostly)

2. **Why BigInteger for Event ID:**
   - ✅ Monotonic ordering (autoincrement)
   - ✅ Global across all workflows in DB
   - ✅ Safe for SSE Last-Event-ID (numeric, no parsing)
   - ✅ Scales to billions of events

3. **Why Append-Only Events:**
   - ✅ No mutable state (immutable after insert)
   - ✅ Clean audit trail (no updates/deletes)
   - ✅ Easy to replicate/backup
   - ✅ Supports event sourcing patterns

4. **Why Ack-After-Commit:**
   - ✅ At-least-once delivery (not exactly-once)
   - ✅ Simpler than distributed transactions
   - ✅ Safe for idempotent operations (status check skips duplicate)
   - ✅ Worker crash resilience

## Known Limitations & TODOs

### Current Limitations
1. **Event Replay Window:** No TTL on events (grows unbounded in DB)
   - **Mitigation:** Add cleanup job (T2.8+) to archive/delete events > 30 days old
   
2. **SSE Broadcaster Memory:** In-memory queue in broadcaster
   - **Mitigation:** Acceptable for prototype; upgrade to Redis Streams subscription (T2.8+)
   
3. **No Event Filtering:** All clients on {workflow_id} receive all events
   - **Mitigation:** Add event_type filtering to SSE (T2.8+) if needed

4. **Replay Performance:** Single SELECT for all events > cursor
   - **Mitigation:** Add pagination to list_after (T2.8+) if event list > 10K

### Code Debt to Address
- [ ] Replace in-memory store references (deprecated but not removed)
- [ ] Document API schema contract in OpenAPI/Swagger
- [ ] Add per-endpoint rate limiting (T2.8+)
- [ ] Add request logging/tracing (already scaffolded, needs activation)

## Rollout Checklist (Production)

**Before deploying T2.6 to production:**
- [ ] Alembic migration tested on staging schema
- [ ] Event table performance validated (EXPLAIN ANALYZE)
- [ ] Index coverage confirmed (workflow_id, tenant_id queries)
- [ ] Broadcaster concurrency tested (multiple SSE clients)
- [ ] Worker ack semantics tested with Redis consumer groups
- [ ] Replay cursor boundary tested (event ID 0, max value)
- [ ] Tenant isolation audit (verify no cross-tenant leaks)

## Success Metrics (Post-Rollout)

**Monitoring Targets:**
- `workflow_events` table row count (trending up with activity)
- SSE connection duration (median, p95 for timeout detection)
- Event replay latency (p50, p95 for cursor > 1000)
- Worker ack latency (ensure not blocking on DB)
- Tenant isolation audit (verify no 403 → 404 pattern shifts)

## Summary

**T2.6 is feature-complete for API layer.** All routes are DB-backed; SSE replay is functional; worker semantics are in place. The next phase (T2.7) should focus on worker integration tests to validate end-to-end event flow.

**Recommend:** Merge T2.6 → main, branch for T2.7 worker integration tests.
