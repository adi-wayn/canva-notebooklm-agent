"""Mock fixtures and response builders for NotebookLM adapter tests.

Provides reusable mocks for httpx and response data builders.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock


def build_notebook_response(
    notebook_id: str = "notebook_abc123",
    title: str = "Test Notebook",
    description: str = None,
    source_count: int = 0,
) -> dict:
    """Build a mock notebook response."""
    return {
        "notebook_id": notebook_id,
        "title": title,
        "description": description,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
        "source_count": source_count,
        "metadata": {},
    }


def build_source_response(
    source_id: str = "source_xyz789",
    notebook_id: str = "notebook_abc123",
    source_type: str = "text",
    source_name: str = "Test Source",
) -> dict:
    """Build a mock notebook source response."""
    return {
        "source_id": source_id,
        "notebook_id": notebook_id,
        "source_type": source_type,
        "source_name": source_name,
        "added_at": datetime.utcnow().isoformat(),
        "metadata": {},
    }


def build_message_response(
    message_id: str = "msg_123",
    notebook_id: str = "notebook_abc123",
    role: str = "assistant",
    content: str = "This is a response.",
) -> dict:
    """Build a mock message response."""
    return {
        "message_id": message_id,
        "notebook_id": notebook_id,
        "role": role,
        "content": content,
        "created_at": datetime.utcnow().isoformat(),
        "metadata": {},
    }


def build_token_response(
    access_token: str = "access_token_abc123",
    refresh_token: str = "refresh_token_xyz",
) -> dict:
    """Build a mock OAuth token response."""
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "Bearer",
        "expires_in": 3600,
    }


def mock_httpx_response(
    status_code: int = 200,
    json_data: dict = None,
    text: str = None,
    headers: dict = None,
) -> MagicMock:
    """Create a mock httpx.Response object."""
    response = MagicMock()
    response.status_code = status_code
    response.headers = headers or {}
    response.text = text or ""

    if json_data:
        response.json = MagicMock(return_value=json_data)
    else:
        response.json = MagicMock(return_value={})

    response.content = b"test content"
    return response


def mock_httpx_client() -> AsyncMock:
    """Create a mock httpx.AsyncClient."""
    client = AsyncMock()
    client.request = AsyncMock()
    client.post = AsyncMock()
    client.get = AsyncMock()
    client.aclose = AsyncMock()
    return client
