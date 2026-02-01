"""
Authentication package for Canva-NotebookLM integration

This package provides authentication management for both Canva and NotebookLM APIs.
"""

from .canva_auth_manager import CanvaAuthManager
from .notebooklm_auth_manager import NotebookLMAuthManager
from .token_manager import TokenManager
from .auth_middleware import (
    AuthContext,
    authenticate_request,
    get_auth_context,
    check_scope,
    check_service,
    oauth2_scheme
)

__all__ = [
    'CanvaAuthManager',
    'NotebookLMAuthManager',
    'TokenManager',
    'AuthContext',
    'authenticate_request',
    'get_auth_context',
    'check_scope',
    'check_service',
    'oauth2_scheme'
]
