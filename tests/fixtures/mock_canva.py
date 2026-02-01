"""Mock fixtures and response builders for Canva API testing."""

from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, MagicMock


def build_design_response(
    design_id: str = "design_abc123",
    title: str = "Test Design",
    created_at: str = "2024-01-17T10:00:00Z",
) -> Dict[str, Any]:
    """Build a mock Canva design response."""
    return {
        "id": design_id,
        "title": title,
        "created_at": created_at,
        "thumbnail_url": f"https://cdn.canva.com/{design_id}/thumbnail.png",
    }


def build_content_element_response(
    element_id: str = "element_xyz",
    element_type: str = "text",
    x: float = 100.0,
    y: float = 100.0,
    width: float = 200.0,
    height: float = 50.0,
) -> Dict[str, Any]:
    """Build a mock content element response."""
    return {
        "id": element_id,
        "type": element_type,
        "position": {"x": x, "y": y},
        "size": {"width": width, "height": height},
    }


def build_template_response(
    template_id: str = "template_123",
    name: str = "Modern Presentation",
    design_type: str = "presentation",
) -> Dict[str, Any]:
    """Build a mock template response."""
    return {
        "id": template_id,
        "name": name,
        "design_type": design_type,
        "thumbnail_url": f"https://cdn.canva.com/{template_id}/thumb.png",
    }


def build_token_response(
    access_token: str = "new_access_token_123",
    refresh_token: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a mock OAuth token response."""
    response = {
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in": 3600,
    }
    if refresh_token:
        response["refresh_token"] = refresh_token
    return response


def mock_httpx_response(
    status_code: int = 200,
    json_data: Optional[Dict[str, Any]] = None,
    text: str = "",
    headers: Optional[Dict[str, str]] = None,
) -> MagicMock:
    """Build a mock httpx.Response object."""
    response = MagicMock()
    response.status_code = status_code
    response.text = text
    response.headers = headers or {}
    response.json = MagicMock(return_value=json_data or {})
    response.raise_for_status = MagicMock()

    # Make json() callable as a method or property
    if json_data:
        response.json.return_value = json_data

    return response


def mock_httpx_client(
    request_mock: Optional[AsyncMock] = None,
    post_mock: Optional[AsyncMock] = None,
    get_mock: Optional[AsyncMock] = None,
) -> MagicMock:
    """Build a mock httpx.AsyncClient."""
    client = MagicMock()
    client.request = request_mock or AsyncMock()
    client.post = post_mock or AsyncMock()
    client.get = get_mock or AsyncMock()
    client.aclose = AsyncMock()
    return client
