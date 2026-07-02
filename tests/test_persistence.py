from __future__ import annotations

import pytest

from waterlink.persistence import InMemoryBackend, JSONFileBackend, PlayerSnapshot
from waterlink.queue import LoopMode
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


def make_snapshot() -> PlayerSnapshot:
    return PlayerSnapshot(
        guild_id=123,
        channel_id=456,
        node_name="main",
        volume=80,
        paused=False,
        loop_mode=LoopMode.QUEUE,
        position_ms=5000,
        current=make_track(0),
        upcoming=[make_track(1), make_track(2)],
    )


def test_snapshot_payload_roundtrip():
    snapshot = make_snapshot()
    payload = snapshot.to_payload()
    restored = PlayerSnapshot.from_payload(payload)
    assert restored.guild_id == snapshot.guild_id
    assert restored.loop_mode == LoopMode.QUEUE
    assert restored.current.title == "Track 0"
    assert len(restored.upcoming) == 2


def test_snapshot_restore_queue():
    snapshot = make_snapshot()
    queue = snapshot.restore_queue()
    assert len(queue) == 2
    assert queue.loop_mode == LoopMode.QUEUE


@pytest.mark.asyncio
async def test_in_memory_backend_save_load_delete():
    backend = InMemoryBackend()
    snapshot = make_snapshot()
    await backend.save(snapshot)

    loaded = await backend.load(123)
    assert loaded is not None
    assert loaded.guild_id == 123

    await backend.delete(123)
    assert await backend.load(123) is None


@pytest.mark.asyncio
async def test_json_file_backend_save_load_delete(tmp_path):
    backend = JSONFileBackend(tmp_path)
    snapshot = make_snapshot()
    await backend.save(snapshot)

    loaded = await backend.load(123)
    assert loaded is not None
    assert loaded.current.title == "Track 0"

    all_snapshots = await backend.load_all()
    assert len(all_snapshots) == 1

    await backend.delete(123)
    assert await backend.load(123) is None
