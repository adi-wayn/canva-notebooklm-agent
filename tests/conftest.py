"""Pytest configuration and shared fixtures for async tests."""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Configure pytest-asyncio for async test support
pytest_plugins = ("pytest_asyncio",)

# Add src to Python path so imports work
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Mock required environment variables BEFORE any module imports
# These are required by Settings classes in config.py

# Core settings
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
# Use SQLite for testing (in-memory database)
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret-key-32-bytes-minimum-!!")
os.environ.setdefault("ENVIRONMENT", "development")

# DatabaseSettings (DATABASE_ prefix) - SQLite test DB
os.environ.setdefault("DATABASE_HOST", ":memory:")
os.environ.setdefault("DATABASE_PORT", "0")
os.environ.setdefault("DATABASE_NAME", ":memory:")
os.environ.setdefault("DATABASE_USERNAME", "test")
os.environ.setdefault("DATABASE_PASSWORD", "test")

# RedisSettings (REDIS_ prefix)
os.environ.setdefault("REDIS_HOST", "localhost")
os.environ.setdefault("REDIS_PORT", "6379")

# CanvaSettings (CANVA_ prefix)
os.environ.setdefault("CANVA_CLIENT_ID", "test-client-id")
os.environ.setdefault("CANVA_CLIENT_SECRET", "test-client-secret")

# NotebookLMSettings (NOTEBOOKLM_ prefix)
os.environ.setdefault("NOTEBOOKLM_API_KEY", "test-notebooklm-key")

# LLMSettings (LLM_ prefix)
os.environ.setdefault("LLM_API_KEY", "test-llm-api-key")

# AuthSettings (AUTH_ prefix)
os.environ.setdefault("AUTH_JWT_SECRET", "test-jwt-secret-32-bytes-minimum-!!")

# ObservabilitySettings (OBSERVABILITY_ prefix)
os.environ.setdefault("OBSERVABILITY_LOG_LEVEL", "INFO")

# VaultSettings (VAULT_ prefix) - optional, set dummy if needed
os.environ.setdefault("VAULT_ADDRESS", "http://localhost:8200")


@pytest.fixture
def mock_token_manager():
    """Mock TokenManager for encryption/decryption."""
    manager = AsyncMock()
    manager.encrypt_token = MagicMock(side_effect=lambda x: f"encrypted:{x}")
    manager.decrypt_token = MagicMock(side_effect=lambda x: x.replace("encrypted:", ""))
    return manager


@pytest.fixture
async def cache(mock_token_manager):
    """Async fixture: RedisCache instance for unit testing with mocked Redis."""
    from storage.cache import RedisCache

    with patch("storage.cache.TokenManager", return_value=mock_token_manager):
        with patch("storage.cache.redis.from_url") as mock_redis_from_url:
            # Create mock Redis client
            mock_redis = AsyncMock()
            mock_redis.get = AsyncMock(return_value=None)
            mock_redis.set = AsyncMock(return_value=True)
            mock_redis.delete = AsyncMock(return_value=1)
            mock_redis.exists = AsyncMock(return_value=False)
            mock_redis.expire = AsyncMock(return_value=True)
            mock_redis.ttl = AsyncMock(return_value=-1)
            mock_redis.keys = AsyncMock(return_value=[])
            mock_redis.scan_iter = AsyncMock(return_value=[])
            mock_redis.flushdb = AsyncMock(return_value=True)
            mock_redis.info = AsyncMock(return_value={"connected_clients": 1})
            mock_redis.close = AsyncMock(return_value=None)

            mock_redis_from_url.return_value = mock_redis

            # Create cache instance
            cache_instance = RedisCache(
                redis_url="redis://localhost:6379/0",
                token_manager=mock_token_manager,
            )
            cache_instance.redis = mock_redis

            yield cache_instance

            # Cleanup
            try:
                await cache_instance.close()
            except Exception:
                pass


@pytest.fixture
def mock_token_manager():
    """Mock TokenManager for encryption/decryption."""
    manager = AsyncMock()
    manager.encrypt_token = MagicMock(side_effect=lambda x: f"encrypted:{x}")
    manager.decrypt_token = MagicMock(side_effect=lambda x: x.replace("encrypted:", ""))
    return manager


@pytest.fixture
async def cache(mock_token_manager):
    """Async fixture: RedisCache instance for unit testing with mocked Redis."""
    from storage.cache import RedisCache

    with patch("storage.cache.TokenManager", return_value=mock_token_manager):
        with patch("storage.cache.redis.from_url") as mock_redis_from_url:
            # Create mock Redis client
            mock_redis = AsyncMock()
            mock_redis.get = AsyncMock(return_value=None)
            mock_redis.set = AsyncMock(return_value=True)
            mock_redis.delete = AsyncMock(return_value=1)
            mock_redis.exists = AsyncMock(return_value=False)
            mock_redis.expire = AsyncMock(return_value=True)
            mock_redis.ttl = AsyncMock(return_value=-1)
            mock_redis.keys = AsyncMock(return_value=[])
            mock_redis.scan_iter = AsyncMock(return_value=[])
            mock_redis.flushdb = AsyncMock(return_value=True)
            mock_redis.info = AsyncMock(return_value={"connected_clients": 1})
            mock_redis.close = AsyncMock(return_value=None)

            mock_redis_from_url.return_value = mock_redis

            # Create cache instance
            cache_instance = RedisCache(
                redis_url="redis://localhost:6379/0",
                token_manager=mock_token_manager,
            )
            cache_instance.redis = mock_redis

            yield cache_instance

            # Cleanup
            try:
                await cache_instance.close()
            except Exception:
                pass
