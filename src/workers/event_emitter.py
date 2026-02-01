"""
Agent Event Emitter

Single source of truth for agent event emission.
All agent_step events must go through this helper:
1. Persist to workflow_events (DB is source of truth)
2. Broadcast via SSE (best-effort)

Hard constraints:
- No alternative emitters
- DB persistence FIRST, then SSE broadcast
- Includes seq (monotonic int) for deterministic ordering
"""

import logging
from typing import Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

# Global sequence counter per workflow (in-memory, reset per worker process)
_seq_counters: Dict[str, int] = {}


def _get_next_seq(workflow_id: str) -> int:
    """Get next sequence number for workflow (monotonic)."""
    if workflow_id not in _seq_counters:
        _seq_counters[workflow_id] = 0
    _seq_counters[workflow_id] += 1
    return _seq_counters[workflow_id]


async def emit_agent_event(
    workflow_id: str,
    tenant_id: str,
    event_name: str,
    message: str,
    progress_pct: int,
    metadata: Dict[str, Any],
    session,  # Database session
    broadcaster  # SSE broadcaster
) -> None:
    """
    Persist agent event to DB and broadcast via SSE.
    
    This is the ONLY way to emit agent events. No alternative code paths.
    
    Args:
        workflow_id: Workflow identifier
        tenant_id: Tenant identifier
        event_name: Semantic event name (e.g., 'agent_thinking')
        message: User-facing message
        progress_pct: Progress percentage (0-100)
        metadata: Event-specific data
        session: Database session for persistence
        broadcaster: SSE broadcaster for real-time updates
        
    Event Structure:
        {
          "event_type": "agent_step",
          "payload": {
            "event_name": "...",
            "message": "...",
            "progress_pct": 0-100,
            "metadata": {...},
            "event_version": 1,
            "seq": monotonic_int,
            "timestamp": "ISO8601"
          }
        }
    """
    from src.storage.repository import WorkflowEventRepository
    
    # Get next sequence number (for deterministic ordering)
    seq = _get_next_seq(workflow_id)
    
    # Build payload
    payload = {
        "event_name": event_name,
        "message": message,
        "progress_pct": progress_pct,
        "metadata": metadata,
        "event_version": 1,
        "seq": seq,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
    
    try:
        # 1. Persist to DB (source of truth) - MUST happen first
        ev_repo = WorkflowEventRepository(session, tenant_id=tenant_id)
        persisted = await ev_repo.append_event(
            workflow_id=workflow_id,
            event_type="agent_step",
            payload=payload
        )
        
        logger.info(
            f"[Agent Event] {workflow_id}: {event_name} (seq={seq}, progress={progress_pct}%)"
        )
        
        # 2. Broadcast via SSE (best-effort) - happens after DB persistence
        try:
            await broadcaster.publish(
                channel=f"workflow:{workflow_id}",
                message={
                    "id": str(persisted.id),
                    "event_type": "agent_step",
                    "payload": payload
                }
            )
        except Exception as broadcast_error:
            # SSE broadcast failure is non-fatal (DB is source of truth)
            logger.warning(
                f"[Agent Event] Failed to broadcast {event_name} for {workflow_id}: {broadcast_error}"
            )
    
    except Exception as e:
        # DB persistence failure is fatal - re-raise
        logger.error(
            f"[Agent Event] Failed to persist {event_name} for {workflow_id}: {e}"
        )
        raise


def reset_seq_counter(workflow_id: str) -> None:
    """
    Reset sequence counter for workflow.
    
    Called when workflow starts to ensure seq starts at 1.
    """
    _seq_counters[workflow_id] = 0
    logger.debug(f"[Agent Event] Reset seq counter for {workflow_id}")
