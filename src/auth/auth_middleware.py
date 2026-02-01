"""
Authentication Middleware for FastAPI

This module provides authentication middleware and dependencies
for the Canva-NotebookLM integration API.
"""

from fastapi import Request, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer
from typing import Optional
from datetime import datetime


# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


class AuthContext:
    """
    Authentication context for API requests
    """
    def __init__(self, authenticated: bool, service: str, user_id: Optional[str] = None, 
                 scopes: Optional[list] = None, api_key: bool = False):
        self.authenticated = authenticated
        self.service = service
        self.user_id = user_id
        self.scopes = scopes or []
        self.api_key = api_key


async def authenticate_request(token: str = Depends(oauth2_scheme)) -> AuthContext:
    """
    Authenticate API requests using OAuth2 tokens

    Args:
        token: OAuth2 token from request

    Returns:
        AuthContext: Authentication context
    """
    # Get token manager (would be injected in real implementation)
    from .token_manager import TokenManager
    token_manager = TokenManager()

    try:
        # Retrieve and validate token
        token_data = token_manager.retrieve_token(token)

        # Check token validity
        if 'expires_at' in token_data:
            expires_at = datetime.fromisoformat(token_data['expires_at'])
            if expires_at < datetime.now():
                raise HTTPException(status_code=401, detail="Token expired")

        return AuthContext(
            authenticated=True,
            service=token_data['service'],
            user_id=token_data.get('user_id'),
            scopes=token_data.get('scopes', [])
        )

    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Authentication failed: {str(e)}")


async def get_auth_context(request: Request) -> AuthContext:
    """
    Get authentication context for request

    Supports both API keys and OAuth2 tokens
    """
    # Check for API key in headers
    api_key = request.headers.get('X-API-Key')

    if api_key:
        # Validate API key
        from .token_manager import TokenManager
        token_manager = TokenManager()

        try:
            token_data = token_manager.retrieve_token(api_key)
            return AuthContext(
                authenticated=True,
                service=token_data['service'],
                api_key=True
            )
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid API key")

    # Use OAuth2 for other authentication
    return await authenticate_request()


def check_scope(scope: str):
    """
    Dependency to check for specific scope

    Args:
        scope: Required scope

    Returns:
        AuthContext: Authentication context
    """
    def dependency(auth_context: AuthContext = Depends(get_auth_context)):
        if scope not in auth_context.scopes:
            raise HTTPException(
                status_code=403,
                detail=f"Missing required scope: {scope}"
            )
        return auth_context

    return dependency


def check_service(service: str):
    """
    Dependency to check for specific service

    Args:
        service: Required service ('canva' or 'notebooklm')

    Returns:
        AuthContext: Authentication context
    """
    def dependency(auth_context: AuthContext = Depends(get_auth_context)):
        if auth_context.service != service:
            raise HTTPException(
                status_code=403,
                detail=f"This endpoint requires {service} authentication"
            )
        return auth_context

    return dependency


# Example usage in FastAPI routes:
#
# @app.get("/protected")
# async def protected_route(auth: AuthContext = Depends(get_auth_context)):
#     return {"message": "Authenticated", "service": auth.service}
#
# @app.get("/canva-only")
# async def canva_only(auth: AuthContext = Depends(check_service("canva"))):
#     return {"message": "Canva authenticated"}
#
# @app.get("/design-scope")
# async def design_scope(auth: AuthContext = Depends(check_scope("design:write"))):
#     return {"message": "Design scope authorized"}
