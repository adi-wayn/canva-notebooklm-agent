"""In-memory SSE event broadcaster (minimal, single-process)."""
import asyncio
from typing import Dict, List


class EventBroadcaster:
    """In-memory pub/sub for streaming workflow events via SSE (single-process only)."""

    def __init__(self):
        self.subscribers: Dict[str, List[asyncio.Queue]] = {}

    def subscribe(self, workflow_id: str) -> asyncio.Queue:
        """Register an SSE client for a workflow (returns queue for events)."""
        queue: asyncio.Queue = asyncio.Queue()
        if workflow_id not in self.subscribers:
            self.subscribers[workflow_id] = []
        self.subscribers[workflow_id].append(queue)
        return queue

    async def publish(self, workflow_id: str, event) -> None:
        """Broadcast an event to all subscribers for a workflow."""
        if workflow_id not in self.subscribers:
            return
        
        dead_queues = []
        for queue in self.subscribers[workflow_id]:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                # Drop slow subscribers
                dead_queues.append(queue)
        
        # Clean up disconnected clients
        for queue in dead_queues:
            self.subscribers[workflow_id].remove(queue)

    def unsubscribe(self, workflow_id: str, queue: asyncio.Queue) -> None:
        """Unregister an SSE client."""
        if workflow_id in self.subscribers and queue in self.subscribers[workflow_id]:
            self.subscribers[workflow_id].remove(queue)
            if not self.subscribers[workflow_id]:
                del self.subscribers[workflow_id]

    def get_subscriber_count(self, workflow_id: str) -> int:
        """Get number of active subscribers for a workflow."""
        return len(self.subscribers.get(workflow_id, []))


# Global singleton broadcaster
broadcaster = EventBroadcaster()
