from __future__ import annotations

import json
import logging
import threading

import psycopg

from ..settings import get_settings
from ..store import get_redis
from ..store import tape as tape_store

log = logging.getLogger(__name__)

CHANNEL = "tape_score_inserted"


class ScoreNotifyListener:
    """Daemon thread holding a LISTEN connection to the platform DB.
    On every pg_notify('tape_score_inserted', {user_id, document_id})
    it removes the matching tape entry from Redis.

    The trigger lives in docs/sql/03-score-notify.sql (upstream owned
    by s3p-database). Covers non-web scoring paths (e.g. the legacy
    telegram bot) so all expert scores reliably clear the Redis tape.
    """

    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._conn: psycopg.Connection | None = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run, name="tape-score-listener", daemon=True,
        )
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            self._thread = None

    def _run(self) -> None:
        s = get_settings()
        dsn = str(s.database_url)
        log.info("worker.listener.start", extra={"channel": CHANNEL})
        try:
            with psycopg.connect(dsn, autocommit=True) as conn:
                self._conn = conn
                with conn.cursor() as cur:
                    cur.execute(f"LISTEN {CHANNEL}")
                while not self._stop.is_set():
                    for notify in conn.notifies(timeout=1.0):
                        if notify.channel != CHANNEL:
                            continue
                        self._handle(notify.payload)
        except psycopg.OperationalError:
            if not self._stop.is_set():
                log.exception("worker.listener.connection_lost")
        finally:
            self._conn = None
            log.info("worker.listener.stop")

    def _handle(self, payload: str) -> None:
        try:
            data = json.loads(payload)
            user_id = int(data["user_id"])
            doc_id = int(data["document_id"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            log.warning("worker.listener.bad_payload", extra={"raw": payload[:200]})
            return
        try:
            removed = tape_store.remove_entry(
                get_redis(), user_id=user_id, document_id=doc_id,
            )
            log.info(
                "worker.listener.removed",
                extra={"user_id": user_id, "document_id": doc_id, "removed": removed},
            )
        except Exception:
            log.exception(
                "worker.listener.remove_failed",
                extra={"user_id": user_id, "document_id": doc_id},
            )
