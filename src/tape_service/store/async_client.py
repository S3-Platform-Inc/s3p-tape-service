from __future__ import annotations

import logging

import redis.asyncio as aioredis

from ..settings import get_settings

log = logging.getLogger(__name__)

_pool: aioredis.ConnectionPool | None = None


async def open_async_redis() -> aioredis.Redis:
    """Open the module-level async Redis connection pool. Idempotent.

    Used by the WebSocket handler so its pubsub listen loop yields to
    the event loop. HTTP/worker paths keep using the sync client at
    store/client.py."""
    global _pool
    if _pool is not None:
        return aioredis.Redis(connection_pool=_pool)
    s = get_settings()
    _pool = aioredis.ConnectionPool.from_url(
        str(s.redis_url),
        max_connections=s.redis_max_connections,
        decode_responses=True,
    )
    client = aioredis.Redis(connection_pool=_pool)
    await client.ping()
    log.info("redis.async_pool.opened", extra={"max": s.redis_max_connections})
    return client


async def close_async_redis() -> None:
    global _pool
    if _pool is None:
        return
    await _pool.aclose()
    _pool = None
    log.info("redis.async_pool.closed")


def get_async_redis() -> aioredis.Redis:
    """Return an async Redis client bound to the module-level pool."""
    if _pool is None:
        raise RuntimeError(
            "Async Redis pool not opened; call open_async_redis() in app lifespan",
        )
    return aioredis.Redis(connection_pool=_pool)
