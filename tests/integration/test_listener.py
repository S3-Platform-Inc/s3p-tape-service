import time

import psycopg
import pytest

from tape_service.db.score import save as score_save
from tape_service.store import open_redis
from tape_service.store.tape import (
    append_entries,
    count_entries,
    entries_key,
)
from tape_service.worker.listener import ScoreNotifyListener

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _settings_env(pg_dsn, redis_url, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", pg_dsn)
    monkeypatch.setenv("REDIS_URL", redis_url)
    monkeypatch.setenv("SESSION_SECRET", "x" * 40)
    from tape_service.settings import get_settings
    get_settings.cache_clear()
    open_redis()
    yield


@pytest.fixture
def cleanup_user1(redis_client, pg_dsn):
    redis_client.delete(entries_key(1))
    with psycopg.connect(pg_dsn, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM score.score WHERE user_id = 1")
    yield
    redis_client.delete(entries_key(1))
    with psycopg.connect(pg_dsn, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM score.score WHERE user_id = 1")


def test_listener_removes_tape_entry_on_score(redis_client, pg_dsn, cleanup_user1):
    # 1. pre-seed a tape entry for (user 1, doc 1)
    append_entries(
        redis_client, user_id=1, doc_ids=[1, 2, 3], run_id=0, start_position=0,
    )
    assert count_entries(redis_client, user_id=1) == 3

    # 2. start the listener
    listener = ScoreNotifyListener()
    listener.start()
    try:
        # give the LISTEN connection a moment to register before we INSERT
        time.sleep(0.3)

        # 3. insert a score → PG trigger fires → listener removes the entry
        with psycopg.connect(pg_dsn, autocommit=True) as conn:
            score_save(
                conn, user_id=1, document_id=1, role_id=1,
                verdict={"verdict": "yes"}, comment=None,
            )

        # 4. wait up to ~3s for the listener to react
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            if count_entries(redis_client, user_id=1) == 2:
                break
            time.sleep(0.1)

        assert count_entries(redis_client, user_id=1) == 2
        remaining = sorted(
            int(m) for m in redis_client.zrange(entries_key(1), 0, -1)
        )
        assert remaining == [2, 3]
    finally:
        listener.stop()
