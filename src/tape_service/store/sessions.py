from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import redis

from ..settings import get_settings

# Keys: sess:<sha256-hex> -> JSON {user_id, created_at, expires_at, last_seen}
# TTL: sliding, equal to session_idle_ttl_days. Absolute expiry is enforced
# in Python by comparing expires_at; Redis idle-expires the key but we
# never trust the TTL alone.


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _key(session_hash: str) -> str:
    return f"sess:{session_hash}"


@dataclass(frozen=True)
class Session:
    user_id: int
    created_at: datetime
    expires_at: datetime
    last_seen: datetime


def issue(client: redis.Redis, *, user_id: int) -> str:
    """Mint a fresh raw session id, store its hash, return the raw id."""
    s = get_settings()
    raw = secrets.token_urlsafe(48)
    now = datetime.now(UTC)
    abs_expires = now + timedelta(days=s.session_absolute_ttl_days)
    idle_seconds = s.session_idle_ttl_days * 86400
    payload = {
        "user_id": int(user_id),
        "created_at": now.isoformat(),
        "expires_at": abs_expires.isoformat(),
        "last_seen": now.isoformat(),
    }
    client.set(_key(_hash(raw)), json.dumps(payload), ex=idle_seconds)
    return raw


def validate(client: redis.Redis, *, raw_session: str) -> Session | None:
    """Look up a session by raw id. Enforce absolute + idle expiry.
    Refresh last_seen and the idle TTL on every successful validate."""
    s = get_settings()
    h = _hash(raw_session)
    blob = client.get(_key(h))
    if blob is None:
        return None
    try:
        payload = json.loads(blob)
    except (TypeError, ValueError):
        client.delete(_key(h))
        return None

    now = datetime.now(UTC)
    try:
        created = datetime.fromisoformat(payload["created_at"])
        expires = datetime.fromisoformat(payload["expires_at"])
        last_seen = datetime.fromisoformat(payload["last_seen"])
    except (KeyError, TypeError, ValueError):
        client.delete(_key(h))
        return None
    _ = last_seen  # value not used; kept as a structural check

    if expires <= now:
        client.delete(_key(h))
        return None

    payload["last_seen"] = now.isoformat()
    idle_seconds = s.session_idle_ttl_days * 86400
    client.set(_key(h), json.dumps(payload), ex=idle_seconds)
    return Session(
        user_id=int(payload["user_id"]),
        created_at=created,
        expires_at=expires,
        last_seen=now,
    )


def revoke(client: redis.Redis, *, raw_session: str) -> None:
    client.delete(_key(_hash(raw_session)))


def constant_time_equal(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))
