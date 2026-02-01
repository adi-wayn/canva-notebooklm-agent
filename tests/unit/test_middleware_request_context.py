"""Unit tests for request context middleware.

Tests:
- X-Request-ID generation and propagation
- X-Tenant-ID extraction
- Health endpoints do not require tenant_id
- Context variables set and reset per request
"""

import pytest
from unittest.mock import AsyncMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.middleware.request_context import RequestContextMiddleware
from src.observability.context import get_request_id, get_tenant_id


@pytest.fixture
def app():
    """Create a test FastAPI app with request context middleware."""
    test_app = FastAPI()
    test_app.add_middleware(RequestContextMiddleware)

    @test_app.get("/health")
    async def health():
        return {"status": "ok"}

    @test_app.get("/ready")
    async def ready():
        return {"ready": True}

    @test_app.get("/protected")
    async def protected():
        # This endpoint uses context variables
        request_id = get_request_id()
        tenant_id = get_tenant_id()
        return {
            "request_id": request_id,
            "tenant_id": tenant_id,
        }

    return test_app


@pytest.fixture
def client(app):
    """Create a test client for the app."""
    return TestClient(app)


class TestRequestContextMiddleware:
    """Test suite for RequestContextMiddleware."""

    def test_request_id_generated(self, client):
        """Test that X-Request-ID is generated if not provided."""
        response = client.get("/protected")

        assert response.status_code == 200
        assert "X-Request-ID" in response.headers
        request_id = response.headers["X-Request-ID"]
        assert request_id is not None
        assert len(request_id) > 0

    def test_request_id_accepted(self, client):
        """Test that X-Request-ID from request is used in response."""
        provided_request_id = "test-request-id-12345"
        response = client.get("/protected", headers={"X-Request-ID": provided_request_id})

        assert response.status_code == 200
        assert response.headers["X-Request-ID"] == provided_request_id
        assert response.json()["request_id"] == provided_request_id

    def test_request_id_propagated_to_context(self, client):
        """Test that X-Request-ID is available in contextvars during request."""
        provided_request_id = "test-req-context-xyz"
        response = client.get("/protected", headers={"X-Request-ID": provided_request_id})

        assert response.status_code == 200
        data = response.json()
        assert data["request_id"] == provided_request_id

    def test_tenant_id_extracted(self, client):
        """Test that X-Tenant-ID header is extracted and available."""
        tenant_id = "tenant-123"
        response = client.get(
            "/protected",
            headers={"X-Tenant-ID": tenant_id},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["tenant_id"] == tenant_id

    def test_tenant_id_optional(self, client):
        """Test that X-Tenant-ID is optional (request succeeds without it)."""
        response = client.get("/protected")

        assert response.status_code == 200
        data = response.json()
        assert data["tenant_id"] is None

    def test_health_endpoint_no_tenant_required(self, client):
        """Test that /health endpoint works without X-Tenant-ID."""
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        assert "X-Request-ID" in response.headers

    def test_ready_endpoint_no_tenant_required(self, client):
        """Test that /ready endpoint works without X-Tenant-ID."""
        response = client.get("/ready")

        assert response.status_code == 200
        assert response.json()["ready"] is True
        assert "X-Request-ID" in response.headers

    def test_request_id_unique_per_request(self, client):
        """Test that each request gets a unique request ID if not provided."""
        response1 = client.get("/protected")
        response2 = client.get("/protected")

        request_id_1 = response1.headers["X-Request-ID"]
        request_id_2 = response2.headers["X-Request-ID"]

        assert request_id_1 != request_id_2

    def test_context_reset_between_requests(self, client):
        """Test that context is reset between requests."""
        # First request with tenant_id
        response1 = client.get(
            "/protected",
            headers={"X-Tenant-ID": "tenant-1"},
        )
        tenant_id_1 = response1.json()["tenant_id"]

        # Second request without tenant_id
        response2 = client.get("/protected")
        tenant_id_2 = response2.json()["tenant_id"]

        assert tenant_id_1 == "tenant-1"
        assert tenant_id_2 is None  # Context should be reset

    def test_both_headers_together(self, client):
        """Test that both X-Request-ID and X-Tenant-ID work together."""
        request_id = "req-both-test-123"
        tenant_id = "tenant-both-test-456"

        response = client.get(
            "/protected",
            headers={
                "X-Request-ID": request_id,
                "X-Tenant-ID": tenant_id,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["request_id"] == request_id
        assert data["tenant_id"] == tenant_id
        assert response.headers["X-Request-ID"] == request_id

    def test_response_includes_request_id_header(self, client):
        """Test that all responses include X-Request-ID header."""
        response = client.get("/protected")

        assert "X-Request-ID" in response.headers
        assert response.headers["X-Request-ID"] is not None

    def test_response_includes_request_id_for_health(self, client):
        """Test that /health response includes X-Request-ID header."""
        response = client.get("/health")

        assert "X-Request-ID" in response.headers
        assert response.headers["X-Request-ID"] is not None

    def test_response_includes_request_id_for_ready(self, client):
        """Test that /ready response includes X-Request-ID header."""
        response = client.get("/ready")

        assert "X-Request-ID" in response.headers
        assert response.headers["X-Request-ID"] is not None
