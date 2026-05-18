import json
from unittest.mock import MagicMock

from tape_service.store import events


def test_channel_for_includes_user_id():
    assert events.channel_for(42) == "tape:events:42"
    assert events.channel_for(0) == "tape:events:0"


def test_publish_writes_json_payload_to_user_channel():
    client = MagicMock()
    client.publish.return_value = 1
    event = events.make_lock_acquired(7)
    n = events.publish(client, user_id=7, event=event)
    assert n == 1
    channel, payload = client.publish.call_args.args
    assert channel == "tape:events:7"
    decoded = json.loads(payload)
    assert decoded["type"] == "lock.acquired"
    assert decoded["user_id"] == 7
    assert "at" in decoded


def test_make_lock_events_shape():
    a = events.make_lock_acquired(1)
    r = events.make_lock_released(1)
    assert a["type"] == "lock.acquired"
    assert r["type"] == "lock.released"
    assert a["user_id"] == r["user_id"] == 1


def test_make_schedule_events_shape():
    q = events.make_schedule_queued(2, "config_dirty")
    s = events.make_schedule_started(2, run_id=99, kind="full")
    c = events.make_schedule_completed(2, run_id=99, status="ok")
    assert q["type"] == "schedule.queued" and q["reason"] == "config_dirty"
    assert s["type"] == "schedule.started" and s["run_id"] == 99 and s["kind"] == "full"
    assert c["type"] == "schedule.completed" and c["status"] == "ok"


def test_make_tape_events_shape():
    add = events.make_tape_entry_added(3, position=5, document_id=17)
    rem = events.make_tape_entry_removed(3, document_id=17)
    regen = events.make_tape_regenerated(3, kind="incremental", added=2, removed=1)
    assert add["type"] == "tape.entry_added"
    assert add["position"] == 5 and add["document_id"] == 17
    assert rem["type"] == "tape.entry_removed" and rem["document_id"] == 17
    assert regen["type"] == "tape.regenerated"
    assert regen["kind"] == "incremental" and regen["added"] == 2 and regen["removed"] == 1
