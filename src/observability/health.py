"""Health check utilities for dependency monitoring.

Provides:
- Redis connectivity checks
- PostgreSQL connectivity checks
- Startup readiness probes
- Liveness probes
"""

import asyncio
import logging
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

import redis.asyncio as redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    """Health check status values."""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"


class HealthCheck:
    """Individual health check result."""

    def __init__(
        self,
        name: str,
        status: HealthStatus,
        response_time_ms: float,
        message: Optional[str] = None,
        timestamp: Optional[datetime] = None,
    ):
        """Initialize health check result.

        Args:
            name: Check name (e.g., 'redis', 'postgres')
            status: Health status
            response_time_ms: Response time in milliseconds
            message: Optional status message
            timestamp: Check timestamp
        """
        self.name = name
        self.status = status
        self.response_time_ms = response_time_ms
        self.message = message
        self.timestamp = timestamp or datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "status": self.status.value,
            "response_time_ms": self.response_time_ms,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
        }


class HealthChecker:
    """Health check coordinator for all dependencies."""

    def __init__(
        self,
        redis_url: Optional[str] = None,
        database_url: Optional[str] = None,
    ):
        """Initialize health checker.

        Args:
            redis_url: Redis connection URL
            database_url: Database connection URL (async)
        """
        self.redis_url = redis_url
        self.database_url = database_url
        self._redis: Optional[redis.Redis] = None
        self._db_engine = None

    async def check_redis(self) -> HealthCheck:
        """Check Redis connectivity.

        Returns:
            HealthCheck result
        """
        if not self.redis_url:
            return HealthCheck(
                name="redis",
                status=HealthStatus.DEGRADED,
                response_time_ms=0,
                message="Redis URL not configured",
            )

        start_time = asyncio.get_event_loop().time()
        try:
            if self._redis is None:
                self._redis = await redis.from_url(
                    self.redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_connect_timeout=5,
                )

            await self._redis.ping()
            response_time = (asyncio.get_event_loop().time() - start_time) * 1000

            return HealthCheck(
                name="redis",
                status=HealthStatus.HEALTHY,
                response_time_ms=response_time,
                message="Redis is reachable",
            )
        except Exception as e:
            response_time = (asyncio.get_event_loop().time() - start_time) * 1000
            logger.error(f"Redis health check failed: {e}")
            return HealthCheck(
                name="redis",
                status=HealthStatus.UNHEALTHY,
                response_time_ms=response_time,
                message=f"Redis check failed: {str(e)[:100]}",
            )

    async def check_database(self) -> HealthCheck:
        """Check database connectivity.

        Returns:
            HealthCheck result
        """
        if not self.database_url:
            return HealthCheck(
                name="postgres",
                status=HealthStatus.DEGRADED,
                response_time_ms=0,
                message="Database URL not configured",
            )

        start_time = asyncio.get_event_loop().time()
        try:
            if self._db_engine is None:
                self._db_engine = create_async_engine(
                    self.database_url,
                    echo=False,
                    pool_pre_ping=True,
                    pool_size=1,
                    max_overflow=0,
                )

            async with self._db_engine.begin() as conn:
                await conn.execute(text("SELECT 1"))

            response_time = (asyncio.get_event_loop().time() - start_time) * 1000

            return HealthCheck(
                name="postgres",
                status=HealthStatus.HEALTHY,
                response_time_ms=response_time,
                message="Database is reachable",
            )
        except Exception as e:
            response_time = (asyncio.get_event_loop().time() - start_time) * 1000
            logger.error(f"Database health check failed: {e}")
            return HealthCheck(
                name="postgres",
                status=HealthStatus.UNHEALTHY,
                response_time_ms=response_time,
                message=f"Database check failed: {str(e)[:100]}",
            )

    async def health(self) -> Dict[str, Any]:
        """Run full health check (liveness probe).

        Returns:
            Dictionary with overall status and individual checks
        """
        redis_check = await self.check_redis()
        db_check = await self.check_database()

        checks = [redis_check, db_check]

        # Overall status is healthy if all checks are healthy
        overall_status = HealthStatus.HEALTHY
        if any(c.status == HealthStatus.UNHEALTHY for c in checks):
            overall_status = HealthStatus.UNHEALTHY
        elif any(c.status == HealthStatus.DEGRADED for c in checks):
            overall_status = HealthStatus.DEGRADED

        return {
            "status": overall_status.value,
            "timestamp": datetime.utcnow().isoformat(),
            "checks": [c.to_dict() for c in checks],
        }

    async def ready(self) -> Dict[str, Any]:
        """Run readiness check (startup probe).

        Returns:
            Dictionary with readiness status
        """
        health_result = await self.health()

        # Ready if all critical dependencies are healthy
        is_ready = health_result["status"] == HealthStatus.HEALTHY.value

        return {
            "ready": is_ready,
            "timestamp": datetime.utcnow().isoformat(),
            "health": health_result,
        }

    async def close(self) -> None:
        """Close all connections."""
        if self._redis:
            await self._redis.close()
            self._redis = None
        if self._db_engine:
            await self._db_engine.dispose()
            self._db_engine = None
