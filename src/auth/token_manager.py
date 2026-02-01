"""
Token Management System

This module provides secure storage and management of authentication tokens
for both Canva and NotebookLM services.
"""

import json
import os
import uuid
from datetime import datetime
from cryptography.fernet import Fernet
import base64
import hashlib
import threading
import pickle


class TokenManager:
    def __init__(self, storage_backend: str = 'file'):
        """
        Initialize token manager

        Args:
            storage_backend: 'file', 'database', or 'memory'
        """
        self.storage_backend = storage_backend
        self.tokens = {}
        self.lock = threading.Lock()

        # Initialize storage
        if storage_backend == 'file':
            self.storage_file = 'tokens_secure.json'
            self.load_from_file()
        elif storage_backend == 'memory':
            self.tokens = {}

    def store_token(self, service: str, token_data: dict, encrypt: bool = True) -> str:
        """
        Store authentication token securely

        Args:
            service: 'canva' or 'notebooklm'
            token_data: Token data to store
            encrypt: Whether to encrypt the token

        Returns:
            str: Token ID
        """
        token_id = str(uuid.uuid4())

        # Add metadata
        token_record = {
            'service': service,
            'data': token_data,
            'timestamp': datetime.now().isoformat(),
            'encrypted': False
        }

        # Encrypt sensitive data if requested
        if encrypt:
            token_record['data'] = self.encrypt_token_data(token_data)
            token_record['encrypted'] = True

        with self.lock:
            self.tokens[token_id] = token_record
            self.save_to_storage()

        return token_id

    def retrieve_token(self, token_id: str, decrypt: bool = True) -> dict:
        """
        Retrieve stored token

        Args:
            token_id: Token ID
            decrypt: Whether to decrypt the token

        Returns:
            dict: Token data
        """
        with self.lock:
            if token_id not in self.tokens:
                raise Exception("Token not found")

            token_record = self.tokens[token_id]
            token_data = token_record['data']

            # Decrypt if needed
            if decrypt and token_record['encrypted']:
                token_data = self.decrypt_token_data(token_data)

            return token_data

    def encrypt_token_data(self, data: dict) -> dict:
        """
        Encrypt sensitive token data

        Args:
            data: Token data to encrypt

        Returns:
            dict: Encrypted token data
        """
        # Get encryption key
        key = self.get_encryption_key()
        cipher = Fernet(key)

        # Encrypt sensitive fields
        encrypted_data = {}
        for k, v in data.items():
            if k in ['access_token', 'refresh_token', 'api_key'] and isinstance(v, str):
                encrypted_data[k] = cipher.encrypt(v.encode()).decode()
            else:
                encrypted_data[k] = v

        return encrypted_data

    def decrypt_token_data(self, data: dict) -> dict:
        """
        Decrypt encrypted token data

        Args:
            data: Encrypted token data

        Returns:
            dict: Decrypted token data
        """
        key = self.get_encryption_key()
        cipher = Fernet(key)

        decrypted_data = {}
        for k, v in data.items():
            if k in ['access_token', 'refresh_token', 'api_key'] and isinstance(v, str):
                try:
                    decrypted_data[k] = cipher.decrypt(v.encode()).decode()
                except Exception:
                    decrypted_data[k] = v  # If decryption fails, keep original
            else:
                decrypted_data[k] = v

        return decrypted_data

    def get_encryption_key(self) -> bytes:
        """
        Get or generate encryption key

        Returns:
            bytes: Encryption key
        """
        # Check if key exists in secure location
        key_file = 'encryption_key.key'

        if os.path.exists(key_file):
            with open(key_file, 'rb') as f:
                return f.read()

        # Generate new key
        key = Fernet.generate_key()

        # Save key securely
        with open(key_file, 'wb') as f:
            f.write(key)

        # Set proper permissions
        os.chmod(key_file, 0o600)

        return key

    def save_to_storage(self):
        """Save tokens to storage backend"""
        if self.storage_backend == 'file':
            with open(self.storage_file, 'w') as f:
                json.dump(self.tokens, f, indent=2)
        elif self.storage_backend == 'memory':
            # No need to save for memory backend
            pass

    def load_from_file(self):
        """Load tokens from file"""
        if os.path.exists(self.storage_file):
            with open(self.storage_file, 'r') as f:
                self.tokens = json.load(f)

    def invalidate_token(self, token_id: str):
        """
        Invalidate/remove a token

        Args:
            token_id: Token ID to invalidate
        """
        with self.lock:
            if token_id in self.tokens:
                del self.tokens[token_id]
                self.save_to_storage()
                return True
            return False

    def list_tokens(self, service_filter: str = None) -> list:
        """
        List stored tokens

        Args:
            service_filter: Filter by service ('canva', 'notebooklm')

        Returns:
            list: List of token metadata
        """
        with self.lock:
            tokens = []
            for token_id, token_record in self.tokens.items():
                if service_filter and token_record['service'] != service_filter:
                    continue

                tokens.append({
                    'token_id': token_id,
                    'service': token_record['service'],
                    'timestamp': token_record['timestamp'],
                    'encrypted': token_record['encrypted']
                })

            return tokens

    def cleanup_expired_tokens(self):
        """
        Clean up expired tokens
        """
        with self.lock:
            expired_tokens = []
            for token_id, token_record in self.tokens.items():
                try:
                    token_data = token_record['data']
                    if 'expires_at' in token_data:
                        expires_at = datetime.fromisoformat(token_data['expires_at'])
                        if expires_at < datetime.now():
                            expired_tokens.append(token_id)
                except Exception:
                    continue

            # Remove expired tokens
            for token_id in expired_tokens:
                del self.tokens[token_id]

            self.save_to_storage()
            return len(expired_tokens)
