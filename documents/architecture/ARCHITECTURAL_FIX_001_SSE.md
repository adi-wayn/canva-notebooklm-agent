# Architectural Fix 001: SSE Reliability & Strict Ordering

**Date:** 2026-02-01
**Author:** Antigravity Agent
**Status:** APPLIED
**Components:** Backend (API), Frontend (Hooks)

## Problem Definition

The system was exhibiting "stuck" states during workflow execution, particularly where the UI would remain at "PROCESSING" despite the worker completing successfully. 

### RCA (Root Cause Analysis)

1.  **Frontend Connection Fragility:** The `useEventStream` hook lacked auto-reconnection logic. If the SSE stream was interrupted (network blip, timeout) before the `COMPLETED` event arrived, the UI would never recover. It would not attempt to reconnect using `Last-Event-ID`.
2.  **Backend Race Condition (Duplicate Events):** The SSE endpoint logic had a race condition where an event could be emitted twice: once from the historical DB replay and once from the live `broadcaster` queue. This occurred because the subscription happened *before* the DB replay, buffering events that were arguably "future" relative to the replay start but "past" relative to the replay end.

## The Solution

### 1. Backend: Strict Monotonic Ordering

Modified `src/api/routes/workflows.py` to enforce strict ordering.

*   **Logic:**
    *   Track `last_replayed_id` during the DB replay phase.
    *   In the live queue loop, **discard** any event where `event.id <= last_replayed_id`.
    *   Update `last_replayed_id` as new events are broadcast.

*   **Benefit:** 
    *   Guarantees exactly-once delivery (on a per-connection basis).
    *   Prevents confusing "time travel" artifacts in the UI.

### 2. Frontend: Auto-Reconnection Strategy

Refactored `ui/src/hooks/useEventStream.js` to implement a robust connection loop.

*   **Logic:**
    *   Introduced `intentionalCloseRef` to distinguish user navigation (intentional) from network errors (unintentional).
    *   Added a `retryTimeout` mechanism.
    *   In the event of an unintentional stream closure, the hook waits 3 seconds and then **reconnects** using the latest `lastId` captured from the stream.
    *   Preserves `workflowId` and `tenantId` in refs to enable seamless re-establishment.

*   **Benefit:**
    *   UI recovers automatically from network interruptions.
    *   If the user refreshes, `Last-Event-ID` (already handled by usage in `WorkflowPage`) ensures state is restored.
    *   If the stream drops mid-workflow, it automatically resumes without user intervention.

## Verification Checklist

To verify this fix:
1.  **Start Workflow:** Create a long-running workflow.
2.  **Kill Network:** Disconnect network (or kill API server briefly).
3.  **Observe:** UI should show an error or stall briefly.
4.  **Restore:** Restore network.
5.  **Result:** UI should automatically reconnect, fetch missing events (via DB replay), and update to the latest state.

## Compliance

This fix aligns with Antigravity constraints:
*   **Persistence:** Relies on PostgreSQL `workflow_events` as the ultimate source of truth for replay.
*   **Replayability:** Enforces usage of `Last-Event-ID`.
*   **No Magic:** Uses standard HTTP/SSE and simple timeouts; no complex client-side libraries.
