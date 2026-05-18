from __future__ import annotations

import json
from datetime import UTC, datetime

import redis

CHANNEL_PREFIX = "tape:events:"


def channel_for(user_id: int) -> str:
    return f"{CHANNEL_PREFIX}{user_id}"


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _envelope(event_type: str, user_id: int, **extra: object) -> dict:
    return {"type": event_type, "user_id": int(user_id), "at": _now_iso(), **extra}


def publish(client: redis.Redis, *, user_id: int, event: dict) -> int:
    """Publish a single event frame to the user's pubsub channel.
    Returns the number of receivers (informational; callers don't act on it)."""
    return int(client.publish(channel_for(user_id), json.dumps(event)))


def make_lock_acquired(user_id: int) -> dict:
    return _envelope("lock.acquired", user_id)


def make_lock_released(user_id: int) -> dict:
    return _envelope("lock.released", user_id)


def make_schedule_queued(user_id: int, reason: str) -> dict:
    return _envelope("schedule.queued", user_id, reason=reason)


def make_schedule_started(user_id: int, run_id: int, kind: str) -> dict:
    return _envelope("schedule.started", user_id, run_id=int(run_id), kind=kind)


def make_schedule_completed(user_id: int, run_id: int, status: str) -> dict:
    return _envelope("schedule.completed", user_id, run_id=int(run_id), status=status)


def make_tape_entry_added(user_id: int, position: int, document_id: int) -> dict:
    return _envelope(
        "tape.entry_added",
        user_id,
        position=int(position),
        document_id=int(document_id),
    )


def make_tape_entry_removed(user_id: int, document_id: int) -> dict:
    return _envelope("tape.entry_removed", user_id, document_id=int(document_id))


def make_tape_regenerated(user_id: int, kind: str, added: int, removed: int) -> dict:
    return _envelope(
        "tape.regenerated",
        user_id,
        kind=kind,
        added=int(added),
        removed=int(removed),
    )
