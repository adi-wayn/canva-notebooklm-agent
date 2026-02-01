"""OAuth authentication routes for external service integrations."""

import logging
import secrets
import base64
import httpx
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, Header, Query
from fastapi.responses import RedirectResponse

from src.config import settings
from src.storage.database import database
from src.storage.repository import UserConnectionRepository, UserRepository
from src.auth.canva_auth_manager import CanvaAuthManager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

# State tokens for CSRF protection (in production, store in Redis with TTL)
_oauth_states = {}

@router.get("/canva/authorize")
async def canva_authorize(
    x_tenant_id: str = Header(None),
    x_user_id: str = Header(None),
    tenant_id: str = Query(None),
    user_id: str = Query(None),
):
    """Initiate Canva OAuth authorization with PKCE.
    
    Redirects user to Canva OAuth consent screen using CanvaAuthManager.
    After user authorizes, browser redirects to /auth/canva/callback?code=X&state=Y
    
    Accepts tenant_id/user_id via headers (preferred) or query params (for browser testing).
    """
    # Try headers first, then query params, then use test defaults
    tenant_id = x_tenant_id or tenant_id or "test-tenant"
    user_id = x_user_id or user_id or "test-user"
    
    # Initialize Canva auth manager
    auth_manager = CanvaAuthManager(
        client_id=settings.canva.client_id.get_secret_value(),
        client_secret=settings.canva.client_secret.get_secret_value(),
        redirect_uri=settings.canva.redirect_uri,
    )
    
    # Generate authorization URL (with PKCE and state)
    auth_url = auth_manager.get_authorization_url()
    
    # Store state and code_verifier for callback validation
    state = auth_manager.state
    _oauth_states[state] = {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "code_verifier": auth_manager.code_verifier,
        "created_at": datetime.now(timezone.utc),
    }
    
    logger.info(f"Initiating Canva OAuth for user {user_id} in tenant {tenant_id}")
    return RedirectResponse(url=auth_url, status_code=302)


@router.get("/canva/callback")
async def canva_callback(
    code: str = Query(..., description="OAuth authorization code"),
    state: str = Query(..., description="CSRF state token"),
):
    """Handle Canva OAuth callback.
    
    Exchanges authorization code for access token and stores in database.
    Redirects to frontend with success/error status.
    """
    # Validate state token
    if state not in _oauth_states:
        logger.warning(f"Invalid OAuth state token: {state}")
        return RedirectResponse(
            url=f"http://localhost:5173/login?error=invalid_state",
            status_code=302,
        )
    
    state_data = _oauth_states.pop(state)
    tenant_id = state_data["tenant_id"]
    user_id = state_data["user_id"]
    code_verifier = state_data["code_verifier"]
    
    # Verify state token not too old (5 minutes)
    if datetime.now(timezone.utc) - state_data["created_at"] > timedelta(minutes=5):
        logger.warning(f"Expired OAuth state token for user {user_id}")
        return RedirectResponse(
            url=f"http://localhost:5173/login?error=state_expired",
            status_code=302,
        )
    
    try:
        # Use auth manager to exchange code for token (with PKCE)
        auth_manager = CanvaAuthManager(
            client_id=settings.canva.client_id.get_secret_value(),
            client_secret=settings.canva.client_secret.get_secret_value(),
            redirect_uri=settings.canva.redirect_uri,
        )
        
        # Set the code_verifier for this exchange
        auth_manager.code_verifier = code_verifier
        
        # Exchange code for tokens
        token_data = auth_manager.exchange_code_for_token(code)
        
        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")
        expires_in = token_data.get("expires_in", 3600)
        
        # Get user info from Canva API
        async with httpx.AsyncClient() as client:
            user_response = await client.get(
                f"{settings.canva.api_base_url}/rest/v1/users/me",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            user_response.raise_for_status()
        
        user_data = user_response.json()
        account_email = user_data.get("email")
        account_name = user_data.get("display_name")
        
        # Store tokens in database
        async with database.session() as session:
            repo = UserConnectionRepository(
                session, user_id=user_id, tenant_id=tenant_id
            )
            
            # Delete existing connection (re-authorize)
            await repo.delete_connection("canva")
            
            # Store new connection
            token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
            await repo.save_connection(
                provider="canva",
                access_token=access_token,
                refresh_token=refresh_token,
                token_expires_at=token_expires_at,
                account_email=account_email,
                account_name=account_name,
            )
        
        logger.info(f"Canva OAuth successful for user {user_id} ({account_email})")
        
        # Redirect to frontend with success
        return RedirectResponse(
            url=f"http://localhost:5173?success=canva_connected&email={account_email}",
            status_code=302,
        )
        
    except httpx.HTTPError as e:
        logger.error(f"Canva OAuth token exchange failed: {e}")
        return RedirectResponse(
            url=f"http://localhost:5173/login?error=oauth_failed",
            status_code=302,
        )
    except Exception as e:
        logger.error(f"Canva OAuth callback error: {e}")
        return RedirectResponse(
            url=f"http://localhost:5173/login?error=callback_error",
            status_code=302,
        )


@router.get("/canva/status")
async def canva_status(
    x_tenant_id: str = Header(None),
    x_user_id: str = Header(None),
    tenant_id: str = Query(None),
    user_id: str = Query(None),
):
    """Get Canva connection status for current user.
    
    Returns:
        {
            "connected": true,
            "provider": "canva",
            "account_email": "user@example.com",
            "account_name": "John Doe",
            "connected_at": "2025-01-18T10:30:00Z"
        }
    
    Accepts tenant_id/user_id via headers (preferred) or query params (for browser testing).
    """
    # Try headers first, then query params, then use test defaults
    tenant_id = x_tenant_id or tenant_id or "test-tenant"
    user_id = x_user_id or user_id or "test-user"
    
    try:
        async with database.session() as session:
            repo = UserConnectionRepository(
                session, user_id=user_id, tenant_id=tenant_id
            )
            connection = await repo.get_connection("canva")
        
        if not connection:
            return {"connected": False, "provider": "canva"}
        
        return {
            "connected": True,
            "provider": "canva",
            "account_email": connection.account_email,
            "account_name": connection.account_name,
            "connected_at": connection.created_at.isoformat(),
        }
    except Exception as e:
        logger.error(f"Error checking Canva connection status: {e}")
        raise HTTPException(status_code=500, detail="Failed to check connection status")


@router.post("/canva/disconnect")
async def canva_disconnect(
    x_tenant_id: str = Header(None),
    x_user_id: str = Header(None),
    tenant_id: str = Query(None),
    user_id: str = Query(None),
):
    """Revoke Canva connection and remove tokens.
    
    Returns:
        {"success": true, "provider": "canva", "message": "Connection revoked"}
    
    Accepts tenant_id/user_id via headers (preferred) or query params (for browser testing).
    """
    # Try headers first, then query params, then use test defaults
    tenant_id = x_tenant_id or tenant_id or "test-tenant"
    user_id = x_user_id or user_id or "test-user"
    
    try:
        async with database.session() as session:
            repo = UserConnectionRepository(
                session, user_id=user_id, tenant_id=tenant_id
            )
            deleted = await repo.delete_connection("canva")
        
        if not deleted:
            raise HTTPException(status_code=404, detail="No Canva connection found")
        
        logger.info(f"Canva connection revoked for user {user_id}")
        return {"success": True, "provider": "canva", "message": "Connection revoked"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error disconnecting Canva: {e}")
        raise HTTPException(status_code=500, detail="Failed to disconnect")
