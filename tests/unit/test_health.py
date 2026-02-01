"""Unit tests for health check functionality.

Tests health status checks for Redis and PostgreSQL with mocked dependencies.
All tests are deterministic and do not require actual services.
"""

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from src.observability.health import HealthCheck, HealthChecker, HealthStatus


@pytest.fixture
def health_checker():
    """Create a HealthChecker instance for testing."""
    return HealthChecker(
        redis_url="redis://localhost:6379/0",
        database_url="postgresql+asyncpg://user:pass@localhost:5432/test",
    )


class TestHealthChecker:
    """Test suite for HealthChecker class."""

    @pytest.mark.asyncio
    async def test_redis_healthy(self, health_checker):
        """Test successful Redis health check."""
        with patch.object(
            health_checker,
            "check_redis",
            new_callable=AsyncMock,
        ) as mock_check:
            mock_check.return_value = HealthCheck(
                name="redis",
                status=HealthStatus.HEALTHY,
                response_time_ms=1.5,
                message="OK",
            )

            result = await health_checker.check_redis()

            assert result.status == HealthStatus.HEALTHY
            assert result.name == "redis"
            assert result.response_time_ms > 0

    @pytest.mark.asyncio
    async def test_redis_unhealthy(self, health_checker):
        """Test Redis health check when connection fails."""
        with patch.object(
            health_checker,
            "check_redis",
            new_callable=AsyncMock,
        ) as mock_check:
            mock_check.return_value = HealthCheck(
                name="redis",
                status=HealthStatus.UNHEALTHY,
                response_time_ms=0,
                message="Connection refused",
            )

            result = await health_checker.check_redis()

            assert result.status == HealthStatus.UNHEALTHY
            assert result.name == "redis"

    @pytest.mark.asyncio
    async def test_postgres_healthy(self, health_checker):
        """Test successful PostgreSQL health check."""
        with patch.object(
            health_checker,
            "check_database",
            new_callable=AsyncMock,
        ) as mock_check:
            mock_check.return_value = HealthCheck(
                name="postgres",
                status=HealthStatus.HEALTHY,
                response_time_ms=2.3,
                message="OK",
            )

            result = await health_checker.check_database()

            assert result.status == HealthStatus.HEALTHY
            assert result.name == "postgres"
            assert result.response_time_ms > 0

    @pytest.mark.asyncio
    async def test_postgres_unhealthy(self, health_checker):
        """Test PostgreSQL health check when connection fails."""
        with patch.object(
            health_checker,
            "check_database",
            new_callable=AsyncMock,
        ) as mock_check:
            mock_check.return_value = HealthCheck(
                name="postgres",
                status=HealthStatus.UNHEALTHY,
                response_time_ms=0,
                message="Connection timeout",
            )

            result = await health_checker.check_database()

            assert result.status == HealthStatus.UNHEALTHY
            assert result.name == "postgres"

    @pytest.mark.asyncio
    async def test_health_all_healthy(self, health_checker):
        """Test health() returns healthy when all checks pass."""
        redis_result = HealthCheck(
            name="redis",
            status=HealthStatus.HEALTHY,
            response_time_ms=1.5,
            message="OK",
        )
        postgres_result = HealthCheck(
            name="postgres",
            status=HealthStatus.HEALTHY,
            response_time_ms=2.3,
            message="OK",
        )

        with patch.object(health_checker, "check_redis", new_callable=AsyncMock) as mock_redis, patch.object(
            health_checker, "check_database", new_callable=AsyncMock
        ) as mock_postgres:
            mock_redis.return_value = redis_result
            mock_postgres.return_value = postgres_result

            result = await health_checker.health()

            assert result["status"] == HealthStatus.HEALTHY.value
            assert len(result["checks"]) == 2
            assert result["checks"][0]["status"] == HealthStatus.HEALTHY.value
            assert result["checks"][1]["status"] == HealthStatus.HEALTHY.value

    @pytest.mark.asyncio
    async def test_health_one_unhealthy(self, health_checker):
        """Test health() returns unhealthy when one check fails."""
        redis_result = HealthCheck(
            name="redis",
            status=HealthStatus.HEALTHY,
            response_time_ms=1.5,
            message="OK",
        )
        postgres_result = HealthCheck(
            name="postgres",
            status=HealthStatus.UNHEALTHY,
            response_time_ms=0,
            message="Connection timeout",
        )

        with patch.object(health_checker, "check_redis", new_callable=AsyncMock) as mock_redis, patch.object(
            health_checker, "check_database", new_callable=AsyncMock
        ) as mock_postgres:
            mock_redis.return_value = redis_result
            mock_postgres.return_value = postgres_result

            result = await health_checker.health()

            assert result["status"] == HealthStatus.UNHEALTHY.value
            assert len(result["checks"]) == 2

    @pytest.mark.asyncio
    async def test_ready_true(self, health_checker):
        """Test ready() returns ready=true when all checks are healthy."""
        redis_result = HealthCheck(
            name="redis",
            status=HealthStatus.HEALTHY,
            response_time_ms=1.5,
            message="OK",
        )
        postgres_result = HealthCheck(
            name="postgres",
            status=HealthStatus.HEALTHY,
            response_time_ms=2.3,
            message="OK",
        )

        with patch.object(health_checker, "check_redis", new_callable=AsyncMock) as mock_redis, patch.object(
            health_checker, "check_database", new_callable=AsyncMock
        ) as mock_postgres:
            mock_redis.return_value = redis_result
            mock_postgres.return_value = postgres_result

            result = await health_checker.ready()

            assert result["ready"] is True
            assert result["health"]["status"] == HealthStatus.HEALTHY.value

    @pytest.mark.asyncio
    async def test_ready_false(self, health_checker):
        """Test ready() returns ready=false when any check is unhealthy."""
        redis_result = HealthCheck(
            name="redis",
            status=HealthStatus.HEALTHY,
            response_time_ms=1.5,
            message="OK",
        )
        postgres_result = HealthCheck(
            name="postgres",
            status=HealthStatus.UNHEALTHY,
            response_time_ms=0,
            message="Connection timeout",
        )

        with patch.object(health_checker, "check_redis", new_callable=AsyncMock) as mock_redis, patch.object(
            health_checker, "check_database", new_callable=AsyncMock
        ) as mock_postgres:
            mock_redis.return_value = redis_result
            mock_postgres.return_value = postgres_result

            result = await health_checker.ready()

            assert result["ready"] is False
            assert result["health"]["status"] == HealthStatus.UNHEALTHY.value

    @pytest.mark.asyncio
    async def test_close(self, health_checker):
        """Test that close() executes without error."""
        with patch.object(health_checker, "close", new_callable=AsyncMock) as mock_close:
            mock_close.return_value = None
            await health_checker.close()
            mock_close.assert_called_once()
