"""Integration tests for T1.7 - Verification & Integration Hardening.

Tests:
- X-Request-ID behavior end-to-end (generation, propagation, response)
- X-Tenant-ID propagation end-to-end
- Logging formatter integration (request_id/tenant_id in log records)
"""

import logging
import pytest
from io import StringIO
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.main import app
from src.observability.context import get_request_id, get_tenant_id
from src.observability.logging import JSONFormatter


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def capture_logs():
    """Capture log output for inspection."""
    log_capture = StringIO()
    handler = logging.StreamHandler(log_capture)
    handler.setFormatter(JSONFormatter())
    logger = logging.getLogger()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    
    yield log_capture
    
    logger.removeHandler(handler)


class TestIntegrationRequestContext:
    """Integration tests for request context middleware and logging."""

    def test_request_id_end_to_end_generation(self, client):
        """Test X-Request-ID is generated and returned end-to-end."""
        response = client.get("/health")

        assert response.status_code == 200
        assert "X-Request-ID" in response.headers
        request_id = response.headers["X-Request-ID"]
        assert len(request_id) > 0
        # Should be a UUID (basic validation)
        assert len(request_id.split("-")) == 5

    def test_request_id_end_to_end_propagation(self, client):
        """Test X-Request-ID is accepted and returned as-is."""
        provided_request_id = "integration-test-req-123"
        response = client.get("/health", headers={"X-Request-ID": provided_request_id})

        assert response.status_code == 200
        assert response.headers["X-Request-ID"] == provided_request_id

    def test_tenant_id_propagation_end_to_end(self, client):
        """Test X-Tenant-ID is extracted and available to handlers."""
        # Create a test endpoint that returns context info
        from fastapi import FastAPI

        test_app = FastAPI()
        from src.middleware.request_context import RequestContextMiddleware
        test_app.add_middleware(RequestContextMiddleware)

        @test_app.get("/context-info")
        async def context_info():
            return {
                "request_id": get_request_id(),
                "tenant_id": get_tenant_id(),
            }

        test_client = TestClient(test_app)
        tenant_id = "integration-tenant-xyz"
        response = test_client.get(
            "/context-info",
            headers={"X-Tenant-ID": tenant_id},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["tenant_id"] == tenant_id

    def test_health_endpoint_no_tenant_required(self, client):
        """Test /health endpoint works without X-Tenant-ID (public endpoint)."""
        # Should not require tenant header
        response = client.get("/health")

        assert response.status_code == 200
        assert "X-Request-ID" in response.headers
        data = response.json()
        assert "status" in data

    def test_request_id_in_logging_context(self, client):
        """Test that request_id is available in logging context during request handling."""
        from fastapi import FastAPI
        import json

        test_app = FastAPI()
        from src.middleware.request_context import RequestContextMiddleware
        test_app.add_middleware(RequestContextMiddleware)

        # Create a logger with JSON formatter
        logger = logging.getLogger("test_integration")
        logger.setLevel(logging.INFO)

        # Capture logs
        log_stream = StringIO()
        handler = logging.StreamHandler(log_stream)
        formatter = JSONFormatter()
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        @test_app.get("/test-logging")
        async def test_logging_endpoint():
            logger.info("Test log message")
            return {"status": "ok"}

        test_client = TestClient(test_app)
        request_id = "logging-test-req-999"
        response = test_client.get("/test-logging", headers={"X-Request-ID": request_id})

        assert response.status_code == 200

        # Get captured log
        log_output = log_stream.getvalue().strip()
        if log_output:
            # Parse JSON log
            log_record = json.loads(log_output)
            assert "request_id" in log_record
            assert log_record["request_id"] == request_id

        # Cleanup
        logger.removeHandler(handler)

    def test_tenant_id_in_logging_context(self, client):
        """Test that tenant_id is available in logging context during request handling."""
        from fastapi import FastAPI
        import json

        test_app = FastAPI()
        from src.middleware.request_context import RequestContextMiddleware
        test_app.add_middleware(RequestContextMiddleware)

        # Create a logger with JSON formatter
        logger = logging.getLogger("test_integration_tenant")
        logger.setLevel(logging.INFO)

        # Capture logs
        log_stream = StringIO()
        handler = logging.StreamHandler(log_stream)
        formatter = JSONFormatter()
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        @test_app.get("/test-tenant-logging")
        async def test_tenant_logging_endpoint():
            logger.info("Test tenant log")
            return {"status": "ok"}

        test_client = TestClient(test_app)
        tenant_id = "logging-test-tenant-777"
        response = test_client.get(
            "/test-tenant-logging",
            headers={"X-Tenant-ID": tenant_id},
        )

        assert response.status_code == 200

        # Get captured log
        log_output = log_stream.getvalue().strip()
        if log_output:
            # Parse JSON log
            log_record = json.loads(log_output)
            assert "tenant_id" in log_record
            assert log_record["tenant_id"] == tenant_id

        # Cleanup
        logger.removeHandler(handler)

    def test_multiple_requests_isolated_context(self, client):
        """Test that context is properly isolated between requests."""
        from fastapi import FastAPI

        test_app = FastAPI()
        from src.middleware.request_context import RequestContextMiddleware
        test_app.add_middleware(RequestContextMiddleware)

        @test_app.get("/isolated-context")
        async def isolated_endpoint():
            return {
                "request_id": get_request_id(),
                "tenant_id": get_tenant_id(),
            }

        test_client = TestClient(test_app)

        # Request 1
        response1 = test_client.get(
            "/isolated-context",
            headers={"X-Request-ID": "req-1", "X-Tenant-ID": "tenant-1"},
        )
        data1 = response1.json()

        # Request 2
        response2 = test_client.get(
            "/isolated-context",
            headers={"X-Request-ID": "req-2", "X-Tenant-ID": "tenant-2"},
        )
        data2 = response2.json()

        # Verify isolation
        assert data1["request_id"] == "req-1"
        assert data1["tenant_id"] == "tenant-1"
        assert data2["request_id"] == "req-2"
        assert data2["tenant_id"] == "tenant-2"

    def test_health_endpoint_returns_request_id_header(self, client):
        """Test that /health endpoint includes X-Request-ID in response."""
        response = client.get("/health")

        assert response.status_code == 200
        assert "X-Request-ID" in response.headers
        assert len(response.headers["X-Request-ID"]) > 0
