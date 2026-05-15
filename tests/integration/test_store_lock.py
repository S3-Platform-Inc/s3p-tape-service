import pytest

from tape_service.store.lock import per_user_lock

pytestmark = pytest.mark.integration


def test_lock_acquires(redis_client):
    with per_user_lock(redis_client, user_id=9001) as got:
        assert got is True
    # released — re-acquire works
    with per_user_lock(redis_client, user_id=9001) as got_again:
        assert got_again is True


def test_lock_blocks_second_holder(redis_client):
    """A second holder while the first is in scope returns False."""
    with per_user_lock(redis_client, user_id=9002) as outer:
        assert outer is True
        with per_user_lock(redis_client, user_id=9002) as inner:
            assert inner is False


def test_lock_keys_are_scoped_per_user(redis_client):
    with per_user_lock(redis_client, user_id=9003) as a:
        assert a is True
        with per_user_lock(redis_client, user_id=9004) as b:
            assert b is True
