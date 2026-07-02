"""Lightweight in-process metrics collection.

No external dependency (no prometheus_client requirement); this just
accumulates counters/gauges in memory and exposes them as plain dicts, and
optionally a Prometheus text-exposition string, so hosts can wire it into
whatever monitoring stack they already use.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field

from .events import (
    EventBus,
    NodeDisconnectedEvent,
    NodeReadyEvent,
    TrackEndEvent,
    TrackExceptionEvent,
    TrackStartEvent,
)

__all__ = ["MetricsCollector"]


@dataclass(slots=True)
class _Counters:
    tracks_started: int = 0
    tracks_ended: int = 0
    track_exceptions: int = 0
    node_ready_events: int = 0
    node_disconnect_events: int = 0
    end_reasons: dict[str, int] = field(default_factory=lambda: defaultdict(int))


class MetricsCollector:
    """Subscribes to the shared event bus and tallies basic playback metrics.

    Thread-safety note: event handlers run on the asyncio loop, so a lock
    isn't strictly required for the increments themselves, but
    :meth:`snapshot` is written to be safe to call from any thread in case
    it's polled by an external exporter.
    """

    def __init__(self, events: EventBus) -> None:
        self._counters = _Counters()
        self._lock = threading.Lock()
        self._start_time = time.time()

        events.add_listener(TrackStartEvent, self._on_track_start)
        events.add_listener(TrackEndEvent, self._on_track_end)
        events.add_listener(TrackExceptionEvent, self._on_track_exception)
        events.add_listener(NodeReadyEvent, self._on_node_ready)
        events.add_listener(NodeDisconnectedEvent, self._on_node_disconnected)

    async def _on_track_start(self, event: TrackStartEvent) -> None:
        with self._lock:
            self._counters.tracks_started += 1

    async def _on_track_end(self, event: TrackEndEvent) -> None:
        with self._lock:
            self._counters.tracks_ended += 1
            self._counters.end_reasons[event.reason] += 1

    async def _on_track_exception(self, event: TrackExceptionEvent) -> None:
        with self._lock:
            self._counters.track_exceptions += 1

    async def _on_node_ready(self, event: NodeReadyEvent) -> None:
        with self._lock:
            self._counters.node_ready_events += 1

    async def _on_node_disconnected(self, event: NodeDisconnectedEvent) -> None:
        with self._lock:
            self._counters.node_disconnect_events += 1

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "uptime_seconds": time.time() - self._start_time,
                "tracks_started": self._counters.tracks_started,
                "tracks_ended": self._counters.tracks_ended,
                "track_exceptions": self._counters.track_exceptions,
                "node_ready_events": self._counters.node_ready_events,
                "node_disconnect_events": self._counters.node_disconnect_events,
                "end_reasons": dict(self._counters.end_reasons),
            }

    def to_prometheus(self) -> str:
        data = self.snapshot()
        lines = [
            "# HELP waterlink_tracks_started_total Total tracks started",
            "# TYPE waterlink_tracks_started_total counter",
            f"waterlink_tracks_started_total {data['tracks_started']}",
            "# HELP waterlink_tracks_ended_total Total tracks ended",
            "# TYPE waterlink_tracks_ended_total counter",
            f"waterlink_tracks_ended_total {data['tracks_ended']}",
            "# HELP waterlink_track_exceptions_total Total track exceptions",
            "# TYPE waterlink_track_exceptions_total counter",
            f"waterlink_track_exceptions_total {data['track_exceptions']}",
            "# HELP waterlink_node_ready_total Total node ready events",
            "# TYPE waterlink_node_ready_total counter",
            f"waterlink_node_ready_total {data['node_ready_events']}",
            "# HELP waterlink_node_disconnect_total Total node disconnect events",
            "# TYPE waterlink_node_disconnect_total counter",
            f"waterlink_node_disconnect_total {data['node_disconnect_events']}",
        ]
        return "\n".join(lines) + "\n"
