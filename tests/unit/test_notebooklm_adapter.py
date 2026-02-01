"""Unit tests for NotebookLM API adapter.

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

from src.adapters.notebooklm_adapter import (
    NotebookLMAdapter,
    Notebook,
    NotebookSource,
    Message,
    ContentFormat,
)
from src.utils.notebooklm_exceptions import (
    NotebookLMAPIError,
    AuthenticationError,
    RateLimitError,
    TokenRefreshError,
    TransientError,
    ValidationError,
)
from tests.fixtures.mock_notebooklm import (
    build_notebook_response,
    build_source_response,
    build_message_response,
    build_token_response,
    mock_httpx_response,
)


@pytest.fixture
def adapter():
    """Create a NotebookLMAdapter instance for testing."""
    return NotebookLMAdapter(
        client_id="test_client_id",
        client_secret="test_client_secret",
        access_token="test_access_token",
        refresh_token="test_refresh_token",
        cache=None,  # No Redis for unit tests
    )


@pytest.mark.asyncio
class TestNotebookLMAdapterTokenRefresh:
    """Test OAuth token refresh behavior."""

    async def test_token_refresh_on_401(self, adapter):
        """Test that 401 triggers token refresh and retry."""
        # Mock initial 401 response, then success
        responses = [
            mock_httpx_response(status_code=401, text="Unauthorized"),
            mock_httpx_response(status_code=200, json_data=build_notebook_response()),
        ]

        with patch.object(adapter.client, "request", side_effect=responses) as mock_request, patch.object(
            adapter, "_refresh_token", new_callable=AsyncMock
        ) as mock_refresh:
            result = await adapter.create_notebook("Test Notebook")

            assert result.notebook_id == "notebook_abc123"
            assert mock_refresh.called

    async def test_token_refresh_failure(self, adapter):
        """Test that token refresh failure raises AuthenticationError."""
        with patch.object(
            adapter, "_refresh_token", side_effect=TokenRefreshError(message="Refresh failed", status_code=401)
        ):
            with pytest.raises(AuthenticationError):
                with patch.object(adapter.client, "request", return_value=mock_httpx_response(status_code=401)):
                    await adapter.create_notebook("Test Notebook")

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
class TestNotebookLMAdapterRateLimiting:
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
        assert call_args[0][0] == "notebooklm:ratelimit:tenant-1"
        assert call_args[0][1] == 6


@pytest.mark.asyncio
class TestNotebookLMAdapterRetry:
    """Test retry logic for transient errors."""

    async def test_retry_on_500_error(self, adapter):
        """Test that 5xx errors trigger retry."""
        responses = [
            mock_httpx_response(status_code=500, text="Server Error"),
            mock_httpx_response(status_code=500, text="Server Error"),
            mock_httpx_response(status_code=200, json_data=build_notebook_response()),
        ]

        with patch.object(adapter.client, "request", side_effect=responses):
            result = await adapter.create_notebook("Test Notebook")

            assert result.notebook_id == "notebook_abc123"

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
                await adapter.create_notebook("Test Notebook")

    async def test_retry_on_timeout(self, adapter):
        """Test that timeouts trigger retry."""
        import httpx

        responses = [
            httpx.TimeoutException("timeout"),
            httpx.TimeoutException("timeout"),
            mock_httpx_response(status_code=200, json_data=build_notebook_response()),
        ]

        with patch.object(adapter.client, "request", side_effect=responses):
            result = await adapter.create_notebook("Test Notebook")

            assert result.notebook_id == "notebook_abc123"

    async def test_no_retry_on_validation_error(self, adapter):
        """Test that validation errors (4xx) do not retry."""
        with patch.object(adapter.client, "request", return_value=mock_httpx_response(status_code=400, text="Bad Request")):
            with pytest.raises(ValidationError):
                await adapter.create_notebook("Test Notebook")


@pytest.mark.asyncio
class TestNotebookLMAdapterErrorMapping:
    """Test custom error exception mapping."""

    async def test_401_maps_to_authentication_error(self, adapter):
        """Test that 401 maps to AuthenticationError."""
        with patch.object(adapter.client, "request", return_value=mock_httpx_response(status_code=401)):
            with patch.object(adapter, "_refresh_token", side_effect=TokenRefreshError("refresh failed", status_code=401)):
                with pytest.raises(AuthenticationError):
                    await adapter.create_notebook("Test")

    async def test_429_maps_to_rate_limit_error(self, adapter):
        """Test that 429 maps to RateLimitError."""
        response = mock_httpx_response(status_code=429)
        response.headers = {"Retry-After": "120"}

        with patch.object(adapter.client, "request", return_value=response):
            with pytest.raises(RateLimitError) as exc_info:
                await adapter.create_notebook("Test")

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
                await adapter.create_notebook("Test")

    async def test_4xx_not_401_maps_to_validation_error(self, adapter):
        """Test that 4xx (not 401) maps to ValidationError."""
        with patch.object(adapter.client, "request", return_value=mock_httpx_response(status_code=400)):
            with pytest.raises(ValidationError):
                await adapter.create_notebook("Test")


@pytest.mark.asyncio
class TestNotebookLMAdapterInterfaceMethods:
    """Test all adapter interface methods."""

    async def test_create_notebook(self, adapter):
        """Test create_notebook method."""
        response_data = build_notebook_response(notebook_id="new_notebook_123", title="My Notebook")

        with patch.object(
            adapter.client, "request", return_value=mock_httpx_response(status_code=200, json_data=response_data)
        ):
            result = await adapter.create_notebook("My Notebook")

            assert isinstance(result, Notebook)
            assert result.notebook_id == "new_notebook_123"
            assert result.title == "My Notebook"

    async def test_create_notebook_with_description(self, adapter):
        """Test create_notebook with description."""
        response_data = build_notebook_response(description="Test description")

        with patch.object(
            adapter.client, "request", return_value=mock_httpx_response(status_code=200, json_data=response_data)
        ) as mock_request:
            await adapter.create_notebook("Notebook", description="Test description")

            # Verify the description was included in the request
            call_args = mock_request.call_args
            assert "json" in call_args.kwargs
            assert call_args.kwargs["json"]["description"] == "Test description"

    async def test_get_notebook(self, adapter):
        """Test get_notebook method."""
        response_data = build_notebook_response()

        with patch.object(
            adapter.client, "request", return_value=mock_httpx_response(status_code=200, json_data=response_data)
        ):
            result = await adapter.get_notebook("notebook_abc123")

            assert isinstance(result, Notebook)
            assert result.notebook_id == "notebook_abc123"

    async def test_list_notebooks(self, adapter):
        """Test list_notebooks method."""
        response_data = {
            "notebooks": [
                build_notebook_response(notebook_id="nb1", title="Notebook 1"),
                build_notebook_response(notebook_id="nb2", title="Notebook 2"),
            ]
        }

        with patch.object(
            adapter.client, "request", return_value=mock_httpx_response(status_code=200, json_data=response_data)
        ):
            result = await adapter.list_notebooks()

            assert isinstance(result, list)
            assert len(result) == 2
            assert all(isinstance(n, Notebook) for n in result)
            assert result[0].notebook_id == "nb1"

    async def test_delete_notebook(self, adapter):
        """Test delete_notebook method."""
        with patch.object(adapter.client, "request", return_value=mock_httpx_response(status_code=204)):
            result = await adapter.delete_notebook("notebook_abc123")

            assert result is True

    async def test_add_source(self, adapter):
        """Test add_source method."""
        source_data = build_source_response(source_id="src_123", source_type="text")

        with patch.object(
            adapter.client, "request", return_value=mock_httpx_response(status_code=200, json_data=source_data)
        ):
            result = await adapter.add_source(
                "notebook_abc123",
                "text",
                "Test Source",
                "Test content",
            )

            assert isinstance(result, NotebookSource)
            assert result.source_type == "text"
            assert result.source_name == "Test Source"

    async def test_send_message(self, adapter):
        """Test send_message method."""
        message_data = build_message_response(message_id="msg_123", role="assistant")

        with patch.object(
            adapter.client, "request", return_value=mock_httpx_response(status_code=200, json_data=message_data)
        ):
            result = await adapter.send_message("notebook_abc123", "Hello")

            assert isinstance(result, Message)
            assert result.role == "assistant"
            assert result.content == "This is a response."

    async def test_export_notebook(self, adapter):
        """Test export_notebook method."""
        with patch.object(
            adapter.client, "request", return_value=mock_httpx_response(status_code=200, json_data={})
        ):
            result = await adapter.export_notebook("notebook_abc123", ContentFormat.MARKDOWN)

            assert isinstance(result, bytes)

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
class TestNotebookLMAdapterHeaders:
    """Test request header handling."""

    async def test_authorization_header_included(self, adapter):
        """Test that Authorization header is included in requests."""
        response_data = build_notebook_response()

        with patch.object(
            adapter.client, "request", return_value=mock_httpx_response(status_code=200, json_data=response_data)
        ) as mock_request:
            await adapter.create_notebook("Test")

            call_args = mock_request.call_args
            headers = call_args.kwargs.get("headers", {})
            assert "Authorization" in headers
            assert headers["Authorization"] == f"Bearer {adapter.access_token}"

    async def test_content_type_header(self, adapter):
        """Test that Content-Type header is set."""
        response_data = build_notebook_response()

        with patch.object(
            adapter.client, "request", return_value=mock_httpx_response(status_code=200, json_data=response_data)
        ) as mock_request:
            await adapter.create_notebook("Test")

            call_args = mock_request.call_args
            headers = call_args.kwargs.get("headers", {})
            assert headers["Content-Type"] == "application/json"

    async def test_user_agent_header(self, adapter):
        """Test that User-Agent header is set."""
        response_data = build_notebook_response()

        with patch.object(
            adapter.client, "request", return_value=mock_httpx_response(status_code=200, json_data=response_data)
        ) as mock_request:
            await adapter.create_notebook("Test")

            call_args = mock_request.call_args
            headers = call_args.kwargs.get("headers", {})
            assert headers["User-Agent"] == "NotebookLMAgent/1.0"
