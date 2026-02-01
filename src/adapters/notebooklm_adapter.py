"""NotebookLM API adapter with OAuth, rate limiting, and retries.

Mirrors the architecture of canva_adapter.py for consistency.
"""

import asyncio
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any

import httpx

from src.observability.context import get_tenant_id
from src.utils.notebooklm_exceptions import (
    NotebookLMAPIError,
    TokenRefreshError,
    RateLimitError,
    TransientError,
    ValidationError,
    AuthenticationError,
)


# Constants
MAX_RETRIES = 3
INITIAL_BACKOFF = 0.5
MAX_BACKOFF = 30.0
RATE_LIMIT_REQUESTS_PER_MINUTE = 100


class ContentFormat(str, Enum):
    """Supported content formats for NotebookLM notebooks."""

    MARKDOWN = "markdown"
    HTML = "html"
    PDF = "pdf"


@dataclass
class Notebook:
    """Represents a NotebookLM notebook."""

    notebook_id: str
    title: str
    description: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    source_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "notebook_id": self.notebook_id,
            "title": self.title,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "source_count": self.source_count,
            "metadata": self.metadata,
        }


@dataclass
class NotebookSource:
    """Represents a source added to a notebook."""

    source_id: str
    notebook_id: str
    source_type: str  # "file", "url", "text", etc.
    source_name: str
    added_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "source_id": self.source_id,
            "notebook_id": self.notebook_id,
            "source_type": self.source_type,
            "source_name": self.source_name,
            "added_at": self.added_at.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class Message:
    """Represents a message in a NotebookLM conversation."""

    message_id: str
    notebook_id: str
    role: str  # "user", "assistant"
    content: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "message_id": self.message_id,
            "notebook_id": self.notebook_id,
            "role": self.role,
            "content": self.content,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }


class NotebookLMAdapterInterface(ABC):
    """Abstract interface for NotebookLM API adapter."""

    @abstractmethod
    async def create_notebook(self, title: str, description: Optional[str] = None) -> Notebook:
        """Create a new notebook."""
        pass

    @abstractmethod
    async def get_notebook(self, notebook_id: str) -> Notebook:
        """Get notebook details."""
        pass

    @abstractmethod
    async def list_notebooks(self) -> List[Notebook]:
        """List all notebooks."""
        pass

    @abstractmethod
    async def delete_notebook(self, notebook_id: str) -> bool:
        """Delete a notebook."""
        pass

    @abstractmethod
    async def add_source(self, notebook_id: str, source_type: str, source_name: str, content: str) -> NotebookSource:
        """Add a source to a notebook."""
        pass

    @abstractmethod
    async def send_message(self, notebook_id: str, content: str) -> Message:
        """Send a message to a notebook and get a response."""
        pass

    @abstractmethod
    async def export_notebook(self, notebook_id: str, format: ContentFormat) -> bytes:
        """Export notebook in specified format."""
        pass

    @abstractmethod
    async def close(self):
        """Close the adapter and cleanup resources."""
        pass


