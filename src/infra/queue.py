"""Redis Streams abstraction for workflow task queuing."""
import os
import logging
import redis.asyncio
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class WorkflowQueue:
    """Redis Streams-based task queue for workflows (at-least-once delivery)."""

    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379")
        self.stream_name = "workflow-queue"
        self.group_name = "workflow-workers"
        self.redis = None
        logger.info(
            f"WorkflowQueue initialized with redis_url={self.redis_url}, stream={self.stream_name}, group={self.group_name}"
        )

    async def initialize(self) -> None:
        """Initialize Redis connection and consumer group."""
        logger.info(f"Initializing Redis connection to {self.redis_url}")
        self.redis = await redis.asyncio.from_url(self.redis_url, decode_responses=True)

        # Create consumer group if it doesn't exist
        try:
            await self.redis.xgroup_create(self.stream_name, self.group_name, id="$", mkstream=True)
            logger.info(
                f"Consumer group '{self.group_name}' created for stream '{self.stream_name}'"
            )
        except redis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                logger.error(f"Failed to create consumer group: {e}")
                raise
            logger.debug(
                f"Consumer group '{self.group_name}' already exists (BUSYGROUP)"
            )

        # Verify consumer group exists
        try:
            groups = await self.redis.xinfo_groups(self.stream_name)
            logger.info(
                f"Active consumer groups on '{self.stream_name}': {[g['name'] for g in groups]}"
            )
        except Exception as e:
            logger.warning(f"Could not verify consumer groups: {e}")

    async def close(self) -> None:
        """Close Redis connection."""
        if self.redis:
            logger.info("Closing Redis connection")
            await self.redis.close()

    async def enqueue(self, workflow_id: str, tenant_id: str, action: str = "process") -> str:
        """Enqueue a workflow task to Redis Stream."""
        if not self.redis:
            await self.initialize()

        entry_id = await self.redis.xadd(
            self.stream_name,
            {"workflow_id": workflow_id, "tenant_id": tenant_id, "action": action},
        )
        logger.info(
            f"✅ ENQUEUED: workflow_id={workflow_id}, tenant_id={tenant_id}, action={action}, entry_id={entry_id}"
        )
        return entry_id

    async def dequeue(self, worker_id: str, timeout_ms: int = 1000) -> Optional[Tuple[str, dict]]:
        """
        Dequeue a workflow task (consumer claims entry).

        Returns: (entry_id, {"workflow_id": ..., "tenant_id": ...}) or None if timeout
        """
        if not self.redis:
            await self.initialize()

        logger.debug(
            f"Polling Redis stream (worker_id={worker_id}, timeout_ms={timeout_ms})"
        )

        entries = await self.redis.xreadgroup(
            self.group_name,
            worker_id,
            {self.stream_name: ">"},
            count=1,
            block=timeout_ms,
        )

        if not entries or not entries[0][1]:
            logger.debug(f"No messages available (timeout after {timeout_ms}ms)")
            return None

        # entries format: [(stream_name, [(entry_id, {data}), ...])]
        entry_id, data = entries[0][1][0]
        logger.info(
            f"✅ DEQUEUED: entry_id={entry_id}, workflow_id={data.get('workflow_id')}, tenant_id={data.get('tenant_id')}"
        )
        return entry_id, data

    async def ack(self, entry_id: str) -> int:
        """Acknowledge a task as processed."""
        if not self.redis:
            await self.initialize()

        result = await self.redis.xack(self.stream_name, self.group_name, entry_id)
        logger.info(f"✅ ACK: entry_id={entry_id}, result={result}")
        return result

    async def pending_count(self) -> int:
        """Get count of pending tasks in the queue."""
        if not self.redis:
            await self.initialize()

        info = await self.redis.xinfo_groups(self.stream_name)
        if info:
            return info[0].get("pending", 0)
        return 0
