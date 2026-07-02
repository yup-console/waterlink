"""Persist and restore player/queue state across bot restarts.

waterlink stays deliberately agnostic about *where* state is stored:
:class:`PersistenceBackend` is a small protocol, and :class:`JSONFileBackend`
is a zero-dependency reference implementation good enough for small/medium
bots. Larger deployments can implement the protocol against Redis,
Postgres, etc.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from .errors import PersistenceError
from .queue import LoopMode, Queue
from .tracks import Track
from .typing import JSONDict

logger = logging.getLogger("waterlink.persistence")

__all__ = [
    "PlayerSnapshot",
    "PersistenceBackend",
    "JSONFileBackend",
    "InMemoryBackend",
]


@dataclass(slots=True)
class PlayerSnapshot:
    """A serializable snapshot of one guild's player state."""

    guild_id: int
    channel_id: int | None
    node_name: str
    volume: int
    paused: bool
    loop_mode: LoopMode
    position_ms: int
    current: Track | None
    upcoming: list[Track] = field(default_factory=list)

    def to_payload(self) -> JSONDict:
        return {
            "guild_id": self.guild_id,
            "channel_id": self.channel_id,
            "node_name": self.node_name,
            "volume": self.volume,
            "paused": self.paused,
            "loop_mode": self.loop_mode.value,
            "position_ms": self.position_ms,
            "current": self.current.to_payload() if self.current else None,
            "upcoming": [t.to_payload() for t in self.upcoming],
        }

    @classmethod
    def from_payload(cls, payload: JSONDict) -> "PlayerSnapshot":
        current_payload = payload.get("current")
        return cls(
            guild_id=int(payload["guild_id"]),
            channel_id=payload.get("channel_id"),
            node_name=payload.get("node_name", "default"),
            volume=int(payload.get("volume", 100)),
            paused=bool(payload.get("paused", False)),
            loop_mode=LoopMode(payload.get("loop_mode", "off")),
            position_ms=int(payload.get("position_ms", 0)),
            current=Track.from_payload(current_payload) if current_payload else None,
            upcoming=[Track.from_payload(t) for t in payload.get("upcoming", [])],
        )

    @classmethod
    def capture(cls, player) -> "PlayerSnapshot":  # type: ignore[no-untyped-def]
        return cls(
            guild_id=player.guild_id,
            channel_id=player.channel_id,
            node_name=player.node.name,
            volume=player.volume,
            paused=player.paused,
            loop_mode=player.queue.loop_mode,
            position_ms=player.position_ms,
            current=player.queue.current,
            upcoming=player.queue.to_list(),
        )

    def restore_queue(self) -> Queue:
        queue = Queue()
        queue.add_many(self.upcoming)
        queue.loop_mode = self.loop_mode
        return queue


class PersistenceBackend(Protocol):
    async def save(self, snapshot: PlayerSnapshot) -> None: ...
    async def load(self, guild_id: int) -> PlayerSnapshot | None: ...
    async def delete(self, guild_id: int) -> None: ...
    async def load_all(self) -> list[PlayerSnapshot]: ...


class InMemoryBackend:
    """Process-local backend. Useful for tests; does not survive restarts."""

    def __init__(self) -> None:
        self._snapshots: dict[int, PlayerSnapshot] = {}

    async def save(self, snapshot: PlayerSnapshot) -> None:
        self._snapshots[snapshot.guild_id] = snapshot

    async def load(self, guild_id: int) -> PlayerSnapshot | None:
        return self._snapshots.get(guild_id)

    async def delete(self, guild_id: int) -> None:
        self._snapshots.pop(guild_id, None)

    async def load_all(self) -> list[PlayerSnapshot]:
        return list(self._snapshots.values())


class JSONFileBackend:
    """Stores one JSON file per guild inside a directory.

    Simple, human-inspectable, and dependency-free. Writes are not
    concurrency-safe across multiple processes; if you're running more
    than one bot process against the same state, use a database-backed
    backend instead.
    """

    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def _path(self, guild_id: int) -> Path:
        return self.directory / f"{guild_id}.json"

    async def save(self, snapshot: PlayerSnapshot) -> None:
        path = self._path(snapshot.guild_id)
        try:
            path.write_text(json.dumps(snapshot.to_payload(), indent=2))
        except OSError as exc:
            raise PersistenceError(f"Failed to write snapshot for guild {snapshot.guild_id}") from exc

    async def load(self, guild_id: int) -> PlayerSnapshot | None:
        path = self._path(guild_id)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text())
        except (OSError, ValueError) as exc:
            raise PersistenceError(f"Failed to read snapshot for guild {guild_id}") from exc
        return PlayerSnapshot.from_payload(payload)

    async def delete(self, guild_id: int) -> None:
        path = self._path(guild_id)
        if path.exists():
            path.unlink()

    async def load_all(self) -> list[PlayerSnapshot]:
        snapshots = []
        for file in self.directory.glob("*.json"):
            try:
                payload = json.loads(file.read_text())
                snapshots.append(PlayerSnapshot.from_payload(payload))
            except (OSError, ValueError):
                logger.warning("Skipping unreadable snapshot file: %s", file)
        return snapshots
