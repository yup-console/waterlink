"""A feature-rich track queue with loop modes, shuffling, and history.

:class:`Queue` is intentionally storage-agnostic: it doesn't know about
Lavalink at all, it just manages an ordered collection of :class:`Track`
objects plus playback-order bookkeeping. :class:`Player` owns one queue
per guild and drives it.
"""

from __future__ import annotations

import random
from collections import deque
from enum import Enum
from typing import Iterable, Iterator

from .errors import InvalidQueueIndexError, QueueEmptyError
from .tracks import Track

__all__ = ["LoopMode", "Queue"]


class LoopMode(Enum):
    """Playback repeat behavior."""

    OFF = "off"
    TRACK = "track"
    QUEUE = "queue"


class Queue:
    """An ordered, mutable collection of upcoming tracks.

    Supports FIFO consumption via :meth:`next`, priority insertion via
    :meth:`push_front`, :class:`LoopMode`-aware advancement, shuffling, and
    a bounded history of recently played tracks for :meth:`previous`.
    """

    def __init__(self, *, max_history: int = 50) -> None:
        self._tracks: deque[Track] = deque()
        self._history: deque[Track] = deque(maxlen=max_history)
        self._current: Track | None = None
        self.loop_mode: LoopMode = LoopMode.OFF

    # -- inspection ---------------------------------------------------- #

    def __len__(self) -> int:
        return len(self._tracks)

    def __iter__(self) -> Iterator[Track]:
        return iter(self._tracks)

    def __bool__(self) -> bool:
        return bool(self._tracks)

    def __getitem__(self, index: int) -> Track:
        try:
            return self._tracks[index]
        except IndexError as exc:
            raise InvalidQueueIndexError(f"No track at index {index}") from exc

    @property
    def current(self) -> Track | None:
        """The track most recently returned by :meth:`next`, if any."""

        return self._current

    @property
    def upcoming(self) -> tuple[Track, ...]:
        return tuple(self._tracks)

    @property
    def history(self) -> tuple[Track, ...]:
        return tuple(self._history)

    @property
    def is_empty(self) -> bool:
        return not self._tracks

    def to_list(self) -> list[Track]:
        return list(self._tracks)

    # -- mutation -------------------------------------------------------- #

    def add(self, track: Track) -> None:
        self._tracks.append(track)

    def add_many(self, tracks: Iterable[Track]) -> int:
        count = 0
        for track in tracks:
            self._tracks.append(track)
            count += 1
        return count

    def push_front(self, track: Track) -> None:
        """Insert a track to play immediately after the current one."""

        self._tracks.appendleft(track)

    def insert(self, index: int, track: Track) -> None:
        if not (0 <= index <= len(self._tracks)):
            raise InvalidQueueIndexError(f"Cannot insert at index {index}")
        self._tracks.insert(index, track)

    def remove(self, index: int) -> Track:
        try:
            track = self._tracks[index]
        except IndexError as exc:
            raise InvalidQueueIndexError(f"No track at index {index}") from exc
        del self._tracks[index]
        return track

    def move(self, from_index: int, to_index: int) -> None:
        if not (0 <= from_index < len(self._tracks)):
            raise InvalidQueueIndexError(f"No track at index {from_index}")
        if not (0 <= to_index < len(self._tracks)):
            raise InvalidQueueIndexError(f"No target index {to_index}")
        track = self._tracks[from_index]
        del self._tracks[from_index]
        self._tracks.insert(to_index, track)

    def clear(self) -> None:
        self._tracks.clear()

    def shuffle(self, *, rng: random.Random | None = None) -> None:
        items = list(self._tracks)
        (rng or random).shuffle(items)
        self._tracks = deque(items)

    def deduplicate(self, *, key: str = "identifier") -> int:
        """Remove duplicate upcoming tracks, keeping first occurrences.

        Returns the number of tracks removed.
        """

        seen: set[str] = set()
        kept: deque[Track] = deque()
        removed = 0
        for track in self._tracks:
            value = getattr(track, key)
            if value in seen:
                removed += 1
                continue
            seen.add(value)
            kept.append(track)
        self._tracks = kept
        return removed

    # -- advancement ------------------------------------------------------ #

    def next(self) -> Track:
        """Advance the queue and return the track that should now play.

        Raises :class:`QueueEmptyError` if there is nothing left to play
        under the current loop mode.
        """

        if self.loop_mode is LoopMode.TRACK and self._current is not None:
            return self._current

        if not self._tracks:
            if self.loop_mode is LoopMode.QUEUE and self._history:
                self._tracks.extend(self._history)
                self._history.clear()
            if not self._tracks:
                raise QueueEmptyError("No tracks remaining in the queue")

        track = self._tracks.popleft()
        if self._current is not None:
            self._history.append(self._current)
        self._current = track
        return track

    def peek_next(self) -> Track | None:
        """Return what :meth:`next` would return, without consuming it."""

        if self.loop_mode is LoopMode.TRACK and self._current is not None:
            return self._current
        if self._tracks:
            return self._tracks[0]
        if self.loop_mode is LoopMode.QUEUE and self._history:
            return self._history[0]
        return None

    def previous(self) -> Track:
        """Move back to the last historical track and requeue the current one."""

        if not self._history:
            raise QueueEmptyError("No previous track in history")
        track = self._history.pop()
        if self._current is not None:
            self._tracks.appendleft(self._current)
        self._current = track
        return track

    def requeue_current(self) -> None:
        """Push the current track back to the front (used by TRACK loop resets)."""

        if self._current is not None:
            self._tracks.appendleft(self._current)
            self._current = None
