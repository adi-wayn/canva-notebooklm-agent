"""FastAPI health check routes.

Provides:
- GET /health - Liveness probe (is the app running?)
- GET /ready - Readiness probe (can it handle traffic?)
"""

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status

from src.config import settings
from src.observability.health import HealthChecker

router = APIRouter(tags=["health"])

# Shared health checker instance
_health_checker: HealthChecker = HealthChecker(
    redis_url=settings.redis.url,
    database_url=settings.database.url,
)


async def get_health_checker() -> HealthChecker:
    """Dependency injection for health checker."""
    return _health_checker


@router.get(
    "/health",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Health Check (Liveness Probe)",
    description="Returns the health status of all dependencies (Redis, PostgreSQL). Returns 200 if any are healthy.",
)
async def health(checker: HealthChecker = Depends(get_health_checker)) -> Dict[str, Any]:
    """Liveness probe endpoint.

    The app is considered "alive" if it's running. This checks all dependencies
    but returns 200 even if some are unhealthy (as long as the app is running).

    Returns:
        {
            "status": "healthy|unhealthy|degraded",
            "timestamp": "ISO8601 timestamp",
            "checks": [
                {"name": "redis", "status": "...", "response_time_ms": 1.5, ...},
                {"name": "postgres", "status": "...", "response_time_ms": 2.3, ...}
            ]
        }
    """
    try:
        result = await checker.health()
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Health check failed: {str(e)}",
        )


@router.get(
    "/ready",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Readiness Probe",
    description="Returns 200 if the app is ready to handle traffic. Returns 503 if dependencies are unavailable.",
)
async def ready(checker: HealthChecker = Depends(get_health_checker)) -> Dict[str, Any]:
    """Readiness probe endpoint.

    The app is considered "ready" if all critical dependencies are healthy.
    Load balancers use this to route traffic only to ready instances.

    Returns:
        {
            "ready": true|false,
            "timestamp": "ISO8601 timestamp",
            "health": {...}  # Full health check result
        }

    Raises:
        HTTPException: 503 Service Unavailable if not ready
    """
    try:
        result = await checker.ready()

        if not result["ready"]:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service not ready: dependencies unhealthy",
            )

        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Readiness check failed: {str(e)}",
        )
