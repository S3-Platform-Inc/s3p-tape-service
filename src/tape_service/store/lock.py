from __future__ import annotations

import secrets
from collections.abc import Iterator
from contextlib import contextmanager

import redis

from ..settings import get_settings

# Lua: only delete the key if its value still matches our token. Prevents
# a release call from freeing a lock the TTL already expired and another
# worker re-acquired.
_RELEASE = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('DEL', KEYS[1])
end
return 0
"""


def _key(user_id: int) -> str:
    return f"tape:lock:{user_id}"


@contextmanager
def per_user_lock(client: redis.Redis, *, user_id: int) -> Iterator[bool]:
    """Yield True if the lock was acquired, False otherwise.

    Lock TTL comes from settings.worker_advisory_lock_ttl_seconds; if the
    worker crashes mid-job the lock auto-releases when the TTL elapses.
    """
    s = get_settings()
    token = secrets.token_hex(16)
    got = client.set(_key(user_id), token, nx=True, ex=s.worker_advisory_lock_ttl_seconds)
    try:
        yield bool(got)
    finally:
        if got:
            client.eval(_RELEASE, 1, _key(user_id), token)
