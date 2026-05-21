from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

pytestmark = pytest.mark.integration

ALLOWED = "https://score.s3platform.ru"
DISALLOWED = "https://attacker.example"
ALPHA = "expert-alpha-token-XXXXXXXXXXXXXXXX"


@pytest.fixture
def cors_client(settings_env, monkeypatch):
    """Fresh app with CORS_ALLOW_ORIGINS configured.

    The session-scoped `app` fixture in tests/conftest.py is built with
    an empty allowlist (the default). To exercise the cross-origin path
    we set the env var, bust the settings cache, and stand up a new app.
    """
    monkeypatch.setenv("CORS_ALLOW_ORIGINS", f'["{ALLOWED}"]')
    from tape_service.settings import get_settings

    get_settings.cache_clear()
    try:
        from tape_service.main import create_app

        app = create_app()
        with TestClient(app) as c:
            yield c
    finally:
        # Restore the cached settings the rest of the suite expects.
        os.environ.pop("CORS_ALLOW_ORIGINS", None)
        get_settings.cache_clear()


def test_preflight_allows_configured_origin(cors_client):
    r = cors_client.options(
        "/auth/login",
        headers={
            "Origin": ALLOWED,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") == ALLOWED
    assert r.headers.get("access-control-allow-credentials") == "true"


def test_preflight_rejects_other_origin(cors_client):
    r = cors_client.options(
        "/auth/login",
        headers={
            "Origin": DISALLOWED,
            "Access-Control-Request-Method": "POST",
        },
    )
    # Starlette returns 400 on a disallowed preflight; either way the
    # browser will never see an allow-origin header echoing the attacker.
    assert r.headers.get("access-control-allow-origin") != DISALLOWED


def test_actual_request_echoes_allowed_origin(cors_client):
    from tape_service.api.auth import reset_login_limiter_for_tests

    reset_login_limiter_for_tests()
    r = cors_client.post(
        "/auth/login",
        json={"token": ALPHA},
        headers={"Origin": ALLOWED},
    )
    assert r.status_code == 200, r.text
    assert r.headers.get("access-control-allow-origin") == ALLOWED
    assert r.headers.get("access-control-allow-credentials") == "true"
    reset_login_limiter_for_tests()


def test_ws_rejects_disallowed_origin(cors_client):
    from tape_service.api.auth import reset_login_limiter_for_tests

    reset_login_limiter_for_tests()
    # Authenticate first so the rejection is provably about Origin, not
    # the missing session cookie.
    r = cors_client.post(
        "/auth/login",
        json={"token": ALPHA},
        headers={"Origin": ALLOWED},
    )
    assert r.status_code == 200, r.text
    try:
        with pytest.raises(WebSocketDisconnect) as exc:
            with cors_client.websocket_connect(
                "/ws", headers={"Origin": DISALLOWED}
            ):
                pass
        assert exc.value.code == 1008
    finally:
        reset_login_limiter_for_tests()


def test_ws_accepts_allowed_origin(cors_client):
    from tape_service.api.auth import reset_login_limiter_for_tests

    reset_login_limiter_for_tests()
    r = cors_client.post(
        "/auth/login",
        json={"token": ALPHA},
        headers={"Origin": ALLOWED},
    )
    assert r.status_code == 200, r.text
    try:
        with cors_client.websocket_connect(
            "/ws", headers={"Origin": ALLOWED}
        ) as ws:
            assert ws is not None
    finally:
        reset_login_limiter_for_tests()
