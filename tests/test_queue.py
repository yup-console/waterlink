from __future__ import annotations

import pytest

from waterlink.errors import InvalidQueueIndexError, QueueEmptyError
from waterlink.queue import LoopMode, Queue
from waterlink.tracks import Track


def make_track(i: int) -> Track:
    return Track(
        encoded=f"enc{i}",
        identifier=str(i),
        is_seekable=True,
        author="Author",
        length_ms=100_000,
        is_stream=False,
        position_ms=0,
        title=f"Track {i}",
        source_name="youtube",
    )


def test_add_and_next_fifo_order():
    q = Queue()
    q.add_many(make_track(i) for i in range(3))
    assert [q.next().title for _ in range(3)] == ["Track 0", "Track 1", "Track 2"]


def test_next_on_empty_raises():
    q = Queue()
    with pytest.raises(QueueEmptyError):
        q.next()


def test_push_front_plays_next():
    q = Queue()
    q.add_many(make_track(i) for i in range(2))
    q.push_front(make_track(99))
    assert q.next().title == "Track 99"
    assert q.next().title == "Track 0"


def test_remove_and_move():
    q = Queue()
    q.add_many(make_track(i) for i in range(3))
    removed = q.remove(1)
    assert removed.title == "Track 1"
    assert [t.title for t in q] == ["Track 0", "Track 2"]

    q.move(1, 0)
    assert [t.title for t in q] == ["Track 2", "Track 0"]


def test_remove_out_of_range_raises():
    q = Queue()
    q.add(make_track(0))
    with pytest.raises(InvalidQueueIndexError):
        q.remove(5)


def test_deduplicate_by_identifier():
    q = Queue()
    q.add(make_track(1))
    q.add(make_track(1))
    q.add(make_track(2))
    removed = q.deduplicate()
    assert removed == 1
    assert len(q) == 2


def test_loop_track_repeats_current():
    q = Queue()
    q.add(make_track(1))
    q.loop_mode = LoopMode.TRACK
    first = q.next()
    second = q.next()
    third = q.next()
    assert first.title == second.title == third.title == "Track 1"


def test_loop_queue_cycles_through_history():
    q = Queue()
    q.add_many(make_track(i) for i in range(2))
    q.loop_mode = LoopMode.QUEUE
    order = [q.next().title for _ in range(5)]
    assert order == ["Track 0", "Track 1", "Track 0", "Track 1", "Track 0"]


def test_previous_moves_back_through_history():
    q = Queue()
    q.add_many(make_track(i) for i in range(2))
    q.next()  # current = Track 0
    q.next()  # current = Track 1, history = [Track 0]
    previous = q.previous()
    assert previous.title == "Track 0"
    assert q.current.title == "Track 0"


def test_shuffle_preserves_all_tracks():
    q = Queue()
    q.add_many(make_track(i) for i in range(10))
    before = {t.identifier for t in q}
    q.shuffle()
    after = {t.identifier for t in q}
    assert before == after
