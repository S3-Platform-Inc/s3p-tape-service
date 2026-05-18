import psycopg
import pytest

from tape_service.api.auth import reset_login_limiter_for_tests
from tape_service.store.lock import per_user_lock
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


def test_get_tape_returns_409_while_locked(client, clean_alpha, redis_client):
    """While the worker holds the per-user advisory lock, /tape must
    refuse so clients don't render stale mid-regen data."""
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

    with per_user_lock(redis_client, user_id=1) as got:
        assert got is True
        r = client.get("/tape")
        assert r.status_code == 409, r.text
        body = r.json()
        assert body["error"]["code"] == "TAPE_LOCKED"

    # Lock released — tape becomes readable again.
    r = client.get("/tape")
    assert r.status_code == 200, r.text
    assert r.json()["state"] == "ok"
