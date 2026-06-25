"""Redis connection management — async Redis client for FastAPI + sync Redis for RQ."""

import logging
from typing import Optional

import redis.asyncio as aioredis
import redis as sync_redis

from app.core.config import settings

logger = logging.getLogger(__name__)

# Async Redis client (FastAPI lifespan)
_async_redis: Optional[aioredis.Redis] = None

# Sync Redis client (RQ worker)
_sync_redis: Optional[sync_redis.Redis] = None

# Connection pool reference
_async_pool: Optional[aioredis.ConnectionPool] = None


async def init_redis() -> None:
    """Initialize Redis connections on application startup."""
    global _async_redis, _async_pool
    try:
        _async_pool = aioredis.ConnectionPool.from_url(
            settings.redis_url,
            decode_responses=True,
            max_connections=50,
            protocol=2,  # RESP2 to avoid RESP3 decode issues
        )
        _async_redis = aioredis.Redis(connection_pool=_async_pool)
        await _async_redis.ping()
        logger.info("Async Redis connected successfully to %s", settings.redis_url)
    except Exception as exc:
        logger.error("Failed to connect async Redis: %s", exc, exc_info=True)
        raise


async def close_redis() -> None:
    """Close Redis connections on application shutdown."""
    global _async_redis, _async_pool
    if _async_redis:
        await _async_redis.aclose()
        _async_redis = None
        logger.info("Async Redis connection closed")
    if _async_pool:
        await _async_pool.disconnect()
        _async_pool = None


def get_async_redis() -> aioredis.Redis:
    """Return the async Redis client (must be initialized first)."""
    if _async_redis is None:
        raise RuntimeError("Async Redis not initialized. Call init_redis() first.")
    return _async_redis


def get_sync_redis() -> sync_redis.Redis:
    """Return a sync Redis connection for RQ.

    Uses a lazy-initialized singleton so the RQ worker and API
    don't fight over the same pool.
    """
    global _sync_redis
    if _sync_redis is None:
        _sync_redis = sync_redis.from_url(
            settings.redis_url,
            decode_responses=False,  # RQ handles its own serialization
            max_connections=10,
            protocol=2,  # RESP2 for stable binary handling
        )
        _sync_redis.ping()
        logger.debug("Sync Redis connected for RQ worker")
    return _sync_redis
