from __future__ import annotations

import asyncio

import pytest

from waterlink.events import Event, EventBus


class DummyEvent(Event):
    __slots__ = ("value",)

    def __init__(self, value: int) -> None:
        self.value = value


@pytest.mark.asyncio
async def test_dispatch_invokes_sync_and_async_listeners():
    bus = EventBus()
    seen = []

    def sync_listener(event: DummyEvent) -> None:
        seen.append(("sync", event.value))

    async def async_listener(event: DummyEvent) -> None:
        seen.append(("async", event.value))

    bus.add_listener(DummyEvent, sync_listener)
    bus.add_listener(DummyEvent, async_listener)

    bus.dispatch(DummyEvent(42))
    await asyncio.sleep(0.01)

    assert ("sync", 42) in seen
    assert ("async", 42) in seen


@pytest.mark.asyncio
async def test_once_listener_fires_only_once():
    bus = EventBus()
    calls = []

    bus.once(DummyEvent, lambda e: calls.append(e.value))

    bus.dispatch(DummyEvent(1))
    await asyncio.sleep(0.01)
    bus.dispatch(DummyEvent(2))
    await asyncio.sleep(0.01)

    assert calls == [1]


@pytest.mark.asyncio
async def test_remove_listener_stops_delivery():
    bus = EventBus()
    calls = []

    def listener(event: DummyEvent) -> None:
        calls.append(event.value)

    bus.add_listener(DummyEvent, listener)
    bus.remove_listener(DummyEvent, listener)
    bus.dispatch(DummyEvent(1))
    await asyncio.sleep(0.01)

    assert calls == []


@pytest.mark.asyncio
async def test_listener_exception_does_not_prevent_other_listeners():
    bus = EventBus()
    calls = []

    def bad_listener(event: DummyEvent) -> None:
        raise RuntimeError("boom")

    def good_listener(event: DummyEvent) -> None:
        calls.append(event.value)

    bus.add_listener(DummyEvent, bad_listener)
    bus.add_listener(DummyEvent, good_listener)
    bus.dispatch(DummyEvent(7))
    await asyncio.sleep(0.01)

    assert calls == [7]
