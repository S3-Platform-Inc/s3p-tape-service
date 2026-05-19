import json
import threading
import time

import pytest

from tape_service.api.auth import reset_login_limiter_for_tests
from tape_service.store import events

pytestmark = pytest.mark.integration

ALPHA = "expert-alpha-token-XXXXXXXXXXXXXXXX"
USER_ID = 1  # ALPHA expert is seeded as user_id=1 in docs/sql/05-fake-data.sql


@pytest.fixture(autouse=True)
def _reset_limiter():
    reset_login_limiter_for_tests()
    yield
    reset_login_limiter_for_tests()


def _login(client) -> None:
    r = client.post("/auth/login", json={"token": ALPHA})
    assert r.status_code == 200, r.text


def _publish_after_subscribe(redis_client, *, user_id: int, event: dict, delay: float = 0.1):
    """Publish on a background thread once the WS handler has had time to
    subscribe. Starlette's WebSocketTestSession blocks the main thread
    inside receive_text, so the publish must come from elsewhere."""

    def _run():
        time.sleep(delay)
        events.publish(redis_client, user_id=user_id, event=event)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return t


def test_ws_forwards_lock_acquired(client, redis_client):
    _login(client)
    with client.websocket_connect("/ws") as ws:
        _publish_after_subscribe(
            redis_client,
            user_id=USER_ID,
            event=events.make_lock_acquired(USER_ID),
        )
        frame = json.loads(ws.receive_text())
    assert frame["type"] == "lock.acquired"
    assert frame["user_id"] == USER_ID


def test_ws_forwards_schedule_lifecycle(client, redis_client):
    _login(client)
    with client.websocket_connect("/ws") as ws:
        _publish_after_subscribe(
            redis_client,
            user_id=USER_ID,
            event=events.make_schedule_started(USER_ID, run_id=42, kind="full"),
        )
        frame = json.loads(ws.receive_text())
    assert frame["type"] == "schedule.started"
    assert frame["run_id"] == 42
    assert frame["kind"] == "full"


def test_ws_forwards_tape_entry_added(client, redis_client):
    _login(client)
    with client.websocket_connect("/ws") as ws:
        _publish_after_subscribe(
            redis_client,
            user_id=USER_ID,
            event=events.make_tape_entry_added(USER_ID, position=3, document_id=17),
        )
        frame = json.loads(ws.receive_text())
    assert frame["type"] == "tape.entry_added"
    assert frame["position"] == 3
    assert frame["document_id"] == 17


def test_ws_isolates_per_user(client, redis_client):
    """A frame published to a different user's channel must not leak to this WS."""
    _login(client)
    other_user = USER_ID + 9999
    with client.websocket_connect("/ws") as ws:
        # Publish to a stranger's channel first, then to ours.
        _publish_after_subscribe(
            redis_client,
            user_id=other_user,
            event=events.make_lock_acquired(other_user),
            delay=0.1,
        )
        _publish_after_subscribe(
            redis_client,
            user_id=USER_ID,
            event=events.make_lock_acquired(USER_ID),
            delay=0.3,
        )
        frame = json.loads(ws.receive_text())
    assert frame["user_id"] == USER_ID
