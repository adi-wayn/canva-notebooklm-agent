"""
Canva OAuth 2.0 Authentication Manager with PKCE

This module implements Canva's OAuth 2.0 authentication flow with
Proof Key for Code Exchange (PKCE) for enhanced security.
"""

import secrets
import hashlib
import base64
from datetime import datetime, timedelta
from urllib.parse import urlencode
import requests
import uuid
from typing import Optional


class CanvaAuthManager:
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        """
        Initialize Canva OAuth 2.0 with PKCE

        Args:
            client_id: Canva API client ID
            client_secret: Canva API client secret
            redirect_uri: OAuth redirect URI
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.token = None
        self.refresh_token = None
        self.token_expiry = None
        self.code_verifier = None
        self.state = None

    def generate_pkce_codes(self) -> tuple:
        """
        Generate PKCE code verifier and challenge

        Returns:
            tuple: (code_verifier, code_challenge)
        """
        # Generate code verifier - random URL-safe string
        code_verifier = secrets.token_urlsafe(64)

        # Generate code challenge - SHA256 hash of verifier
        code_verifier_bytes = code_verifier.encode('ascii')
        code_challenge_bytes = hashlib.sha256(code_verifier_bytes).digest()
        code_challenge = base64.urlsafe_b64encode(code_challenge_bytes).decode('ascii').rstrip('=')

        return code_verifier, code_challenge

    def get_authorization_url(self, state: str = None) -> str:
        """
        Generate Canva OAuth authorization URL

        Args:
            state: Optional state parameter for CSRF protection

        Returns:
            str: Authorization URL for user redirect
        """
        # Generate PKCE codes
        code_verifier, code_challenge = self.generate_pkce_codes()

        # Store verifier for later use
        self.code_verifier = code_verifier

        # Generate state if not provided
        self.state = state or str(uuid.uuid4())

        # Build authorization URL
        params = {
            'client_id': self.client_id,
            'response_type': 'code',
            'redirect_uri': self.redirect_uri,
            'code_challenge': code_challenge,
            'code_challenge_method': 'S256',
            # Align with Canva documented scopes
            'scope': 'design:content:read design:content:write design:meta:read',
            'state': self.state
        }

        return f"https://www.canva.com/api/oauth/authorize?{urlencode(params)}"

    def exchange_code_for_token(self, authorization_code: str, code_verifier: Optional[str] = None) -> dict:
        """
        Exchange authorization code for access token using PKCE

        Per Canva docs: https://www.canva.dev/docs/connect/authentication/
        - Must use Basic auth with client_id:client_secret
        - Must provide code_verifier for PKCE
        - Endpoint: https://www.canva.com/api/oauth/token

        Args:
            authorization_code: OAuth authorization code from redirect
            code_verifier: PKCE code verifier (optional, uses stored if not provided)

        Returns:
            dict: Token response with access_token, refresh_token, etc.
        """
        # Use provided verifier or stored one
        verifier = code_verifier or self.code_verifier
        if not verifier:
            raise Exception("PKCE code verifier not found. Did you call get_authorization_url first?")

        # Build Basic auth header
        credentials = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode()
        ).decode()

        # Prepare token exchange request per Canva docs
        # Canva Connect docs now require the REST base host for token exchange
        # https://www.canva.dev/docs/connect/api-requests-responses/#example-curl-request
        token_url = "https://api.canva.com/rest/v1/oauth/token"

        # Make POST request to token endpoint
        response = requests.post(
            token_url,
            data={
                'grant_type': 'authorization_code',
                'code': authorization_code,
                'code_verifier': verifier,
                # Canva requires redirect_uri to match the authorize step
                'redirect_uri': self.redirect_uri,
            },
            headers={
                'Authorization': f'Basic {credentials}',
            },
            timeout=30
        )

        # Handle response
        if response.status_code == 200:
            token_data = response.json()
            self.token = token_data['access_token']
            self.refresh_token = token_data.get('refresh_token')
            self.token_expiry = datetime.now() + timedelta(seconds=token_data['expires_in'])
            return token_data
        else:
            error_msg = f"Token exchange failed: {response.status_code} - {response.text}"
            raise Exception(error_msg)

    def refresh_access_token(self) -> dict:
        """
        Refresh access token using refresh token

        Per Canva docs: uses same endpoint with refresh_token grant type
        - Must use Basic auth with client_id:client_secret
        - Endpoint: https://www.canva.com/api/oauth/token

        Returns:
            dict: New token response
        """
        # Check if we have a refresh token
        if not self.refresh_token:
            raise Exception("No refresh token available")

        # Build Basic auth header
        credentials = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode()
        ).decode()

        # Make refresh request per Canva docs
        refresh_url = "https://api.canva.com/rest/v1/oauth/token"

        response = requests.post(
            refresh_url,
            data={
                'grant_type': 'refresh_token',
                'refresh_token': self.refresh_token,
            },
            headers={
                'Authorization': f'Basic {credentials}',
            },
            timeout=30
        )

        # Handle response
        if response.status_code == 200:
            token_data = response.json()
            self.token = token_data['access_token']
            self.refresh_token = token_data.get('refresh_token') or self.refresh_token
            self.token_expiry = datetime.now() + timedelta(seconds=token_data['expires_in'])
            return token_data
        else:
            error_msg = f"Token refresh failed: {response.status_code} - {response.text}"
            raise Exception(error_msg)

    def get_valid_token(self) -> str:
        """
        Get valid access token, refresh if needed

        Returns:
            str: Valid access token
        """
        # Check if token is expired or about to expire (within 5 minutes)
        if not self.token or self.token_expiry < datetime.now() + timedelta(minutes=5):
            if self.refresh_token:
                self.refresh_access_token()
            else:
                raise Exception("No valid token available and no refresh token")

        return self.token

    def revoke_token(self) -> bool:
        """
        Revoke current access token

        Returns:
            bool: Success status
        """
        # Check if we have a token to revoke
        if not self.token:
            return False

        # Make revocation request
        revoke_url = "https://api.canva.com/oauth/revoke"

        response = requests.post(revoke_url, data={
            'token': self.token,
            'client_id': self.client_id,
            'client_secret': self.client_secret
        })

        # Handle response
        if response.status_code == 200:
            # Clear tokens
            self.token = None
            self.refresh_token = None
            self.token_expiry = None
            return True
        else:
            return False

    def validate_state(self, returned_state: str) -> bool:
        """
        Validate state parameter to prevent CSRF

        Args:
            returned_state: State parameter returned from OAuth redirect

        Returns:
            bool: True if state is valid
        """
        return returned_state == self.state

    def get_token_info(self) -> dict:
        """
        Get current token information

        Returns:
            dict: Token information
        """
        return {
            'access_token': self.token,
            'refresh_token': self.refresh_token,
            'expires_at': self.token_expiry.isoformat() if self.token_expiry else None,
            'is_valid': self.token is not None and self.token_expiry > datetime.now()
        }
