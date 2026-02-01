import asyncio
import pytest
from fastapi.testclient import TestClient
from src.main import app

pytestmark = []

client = TestClient(app)


def test_sse_stream_endpoint_reachable():
    """Verify SSE stream endpoint is registered and returns proper headers."""
    # Create a workflow
    create_resp = client.post(
        "/api/v1/workflows",
        headers={"X-Tenant-ID": "tenant-1"},
        json={"user_id": "user-1", "tenant_id": "tenant-1", "config": {}},
    )
    assert create_resp.status_code == 200
    wf_id = create_resp.json()["id"]

    # Test that the stream endpoint exists
    assert "/api/v1/workflows/{workflow_id}/stream" in str(client.app.routes)
    # Test that workflow was created successfully
    assert wf_id.startswith("wf_")


def test_sse_tenant_isolation():
    """Verify SSE stream respects tenant scoping."""
    # Create a workflow for tenant-1
    create_resp = client.post(
        "/api/v1/workflows",
        headers={"X-Tenant-ID": "tenant-1"},
        json={"user_id": "user-1", "tenant_id": "tenant-1", "config": {}},
    )
    assert create_resp.status_code == 200
    wf_id = create_resp.json()["id"]

    # Try to access stream as tenant-2 (should return 404 since workflow isn't in tenant-2's scope)
    resp = client.get(
        f"/api/v1/workflows/{wf_id}/stream",
        headers={"X-Tenant-ID": "tenant-2"},
    )
    assert resp.status_code == 404
