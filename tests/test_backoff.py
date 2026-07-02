from __future__ import annotations

from waterlink.backoff import ExponentialBackoff


def test_delay_grows_and_caps():
    b = ExponentialBackoff(base=1.0, max_delay=10.0, factor=2.0, jitter=0.0)
    delays = [b.next_delay() for _ in range(6)]
    assert delays[0] == 1.0
    assert delays[1] == 2.0
    assert delays[2] == 4.0
    assert delays[3] == 8.0
    assert delays[4] == 10.0
    assert delays[5] == 10.0


def test_reset_restarts_progression():
    b = ExponentialBackoff(base=1.0, max_delay=100.0, factor=2.0, jitter=0.0)
    b.next_delay()
    b.next_delay()
    assert b.attempt == 2
    b.reset()
    assert b.attempt == 0
    assert b.next_delay() == 1.0


def test_jitter_stays_within_bounds():
    b = ExponentialBackoff(base=4.0, max_delay=4.0, factor=1.0, jitter=0.5)
    for _ in range(50):
        delay = b.next_delay()
        assert 2.0 <= delay <= 6.0
