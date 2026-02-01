# E2E Testing Report: Event Persistence → SSE Replay → UI Visibility

**Date**: 2026-01-18  
**Purpose**: Systematically validate the event delivery path: Postgres persistence → SSE replay → Frontend UI  
**Conclusion**: ✅ Steps A & B PASSED. Postgres persistence and SSE replay both fully functional.

---

## STEP A: Event Persistence Validation ✅ PASSED

**Objective**: Verify that workflow completion events are persisted in Postgres  
**Test Approach**: Create workflow, let it complete, query Postgres for events  
**Expected Outcome**: At least one `status_changed` event with `new_status = 'COMPLETED'` or `'FAILED'`

### Test Execution

```bash
# 1. Start services
make up

# 2. Start API
python -m uvicorn src.main:app --host 127.0.0.1 --port 8000 --reload

# 3. Start worker
python -m src.workers

# 4. Create workflow
curl -X POST http://localhost:8000/api/v1/workflows \
  -H 'X-Tenant-ID: demo-tenant' \
  -H 'Content-Type: application/json' \
  -d '{"design_id": "test-design-abc", "source_id": "test-source-xyz"}'

# Response: {"id": "wf_5d78aa397f09", "status": "SUBMITTED", ...}

# 5. Wait for completion (5-10 seconds)
sleep 12

# 6. Query Postgres (using check_step_a.py)
python check_step_a.py wf_5d78aa397f09
```

### Test Results

```
✅ STEP A - EVENT PERSISTENCE: Found 8 events for wf_5d78aa397f09
======================================================================================
=====                                                                                
ID: 2574 | Type: status_changed       | Status: QUEUED      
ID: 2575 | Type: status_changed       | Status: PROCESSING  
ID: 2576 | Type: step_progressed      | Status: N/A         
ID: 2577 | Type: step_progressed      | Status: N/A         
ID: 2578 | Type: step_progressed      | Status: N/A         
ID: 2579 | Type: step_progressed      | Status: N/A         
ID: 2580 | Type: artifact_created     | Status: N/A         
ID: 2581 | Type: status_changed       | Status: COMPLETED   

✅ Terminal Status Found: COMPLETED
✅ STEP A PASSED: Events are persisted in Postgres
```

### Worker Logs (Confirmation)

```
2026-01-18 02:52:57,741 [INFO] src.workers.workflow_worker: 🔔 [worker-1] Event emitted: type=status_changed, workflow=wf_5d78aa397f09
2026-01-18 02:52:57,749 [INFO] src.workers.workflow_worker: 💾 [worker-1] Event persisted: event_type=status_changed, event_id=2574, workflow=wf_5d78aa397f09
2026-01-18 02:52:57,750 [INFO] src.workers.workflow_worker: 📡 [worker-1] Event broadcast: event_id=2574, workflow=wf_5d78aa397f09
...
2026-01-18 02:52:58,146 [INFO] src.workers.workflow_worker: ✅ [worker-1] Workflow wf_5d78aa397f09 execution completed successfully
2026-01-18 02:52:58,152 [INFO] src.workers.workflow_worker: 💾 [worker-1] Event persisted: event_type=status_changed, event_id=2581, workflow=wf_5d78aa397f09
2026-01-18 02:52:58,163 [INFO] src.workers.workflow_worker: ✅ [worker-1] DB state committed: workflow_id=wf_5d78aa397f09
2026-01-18 02:52:58,164 [INFO] src.infra.queue: ✅ ACK: entry_id=1768697577723-0, result=1
```

### Analysis

- **8 events persisted** for a single workflow execution  
- **Event ordering preserved**: QUEUED → PROCESSING → step_progressed (4×) → artifact_created → COMPLETED  
- **Terminal state confirmed**: Event ID 2581 shows `new_status = 'COMPLETED'`  
- **Database consistency**: All events queried successfully; no data loss
- **Worker handling**: Emits → Persists → Broadcasts sequence verified in logs

**Conclusion**: ✅ Event persistence to Postgres is **fully functional**. The durability path is solid.

---

## STEP B: SSE Replay Validation ✅ PASSED

**Objective**: Verify that persisted events are replayed via SSE stream endpoint  
**Test Approach**: Curl the `/stream` endpoint with `last_event_id=0`, verify all events returned in order  
**Expected Outcome**: Complete SSE frames with all events, including terminal status change

