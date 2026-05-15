import psycopg
import pytest

from tape_service.api.auth import reset_login_limiter_for_tests
from tape_service.store.tape import (
    append_entries,
    cfg_key,
    cfg_sources_key,
    count_entries,
    entries_key,
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


def test_score_unauthorized(client):
    r = client.post("/score", json={"document_id": 1, "role_id": 1, "verdict": "yes"})
    assert r.status_code == 401


def test_score_happy_path_removes_tape_entry(client, clean_alpha, redis_client):
    append_entries(
        redis_client,
        user_id=1,
        doc_ids=[1, 2, 3],
        run_id=0,
        start_position=0,
    )
    assert count_entries(redis_client, user_id=1) == 3

    _login(client)
    r = client.post(
        "/score",
        json={
            "document_id": 1,
            "role_id": 1,
            "verdict": "yes",
        },
    )
    assert r.status_code == 200, r.text
    assert isinstance(r.json()["score_id"], int)
    assert count_entries(redis_client, user_id=1) == 2


def test_score_duplicate_returns_already_scored(client, clean_alpha):
    _login(client)
    payload = {"document_id": 1, "role_id": 1, "verdict": "no"}
    r1 = client.post("/score", json=payload)
    assert r1.status_code == 200, r1.text
    r2 = client.post("/score", json=payload)
    assert r2.status_code == 409
    assert r2.json()["error"]["code"] == "ALREADY_SCORED"


def test_score_validation_rejects_unknown_verdict(client, clean_alpha):
    _login(client)
    r = client.post(
        "/score",
        json={
            "document_id": 1,
            "role_id": 1,
            "verdict": "maybe",
        },
    )
    assert r.status_code == 422


def test_score_accepts_optional_comment(client, clean_alpha):
    _login(client)
    r = client.post(
        "/score",
        json={
            "document_id": 1,
            "role_id": 1,
            "verdict": "unsure",
            "comment": "leaning unsure, second pass needed",
        },
    )
    assert r.status_code == 200, r.text
