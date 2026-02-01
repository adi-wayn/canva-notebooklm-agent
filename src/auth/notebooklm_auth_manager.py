"""
NotebookLM Google Cloud Authentication Manager

This module implements authentication for NotebookLM using Google Cloud
service accounts and API keys.
"""

from datetime import datetime, timedelta
from google.oauth2 import service_account
from google.auth.transport.requests import Request
import requests
import json
import os


class NotebookLMAuthManager:
    def __init__(self, service_account_file: str = None, api_key: str = None):
        """
        Initialize NotebookLM authentication

        Args:
            service_account_file: Path to Google service account JSON file
            api_key: Optional API key for simpler authentication
        """
        self.service_account_file = service_account_file
        self.api_key = api_key
        self.credentials = None
        self.token = None
        self.token_expiry = None

    def authenticate_with_service_account(self) -> dict:
        """
        Authenticate using Google service account

        Returns:
            dict: Authentication credentials
        """
        # Check if service account file is provided
        if not self.service_account_file:
            raise Exception("Service account file not provided")

        # Check if file exists
        if not os.path.exists(self.service_account_file):
            raise Exception(f"Service account file not found: {self.service_account_file}")

        # Load service account credentials
        try:
            self.credentials = service_account.Credentials.from_service_account_file(
                self.service_account_file,
                scopes=[
                    'https://www.googleapis.com/auth/cloud-platform',
                    'https://www.googleapis.com/auth/notebooklm',
                    'https://www.googleapis.com/auth/drive.readonly'
                ]
            )
        except Exception as e:
            raise Exception(f"Failed to load service account credentials: {str(e)}")

        # Refresh credentials to get initial token
        if not self.credentials.valid:
            request = Request()
            self.credentials.refresh(request)

        self.token = self.credentials.token
        self.token_expiry = datetime.now() + timedelta(seconds=self.credentials.expires_in)

        return {
            'access_token': self.token,
            'expires_in': self.credentials.expires_in,
            'token_type': 'Bearer',
            'scopes': self.credentials.scopes
        }

    def authenticate_with_api_key(self) -> dict:
        """
        Authenticate using API key (simpler method)

        Returns:
            dict: Authentication credentials
        """
        if not self.api_key:
            raise Exception("API key not provided")

        # For API key authentication, we just store the key
        self.token = self.api_key
        self.token_expiry = None  # API keys don't expire

        return {
            'api_key': self.api_key,
            'token_type': 'API Key'
        }

    def get_valid_token(self) -> str:
        """
        Get valid access token

        Returns:
            str: Valid access token or API key
        """
        # Check if using service account credentials
        if self.credentials:
            if not self.credentials.valid:
                request = Request()
                self.credentials.refresh(request)
                self.token = self.credentials.token
                self.token_expiry = datetime.now() + timedelta(seconds=self.credentials.expires_in)
            return self.token

        # Using API key
        return self.api_key

    def revoke_token(self) -> bool:
        """
        Revoke current access token

        Returns:
            bool: Success status
        """
        # For service account credentials
        if self.credentials:
            try:
                # Revoke the token
                revoke_url = 'https://oauth2.googleapis.com/revoke'
                params = {'token': self.token}
                response = requests.post(revoke_url, params=params)

                if response.status_code == 200:
                    self.credentials = None
                    self.token = None
                    self.token_expiry = None
                    return True
                return False
            except Exception:
                return False

        # For API keys, we can't revoke them
        return False

    def get_token_info(self) -> dict:
        """
        Get current token information

        Returns:
            dict: Token information
        """
        if self.credentials:
            return {
                'access_token': self.token,
                'expires_at': self.token_expiry.isoformat() if self.token_expiry else None,
                'token_type': 'Bearer',
                'is_valid': self.credentials.valid,
                'scopes': self.credentials.scopes
            }
        else:
            return {
                'api_key': self.api_key,
                'token_type': 'API Key',
                'is_valid': True
            }

    def validate_service_account_file(self) -> bool:
        """
        Validate service account file structure

        Returns:
            bool: True if file is valid
        """
        try:
            with open(self.service_account_file, 'r') as f:
                data = json.load(f)

            # Check required fields
            required_fields = ['type', 'project_id', 'private_key_id', 'private_key', 'client_email']
            return all(field in data for field in required_fields)
        except Exception:
            return False
