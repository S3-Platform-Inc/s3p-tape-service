from __future__ import annotations

import logging

import redis

from ..db import get_pool
from ..db.candidates import candidates_for_user
from ..store import get_redis
from ..store import tape as tape_store
from ..store.lock import per_user_lock

log = logging.getLogger(__name__)


def generate_for_user(
    *,
    r: redis.Redis,
    user_id: int,
    dirty: bool,
) -> tuple[str, int]:
    """Generate or top up a single user's tape. Returns (kind, added).
    'kind' is one of 'full', 'incremental', or 'skipped' (lock unavailable
    or no config sources)."""
    cfg = tape_store.get_config(r, user_id=user_id)
    if cfg is None:
        return ("skipped", 0)
    sources = tape_store.get_config_sources(r, user_id=user_id)
    if not sources:
        if dirty:
            tape_store.delete_all_entries(r, user_id=user_id)
            tape_store.clear_dirty(r, user_id=user_id)
        return ("skipped", 0)

    with per_user_lock(r, user_id=user_id) as got:
        if not got:
            log.info("worker.generate.skip_locked", extra={"user_id": user_id})
            return ("skipped", 0)

        kind = "full" if dirty else "incremental"
        run_id = tape_store.create_run(r, user_id=user_id, kind=kind)
        removed = 0
        try:
            if dirty:
                removed = tape_store.delete_all_entries(r, user_id=user_id)
                start = 0
                existing: list[int] = []
            else:
                start = tape_store.max_position(r, user_id=user_id) + 1
                page = tape_store.list_entries_page(
                    r,
                    user_id=user_id,
                    after_position=None,
                    limit=10_000,
                )
                existing = [doc_id for (_pos, doc_id) in page]

            with get_pool().connection() as conn:
                conn.autocommit = True
                doc_ids = candidates_for_user(
                    conn,
                    user_id=user_id,
                    source_ids=sources,
                    date_from=cfg.date_from,
                    date_to=cfg.date_to,
                    ordering=cfg.ordering,
                    exclude_ids=existing,
                )

            appended = tape_store.append_entries(
                r,
                user_id=user_id,
                doc_ids=doc_ids,
                run_id=run_id,
                start_position=start,
            )
            added = len(appended)
            if dirty:
                tape_store.clear_dirty(r, user_id=user_id)
            tape_store.finish_run(
                r,
                user_id=user_id,
                run_id=run_id,
                status="ok",
                added=added,
                removed=removed,
            )
            log.info(
                "worker.generate.ok",
                extra={
                    "user_id": user_id,
                    "kind": kind,
                    "added": added,
                    "removed": removed,
                },
            )
            return (kind, added)
        except Exception:
            tape_store.finish_run(
                r,
                user_id=user_id,
                run_id=run_id,
                status="error",
                added=0,
                removed=removed,
            )
            log.exception("worker.generate.error", extra={"user_id": user_id})
            raise


def tick() -> None:
    """Per-scheduler-tick entry: scan users with config, run generation."""
    r = get_redis()
    users = tape_store.list_users_with_config(r)
    log.info("worker.tick.users", extra={"count": len(users)})
    for user_id, dirty in users:
        try:
            generate_for_user(r=r, user_id=user_id, dirty=dirty)
        except Exception:
            log.exception("worker.generate.unhandled", extra={"user_id": user_id})
