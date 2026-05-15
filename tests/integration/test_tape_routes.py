import psycopg
import pytest

from tape_service.api.auth import reset_login_limiter_for_tests
from tape_service.store.tape import (
    append_entries,
    cfg_key,
    cfg_sources_key,
    entries_key,
    set_config_sources,
    upsert_config,
)

pytestmark = pytest.mark.integration

ALPHA = "expert-alpha-token-XXXXXXXXXXXXXXXX"


@pytest.fixture(autouse=True)
def _reset_limiter():
    reset_login_limiter_for_tests()
    yield
    reset_login_limiter_for_tests()


@pytest.fixture
def clean_alpha(redis_client, pg_dsn):
    keys = (cfg_key(1), cfg_sources_key(1), entries_key(1))
    redis_client.delete(*keys)
    with psycopg.connect(pg_dsn, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM score.score WHERE user_id = 1")
    yield
    redis_client.delete(*keys)
    with psycopg.connect(pg_dsn, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM score.score WHERE user_id = 1")


def _login(client, token: str = ALPHA) -> None:
    r = client.post("/auth/login", json={"token": token})
    assert r.status_code == 200, r.text


def test_get_tape_unauthorized(client):
    r = client.get("/tape")
    assert r.status_code == 401


def test_get_tape_empty_when_no_config(client, clean_alpha):
    _login(client)
    r = client.get("/tape")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["state"] == "empty"
    assert body["items"] == []
    assert body["next_position"] is None


def test_get_tape_preparing_when_dirty_no_entries(client, clean_alpha, redis_client):
    upsert_config(
        redis_client,
        user_id=1,
        ordering="asc",
        display_mode="compact",
        page_size=10,
        date_from=None,
        date_to=None,
    )
    set_config_sources(redis_client, user_id=1, source_ids=[1, 2])
    _login(client)
    r = client.get("/tape")
    body = r.json()
    assert body["state"] == "preparing"
    assert body["items"] == []


def test_get_tape_ok_with_entries(client, clean_alpha, redis_client):
    upsert_config(
        redis_client,
        user_id=1,
        ordering="asc",
        display_mode="compact",
        page_size=10,
        date_from=None,
        date_to=None,
    )
    set_config_sources(redis_client, user_id=1, source_ids=[1, 2])
    append_entries(
        redis_client,
        user_id=1,
        doc_ids=[1, 2, 3],
        run_id=0,
        start_position=0,
    )
    _login(client)
    r = client.get("/tape")
    body = r.json()
    assert body["state"] == "ok"
    assert body["display_mode"] == "compact"
    assert [it["document"]["id"] for it in body["items"]] == [1, 2, 3]
    # Compact mode omits the full text.
    for it in body["items"]:
        assert it["document"]["text"] is None
        assert it["document"]["title"].startswith("Test doc")
        assert len(it["roles"]) >= 1


def test_get_tape_detailed_mode_includes_text(client, clean_alpha, redis_client):
    upsert_config(
        redis_client,
        user_id=1,
        ordering="asc",
        display_mode="detailed",
        page_size=10,
        date_from=None,
        date_to=None,
    )
    set_config_sources(redis_client, user_id=1, source_ids=[1])
    append_entries(
        redis_client,
        user_id=1,
        doc_ids=[1],
        run_id=0,
        start_position=0,
    )
    _login(client)
    r = client.get("/tape")
    body = r.json()
    assert body["display_mode"] == "detailed"
    assert body["items"][0]["document"]["text"]


def test_get_tape_paging(client, clean_alpha, redis_client):
    upsert_config(
        redis_client,
        user_id=1,
        ordering="asc",
        display_mode="compact",
        page_size=2,
        date_from=None,
        date_to=None,
    )
    set_config_sources(redis_client, user_id=1, source_ids=[1, 2])
    append_entries(
        redis_client,
        user_id=1,
        doc_ids=[1, 2, 3, 4, 5],
        run_id=0,
        start_position=0,
    )
    _login(client)

    first = client.get("/tape").json()
    assert [it["document"]["id"] for it in first["items"]] == [1, 2]
    assert first["next_position"] == 1

    second = client.get(f"/tape?after={first['next_position']}").json()
    assert [it["document"]["id"] for it in second["items"]] == [3, 4]
    assert second["next_position"] == 3

    third = client.get(f"/tape?after={second['next_position']}").json()
    assert [it["document"]["id"] for it in third["items"]] == [5]
    assert third["next_position"] is None
