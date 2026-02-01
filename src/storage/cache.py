"""
Redis cache layer with async support, JSON serialization, and encryption.

Provides:
- Async Redis connection pooling
- Type-safe get/set/delete operations with JSON serialization
- TTL/expiration helpers
- Cache invalidation patterns
- Encrypted session token storage using auth module's encryption

Design:
- Lazy connection (connect on first use)
- All operations are async (no blocking I/O)
- JSON serialization with Pydantic models for type safety
- Tenant-scoped keys (all keys include tenant_id prefix)
- Session tokens encrypted at rest using crypto.encrypt_token()

Usage:
    cache = RedisCache(settings)
    
    # Simple get/set
    await cache.set("user:123", {"name": "Alice"}, ttl=3600)
    user = await cache.get("user:123")
    
    # Session token (encrypted)
    await cache.set_session_token("sess_abc", token_data, ttl=86400)
    token_data = await cache.get_session_token("sess_abc")
    
    # Cache invalidation
    await cache.invalidate_pattern("user:*")
    
    # Cleanup
    await cache.close()
"""

import json
import logging
from typing import Any, Dict, Optional, Type, TypeVar

import redis.asyncio as redis
from pydantic import BaseModel

from src.auth.token_manager import TokenManager
from src.config import Settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class RedisCache:
    """Async Redis cache with encryption and tenant-scoping."""

    def __init__(self, settings: Settings):
        """
        Initialize Redis cache.

        Args:
            settings: Application settings with REDIS_URL
        """
        self.settings = settings
        self.redis_url = settings.REDIS_URL
        self._pool: Optional[redis.Redis] = None
        self._token_manager = TokenManager(settings)

    async def connect(self) -> None:
        """
        Establish Redis connection pool (lazy).

        Called automatically on first operation.
        """
        if self._pool is not None:
            return

        try:
            self._pool = await redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5,
                socket_keepalive=True,
                health_check_interval=30,
            )
            await self._pool.ping()
            logger.info("✅ Redis connected")
        except Exception as e:
            logger.error(f"❌ Redis connection failed: {e}")
            raise

    async def close(self) -> None:
        """
        Close Redis connection pool.

        Safe to call even if not connected.
        """
        if self._pool:
            await self._pool.close(close_connection_pool=True)
            self._pool = None
            logger.info("✅ Redis closed")

    async def health_check(self) -> bool:
        """
        Check Redis connectivity.

        Returns:
            True if Redis is available, False otherwise
        """
        try:
            await self.connect()
            await self._pool.ping()
            return True
        except Exception as e:
            logger.warning(f"Redis health check failed: {e}")
            return False

    def _make_key(self, key: str, tenant_id: Optional[str] = None) -> str:
        """
        Create tenant-scoped cache key.

        Args:
            key: Base key
            tenant_id: Tenant ID (optional; if None, key is global)

        Returns:
            Scoped key: "{tenant_id}:{key}" or "{key}"
        """
        if tenant_id:
            return f"{tenant_id}:{key}"
        return key

    async def get(
        self, key: str, model: Optional[Type[T]] = None, tenant_id: Optional[str] = None
    ) -> Optional[Any]:
        """
        Get value from cache (with optional JSON deserialization).

        Args:
            key: Cache key
            model: Pydantic model to deserialize to (optional)
            tenant_id: Tenant ID for scoping (optional)

        Returns:
            Deserialized value or None if not found
        """
        await self.connect()
        scoped_key = self._make_key(key, tenant_id)

        try:
            value = await self._pool.get(scoped_key)
            if value is None:
                return None

            if model:
                data = json.loads(value)
                return model(**data)
            return json.loads(value)
        except json.JSONDecodeError:
            logger.warning(f"Failed to deserialize cache value for {scoped_key}")
            return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        tenant_id: Optional[str] = None,
    ) -> bool:
        """
        Set value in cache (with JSON serialization).

        Args:
            key: Cache key
            value: Value to cache (will be JSON serialized)
            ttl: Time-to-live in seconds (optional)
            tenant_id: Tenant ID for scoping (optional)

        Returns:
            True if successful
        """
        await self.connect()
        scoped_key = self._make_key(key, tenant_id)

        try:
            # Serialize value
            if isinstance(value, BaseModel):
                json_value = value.model_dump_json()
            else:
                json_value = json.dumps(value)

            # Set with optional TTL
            if ttl:
                await self._pool.setex(scoped_key, ttl, json_value)
            else:
                await self._pool.set(scoped_key, json_value)

            logger.debug(f"Cache SET {scoped_key}")
            return True
        except Exception as e:
            logger.error(f"Cache SET failed for {scoped_key}: {e}")
            return False

    async def delete(self, key: str, tenant_id: Optional[str] = None) -> bool:
        """
        Delete key from cache.

        Args:
            key: Cache key
            tenant_id: Tenant ID for scoping (optional)

        Returns:
            True if key was deleted, False if not found
        """
        await self.connect()
        scoped_key = self._make_key(key, tenant_id)

        try:
            result = await self._pool.delete(scoped_key)
            logger.debug(f"Cache DELETE {scoped_key}")
            return result > 0
        except Exception as e:
            logger.error(f"Cache DELETE failed for {scoped_key}: {e}")
            return False

    async def exists(self, key: str, tenant_id: Optional[str] = None) -> bool:
        """
        Check if key exists in cache.

        Args:
            key: Cache key
            tenant_id: Tenant ID for scoping (optional)

        Returns:
            True if key exists
        """
        await self.connect()
        scoped_key = self._make_key(key, tenant_id)

        try:
            result = await self._pool.exists(scoped_key)
            return result > 0
        except Exception as e:
            logger.error(f"Cache EXISTS check failed for {scoped_key}: {e}")
            return False

    async def expire(
        self, key: str, ttl: int, tenant_id: Optional[str] = None
    ) -> bool:
        """
        Set expiration on existing key.

        Args:
            key: Cache key
            ttl: Time-to-live in seconds
            tenant_id: Tenant ID for scoping (optional)

        Returns:
            True if expiration was set
        """
        await self.connect()
        scoped_key = self._make_key(key, tenant_id)

        try:
            result = await self._pool.expire(scoped_key, ttl)
            logger.debug(f"Cache EXPIRE {scoped_key} ({ttl}s)")
            return result > 0
        except Exception as e:
            logger.error(f"Cache EXPIRE failed for {scoped_key}: {e}")
            return False

    async def ttl(self, key: str, tenant_id: Optional[str] = None) -> int:
        """
        Get remaining TTL for key.

        Args:
            key: Cache key
            tenant_id: Tenant ID for scoping (optional)

        Returns:
            Remaining TTL in seconds, or -1 if no expiry, -2 if not found
        """
        await self.connect()
        scoped_key = self._make_key(key, tenant_id)

        try:
            result = await self._pool.ttl(scoped_key)
            return result
        except Exception as e:
            logger.error(f"Cache TTL check failed for {scoped_key}: {e}")
            return -2

    # ========================================================================
    # Cache Invalidation Patterns
    # ========================================================================

    async def invalidate_pattern(self, pattern: str, tenant_id: Optional[str] = None) -> int:
        """
        Delete all keys matching a pattern (tenant-scoped).

        Args:
            pattern: Pattern (e.g., "user:*", "session:*")
            tenant_id: Tenant ID for scoping (optional)

        Returns:
            Number of keys deleted
        """
        await self.connect()
        scoped_pattern = self._make_key(pattern, tenant_id)

        try:
            cursor = "0"
            deleted = 0
            while True:
                cursor, keys = await self._pool.scan(cursor, match=scoped_pattern)
                if keys:
                    deleted += await self._pool.delete(*keys)
                if cursor == "0":
                    break

            logger.debug(f"Cache INVALIDATE {scoped_pattern} ({deleted} keys)")
            return deleted
        except Exception as e:
            logger.error(f"Cache INVALIDATE failed for {scoped_pattern}: {e}")
            return 0

    async def invalidate_user(self, user_id: str, tenant_id: Optional[str] = None) -> int:
        """
        Invalidate all cache keys for a user.

        Args:
            user_id: User ID
            tenant_id: Tenant ID for scoping (optional)

        Returns:
            Number of keys deleted
        """
        return await self.invalidate_pattern(f"user:{user_id}:*", tenant_id)

    async def invalidate_tenant(self, tenant_id: str) -> int:
        """
        Invalidate all cache keys for a tenant.

        Args:
            tenant_id: Tenant ID

        Returns:
            Number of keys deleted
        """
        return await self.invalidate_pattern("*", tenant_id)

    # ========================================================================
    # Encrypted Session Token Storage
    # ========================================================================

    async def set_session_token(
        self,
        session_id: str,
        token_data: Dict[str, Any],
        ttl: int = 86400,
        tenant_id: Optional[str] = None,
    ) -> bool:
        """
        Store encrypted session token in cache.

        Token is encrypted using auth module's encryption utilities.

        Args:
            session_id: Session ID (key)
            token_data: Token payload (will be JSON encoded and encrypted)
            ttl: Time-to-live in seconds (default 24h)
            tenant_id: Tenant ID for scoping (optional)

        Returns:
            True if successful
        """
        try:
            # Serialize to JSON
            json_data = json.dumps(token_data)

            # Encrypt using token manager
            encrypted = self._token_manager.encrypt_token(json_data)

            # Store encrypted value
            return await self.set(
                f"session:{session_id}",
                {"encrypted": encrypted},
                ttl=ttl,
                tenant_id=tenant_id,
            )
        except Exception as e:
            logger.error(f"Failed to set session token {session_id}: {e}")
            return False

    async def get_session_token(
        self, session_id: str, tenant_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve and decrypt session token from cache.

        Args:
            session_id: Session ID
            tenant_id: Tenant ID for scoping (optional)

        Returns:
            Decrypted token payload or None if not found
        """
        try:
            cached = await self.get(f"session:{session_id}", tenant_id=tenant_id)
            if not cached or "encrypted" not in cached:
                return None

            # Decrypt using token manager
            decrypted = self._token_manager.decrypt_token(cached["encrypted"])

            # Deserialize JSON
            return json.loads(decrypted)
        except Exception as e:
            logger.error(f"Failed to get session token {session_id}: {e}")
            return None

    async def delete_session_token(
        self, session_id: str, tenant_id: Optional[str] = None
    ) -> bool:
        """
        Delete session token from cache.

        Args:
            session_id: Session ID
            tenant_id: Tenant ID for scoping (optional)

        Returns:
            True if deleted
        """
        return await self.delete(f"session:{session_id}", tenant_id=tenant_id)

    # ========================================================================
    # Utility: Cache Warming & Statistics
    # ========================================================================

    async def flush_all(self) -> bool:
        """
        Clear all cache (use with caution in production).

        Returns:
            True if successful
        """
        await self.connect()
        try:
            await self._pool.flushdb()
            logger.warning("Cache FLUSHDB executed")
            return True
        except Exception as e:
            logger.error(f"Cache FLUSHDB failed: {e}")
            return False

    async def info(self) -> Optional[Dict[str, Any]]:
        """
        Get Redis server info.

        Returns:
            Info dict or None on error
        """
        await self.connect()
        try:
            info = await self._pool.info()
            return info
        except Exception as e:
            logger.error(f"Failed to get Redis info: {e}")
            return None