### Test Execution

```bash
# Call the stream endpoint (note: -N disables buffering for SSE, head -50 limits output)
curl -s -N -H 'X-Tenant-ID: demo-tenant' \
  'http://localhost:8000/api/v1/workflows/wf_5d78aa397f09/stream?last_event_id=0' | head -50
```

### Test Results

```
id: 2574
data: {"workflow_id": "wf_5d78aa397f09", "tenant_id": "demo-tenant", "request_id": "ae018bbd-...", "event_type": "status_changed", "old_status": "SUBMITTED", "new_status": "QUEUED", "step": "queued", "progress_pct": 5, "error": null, "timestamp": "2026-01-18T00:52:57.741189"}

id: 2575
data: {"workflow_id": "wf_5d78aa397f09", "tenant_id": "demo-tenant", "request_id": "ae018bbd-...", "event_type": "status_changed", "old_status": "QUEUED", "new_status": "PROCESSING", "step": "initializing", "progress_pct": 10, "error": null, "timestamp": "2026-01-18T00:52:57.741228"}

id: 2576
data: {"workflow_id": "wf_5d78aa397f09", "tenant_id": "demo-tenant", "request_id": "ae018bbd-...", "event_type": "step_progressed", "old_status": null, "new_status": null, "step": "analyzing", "progress_pct": 25, "error": null, "timestamp": "2026-01-18T00:52:57.741256"}

id: 2577
data: {"workflow_id": "wf_5d78aa397f09", "tenant_id": "demo-tenant", "request_id": "ae018bbd-...", "event_type": "step_progressed", "old_status": null, "new_status": null, "step": "generating", "progress_pct": 50, "error": null, "timestamp": "2026-01-18T00:52:57.842384"}

id: 2578
data: {"workflow_id": "wf_5d78aa397f09", "tenant_id": "demo-tenant", "request_id": "ae018bbd-...", "event_type": "step_progressed", "old_status": null, "new_status": null, "step": "creating", "progress_pct": 75, "error": null, "timestamp": "2026-01-18T00:52:57.943620"}

id: 2579
data: {"workflow_id": "wf_5d78aa397f09", "tenant_id": "demo-tenant", "request_id": "ae018bbd-...", "event_type": "step_progressed", "old_status": null, "new_status": null, "step": "finalizing", "progress_pct": 95, "error": null, "timestamp": "2026-01-18T00:52:58.044853"}

id: 2580
data: {"workflow_id": "wf_5d78aa397f09", "tenant_id": "demo-tenant", "request_id": "ae018bbd-...", "event_type": "artifact_created", "old_status": null, "new_status": null, "step": "finalizing", "progress_pct": 95, "error": null, "timestamp": "2026-01-18T00:52:58.146082"}

id: 2581
data: {"workflow_id": "wf_5d78aa397f09", "tenant_id": "demo-tenant", "request_id": "ae018bbd-...", "event_type": "status_changed", "old_status": "PROCESSING", "new_status": "COMPLETED", "step": "completed", "progress_pct": 100, "error": null, "timestamp": "2026-01-18T00:52:58.146255"}
```

### Analysis

- **8 SSE frames delivered** in correct order (id: 2574 → 2581)
- **Complete JSON payload** per frame: workflow_id, event_type, status transitions, progress_pct, timestamps
- **Terminal status visible**: Last frame shows `new_status: "COMPLETED"` with `progress_pct: 100`
- **Backward-compatible format**: Each frame is valid SSE (id + data on separate lines)

**Conclusion**: ✅ SSE replay from Postgres is **fully functional**. The durable delivery path works end-to-end.

---

## STEP C: Live Streaming & UI Visibility (PENDING)

**Objective**: Verify that frontend receives updates in real-time or via polling  
**Test Approach**: Create new workflow, observe UI state changes as events stream  
**Expected Outcome**: UI displays PROCESSING → COMPLETED transition with 100% progress

### Planned Test

```bash
# 1. Open browser to localhost:5173 (Vite dev server)
# 2. Create new workflow via UI
# 3. Observe state transitions:
#    - SUBMITTED → QUEUED (within 1 sec)
#    - QUEUED → PROCESSING (within 2 sec)
#    - PROCESSING → COMPLETED (within 8 sec)
# 4. Verify progress bar reaches 100%
```

