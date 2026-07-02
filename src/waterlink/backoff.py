"""Reconnect backoff strategies."""

from __future__ import annotations

import random

__all__ = ["ExponentialBackoff"]


class ExponentialBackoff:
    """Exponential backoff with jitter, capped at ``max_delay``.

    Not thread-safe, but that's fine: each :class:`~waterlink.node.Node`
    owns its own instance and only ever touches it from its own reconnect
    loop task.
    """

    def __init__(
        self,
        *,
        base: float = 1.0,
        max_delay: float = 60.0,
        factor: float = 2.0,
        jitter: float = 0.25,
    ) -> None:
        self.base = base
        self.max_delay = max_delay
        self.factor = factor
        self.jitter = jitter
        self._attempt = 0

    @property
    def attempt(self) -> int:
        return self._attempt

    def reset(self) -> None:
        self._attempt = 0

    def next_delay(self) -> float:
        delay = min(self.base * (self.factor**self._attempt), self.max_delay)
        self._attempt += 1
        jitter_span = delay * self.jitter
        return max(0.0, delay + random.uniform(-jitter_span, jitter_span))
