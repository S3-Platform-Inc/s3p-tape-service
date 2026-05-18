import pytest
from starlette.websockets import WebSocketDisconnect

from tape_service.api.auth import reset_login_limiter_for_tests

pytestmark = pytest.mark.integration

ALPHA = "expert-alpha-token-XXXXXXXXXXXXXXXX"


@pytest.fixture(autouse=True)
def _reset_limiter():
    reset_login_limiter_for_tests()
    yield
    reset_login_limiter_for_tests()


def _login(client) -> None:
    r = client.post("/auth/login", json={"token": ALPHA})
    assert r.status_code == 200, r.text


def test_ws_rejects_when_no_cookie(client):
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/ws"):
            pass
    assert exc.value.code == 1008


def test_ws_rejects_with_bogus_cookie(client):
    client.cookies.set("s3p_session", "not-a-real-token")
    try:
        with pytest.raises(WebSocketDisconnect) as exc:
            with client.websocket_connect("/ws"):
                pass
        assert exc.value.code == 1008
    finally:
        client.cookies.clear()


def test_ws_accepts_after_login(client):
    _login(client)
    # Connect succeeds; we immediately disconnect without expecting any frame.
    with client.websocket_connect("/ws") as ws:
        assert ws is not None
