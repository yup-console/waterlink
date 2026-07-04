"""Background health monitor for players and nodes.

The watchdog periodically checks every registered player for stalled
playback (position not advancing while supposedly playing) and every node
for staleness (no stats update within an expected window), emitting log
warnings and, optionally, invoking a recovery callback.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Awaitable, Callable

from .pool import NodePool

logger = logging.getLogger("waterlink.watchdog")

__all__ = ["Watchdog", "WatchdogConfig"]

RecoveryCallback = Callable[["object"], Awaitable[None]]


@dataclass(slots=True)
class WatchdogConfig:
    interval_seconds: float = 15.0
    stall_threshold_seconds: float = 20.0
    """How long a playing track's position may fail to advance before
    it's considered stalled."""
    node_stale_seconds: float = 90.0
    """How long a node may go without a stats update before it's flagged."""


class Watchdog:
    """Polls the node pool for unhealthy players/nodes on an interval.

    Usage::

        watchdog = Watchdog(pool)
        watchdog.on_stalled_player(my_recovery_coroutine)
        await watchdog.start()
        ...
        await watchdog.stop()
    """

    def __init__(self, pool: NodePool, config: WatchdogConfig | None = None) -> None:
        self.pool = pool
        self.config = config or WatchdogConfig()
        self._task: asyncio.Task[None] | None = None
        self._last_positions: dict[int, tuple[int, float]] = {}
        self._stalled_callbacks: list[RecoveryCallback] = []
        self._node_ready_since: dict[str, float] = {}

    def on_stalled_player(self, callback: RecoveryCallback) -> None:
        self._stalled_callbacks.append(callback)

    async def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run(), name="waterlink-watchdog")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
            self._task = None

    async def _run(self) -> None:
        while True:
            try:
                await self._check_once()
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001
                logger.exception("Watchdog check iteration failed")
            await asyncio.sleep(self.config.interval_seconds)

    async def _check_once(self) -> None:
        now = time.monotonic()

        for node in self.pool.nodes:
            if not node.is_ready:
                self._node_ready_since.pop(node.name, None)
            else:
                # `node.last_stats_at` is set directly from the real
                # `stats` OP timestamps (see Node._on_stats), reset to
                # None on every disconnect - so this reflects genuine
                # staleness rather than "did we happen to poll while
                # ready", which previously let a node with an open but
                # silent websocket go undetected indefinitely.
                if node.last_stats_at is None:
                    ready_since = self._node_ready_since.setdefault(node.name, now)
                    if now - ready_since > self.config.node_stale_seconds:
                        logger.warning(
                            "Node %s has been ready for over %.0fs without ever "
                            "reporting stats",
                            node.name,
                            self.config.node_stale_seconds,
                        )
                elif now - node.last_stats_at > self.config.node_stale_seconds:
                    logger.warning(
                        "Node %s has not reported stats in over %.0fs",
                        node.name,
                        self.config.node_stale_seconds,
                    )

            for player in list(node._players.values()):  # noqa: SLF001 - internal, same package
                await self._check_player(player, now)

    async def _check_player(self, player, now: float) -> None:  # type: ignore[no-untyped-def]
        if not player.is_playing or player.queue.current is None:
            self._last_positions.pop(player.guild_id, None)
            return

        position = player.position_ms
        previous = self._last_positions.get(player.guild_id)

        if previous is not None:
            prev_position, prev_time = previous
            elapsed = now - prev_time
            if (
                elapsed >= self.config.stall_threshold_seconds
                and abs(position - prev_position) < 1000
            ):
                logger.warning(
                    "Player for guild %s appears stalled at position %sms",
                    player.guild_id,
                    position,
                )
                for callback in self._stalled_callbacks:
                    try:
                        await callback(player)
                    except Exception:  # noqa: BLE001
                        logger.exception("Watchdog recovery callback failed")

        self._last_positions[player.guild_id] = (position, now)
