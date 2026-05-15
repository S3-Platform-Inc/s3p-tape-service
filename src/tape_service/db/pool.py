from __future__ import annotations

import logging

from psycopg_pool import ConnectionPool

from ..settings import get_settings

log = logging.getLogger(__name__)
_pool: ConnectionPool | None = None


def open_pool() -> ConnectionPool:
    global _pool
    if _pool is not None:
        return _pool
    s = get_settings()
    _pool = ConnectionPool(
        conninfo=str(s.database_url),
        min_size=s.db_pool_min_size,
        max_size=s.db_pool_max_size,
        kwargs={"autocommit": False},
        open=False,
        name="tape-service",
    )
    _pool.open(wait=True, timeout=10.0)
    log.info("db.pool.opened", extra={"min": s.db_pool_min_size, "max": s.db_pool_max_size})
    return _pool


def close_pool() -> None:
    global _pool
    if _pool is None:
        return
    _pool.close()
    _pool = None
    log.info("db.pool.closed")


def get_pool() -> ConnectionPool:
    if _pool is None:
        raise RuntimeError("DB pool not opened; call open_pool() in app lifespan")
    return _pool
