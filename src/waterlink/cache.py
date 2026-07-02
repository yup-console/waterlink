"""A small TTL + LRU cache, primarily intended for search-result caching.

Not distributed or persistent — this is a per-process optimization to
avoid hammering a node with repeated identical ``/loadtracks`` calls (e.g.
several users queueing the same trending song within a short window).
"""

from __future__ import annotations

import time
from collections import OrderedDict
from typing import Generic, TypeVar

__all__ = ["TTLCache"]

K = TypeVar("K")
V = TypeVar("V")


class TTLCache(Generic[K, V]):
    """An ``OrderedDict``-backed cache with per-entry expiry and an LRU
    eviction policy once ``max_size`` is exceeded.
    """

    def __init__(self, *, max_size: int = 256, ttl_seconds: float = 300.0) -> None:
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._data: OrderedDict[K, tuple[V, float]] = OrderedDict()

    def get(self, key: K) -> V | None:
        entry = self._data.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if expires_at < time.monotonic():
            del self._data[key]
            return None
        self._data.move_to_end(key)
        return value

    def set(self, key: K, value: V) -> None:
        expires_at = time.monotonic() + self.ttl_seconds
        self._data[key] = (value, expires_at)
        self._data.move_to_end(key)
        while len(self._data) > self.max_size:
            self._data.popitem(last=False)

    def invalidate(self, key: K) -> None:
        self._data.pop(key, None)

    def clear(self) -> None:
        self._data.clear()

    def __len__(self) -> int:
        return len(self._data)

    def __contains__(self, key: K) -> bool:
        return self.get(key) is not None