### Implementation Notes

**Current Architecture**:
- **Event Persistence**: Postgres `workflow_events` table with auto-incrementing IDs
- **SSE Replay**: `/api/v1/workflows/{id}/stream?last_event_id=X` returns all events after ID X
- **Live Broadcasting**: In-memory `broadcaster` Dict[workflow_id → List[asyncio.Queue]]
- **Frontend Consumption**: `useEventStream()` hook reads SSE stream via event listener

**Known Issues to Debug**:
1. E2E tests report 4 passed / 4 failed despite worker logs showing COMPLETED
2. May indicate: (a) UI not polling stream endpoint correctly, (b) SSE frame parsing issue, or (c) test timing (workflow completes before test subscribes)

**Validation Checklist**:
- [ ] Frontend subscribes to stream immediately after workflow creation
- [ ] SSE event listener captures all frames
- [ ] State updates propagate to React state via `setWorkflow()`
- [ ] UI rerenders with new status/progress
- [ ] Terminal states (COMPLETED/FAILED) persist in UI

---

## Summary Table

| Step | Test | Status | Evidence |
|------|------|--------|----------|
| A | Event Persistence | ✅ PASSED | 8 events in Postgres, including COMPLETED |
| B | SSE Replay | ✅ PASSED | All 8 events replayed via /stream endpoint |
| C | UI Visibility | ⏳ PENDING | Requires full E2E test with frontend |

---

## Architectural Decisions

### Why Postgres + SSE (vs Redis Pub/Sub)?

1. **Durability**: Events survive server restarts; persistent audit log
2. **Replay**: New subscribers can fetch full history via `last_event_id`
3. **Simplicity**: No cross-process coordination; single source of truth
4. **Scaleability**: DB queries scale with indexed lookups; Pub/Sub requires all consumers online

### Broadcaster Role

In-memory broadcaster is **optional** for E2E tests:
- **Single-process context** (worker + API in same container): Works perfectly
- **Multi-container production**: Would need Redis Pub/Sub or similar for cross-process events
- **Current implementation**: In-memory Dict[workflow_id → List[asyncio.Queue]] sufficient for dev/test

---

## Next Steps

1. **If Step C passes**: Architecture is complete; focus on production deployment
2. **If Step C fails**: Debug UI subscription logic:
   - Verify `useEventStream()` hook calls stream endpoint
   - Check browser console for SSE event errors
   - Inspect Network tab for /stream response frames
   - Measure time between worker completion log and UI state update

3. **Potential fixes**:
   - Add polling fallback if SSE not supported
   - Increase subscription timeout in `useEventStream()`
   - Add explicit error handling for failed requests
   - Log all SSE frames received in browser dev tools

# Wait a moment for subscription
sleep 1

# Query status
echo "Initial status:"
curl -s -H "X-Tenant-ID: $TENANT_ID" \
  http://localhost:8000/api/v1/workflows/$WORKFLOW_ID | jq '.status'

# Wait for worker to process
sleep 10

# Check SSE output
echo "SSE frames received:"
cat /tmp/sse_live.log
```

**Expected Result:**
- SSE log contains frame with terminal status emitted after workflow creation
- Status field transitions from PROCESSING to COMPLETED/FAILED

**Actual Output:**
```
[To be filled after running live test]
```

---

## Summary

| Step | Status | Notes |
|------|--------|-------|
| A. Event Persistence | ⏳ | Query Postgres for terminal event |
| B. SSE Replay | ⏳ | Curl stream endpoint with last_event_id=0 |
| C. Live Streaming | ⏳ | Only if B passes |

---

## Findings & Decisions

[To be updated after completing A, B, C]

**Current Hypothesis:**
- Event persistence likely works (worker logs show completion)
- Replay may have timing/ordering issues
- Live updates require same-process broadcasting (E2E context)

**Next Actions (if issues found):**
1. Check event payload format matches SSE expectations
2. Verify Last-Event-ID cursor logic in stream endpoint
3. Add explicit logging in event persistence callback
4. Consider periodic polling as fallback for multi-process deployments
