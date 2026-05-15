from __future__ import annotations

import logging

import redis

from ..settings import get_settings

log = logging.getLogger(__name__)

_pool: redis.ConnectionPool | None = None


def open_redis() -> redis.Redis:
    """Open the module-level Redis connection pool. Idempotent."""
    global _pool
    if _pool is not None:
        return redis.Redis(connection_pool=_pool, decode_responses=True)
    s = get_settings()
    _pool = redis.ConnectionPool.from_url(
        str(s.redis_url),
        max_connections=s.redis_max_connections,
        decode_responses=True,
    )
    # Eager ping so a misconfigured Redis fails fast at startup, not at
    # first request.
    client = redis.Redis(connection_pool=_pool, decode_responses=True)
    client.ping()
    log.info("redis.pool.opened", extra={"max": s.redis_max_connections})
    return client


def close_redis() -> None:
    global _pool
    if _pool is None:
        return
    _pool.close()
    _pool = None
    log.info("redis.pool.closed")


def get_redis() -> redis.Redis:
    """Return a Redis client bound to the module-level pool."""
    if _pool is None:
        raise RuntimeError(
            "Redis pool not opened; call open_redis() in app/worker lifespan",
        )
    return redis.Redis(connection_pool=_pool, decode_responses=True)
