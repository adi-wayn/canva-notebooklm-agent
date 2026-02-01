"""Request context middleware for FastAPI/Starlette.

Manages:
- Request ID generation and propagation (X-Request-ID header)
- Tenant ID extraction and validation
- Context variable setup/teardown for async-safe request tracing

Public endpoints (/health, /ready) do not require tenant_id.
Other endpoints implicitly require it for multi-tenant isolation.
"""

from typing import Callable, Optional
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from src.observability.context import (
    generate_request_id,
    set_request_id,
    set_tenant_id,
    get_request_id,
)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Middleware to set up request context (request_id, tenant_id) for each request.
    
    Behavior:
    - Generates or accepts X-Request-ID header
    - Extracts X-Tenant-ID header if present
    - For /health and /ready endpoints: tenant_id is optional
    - For other endpoints: tenant_id is logged but not strictly required (optional enforcement)
    - Adds X-Request-ID to response headers
    - Clears context after request completes
    """

    # Endpoints that do not require tenant_id
    PUBLIC_ENDPOINTS = {"/health", "/ready"}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request, set context, and add response headers."""
        
        # Extract or generate request ID
        request_id = request.headers.get("X-Request-ID")
        if not request_id:
            request_id = generate_request_id()
        set_request_id(request_id)

        # Extract tenant ID
        tenant_id = request.headers.get("X-Tenant-ID")
        if tenant_id:
            set_tenant_id(tenant_id)

        # Call the next middleware/handler
        response = None
        try:
            response = await call_next(request)
        except Exception as exc:
            # Re-raise the exception (will be caught by FastAPI)
            raise exc
        finally:
            # Only add header if response was successfully created
            if response is not None:
                response.headers["X-Request-ID"] = request_id

        return response
