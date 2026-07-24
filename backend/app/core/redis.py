# app/core/redis.py
import logging
from typing import AsyncGenerator
from redis.asyncio import Redis, ConnectionPool
from app.core.config import get_settings

logger = logging.getLogger(__name__)

_redis_pool: ConnectionPool | None = None


def get_redis_pool() -> ConnectionPool:
    global _redis_pool
    if _redis_pool is None:
        settings = get_settings()
        _redis_pool = ConnectionPool.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            max_connections=20,
        )
    return _redis_pool


async def get_redis() -> AsyncGenerator[Redis, None]:
    """FastAPI Dependency for obtaining an async Redis client instance."""
    pool = get_redis_pool()
    client = Redis(connection_pool=pool)
    try:
        yield client
    finally:
        await client.aclose()


async def close_redis_pool() -> None:
    """Clean up Redis connections on application shutdown."""
    global _redis_pool
    if _redis_pool is not None:
        await _redis_pool.disconnect()
        logger.info("Redis connection pool disconnected.")
        _redis_pool = None