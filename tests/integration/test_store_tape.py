import pytest

from tape_service.store.tape import (
    append_entries,
    cfg_key,
    cfg_sources_key,
    clear_dirty,
    count_entries,
    create_run,
    delete_all_entries,
    entries_key,
    finish_run,
    get_config,
    get_config_sources,
    list_entries_page,
    max_position,
    remove_entry,
    set_config_sources,
    upsert_config,
)

pytestmark = pytest.mark.integration


@pytest.fixture
def cleanup(redis_client):
    """Clean up tape keys for the synthetic test users used in this module."""
    user_ids = list(range(9200, 9300))
    yield
    keys = []
    for u in user_ids:
        keys += [cfg_key(u), cfg_sources_key(u), entries_key(u)]
    if keys:
        redis_client.delete(*keys)


def test_get_config_returns_none_when_missing(redis_client, cleanup):
    assert get_config(redis_client, user_id=9201) is None


def test_upsert_then_get_config(redis_client, cleanup):
    upsert_config(
        redis_client,
        user_id=9202,
        ordering="desc",
        display_mode="compact",
        page_size=25,
        date_from=None,
        date_to=None,
    )
    cfg = get_config(redis_client, user_id=9202)
    assert cfg is not None
    assert cfg.user_id == 9202
    assert cfg.ordering == "desc"
    assert cfg.display_mode == "compact"
    assert cfg.page_size == 25
    assert cfg.dirty is True


def test_set_and_get_config_sources(redis_client, cleanup):
    upsert_config(
        redis_client,
        user_id=9203,
        ordering="asc",
        display_mode="detailed",
        page_size=10,
        date_from=None,
        date_to=None,
    )
    set_config_sources(redis_client, user_id=9203, source_ids=[1, 2])
    assert get_config_sources(redis_client, user_id=9203) == [1, 2]
    cfg = get_config(redis_client, user_id=9203)
    assert cfg is not None and cfg.dirty is True


def test_clear_dirty(redis_client, cleanup):
    upsert_config(
        redis_client,
        user_id=9204,
        ordering="desc",
        display_mode="compact",
        page_size=20,
        date_from=None,
        date_to=None,
    )
    clear_dirty(redis_client, user_id=9204)
    cfg = get_config(redis_client, user_id=9204)
    assert cfg is not None and cfg.dirty is False


def test_append_entries_and_paging(redis_client, cleanup):
    n = append_entries(
        redis_client,
        user_id=9205,
        doc_ids=[101, 102, 103, 104, 105],
        run_id=1,
        start_position=0,
    )
    assert n == 5
    assert count_entries(redis_client, user_id=9205) == 5
    assert max_position(redis_client, user_id=9205) == 4

    page = list_entries_page(redis_client, user_id=9205, after_position=None, limit=3)
    assert page == [(0, 101), (1, 102), (2, 103)]

    next_page = list_entries_page(redis_client, user_id=9205, after_position=2, limit=10)
    assert next_page == [(3, 104), (4, 105)]


def test_append_entries_skips_existing(redis_client, cleanup):
    append_entries(
        redis_client,
        user_id=9206,
        doc_ids=[1, 2, 3],
        run_id=1,
        start_position=0,
    )
    n = append_entries(
        redis_client,
        user_id=9206,
        doc_ids=[2, 3, 4],
        run_id=2,
        start_position=3,
    )
    assert n == 1
    assert count_entries(redis_client, user_id=9206) == 4


def test_remove_entry(redis_client, cleanup):
    append_entries(
        redis_client,
        user_id=9207,
        doc_ids=[10, 11, 12],
        run_id=1,
        start_position=0,
    )
    assert remove_entry(redis_client, user_id=9207, document_id=11) == 1
    assert remove_entry(redis_client, user_id=9207, document_id=11) == 0
    assert count_entries(redis_client, user_id=9207) == 2


def test_delete_all_entries(redis_client, cleanup):
    append_entries(
        redis_client,
        user_id=9208,
        doc_ids=[20, 21, 22, 23],
        run_id=1,
        start_position=0,
    )
    removed = delete_all_entries(redis_client, user_id=9208)
    assert removed == 4
    assert count_entries(redis_client, user_id=9208) == 0


def test_run_lifecycle(redis_client, cleanup):
    run_id = create_run(redis_client, user_id=9209, kind="full")
    assert isinstance(run_id, int) and run_id > 0
    finish_run(
        redis_client,
        user_id=9209,
        run_id=run_id,
        status="ok",
        added=3,
        removed=0,
    )
