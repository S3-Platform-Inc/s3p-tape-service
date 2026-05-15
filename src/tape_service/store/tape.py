from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

import redis

DisplayMode = Literal["compact", "detailed"]
Ordering = Literal["asc", "desc"]


def cfg_key(user_id: int) -> str:
    return f"tape:cfg:{user_id}"


def cfg_sources_key(user_id: int) -> str:
    return f"tape:cfg:src:{user_id}"


def entries_key(user_id: int) -> str:
    return f"tape:entries:{user_id}"


def runs_key(user_id: int) -> str:
    return f"tape:runs:{user_id}"


RUN_COUNTER_KEY = "tape:run:counter"


@dataclass(frozen=True)
class TapeConfig:
    user_id: int
    ordering: Ordering
    display_mode: DisplayMode
    page_size: int
    date_from: datetime | None
    date_to: datetime | None
    dirty: bool


def _iso_or_none(s: str | None) -> datetime | None:
    if not s:
        return None
    return datetime.fromisoformat(s)


def get_config(client: redis.Redis, *, user_id: int) -> TapeConfig | None:
    raw = client.hgetall(cfg_key(user_id))
    if not raw:
        return None
    return TapeConfig(
        user_id=user_id,
        ordering=raw.get("ordering", "desc"),  # type: ignore[arg-type]
        display_mode=raw.get("display_mode", "compact"),  # type: ignore[arg-type]
        page_size=int(raw.get("page_size", 20)),
        date_from=_iso_or_none(raw.get("date_from")),
        date_to=_iso_or_none(raw.get("date_to")),
        dirty=raw.get("dirty") == "1",
    )


def upsert_config(
    client: redis.Redis,
    *,
    user_id: int,
    ordering: Ordering,
    display_mode: DisplayMode,
    page_size: int,
    date_from: datetime | None,
    date_to: datetime | None,
) -> None:
    mapping = {
        "ordering": ordering,
        "display_mode": display_mode,
        "page_size": str(page_size),
        "date_from": date_from.isoformat() if date_from else "",
        "date_to": date_to.isoformat() if date_to else "",
        "dirty": "1",
        "updated_at": datetime.now(UTC).isoformat(),
    }
    client.hset(cfg_key(user_id), mapping=mapping)


def list_users_with_config(client: redis.Redis) -> list[tuple[int, bool]]:
    """SCAN the tape:cfg:<user_id> hashes and return [(user_id, dirty)].

    Skips tape:cfg:src:<user_id> sets (different key namespace prefix).
    Uses SCAN, not KEYS, so it stays cheap on large instances.
    """
    out: list[tuple[int, bool]] = []
    for raw_key in client.scan_iter(match="tape:cfg:*", count=200):
        key = raw_key if isinstance(raw_key, str) else raw_key.decode("utf-8")
        if key.startswith("tape:cfg:src:"):
            continue
        suffix = key.removeprefix("tape:cfg:")
        try:
            uid = int(suffix)
        except ValueError:
            continue
        dirty = client.hget(key, "dirty") == "1"
        out.append((uid, dirty))
    return out


def mark_dirty(client: redis.Redis, *, user_id: int) -> None:
    client.hset(cfg_key(user_id), "dirty", "1")


def clear_dirty(client: redis.Redis, *, user_id: int) -> None:
    client.hset(cfg_key(user_id), "dirty", "0")


def get_config_sources(client: redis.Redis, *, user_id: int) -> list[int]:
    members = client.smembers(cfg_sources_key(user_id))
    return sorted(int(m) for m in members)


def set_config_sources(
    client: redis.Redis, *, user_id: int, source_ids: list[int]
) -> None:
    key = cfg_sources_key(user_id)
    pipe = client.pipeline(transaction=True)
    pipe.delete(key)
    if source_ids:
        pipe.sadd(key, *(str(s) for s in source_ids))
    pipe.hset(cfg_key(user_id), "dirty", "1")
    pipe.execute()


# --- entries ----------------------------------------------------------------


def list_entries_page(
    client: redis.Redis, *, user_id: int, after_position: int | None, limit: int
) -> list[tuple[int, int]]:
    """Return [(position, document_id), ...] up to `limit`, ordered by position."""
    key = entries_key(user_id)
    if after_position is None:
        rows = client.zrange(key, 0, limit - 1, withscores=True)
    else:
        rows = client.zrangebyscore(
            key, min=f"({after_position}", max="+inf",
            start=0, num=limit, withscores=True,
        )
    return [(int(score), int(member)) for member, score in rows]


def count_entries(client: redis.Redis, *, user_id: int) -> int:
    return int(client.zcard(entries_key(user_id)))


def max_position(client: redis.Redis, *, user_id: int) -> int:
    last = client.zrange(entries_key(user_id), -1, -1, withscores=True)
    if not last:
        return -1
    return int(last[0][1])


def append_entries(
    client: redis.Redis,
    *,
    user_id: int,
    doc_ids: list[int],
    run_id: int,
    start_position: int,
) -> int:
    """Append docs to the user's tape with positions starting at `start_position`.
    Existing (user, doc) pairs are skipped — sorted-set members are unique."""
    if not doc_ids:
        return 0
    key = entries_key(user_id)
    pipe = client.pipeline(transaction=False)
    for i, doc_id in enumerate(doc_ids):
        pipe.zadd(key, {str(doc_id): start_position + i}, nx=True)
    results = pipe.execute()
    _ = run_id  # tracked in tape.run; entries themselves carry only position
    return sum(int(r) for r in results)


def remove_entry(client: redis.Redis, *, user_id: int, document_id: int) -> int:
    return int(client.zrem(entries_key(user_id), str(document_id)))


def delete_all_entries(client: redis.Redis, *, user_id: int) -> int:
    pipe = client.pipeline(transaction=True)
    pipe.zcard(entries_key(user_id))
    pipe.delete(entries_key(user_id))
    n, _ = pipe.execute()
    return int(n)


# --- runs -------------------------------------------------------------------


def create_run(client: redis.Redis, *, user_id: int, kind: str) -> int:
    run_id = int(client.incr(RUN_COUNTER_KEY))
    client.xadd(
        runs_key(user_id),
        {
            "id": str(run_id),
            "kind": kind,
            "status": "running",
            "started_at": datetime.now(UTC).isoformat(),
        },
        maxlen=100,
        approximate=True,
    )
    return run_id


def finish_run(
    client: redis.Redis, *, user_id: int, run_id: int, status: str,
    added: int, removed: int,
) -> None:
    client.xadd(
        runs_key(user_id),
        {
            "id": str(run_id),
            "status": status,
            "finished_at": datetime.now(UTC).isoformat(),
            "added": str(added),
            "removed": str(removed),
        },
        maxlen=100,
        approximate=True,
    )
