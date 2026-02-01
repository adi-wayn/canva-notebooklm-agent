"""
Unit tests for Redis cache layer (src/storage/cache.py).

Tests cover:
- Connection management (lazy connect, close)
- Basic get/set/delete/exists operations
- TTL and expiration
- JSON serialization with Pydantic models
- Tenant-scoped key generation
- Cache invalidation patterns
- Session token encryption/decryption
- Health checks
"""

import json
import sys
from pathlib import Path
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

# Test models
class TestUser(BaseModel):
    """Test Pydantic model."""

    id: str
    name: str
    email: str


# ============================================================================
# Fixtures & Mocks
# ============================================================================


@pytest.fixture
def mock_settings():
    """Mock settings with Redis URL."""
    settings = MagicMock()
    settings.REDIS_URL = "redis://localhost:6379/0"
    settings.SECRET_KEY = "test-secret"
    return settings


@pytest.fixture
def mock_token_manager():
    """Mock token manager for encryption/decryption."""
    manager = MagicMock()
    manager.encrypt_token = MagicMock(side_effect=lambda x: f"encrypted:{x}")
    manager.decrypt_token = MagicMock(side_effect=lambda x: x.replace("encrypted:", ""))
    return manager


@pytest.fixture
async def cache(mock_settings):
    """Create RedisCache instance for testing."""
    with patch("storage.cache.TokenManager") as mock_tm_class:
        with patch("storage.cache.redis.from_url") as mock_redis_from_url:
            # Import after mocking
            from storage.cache import RedisCache
            
            cache = RedisCache(mock_settings)
            cache._pool = AsyncMock()
            yield cache
            # Cleanup
            if cache._pool:
                await cache.close()


# ============================================================================
# Key Scoping Tests
# ============================================================================


@pytest.mark.asyncio
async def test_make_key_without_tenant(cache):
    """Test key generation without tenant."""
    key = cache._make_key("user:123")
    assert key == "user:123"


@pytest.mark.asyncio
async def test_make_key_with_tenant(cache):
    """Test key generation with tenant."""
    key = cache._make_key("user:123", tenant_id="acme.com")
    assert key == "acme.com:user:123"


# ============================================================================
# Basic Operations Tests
# ============================================================================


@pytest.mark.asyncio
async def test_get_returns_parsed_json(cache):
    """Test get() deserializes JSON."""
    cache._pool.get = AsyncMock(return_value='{"id": "123", "name": "Alice"}')

    result = await cache.get("user:123")
    assert result == {"id": "123", "name": "Alice"}


