import time

from tape_service.auth.rate_limit import TokenBucket


def test_allows_up_to_limit_then_blocks():
    b = TokenBucket(capacity=3, window_seconds=10)
    assert b.allow("1.1.1.1")
    assert b.allow("1.1.1.1")
    assert b.allow("1.1.1.1")
    assert not b.allow("1.1.1.1")


def test_other_key_unaffected():
    b = TokenBucket(capacity=2, window_seconds=10)
    assert b.allow("a") and b.allow("a") and not b.allow("a")
    assert b.allow("b")


def test_refills_after_window():
    b = TokenBucket(capacity=1, window_seconds=0.05)
    assert b.allow("k")
    assert not b.allow("k")
    time.sleep(0.06)
    assert b.allow("k")
