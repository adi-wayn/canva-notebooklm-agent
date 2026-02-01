"""
Integration tests for Redis cache with real Redis container (docker-compose).

These tests require:
- Redis running via docker-compose: make up
- REDIS_URL environment variable pointing to running Redis instance

To run:
  make up
  pytest tests/integration/test_cache_integration.py -v
  make down
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any

import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from config import Settings
from storage.cache import RedisCache


@pytest.fixture
async def real_cache():
    """Create RedisCache connected to real Redis instance."""
    settings = Settings()
    cache = RedisCache(settings)
    await cache.connect()

    # Cleanup before test
    await cache.flush_all()

    yield cache

    # Cleanup after test
    await cache.flush_all()
    await cache.close()


# ============================================================================
# Basic Operations Integration Tests
# ============================================================================


@pytest.mark.asyncio
async def test_set_and_get_dict(real_cache):
    """Test set/get with real Redis."""
    data = {"id": "user1", "name": "Alice", "email": "alice@example.com"}
    await real_cache.set("user:1", data)

    result = await real_cache.get("user:1")
    assert result == data


@pytest.mark.asyncio
async def test_set_and_get_with_ttl(real_cache):
    """Test set with TTL and get."""
    data = {"temp": "data"}
    await real_cache.set("temp:key", data, ttl=3600)

    result = await real_cache.get("temp:key")
    assert result == data

    # Verify TTL is set
    ttl = await real_cache.ttl("temp:key")
    assert ttl > 0


@pytest.mark.asyncio
async def test_delete_key(real_cache):
    """Test delete removes key."""
    await real_cache.set("to_delete", {"data": "value"})
    assert await real_cache.exists("to_delete")

    result = await real_cache.delete("to_delete")
    assert result is True
    assert not await real_cache.exists("to_delete")


@pytest.mark.asyncio
async def test_delete_nonexistent(real_cache):
    """Test delete on nonexistent key."""
    result = await real_cache.delete("nonexistent")
    assert result is False


# ============================================================================
# Tenant-Scoped Operations Integration Tests
# ============================================================================


@pytest.mark.asyncio
async def test_tenant_scoped_set_get(real_cache):
    """Test tenant-scoped keys don't collide."""
    data1 = {"tenant": "acme"}
    data2 = {"tenant": "globex"}

    await real_cache.set("config", data1, tenant_id="acme.com")
    await real_cache.set("config", data2, tenant_id="globex.com")

    result1 = await real_cache.get("config", tenant_id="acme.com")
    result2 = await real_cache.get("config", tenant_id="globex.com")

    assert result1 == data1
    assert result2 == data2


@pytest.mark.asyncio
async def test_tenant_scoped_delete(real_cache):
    """Test tenant-scoped delete only removes tenant's key."""
    await real_cache.set("key", {"a": 1}, tenant_id="acme.com")
    await real_cache.set("key", {"b": 2}, tenant_id="globex.com")

    await real_cache.delete("key", tenant_id="acme.com")

    assert not await real_cache.exists("key", tenant_id="acme.com")
    assert await real_cache.exists("key", tenant_id="globex.com")


# ============================================================================
# Cache Invalidation Integration Tests
# ============================================================================


@pytest.mark.asyncio
async def test_invalidate_pattern(real_cache):
    """Test pattern-based cache invalidation."""
    await real_cache.set("user:1", {"name": "Alice"})
    await real_cache.set("user:2", {"name": "Bob"})
    await real_cache.set("post:1", {"title": "Post"})

    deleted = await real_cache.invalidate_pattern("user:*")

    assert deleted == 2
    assert not await real_cache.exists("user:1")
    assert not await real_cache.exists("user:2")
    assert await real_cache.exists("post:1")


