"""
Test suite for authentication systems

This module provides comprehensive tests for the authentication implementation.
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
import json
import os


class TestCanvaAuthManager:
    """Test Canva OAuth 2.0 with PKCE implementation"""

    def test_pkce_generation(self):
        """Test PKCE code generation"""
        from src.auth.canva_auth_manager import CanvaAuthManager

        manager = CanvaAuthManager('client_id', 'client_secret', 'http://localhost/callback')
        verifier, challenge = manager.generate_pkce_codes()

        # Verify lengths and formats
        assert len(verifier) >= 43  # URL-safe base64
        assert len(challenge) >= 43  # URL-safe base64
        assert verifier != challenge

    def test_authorization_url_generation(self):
        """Test authorization URL generation"""
        from src.auth.canva_auth_manager import CanvaAuthManager

        manager = CanvaAuthManager('client_id', 'client_secret', 'http://localhost/callback')
        url = manager.get_authorization_url('test_state')

        # Verify URL structure
        assert url.startswith('https://api.canva.com/oauth/authorize?')
        assert 'client_id=client_id' in url
        assert 'redirect_uri=http%3A%2F%2Flocalhost%2Fcallback' in url
        assert 'code_challenge=' in url
        assert 'code_challenge_method=S256' in url
        assert 'state=test_state' in url

    @patch('requests.post')
    def test_token_exchange_success(self, mock_post):
        """Test successful token exchange"""
        from src.auth.canva_auth_manager import CanvaAuthManager

        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'access_token': 'test_access_token',
            'refresh_token': 'test_refresh_token',
            'expires_in': 3600,
            'token_type': 'Bearer'
        }
        mock_post.return_value = mock_response

        manager = CanvaAuthManager('client_id', 'client_secret', 'http://localhost/callback')
        manager.get_authorization_url()  # Generate PKCE codes

        result = manager.exchange_code_for_token('test_code')

        # Verify token storage
        assert manager.token == 'test_access_token'
        assert manager.refresh_token == 'test_refresh_token'
        assert manager.token_expiry > datetime.now()

        # Verify return value
        assert result['access_token'] == 'test_access_token'

    @patch('requests.post')
    def test_token_exchange_failure(self, mock_post):
        """Test failed token exchange"""
        from src.auth.canva_auth_manager import CanvaAuthManager

        # Mock failed response
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = 'Invalid code'
        mock_post.return_value = mock_response

        manager = CanvaAuthManager('client_id', 'client_secret', 'http://localhost/callback')
        manager.get_authorization_url()  # Generate PKCE codes

        with pytest.raises(Exception) as exc_info:
            manager.exchange_code_for_token('invalid_code')

        assert 'Token exchange failed' in str(exc_info.value)

    @patch('requests.post')
    def test_token_refresh(self, mock_post):
        """Test token refresh functionality"""
        from src.auth.canva_auth_manager import CanvaAuthManager

        # Mock successful refresh response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'access_token': 'new_access_token',
            'expires_in': 3600,
            'token_type': 'Bearer'
        }
        mock_post.return_value = mock_response

        manager = CanvaAuthManager('client_id', 'client_secret', 'http://localhost/callback')
        manager.refresh_token = 'test_refresh_token'

        result = manager.refresh_access_token()

        # Verify token update
        assert manager.token == 'new_access_token'
        assert manager.refresh_token == 'test_refresh_token'  # Should keep old refresh token if not provided

        # Verify request parameters
        call_args = mock_post.call_args
        assert call_args[1]['data']['grant_type'] == 'refresh_token'
        assert call_args[1]['data']['refresh_token'] == 'test_refresh_token'


class TestNotebookLMAuthManager:
    """Test NotebookLM authentication implementation"""

    def test_service_account_validation(self):
        """Test service account file validation"""
        from src.auth.notebooklm_auth_manager import NotebookLMAuthManager

        # Create a temporary valid service account file
        valid_account = {
            'type': 'service_account',
            'project_id': 'test-project',
            'private_key_id': 'test-key-id',
            'private_key': """-----BEGIN PRIVATE KEY-----
            test
            -----END PRIVATE KEY-----
            """,
            'client_email': 'test@test-project.iam.gserviceaccount.com'
        }

        with open('test_service_account.json', 'w') as f:
            json.dump(valid_account, f)

        manager = NotebookLMAuthManager('test_service_account.json')
        assert manager.validate_service_account_file()

        # Clean up
        os.remove('test_service_account.json')

    @patch('google.oauth2.service_account.Credentials.from_service_account_file')
    def test_service_account_authentication(self, mock_credentials):
        """Test service account authentication"""
        from src.auth.notebooklm_auth_manager import NotebookLMAuthManager

        # Mock credentials
        mock_cred_instance = Mock()
        mock_cred_instance.valid = False
        mock_cred_instance.token = 'test_token'
        mock_cred_instance.expires_in = 3600
        mock_cred_instance.scopes = ['https://www.googleapis.com/auth/notebooklm']
        mock_cred_instance.refresh = Mock()
        mock_credentials.return_value = mock_cred_instance

        # Create a temporary service account file
        with open('test_service_account.json', 'w') as f:
            json.dump({'type': 'service_account'}, f)

        manager = NotebookLMAuthManager('test_service_account.json')
        result = manager.authenticate_with_service_account()

        # Verify authentication
        assert manager.token == 'test_token'
        assert result['access_token'] == 'test_token'

        # Clean up
        os.remove('test_service_account.json')

    def test_api_key_authentication(self):
        """Test API key authentication"""
        from src.auth.notebooklm_auth_manager import NotebookLMAuthManager

        manager = NotebookLMAuthManager(api_key='test_api_key')
        result = manager.authenticate_with_api_key()

        # Verify API key storage
        assert manager.token == 'test_api_key'
        assert result['api_key'] == 'test_api_key'


class TestTokenManager:
    """Test token management system"""

    def test_token_storage_and_retrieval(self):
        """Test basic token storage and retrieval"""
        from src.auth.token_manager import TokenManager

        manager = TokenManager(storage_backend='memory')

        # Store a token
        token_data = {
            'access_token': 'test_token',
            'refresh_token': 'test_refresh',
            'expires_at': (datetime.now() + timedelta(hours=1)).isoformat()
        }

        token_id = manager.store_token('canva', token_data, encrypt=False)

        # Retrieve the token
        retrieved_data = manager.retrieve_token(token_id, decrypt=False)

        # Verify data integrity
        assert retrieved_data['access_token'] == 'test_token'
        assert retrieved_data['refresh_token'] == 'test_refresh'

    def test_token_encryption(self):
        """Test token encryption and decryption"""
        from src.auth.token_manager import TokenManager

        manager = TokenManager(storage_backend='memory')

        # Store encrypted token
        token_data = {
            'access_token': 'sensitive_token',
            'refresh_token': 'sensitive_refresh',
            'expires_at': (datetime.now() + timedelta(hours=1)).isoformat()
        }

        token_id = manager.store_token('notebooklm', token_data, encrypt=True)

        # Retrieve and decrypt
        retrieved_data = manager.retrieve_token(token_id, decrypt=True)

        # Verify decryption
        assert retrieved_data['access_token'] == 'sensitive_token'
        assert retrieved_data['refresh_token'] == 'sensitive_refresh'

    def test_token_invalidation(self):
        """Test token invalidation"""
        from src.auth.token_manager import TokenManager

        manager = TokenManager(storage_backend='memory')

        # Store a token
        token_id = manager.store_token('canva', {'access_token': 'test'}, encrypt=False)

        # Invalidate the token
        result = manager.invalidate_token(token_id)
        assert result

        # Verify token is gone
        with pytest.raises(Exception):
            manager.retrieve_token(token_id)

    def test_token_listing(self):
        """Test token listing functionality"""
        from src.auth.token_manager import TokenManager

        manager = TokenManager(storage_backend='memory')

        # Store multiple tokens
        token1 = manager.store_token('canva', {'access_token': 'test1'}, encrypt=False)
        token2 = manager.store_token('notebooklm', {'access_token': 'test2'}, encrypt=False)
        token3 = manager.store_token('canva', {'access_token': 'test3'}, encrypt=False)

        # List all tokens
        all_tokens = manager.list_tokens()
        assert len(all_tokens) == 3

        # List filtered tokens
        canva_tokens = manager.list_tokens('canva')
        assert len(canva_tokens) == 2

        notebooklm_tokens = manager.list_tokens('notebooklm')
        assert len(notebooklm_tokens) == 1


class TestAuthMiddleware:
    """Test authentication middleware"""

    def test_auth_context(self):
        """Test AuthContext creation"""
        from src.auth.auth_middleware import AuthContext

        context = AuthContext(
            authenticated=True,
            service='canva',
            user_id='user123',
            scopes=['design:read', 'design:write']
        )

        assert context.authenticated
        assert context.service == 'canva'
        assert context.user_id == 'user123'
        assert 'design:write' in context.scopes

    @pytest.mark.asyncio
    @patch('src.auth.token_manager.TokenManager')
    async def test_authenticate_request_success(self, mock_token_manager):
        """Test successful request authentication"""
        from src.auth.auth_middleware import authenticate_request
        from src.auth.auth_middleware import AuthContext

        # Mock token manager
        mock_instance = Mock()
        mock_instance.retrieve_token.return_value = {
            'service': 'canva',
            'expires_at': (datetime.now() + timedelta(hours=1)).isoformat()
        }
        mock_token_manager.return_value = mock_instance

        # Test authentication
        result = await authenticate_request('test_token')

        assert isinstance(result, AuthContext)
        assert result.authenticated
        assert result.service == 'canva'

    @pytest.mark.asyncio
    @patch('src.auth.token_manager.TokenManager')
    async def test_authenticate_request_expired(self, mock_token_manager):
        """Test authentication with expired token"""
        from src.auth.auth_middleware import authenticate_request

        # Mock token manager with expired token
        mock_instance = Mock()
        mock_instance.retrieve_token.return_value = {
            'service': 'canva',
            'expires_at': (datetime.now() - timedelta(hours=1)).isoformat()
        }
        mock_token_manager.return_value = mock_instance

        # Test should raise exception
        with pytest.raises(Exception) as exc_info:
            await authenticate_request('expired_token')

        assert 'Token expired' in str(exc_info.value)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
