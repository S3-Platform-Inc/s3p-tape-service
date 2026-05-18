import psycopg
import pytest

from tape_service.store import open_redis
from tape_service.store.tape import (
    append_entries,
    cfg_key,
    cfg_sources_key,
    clear_dirty,
    count_entries,
    entries_key,
    list_entries_page,
    set_config_sources,
    upsert_config,
)
from tape_service.worker.generator import generate_for_user, tick

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _pools(pg_dsn, redis_url, monkeypatch):
    """The generator uses get_pool()/get_redis() so it needs both
    pools open. Mirror what tests/conftest.settings_env does for app
    tests so generator tests can run standalone."""
    monkeypatch.setenv("DATABASE_URL", pg_dsn)
    monkeypatch.setenv("REDIS_URL", redis_url)
    monkeypatch.setenv("SESSION_SECRET", "x" * 40)
    from tape_service.db.pool import close_pool, open_pool
    from tape_service.settings import get_settings

    get_settings.cache_clear()
    open_pool()
    open_redis()
    yield
    close_pool()


@pytest.fixture
def clean_alpha(redis_client, pg_dsn):
    redis_client.delete(cfg_key(1), cfg_sources_key(1), entries_key(1))
    with psycopg.connect(pg_dsn, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM score.score WHERE user_id = 1")
    yield
    redis_client.delete(cfg_key(1), cfg_sources_key(1), entries_key(1))


def test_full_rebuild_populates_tape(redis_client, clean_alpha):
    upsert_config(
        redis_client,
        user_id=1,
        ordering="asc",
        display_mode="compact",
        page_size=20,
        date_from=None,
        date_to=None,
    )
    set_config_sources(redis_client, user_id=1, source_ids=[1, 2])

    kind, added = generate_for_user(r=redis_client, user_id=1, dirty=True)
    assert kind == "full"
    assert added == 7
    assert count_entries(redis_client, user_id=1) == 7

    page = list_entries_page(redis_client, user_id=1, after_position=None, limit=10)
    doc_ids = [d for (_p, d) in page]
    # ASC by published over sources {1, 2}: doc 1 (05-01), 2 (05-03),
    # 3 (05-05), 4 (05-08), 5 (05-10), 14 (05-15), 15 (05-16).
    assert doc_ids == [1, 2, 3, 4, 5, 14, 15]


def test_incremental_appends_new_docs(redis_client, clean_alpha):
    upsert_config(
        redis_client,
        user_id=1,
        ordering="asc",
        display_mode="compact",
        page_size=20,
        date_from=None,
        date_to=None,
    )
    set_config_sources(redis_client, user_id=1, source_ids=[1, 2])
    # Pre-seed first 3 docs at positions 0..2 so the next pass appends 2 more.
    append_entries(
        redis_client,
        user_id=1,
        doc_ids=[1, 2, 3],
        run_id=0,
        start_position=0,
    )
    clear_dirty(redis_client, user_id=1)

    kind, added = generate_for_user(r=redis_client, user_id=1, dirty=False)
    assert kind == "incremental"
    # Sources {1, 2} own docs {1, 2, 3, 4, 5, 14, 15}; minus the
    # pre-seeded {1, 2, 3} that leaves 4 new ones: {4, 5, 14, 15}.
    assert added == 4
    assert count_entries(redis_client, user_id=1) == 7


def test_no_sources_returns_skipped(redis_client, clean_alpha):
    upsert_config(
        redis_client,
        user_id=1,
        ordering="desc",
        display_mode="compact",
        page_size=20,
        date_from=None,
        date_to=None,
    )
    set_config_sources(redis_client, user_id=1, source_ids=[])
    kind, added = generate_for_user(r=redis_client, user_id=1, dirty=True)
    assert kind == "skipped"
    assert added == 0


def test_tick_processes_known_users(redis_client, clean_alpha):
    upsert_config(
        redis_client,
        user_id=1,
        ordering="desc",
        display_mode="compact",
        page_size=20,
        date_from=None,
        date_to=None,
    )
    set_config_sources(redis_client, user_id=1, source_ids=[1])
    tick()
    # Source 1 owns 4 seed documents (ids 1, 2, 5, 15).
    assert count_entries(redis_client, user_id=1) == 4