@pytest.mark.asyncio
async def test_invalidate_user(real_cache):
    """Test invalidate_user removes all user cache."""
    await real_cache.set("user:1:profile", {"name": "Alice"}, tenant_id="acme.com")
    await real_cache.set("user:1:sessions", {"count": 3}, tenant_id="acme.com")
    await real_cache.set("user:2:profile", {"name": "Bob"}, tenant_id="acme.com")

    deleted = await real_cache.invalidate_user("1", tenant_id="acme.com")

    assert deleted == 2
    assert not await real_cache.exists("user:1:profile", tenant_id="acme.com")
    assert not await real_cache.exists("user:1:sessions", tenant_id="acme.com")
    assert await real_cache.exists("user:2:profile", tenant_id="acme.com")


@pytest.mark.asyncio
async def test_invalidate_tenant(real_cache):
    """Test invalidate_tenant removes all tenant cache."""
    await real_cache.set("user:1", {"name": "Alice"}, tenant_id="acme.com")
    await real_cache.set("config", {"setting": "value"}, tenant_id="acme.com")
    await real_cache.set("user:1", {"name": "Charlie"}, tenant_id="globex.com")

    deleted = await real_cache.invalidate_tenant("acme.com")

    assert deleted == 2
    assert not await real_cache.exists("user:1", tenant_id="acme.com")
    assert not await real_cache.exists("config", tenant_id="acme.com")
    assert await real_cache.exists("user:1", tenant_id="globex.com")


# ============================================================================
# Session Token Integration Tests
# ============================================================================


@pytest.mark.asyncio
async def test_set_and_get_session_token(real_cache):
    """Test encrypted session token storage/retrieval."""
    token_data = {"user_id": "user1", "scope": "read:write", "exp": 1234567890}

    result = await real_cache.set_session_token(
        "sess_abc123", token_data, ttl=3600, tenant_id="acme.com"
    )
    assert result is True

    retrieved = await real_cache.get_session_token(
        "sess_abc123", tenant_id="acme.com"
    )
    assert retrieved == token_data


@pytest.mark.asyncio
async def test_session_token_encryption(real_cache):
    """Test session token is encrypted at rest."""
    token_data = {"user_id": "user1", "secret": "sensitive"}

    await real_cache.set_session_token(
        "sess_abc", token_data, tenant_id="acme.com"
    )

    # Get raw value from cache to verify encryption
    raw = await real_cache.get("session:sess_abc", tenant_id="acme.com")
    assert raw is not None
    assert "encrypted" in raw
    # Verify it's not stored in plain text
    assert token_data["secret"] not in str(raw)


@pytest.mark.asyncio
async def test_delete_session_token(real_cache):
    """Test session token deletion."""
    token_data = {"user_id": "user1"}

    await real_cache.set_session_token("sess_abc", token_data)
    assert await real_cache.exists("session:sess_abc")

    deleted = await real_cache.delete_session_token("sess_abc")
    assert deleted is True
    assert not await real_cache.exists("session:sess_abc")


# ============================================================================
# TTL & Expiration Integration Tests
# ============================================================================


@pytest.mark.asyncio
async def test_ttl_on_set_with_ttl(real_cache):
    """Test TTL is correctly set."""
    await real_cache.set("key", {"value": 1}, ttl=10)

    ttl = await real_cache.ttl("key")
    assert 8 <= ttl <= 10


@pytest.mark.asyncio
async def test_expire_existing_key(real_cache):
    """Test expire() on existing key."""
    await real_cache.set("key", {"value": 1})

    result = await real_cache.expire("key", 10)
    assert result is True

    ttl = await real_cache.ttl("key")
    assert 8 <= ttl <= 10


@pytest.mark.asyncio
async def test_expire_nonexistent_key(real_cache):
    """Test expire() on nonexistent key."""
    result = await real_cache.expire("nonexistent", 10)
    assert result is False


# ============================================================================
# Health & Info Integration Tests
# ============================================================================


@pytest.mark.asyncio
async def test_health_check_with_real_redis(real_cache):
    """Test health check with real Redis."""
    result = await real_cache.health_check()
    assert result is True


@pytest.mark.asyncio
async def test_info_returns_stats(real_cache):
    """Test info() returns Redis statistics."""
    info = await real_cache.info()

    assert info is not None
    assert "redis_version" in info
    assert "connected_clients" in info
    assert "used_memory" in info
