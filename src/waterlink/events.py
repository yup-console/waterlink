"""Event bus and event payload definitions.

waterlink dispatches strongly-typed dataclass events instead of raw
dictionaries. Consumers attach listeners with :meth:`EventBus.on` (as a
decorator or plain call) and the bus takes care of scheduling each listener
as an independent task so a slow or failing handler never blocks the
websocket read loop or other listeners.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, TypeVar

if TYPE_CHECKING:
    from .node import Node
    from .player import Player
    from .tracks import Track

logger = logging.getLogger("waterlink.events")

EventT = TypeVar("EventT", bound="Event")
Listener = Callable[[Any], Any]


@dataclass(slots=True)
class Event:
    """Base class for all events dispatched by waterlink."""


# --------------------------------------------------------------------------- #
# Node lifecycle events
# --------------------------------------------------------------------------- #


@dataclass(slots=True)
class NodeReadyEvent(Event):
    """Fired once a node completes its websocket handshake."""

    node: "Node"
    resumed: bool
    session_id: str


@dataclass(slots=True)
class NodeDisconnectedEvent(Event):
    """Fired when a node's websocket connection drops."""

    node: "Node"
    code: int
    reason: str
    will_reconnect: bool


@dataclass(slots=True)
class NodeReconnectingEvent(Event):
    """Fired before each reconnect attempt to a node."""

    node: "Node"
    attempt: int
    delay: float


@dataclass(slots=True)
class NodeErrorEvent(Event):
    """Fired when a node experiences a non-fatal internal error."""

    node: "Node"
    error: BaseException


@dataclass(slots=True)
class NodeStatsUpdateEvent(Event):
    """Fired whenever a node reports fresh stats (players, CPU, memory...)."""

    node: "Node"


# --------------------------------------------------------------------------- #
# Track / player events
# --------------------------------------------------------------------------- #


@dataclass(slots=True)
class TrackStartEvent(Event):
    """Fired when a track begins playback."""

    player: "Player"
    track: "Track"


@dataclass(slots=True)
class TrackEndEvent(Event):
    """Fired when a track finishes, is skipped, or is replaced."""

    player: "Player"
    track: "Track"
    reason: str

    @property
    def may_start_next(self) -> bool:
        """Whether it's appropriate to advance the queue after this event.

        Mirrors Lavalink's guidance: don't auto-advance on ``REPLACED`` (a
        new track was already explicitly set) and don't auto-advance on
        ``STOPPED`` (the user asked playback to stop).
        """

        return self.reason not in ("REPLACED", "STOPPED")


@dataclass(slots=True)
class TrackExceptionEvent(Event):
    """Fired when a track raises a playback exception on the node."""

    player: "Player"
    track: "Track"
    message: str | None
    severity: str
    cause: str


@dataclass(slots=True)
class TrackStuckEvent(Event):
    """Fired when a track's playback position stops advancing."""

    player: "Player"
    track: "Track"
    threshold_ms: int


@dataclass(slots=True)
class WebSocketClosedEvent(Event):
    """Fired when the voice websocket for a player's guild closes."""

    player: "Player"
    code: int
    reason: str
    by_remote: bool


@dataclass(slots=True)
class QueueEndEvent(Event):
    """Fired when the queue is exhausted and nothing more will auto-play."""

    player: "Player"


@dataclass(slots=True)
class PlayerUpdateEvent(Event):
    """Fired on periodic player state updates (position/connected/ping)."""

    player: "Player"
    position_ms: int
    connected: bool
    ping_ms: int


class EventBus:
    """A minimal async pub/sub dispatcher keyed by event type.

    Handlers are invoked concurrently (each wrapped in its own task) so
    that one slow consumer cannot delay delivery to the others, and any
    handler exception is logged rather than propagated.
    """

    __slots__ = ("_listeners", "_once_listeners")

    def __init__(self) -> None:
        self._listeners: dict[type[Event], list[Listener]] = defaultdict(list)
        self._once_listeners: dict[type[Event], list[Listener]] = defaultdict(list)

    def on(self, event_type: type[EventT]) -> Callable[[Listener], Listener]:
        """Decorator form: ``@bus.on(TrackStartEvent)``."""

        def decorator(func: Listener) -> Listener:
            self.add_listener(event_type, func)
            return func

        return decorator

    def add_listener(self, event_type: type[EventT], callback: Listener) -> None:
        self._listeners[event_type].append(callback)

    def remove_listener(self, event_type: type[EventT], callback: Listener) -> None:
        try:
            self._listeners[event_type].remove(callback)
        except ValueError:
            pass

    def once(self, event_type: type[EventT], callback: Listener) -> None:
        self._once_listeners[event_type].append(callback)

    def dispatch(self, event: Event) -> None:
        """Schedule every listener registered for ``type(event)``.

        Safe to call from synchronous websocket callback code; it never
        awaits, it only schedules tasks on the running loop.
        """

        event_type = type(event)
        handlers = list(self._listeners.get(event_type, ()))
        once_handlers = self._once_listeners.pop(event_type, [])
        if not handlers and not once_handlers:
            return

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            logger.debug("dispatch(%s) called with no running loop; dropping", event_type.__name__)
            return

        for callback in (*handlers, *once_handlers):
            loop.create_task(self._invoke(callback, event))

    async def _invoke(self, callback: Listener, event: Event) -> None:
        try:
            result = callback(event)
            if inspect.isawaitable(result):
                await result
        except Exception:  # noqa: BLE001 - listener failures must not crash the bus
            logger.exception(
                "Unhandled exception in listener %r for event %s",
                getattr(callback, "__qualname__", callback),
                type(event).__name__,
            )


__all__ = [
    "Event",
    "EventBus",
    "NodeReadyEvent",
    "NodeDisconnectedEvent",
    "NodeReconnectingEvent",
    "NodeErrorEvent",
    "NodeStatsUpdateEvent",
    "TrackStartEvent",
    "TrackEndEvent",
    "TrackExceptionEvent",
    "TrackStuckEvent",
    "WebSocketClosedEvent",
    "QueueEndEvent",
    "PlayerUpdateEvent",
]
