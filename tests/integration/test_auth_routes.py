import pytest

from tape_service.api.auth import reset_login_limiter_for_tests

pytestmark = pytest.mark.integration

ALPHA = "expert-alpha-token-XXXXXXXXXXXXXXXX"
CHARLIE = "reader-charlie-token-ZZZZZZZZZZZZZZ"
BOGUS = "definitely-not-a-real-token-ZZZZZZZZ"


@pytest.fixture(autouse=True)
def _reset_limiter():
    """Each test starts with a fresh in-process rate-limit bucket."""
    reset_login_limiter_for_tests()
    yield
    reset_login_limiter_for_tests()


def test_login_unknown_token_returns_401(client):
    r = client.post("/auth/login", json={"token": BOGUS})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "UNAUTHORIZED"


def test_login_non_expert_returns_403(client):
    r = client.post("/auth/login", json={"token": CHARLIE})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "FORBIDDEN"


def test_login_expert_sets_cookie_and_returns_user_id(client):
    r = client.post("/auth/login", json={"token": ALPHA})
    assert r.status_code == 200, r.text
    assert r.json() == {"user_id": 1}
    cookie = r.cookies.get("s3p_session")
    assert cookie and len(cookie) > 20


def test_me_requires_session(client):
    r = client.get("/auth/me")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "UNAUTHORIZED"


def test_me_returns_user_id_for_logged_in_expert(client):
    client.post("/auth/login", json={"token": ALPHA})
    r = client.get("/auth/me")
    assert r.status_code == 200
    assert r.json() == {"user_id": 1}


def test_logout_invalidates_session(client):
    client.post("/auth/login", json={"token": ALPHA})
    r = client.post("/auth/logout")
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    client.cookies.clear()
    assert client.get("/auth/me").status_code == 401


def test_login_validation_rejects_short_token(client):
    r = client.post("/auth/login", json={"token": "abc"})
    assert r.status_code == 422  # pydantic validation


def test_login_rate_limit_returns_429(client):
    statuses = []
    for _ in range(12):
        statuses.append(client.post("/auth/login", json={"token": BOGUS}).status_code)
    assert 429 in statuses
    assert statuses.count(429) >= 2
