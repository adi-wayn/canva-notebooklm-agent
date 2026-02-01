"""Unit tests for Canva API adapter.

Tests cover:
- Token refresh on 401
- Rate limiting enforcement
- Transient error retry with exponential backoff
- Custom exception mapping
- All adapter interface methods
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

from src.adapters.canva_adapter import (
    CanvaAdapter,
    Design,
    ContentElement,
    Template,
    ExportFormat,
)
from src.utils.canva_exceptions import (
    CanvaAPIError,
    AuthenticationError,
    RateLimitError,
    TokenRefreshError,
    TransientError,
    ValidationError,
)
from tests.fixtures.mock_canva import (
    build_design_response,
    build_content_element_response,
    build_template_response,
    build_token_response,
    mock_httpx_response,
)


@pytest.fixture
def adapter():
    """Create a CanvaAdapter instance for testing."""
    return CanvaAdapter(
        client_id="test_client_id",
        client_secret="test_client_secret",
        access_token="test_access_token",
        refresh_token="test_refresh_token",
        cache=None,  # No Redis for unit tests
    )


@pytest.mark.asyncio
class TestCanvaAdapterTokenRefresh:
    """Test OAuth token refresh behavior."""

    async def test_token_refresh_on_401(self, adapter):
        """Test that 401 triggers token refresh and retry."""
        # Mock initial 401 response, then success
        responses = [
            mock_httpx_response(status_code=401, text="Unauthorized"),
            mock_httpx_response(status_code=200, json_data=build_design_response()),
        ]

        with patch.object(adapter.client, "request", side_effect=responses) as mock_request, patch.object(
            adapter, "_refresh_token", new_callable=AsyncMock
        ) as mock_refresh:
            result = await adapter.create_presentation("Test Design")

            assert result.design_id == "design_abc123"
            assert mock_refresh.called

    async def test_token_refresh_failure(self, adapter):
        """Test that token refresh failure raises AuthenticationError."""
        with patch.object(
            adapter, "_refresh_token", side_effect=TokenRefreshError(message="Refresh failed", status_code=401)
        ):
            with pytest.raises(AuthenticationError):
                with patch.object(adapter.client, "request", return_value=mock_httpx_response(status_code=401)):
                    await adapter.create_presentation("Test Design")

    async def test_refresh_token_updates_access_token(self, adapter):
        """Test that refresh_token method updates the access token."""
        new_token = "new_access_token_999"
        token_response = build_token_response(access_token=new_token, refresh_token="new_refresh_token")

        with patch.object(
            adapter.client,
            "post",
            return_value=mock_httpx_response(status_code=200, json_data=token_response),
        ):
            await adapter._refresh_token()

            assert adapter.access_token == new_token
            assert adapter.refresh_token == "new_refresh_token"

    async def test_refresh_token_without_refresh_token_raises_error(self, adapter):
        """Test that refresh fails if no refresh_token is available."""
        adapter.refresh_token = None

        with pytest.raises(TokenRefreshError):
            await adapter._refresh_token()


@pytest.mark.asyncio
class TestCanvaAdapterRateLimiting:
    """Test rate limiting behavior."""

    async def test_rate_limit_check_passes(self, adapter):
        """Test that rate limit check passes for first request."""
        # With no cache, should always pass
        await adapter._check_rate_limit("tenant-1")
        # Should not raise

    async def test_rate_limit_exceeded_raises_error(self, adapter):
        """Test that rate limit exceeded raises RateLimitError."""
        mock_cache = AsyncMock()
        mock_cache.get = AsyncMock(return_value="100")  # Simulating count at limit
        adapter.cache = mock_cache

        with pytest.raises(RateLimitError) as exc_info:
            await adapter._check_rate_limit("tenant-1")

        assert exc_info.value.status_code == 429
        assert exc_info.value.retry_after == 60

    async def test_rate_limit_increments(self, adapter):
        """Test that rate limit counter increments."""
        mock_cache = AsyncMock()
        mock_cache.get = AsyncMock(return_value="5")  # Count at 5
        mock_cache.set = AsyncMock()
        adapter.cache = mock_cache

        await adapter._check_rate_limit("tenant-1")

        # Should increment to 6
        mock_cache.set.assert_called_once()
        call_args = mock_cache.set.call_args
        assert call_args[0][0] == "canva:ratelimit:tenant-1"
        assert call_args[0][1] == 6


@pytest.mark.asyncio
class TestCanvaAdapterRetry:
    """Test retry logic for transient errors."""

    async def test_retry_on_500_error(self, adapter):
        """Test that 5xx errors trigger retry."""
        responses = [
            mock_httpx_response(status_code=500, text="Server Error"),
            mock_httpx_response(status_code=500, text="Server Error"),
            mock_httpx_response(status_code=200, json_data=build_design_response()),
        ]

        with patch.object(adapter.client, "request", side_effect=responses):
            result = await adapter.create_presentation("Test Design")

            assert result.design_id == "design_abc123"

    async def test_retry_max_attempts_exceeded(self, adapter):
        """Test that max retries raises TransientError."""
        # Return same 503 response on all retries
        side_effect_responses = [
            mock_httpx_response(status_code=503, text="Service Unavailable"),
            mock_httpx_response(status_code=503, text="Service Unavailable"),
            mock_httpx_response(status_code=503, text="Service Unavailable"),
        ]
        with patch.object(adapter.client, "request", side_effect=side_effect_responses):
            with pytest.raises(TransientError):
                await adapter.create_presentation("Test Design")

    async def test_retry_on_timeout(self, adapter):
        """Test that timeouts trigger retry."""
        import httpx

        responses = [
            httpx.TimeoutException("timeout"),
            httpx.TimeoutException("timeout"),
            mock_httpx_response(status_code=200, json_data=build_design_response()),
        ]

        with patch.object(adapter.client, "request", side_effect=responses):
            result = await adapter.create_presentation("Test Design")

            assert result.design_id == "design_abc123"

    async def test_no_retry_on_validation_error(self, adapter):
        """Test that validation errors (4xx) do not retry."""
        with patch.object(adapter.client, "request", return_value=mock_httpx_response(status_code=400, text="Bad Request")):
            with pytest.raises(ValidationError):
                await adapter.create_presentation("Test Design")


@pytest.mark.asyncio
class TestCanvaAdapterErrorMapping:
    """Test custom error exception mapping."""

    async def test_401_maps_to_authentication_error(self, adapter):
        """Test that 401 maps to AuthenticationError."""
        with patch.object(adapter.client, "request", return_value=mock_httpx_response(status_code=401)):
            with patch.object(adapter, "_refresh_token", side_effect=TokenRefreshError("refresh failed", status_code=401)):
                with pytest.raises(AuthenticationError):
                    await adapter.create_presentation("Test")

    async def test_429_maps_to_rate_limit_error(self, adapter):
        """Test that 429 maps to RateLimitError."""
        response = mock_httpx_response(status_code=429)
        response.headers = {"Retry-After": "120"}

        with patch.object(adapter.client, "request", return_value=response):
            with pytest.raises(RateLimitError) as exc_info:
                await adapter.create_presentation("Test")

            assert exc_info.value.retry_after == 120

    async def test_5xx_maps_to_transient_error(self, adapter):
        """Test that 5xx maps to TransientError."""
        # Use side_effect with a list of responses to always fail
        side_effect_responses = [
            mock_httpx_response(status_code=502, text="Bad Gateway"),
            mock_httpx_response(status_code=502, text="Bad Gateway"),
            mock_httpx_response(status_code=502, text="Bad Gateway"),
        ]
        with patch.object(adapter.client, "request", side_effect=side_effect_responses):
            with pytest.raises(TransientError):
                await adapter.create_presentation("Test")

    async def test_4xx_not_401_maps_to_validation_error(self, adapter):
        """Test that 4xx (not 401) maps to ValidationError."""
        with patch.object(adapter.client, "request", return_value=mock_httpx_response(status_code=400)):
            with pytest.raises(ValidationError):
                await adapter.create_presentation("Test")


@pytest.mark.asyncio
class TestCanvaAdapterInterfaceMethods:
    """Test all adapter interface methods."""

    async def test_create_presentation(self, adapter):
        """Test create_presentation method."""
        response_data = build_design_response(design_id="new_design_123", title="My Design")

        with patch.object(
            adapter.client, "request", return_value=mock_httpx_response(status_code=200, json_data=response_data)
        ):
            result = await adapter.create_presentation("My Design")

            assert isinstance(result, Design)
            assert result.design_id == "new_design_123"
            assert result.title == "My Design"

    async def test_create_presentation_with_template(self, adapter):
        """Test create_presentation with template_id."""
        response_data = build_design_response()

        with patch.object(
            adapter.client, "request", return_value=mock_httpx_response(status_code=200, json_data=response_data)
        ) as mock_request:
            await adapter.create_presentation("Design", template_id="template_123")

            # Verify the template_id was included in the request
            call_args = mock_request.call_args
            assert "json" in call_args.kwargs
            assert call_args.kwargs["json"]["template_id"] == "template_123"

    async def test_get_design(self, adapter):
        """Test get_design method."""
        response_data = build_design_response()

        with patch.object(
            adapter.client, "request", return_value=mock_httpx_response(status_code=200, json_data=response_data)
        ):
            result = await adapter.get_design("design_abc123")

            assert isinstance(result, Design)
            assert result.design_id == "design_abc123"

    async def test_add_text_block(self, adapter):
        """Test add_text_block method."""
        element_data = build_content_element_response(element_id="text_123", element_type="text")

        with patch.object(
            adapter.client, "request", return_value=mock_httpx_response(status_code=200, json_data=element_data)
        ):
            result = await adapter.add_text_block(
                "design_abc123",
                "Hello World",
                x=100.0,
                y=100.0,
                width=200.0,
                height=50.0,
                font_size=16,
            )

            assert isinstance(result, ContentElement)
            assert result.element_type == "text"
            assert result.content["text"] == "Hello World"
            assert result.content["font_size"] == 16

    async def test_add_image(self, adapter):
        """Test add_image method."""
        element_data = build_content_element_response(element_id="image_123", element_type="image")

        with patch.object(
            adapter.client, "request", return_value=mock_httpx_response(status_code=200, json_data=element_data)
        ):
            result = await adapter.add_image(
                "design_abc123",
                "https://example.com/image.png",
                x=0.0,
                y=0.0,
                width=300.0,
                height=300.0,
            )

            assert isinstance(result, ContentElement)
            assert result.element_type == "image"
            assert result.content["image_url"] == "https://example.com/image.png"

    async def test_apply_template(self, adapter):
        """Test apply_template method."""
        response_data = build_design_response()

        with patch.object(
            adapter.client, "request", return_value=mock_httpx_response(status_code=200, json_data=response_data)
        ):
            result = await adapter.apply_template("design_abc123", "template_xyz")

            assert isinstance(result, Design)

    async def test_export_design(self, adapter):
        """Test export_design method."""
        mock_data = {"status": "exported", "download_url": "https://example.com/export.pdf"}

        with patch.object(
            adapter.client, "request", return_value=mock_httpx_response(status_code=200, json_data=mock_data)
        ):
            result = await adapter.export_design("design_abc123", ExportFormat.PDF)

            assert isinstance(result, bytes)

    async def test_list_templates(self, adapter):
        """Test list_templates method."""
        response_data = {
            "templates": [
                build_template_response(template_id="t1", name="Template 1"),
                build_template_response(template_id="t2", name="Template 2"),
            ]
        }

        with patch.object(
            adapter.client, "request", return_value=mock_httpx_response(status_code=200, json_data=response_data)
        ):
            result = await adapter.list_templates("presentation")

            assert isinstance(result, list)
            assert len(result) == 2
            assert all(isinstance(t, Template) for t in result)
            assert result[0].template_id == "t1"

    async def test_close(self, adapter):
        """Test close method."""
        with patch.object(adapter.client, "aclose", new_callable=AsyncMock) as mock_close:
            await adapter.close()

            mock_close.assert_called_once()

    async def test_context_manager(self, adapter):
        """Test async context manager."""
        with patch.object(adapter.client, "aclose", new_callable=AsyncMock):
            async with adapter:
                pass

            assert adapter.client.aclose.called


@pytest.mark.asyncio
class TestCanvaAdapterHeaders:
    """Test request header handling."""

    async def test_authorization_header_included(self, adapter):
        """Test that Authorization header is included in requests."""
        response_data = build_design_response()

        with patch.object(
            adapter.client, "request", return_value=mock_httpx_response(status_code=200, json_data=response_data)
        ) as mock_request:
            await adapter.create_presentation("Test")

            call_args = mock_request.call_args
            headers = call_args.kwargs.get("headers", {})
            assert "Authorization" in headers
            assert headers["Authorization"] == f"Bearer {adapter.access_token}"

    async def test_content_type_header(self, adapter):
        """Test that Content-Type header is set."""
        response_data = build_design_response()

        with patch.object(
            adapter.client, "request", return_value=mock_httpx_response(status_code=200, json_data=response_data)
        ) as mock_request:
            await adapter.create_presentation("Test")

            call_args = mock_request.call_args
            headers = call_args.kwargs.get("headers", {})
            assert headers["Content-Type"] == "application/json"
