import pytest

from tape_service.api.auth import reset_login_limiter_for_tests
from tape_service.store.tape import cfg_key, cfg_sources_key

pytestmark = pytest.mark.integration

ALPHA = "expert-alpha-token-XXXXXXXXXXXXXXXX"


@pytest.fixture(autouse=True)
def _reset_limiter():
    reset_login_limiter_for_tests()
    yield
    reset_login_limiter_for_tests()


@pytest.fixture
def alpha_clean_config(redis_client):
    """Drop Alpha's tape:cfg* keys so /config starts from defaults."""
    redis_client.delete(cfg_key(1), cfg_sources_key(1))
    yield
    redis_client.delete(cfg_key(1), cfg_sources_key(1))


def _login(client, token: str = ALPHA) -> None:
    r = client.post("/auth/login", json={"token": token})
    assert r.status_code == 200, r.text


def test_get_config_unauthorized_without_session(client):
    r = client.get("/config")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "UNAUTHORIZED"


def test_get_config_returns_defaults_for_new_user(client, alpha_clean_config):
    _login(client)
    r = client.get("/config")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ordering"] == "desc"
    assert body["display_mode"] == "compact"
    assert body["page_size"] == 20
    assert body["dirty"] is False
    assert body["selected_source_ids"] == []
    # Alpha (user 1) has role ALL, which covers both seed sources.
    assert {s["id"] for s in body["available_sources"]} == {1, 2}


def test_put_config_rejects_unauthorized_source(client, alpha_clean_config):
    _login(client)
    r = client.put("/config", json={
        "ordering": "desc",
        "display_mode": "compact",
        "page_size": 10,
        "selected_source_ids": [-999],
    })
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "FORBIDDEN"


def test_put_config_round_trips_and_marks_dirty(client, alpha_clean_config):
    _login(client)
    r = client.put("/config", json={
        "ordering": "asc",
        "display_mode": "detailed",
        "page_size": 50,
        "selected_source_ids": [1, 2],
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ordering"] == "asc"
    assert body["display_mode"] == "detailed"
    assert body["page_size"] == 50
    assert body["selected_source_ids"] == [1, 2]
    assert body["dirty"] is True

    # GET reads back identical state.
    r2 = client.get("/config")
    assert r2.status_code == 200
    body2 = r2.json()
    assert body2["ordering"] == "asc"
    assert body2["display_mode"] == "detailed"
    assert body2["page_size"] == 50
    assert body2["selected_source_ids"] == [1, 2]
    assert body2["dirty"] is True


def test_put_config_validation_rejects_huge_page_size(client, alpha_clean_config):
    _login(client)
    r = client.put("/config", json={
        "ordering": "desc",
        "display_mode": "compact",
        "page_size": 9999,
        "selected_source_ids": [],
    })
    assert r.status_code == 422