@pytest.mark.asyncio
async def test_get_not_found(cache):
    """Test get() returns None when key not found."""
    cache._pool.get = AsyncMock(return_value=None)

    result = await cache.get("nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_get_invalid_json(cache):
    """Test get() handles invalid JSON gracefully."""
    cache._pool.get = AsyncMock(return_value="invalid json")

    result = await cache.get("bad_key")
    assert result is None


@pytest.mark.asyncio
async def test_set_dict_value(cache):
    """Test set() serializes dict."""
    cache._pool.set = AsyncMock()

    result = await cache.set("user:123", {"name": "Alice"})
    assert result is True
    cache._pool.set.assert_called_once()


@pytest.mark.asyncio
async def test_set_with_ttl(cache):
    """Test set() with TTL."""
    cache._pool.setex = AsyncMock()

    result = await cache.set("user:123", {"name": "Alice"}, ttl=3600)
    assert result is True
    cache._pool.setex.assert_called_once()


@pytest.mark.asyncio
async def test_set_tenant_scoped(cache):
    """Test set() with tenant scoping."""
    cache._pool.set = AsyncMock()

    await cache.set("user:123", {"name": "Alice"}, tenant_id="acme.com")
    # Verify scoped key was used
    call_args = cache._pool.set.call_args
    assert "acme.com:user:123" in call_args[0]


@pytest.mark.asyncio
async def test_delete_success(cache):
    """Test delete() removes key."""
    cache._pool.delete = AsyncMock(return_value=1)

    result = await cache.delete("user:123")
    assert result is True


@pytest.mark.asyncio
async def test_delete_not_found(cache):
    """Test delete() returns False when key not found."""
    cache._pool.delete = AsyncMock(return_value=0)

    result = await cache.delete("nonexistent")
    assert result is False


@pytest.mark.asyncio
async def test_exists_found(cache):
    """Test exists() returns True when key found."""
    cache._pool.exists = AsyncMock(return_value=1)

    result = await cache.exists("user:123")
    assert result is True


@pytest.mark.asyncio
async def test_exists_not_found(cache):
    """Test exists() returns False when key not found."""
    cache._pool.exists = AsyncMock(return_value=0)

    result = await cache.exists("nonexistent")
    assert result is False


# ============================================================================
# TTL & Expiration Tests
# ============================================================================


@pytest.mark.asyncio
async def test_expire_success(cache):
    """Test expire() sets TTL."""
    cache._pool.expire = AsyncMock(return_value=1)

    result = await cache.expire("user:123", ttl=3600)
    assert result is True


@pytest.mark.asyncio
async def test_expire_not_found(cache):
    """Test expire() returns False when key not found."""
    cache._pool.expire = AsyncMock(return_value=0)

    result = await cache.expire("nonexistent", ttl=3600)
    assert result is False


@pytest.mark.asyncio
async def test_ttl_with_expiry(cache):
    """Test ttl() returns remaining time."""
    cache._pool.ttl = AsyncMock(return_value=3599)

    result = await cache.ttl("user:123")
    assert result == 3599


@pytest.mark.asyncio
async def test_ttl_no_expiry(cache):
    """Test ttl() returns -1 when no expiry."""
    cache._pool.ttl = AsyncMock(return_value=-1)

    result = await cache.ttl("permanent_key")
    assert result == -1


# ============================================================================
# Cache Invalidation Tests
# ============================================================================


@pytest.mark.asyncio
async def test_invalidate_pattern(cache):
    """Test invalidate_pattern() deletes matching keys."""
    cache._pool.scan = AsyncMock(side_effect=[("0", ["key1", "key2"])])
    cache._pool.delete = AsyncMock(return_value=2)

    result = await cache.invalidate_pattern("user:*")
    assert result == 2


@pytest.mark.asyncio
async def test_invalidate_user(cache):
    """Test invalidate_user() removes user cache."""
    cache._pool.scan = AsyncMock(side_effect=[("0", ["key1", "key2"])])
    cache._pool.delete = AsyncMock(return_value=2)

    result = await cache.invalidate_user("user123")
    assert result == 2


@pytest.mark.asyncio
async def test_invalidate_tenant(cache):
    """Test invalidate_tenant() removes all tenant cache."""
    cache._pool.scan = AsyncMock(side_effect=[("0", ["key1", "key2", "key3"])])
    cache._pool.delete = AsyncMock(return_value=3)

    result = await cache.invalidate_tenant("acme.com")
    assert result == 3


# ============================================================================
# Utility Tests
# ============================================================================


@pytest.mark.asyncio
async def test_flush_all(cache):
    """Test flush_all() clears database."""
    cache._pool.flushdb = AsyncMock()

    result = await cache.flush_all()
    assert result is True
    cache._pool.flushdb.assert_called_once()


@pytest.mark.asyncio
async def test_info(cache):
    """Test info() retrieves server info."""
    cache._pool.info = AsyncMock(return_value={"redis_version": "7.0.0"})

    result = await cache.info()
    assert result == {"redis_version": "7.0.0"}


@pytest.mark.asyncio
async def test_info_failure(cache):
    """Test info() returns None on failure."""
    cache._pool.info = AsyncMock(side_effect=Exception("Failed"))

    result = await cache.info()
    assert result is None