class NotebookLMAdapter(NotebookLMAdapterInterface):
    """NotebookLM API adapter with OAuth, rate limiting, and retries.

    Implements exponential backoff retry logic for transient errors,
    per-tenant rate limiting, and automatic OAuth token refresh.
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        access_token: str,
        refresh_token: Optional[str] = None,
        base_url: str = "https://notebooklm.googleapis.com/v1",
        cache=None,
    ):
        """Initialize NotebookLM adapter.

        Args:
            client_id: OAuth 2.0 client ID
            client_secret: OAuth 2.0 client secret
            access_token: Initial access token
            refresh_token: Refresh token for token rotation
            base_url: API base URL
            cache: Cache instance for rate limiting (optional)
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.base_url = base_url
        self.cache = cache

        self.client = httpx.AsyncClient(
            timeout=30.0,
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

    async def _check_rate_limit(self, tenant_id: str):
        """Check and enforce per-tenant rate limit.

        Args:
            tenant_id: Tenant identifier for rate limit key

        Raises:
            RateLimitError: If rate limit exceeded
        """
        if self.cache is None:
            return

        key = f"notebooklm:ratelimit:{tenant_id}"
        count = await self.cache.get(key)
        count = int(count) if count else 0

        if count >= RATE_LIMIT_REQUESTS_PER_MINUTE:
            raise RateLimitError(
                message="NotebookLM API rate limit exceeded (100 req/min)",
                retry_after=60,
                status_code=429,
            )

        await self.cache.set(key, count + 1, ttl=60)

    async def _refresh_token(self):
        """Refresh OAuth token.

        Raises:
            TokenRefreshError: If token refresh fails
        """
        if not self.refresh_token:
            raise TokenRefreshError(
                message="No refresh token available",
                status_code=401,
            )

        try:
            response = await self.client.post(
                "https://oauth2.googleapis.com/token",
                json={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "refresh_token": self.refresh_token,
                    "grant_type": "refresh_token",
                },
            )

            if response.status_code != 200:
                raise TokenRefreshError(
                    message=f"Token refresh failed with status {response.status_code}",
                    status_code=response.status_code,
                )

            data = response.json()
            self.access_token = data["access_token"]
            if "refresh_token" in data:
                self.refresh_token = data["refresh_token"]

        except httpx.RequestError as e:
            raise TokenRefreshError(
                message=f"Token refresh request failed: {str(e)}",
                status_code=500,
            ) from e

    async def _make_request(
        self,
        method: str,
        path: str,
        tenant_id: Optional[str] = None,
        **kwargs,
    ) -> httpx.Response:
        """Make HTTP request with retries and error handling.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: API path (e.g., "/notebooks")
            tenant_id: Tenant ID for rate limiting
            **kwargs: Additional arguments for httpx request

        Returns:
            httpx.Response object

        Raises:
            Various NotebookLMAPIError subclasses based on response
        """
        if tenant_id is None:
            try:
                tenant_id = get_tenant_id()
                if tenant_id is None:
                    tenant_id = "default"
            except Exception:
                tenant_id = "default"

        # Check rate limit before making request
        await self._check_rate_limit(tenant_id)

        # Prepare headers
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self.access_token}"
        headers["Content-Type"] = "application/json"
        headers["User-Agent"] = "NotebookLMAgent/1.0"

        url = f"{self.base_url}{path}"
        backoff = INITIAL_BACKOFF
        last_error = None

        for attempt in range(MAX_RETRIES):
            try:
                response = await self.client.request(
                    method,
                    url,
                    headers=headers,
                    **kwargs,
                )

                # Handle 401: attempt token refresh and retry once
                if response.status_code == 401:
                    if attempt == 0:
                        try:
                            await self._refresh_token()
                            headers["Authorization"] = f"Bearer {self.access_token}"
                            continue
                        except TokenRefreshError:
                            raise AuthenticationError(
                                message="Authentication failed (token refresh unsuccessful)",
                                status_code=401,
                            )
                    else:
                        raise AuthenticationError(
                            message="Authentication failed (still unauthorized after token refresh)",
                            status_code=401,
                        )

                # Handle 429: rate limit
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    raise RateLimitError(
                        message="API rate limit exceeded",
                        retry_after=retry_after,
                        status_code=429,
                    )

                # Handle 5xx: retry with exponential backoff
                if response.status_code >= 500:
                    if attempt < MAX_RETRIES - 1:
                        jitter = random.uniform(0, 0.1 * backoff)
                        wait_time = min(backoff + jitter, MAX_BACKOFF)
                        await asyncio.sleep(wait_time)
                        backoff *= 2
                        continue
                    else:
                        raise TransientError(
                            message=f"Transient API error (HTTP {response.status_code})",
                            status_code=response.status_code,
                        )

                # Handle 4xx (non-401/429): validation error
                if 400 <= response.status_code < 500:
                    raise ValidationError(
                        message=f"Invalid request (HTTP {response.status_code})",
                        status_code=response.status_code,
                    )

                return response

            except (httpx.TimeoutException, httpx.ConnectError) as e:
                if attempt < MAX_RETRIES - 1:
                    jitter = random.uniform(0, 0.1 * backoff)
                    wait_time = min(backoff + jitter, MAX_BACKOFF)
                    await asyncio.sleep(wait_time)
                    backoff *= 2
                    last_error = e
                    continue
                else:
                    raise TransientError(
                        message=f"Request timeout/connection failed: {str(e)}",
                        status_code=None,
                    ) from e

        if last_error:
            raise TransientError(
                message=f"Max retries exceeded: {str(last_error)}",
                status_code=None,
            ) from last_error

        raise TransientError(message="Max retries exceeded", status_code=None)

    async def create_notebook(self, title: str, description: Optional[str] = None) -> Notebook:
        """Create a new notebook.

        Args:
            title: Notebook title
            description: Optional notebook description

        Returns:
            Notebook object
        """
        payload = {"title": title}
        if description:
            payload["description"] = description

        response = await self._make_request("POST", "/notebooks", json=payload)
        data = response.json()

        return Notebook(
            notebook_id=data.get("notebook_id"),
            title=data.get("title"),
            description=data.get("description"),
            created_at=datetime.fromisoformat(data.get("created_at", datetime.utcnow().isoformat())),
            updated_at=datetime.fromisoformat(data.get("updated_at", datetime.utcnow().isoformat())),
            source_count=data.get("source_count", 0),
            metadata=data.get("metadata", {}),
        )

    async def get_notebook(self, notebook_id: str) -> Notebook:
        """Get notebook details.

        Args:
            notebook_id: Notebook ID

        Returns:
            Notebook object
        """
        response = await self._make_request("GET", f"/notebooks/{notebook_id}")
        data = response.json()

        return Notebook(
            notebook_id=data.get("notebook_id"),
            title=data.get("title"),
            description=data.get("description"),
            created_at=datetime.fromisoformat(data.get("created_at", datetime.utcnow().isoformat())),
            updated_at=datetime.fromisoformat(data.get("updated_at", datetime.utcnow().isoformat())),
            source_count=data.get("source_count", 0),
            metadata=data.get("metadata", {}),
        )

    async def list_notebooks(self) -> List[Notebook]:
        """List all notebooks.

        Returns:
            List of Notebook objects
        """
        response = await self._make_request("GET", "/notebooks")
        data = response.json()

        notebooks = []
        for item in data.get("notebooks", []):
            notebooks.append(
                Notebook(
                    notebook_id=item.get("notebook_id"),
                    title=item.get("title"),
                    description=item.get("description"),
                    created_at=datetime.fromisoformat(item.get("created_at", datetime.utcnow().isoformat())),
                    updated_at=datetime.fromisoformat(item.get("updated_at", datetime.utcnow().isoformat())),
                    source_count=item.get("source_count", 0),
                    metadata=item.get("metadata", {}),
                )
            )

        return notebooks

    async def delete_notebook(self, notebook_id: str) -> bool:
        """Delete a notebook.

        Args:
            notebook_id: Notebook ID

        Returns:
            True if deletion successful
        """
        response = await self._make_request("DELETE", f"/notebooks/{notebook_id}")
        return response.status_code == 204

    async def add_source(self, notebook_id: str, source_type: str, source_name: str, content: str) -> NotebookSource:
        """Add a source to a notebook.

        Args:
            notebook_id: Notebook ID
            source_type: Type of source ("file", "url", "text", etc.)
            source_name: Name/title of source
            content: Source content

        Returns:
            NotebookSource object
        """
        payload = {
            "source_type": source_type,
            "source_name": source_name,
            "content": content,
        }

        response = await self._make_request("POST", f"/notebooks/{notebook_id}/sources", json=payload)
        data = response.json()

        return NotebookSource(
            source_id=data.get("source_id"),
            notebook_id=data.get("notebook_id"),
            source_type=data.get("source_type"),
            source_name=data.get("source_name"),
            added_at=datetime.fromisoformat(data.get("added_at", datetime.utcnow().isoformat())),
            metadata=data.get("metadata", {}),
        )

    async def send_message(self, notebook_id: str, content: str) -> Message:
        """Send a message to a notebook and get a response.

        Args:
            notebook_id: Notebook ID
            content: Message content

        Returns:
            Message object with assistant response
        """
        payload = {"content": content}

        response = await self._make_request("POST", f"/notebooks/{notebook_id}/messages", json=payload)
        data = response.json()

        return Message(
            message_id=data.get("message_id"),
            notebook_id=data.get("notebook_id"),
            role=data.get("role", "assistant"),
            content=data.get("content"),
            created_at=datetime.fromisoformat(data.get("created_at", datetime.utcnow().isoformat())),
            metadata=data.get("metadata", {}),
        )

    async def export_notebook(self, notebook_id: str, format: ContentFormat) -> bytes:
        """Export notebook in specified format.

        Args:
            notebook_id: Notebook ID
            format: Export format (markdown, html, pdf)

        Returns:
            Exported content as bytes
        """
        response = await self._make_request(
            "GET",
            f"/notebooks/{notebook_id}/export",
            params={"format": format.value},
        )

        return response.content
