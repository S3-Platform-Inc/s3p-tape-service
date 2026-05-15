import pytest

from tape_service.store.sessions import issue, revoke, validate

pytestmark = pytest.mark.integration


def test_issue_validate_revoke_roundtrip(redis_client):
    raw = issue(redis_client, user_id=9101)
    assert isinstance(raw, str) and len(raw) > 20

    sess = validate(redis_client, raw_session=raw)
    assert sess is not None
    assert sess.user_id == 9101

    revoke(redis_client, raw_session=raw)
    assert validate(redis_client, raw_session=raw) is None


def test_validate_unknown_returns_none(redis_client):
    assert validate(redis_client, raw_session="totally-fake-session-id-xyz") is None


def test_validate_refreshes_last_seen(redis_client):
    raw = issue(redis_client, user_id=9102)
    first = validate(redis_client, raw_session=raw)
    second = validate(redis_client, raw_session=raw)
    assert first is not None and second is not None
    assert second.last_seen >= first.last_seen
    revoke(redis_client, raw_session=raw)


def test_raw_session_id_is_not_a_key(redis_client):
    """Defence-in-depth: the raw session id must never be a Redis key."""
    raw = issue(redis_client, user_id=9103)
    assert redis_client.exists(f"sess:{raw}") == 0
    revoke(redis_client, raw_session=raw)
