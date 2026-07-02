"""Crossfade: smoothly ramp volume down/up across a track transition.

Lavalink has no native crossfade primitive, so this is implemented
client-side by scheduling a series of small volume updates near the end of
the current track and the start of the next one. It's a best-effort
approximation — precise sample-accurate crossfading would require a custom
audio pipeline plugin on the node — but it's smooth enough for typical
music-bot use and requires no server-side changes.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

logger = logging.getLogger("waterlink.crossfade")

__all__ = ["CrossfadeConfig", "CrossfadeController"]


@dataclass(slots=True)
class CrossfadeConfig:
    duration_ms: int = 3000
    steps: int = 12
    min_track_length_ms: int = 15_000
    """Tracks shorter than this are played at full volume without fading,
    since a fade would consume too large a fraction of their runtime."""


class CrossfadeController:
    """Owns the fade-out/fade-in scheduling for one player."""

    def __init__(self, player, config: CrossfadeConfig | None = None) -> None:  # type: ignore[no-untyped-def]
        self.player = player
        self.config = config or CrossfadeConfig()
        self.enabled = False
        self._fade_task: asyncio.Task[None] | None = None
        self._base_volume: int = player.volume

    def enable(self) -> None:
        self.enabled = True

    def disable(self) -> None:
        self.enabled = False
        self._cancel_active_fade()

    def _cancel_active_fade(self) -> None:
        if self._fade_task is not None and not self._fade_task.done():
            self._fade_task.cancel()
        self._fade_task = None

    async def maybe_schedule_fade_out(self) -> None:
        """Call periodically (e.g. on playerUpdate) to check whether the
        current track is close enough to ending to start fading out.
        """

        if not self.enabled:
            return
        track = self.player.queue.current
        if track is None or not track.is_finite:
            return
        if track.length_ms < self.config.min_track_length_ms:
            return

        remaining = track.length_ms - self.player.position_ms
        if remaining <= self.config.duration_ms and self._fade_task is None:
            self._fade_task = asyncio.create_task(self._fade_out())

    async def _fade_out(self) -> None:
        try:
            steps = max(1, self.config.steps)
            interval = (self.config.duration_ms / 1000) / steps
            start_volume = self.player.volume
            self._base_volume = start_volume
            for i in range(steps, 0, -1):
                target = int(start_volume * (i / steps))
                await self.player.set_volume(max(target, 0))
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            logger.exception("Crossfade fade-out failed for guild %s", self.player.guild_id)
        finally:
            self._fade_task = None

    async def fade_in(self) -> None:
        """Call right after a new track starts, to ramp volume back up."""

        if not self.enabled:
            return
        self._cancel_active_fade()
        self._fade_task = asyncio.create_task(self._fade_in())

    async def _fade_in(self) -> None:
        try:
            target_volume = self._base_volume or self.player.volume
            steps = max(1, self.config.steps)
            interval = (self.config.duration_ms / 1000) / steps
            await self.player.set_volume(0)
            for i in range(1, steps + 1):
                value = int(target_volume * (i / steps))
                await self.player.set_volume(value)
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            logger.exception("Crossfade fade-in failed for guild %s", self.player.guild_id)
        finally:
            self._fade_task = None
