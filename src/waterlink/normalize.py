"""Smooth out jarring volume differences between tracks.

Free sources (YouTube especially) are mastered at wildly inconsistent
loudness levels — one track might be a quiet acoustic recording, the next
a loudness-war-mastered pop remaster twice as loud. Lavalink has no
built-in loudness normalization (that requires analyzing audio data
Lavalink doesn't expose), so this module offers a practical, metadata-only
approximation: smoothing volume transitions between tracks so changes
aren't jarring, plus a simple per-guild target volume the normalizer
gently eases toward rather than snapping to.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

logger = logging.getLogger("waterlink.normalize")

__all__ = ["NormalizationConfig", "VolumeNormalizer"]


@dataclass(slots=True)
class NormalizationConfig:
    target_volume: int = 100
    """The steady-state volume (0-1000) tracks should settle at."""
    ramp_steps: int = 6
    """How many discrete volume steps to use when easing toward the target."""
    ramp_duration_ms: int = 1200
    """Total time to spend ramping from the previous track's volume to
    the target when a new track starts."""
    max_jump: int = 40
    """If the volume would otherwise need to change by more than this in
    one step, the change is spread across the full ramp instead of
    applied immediately — this is what actually smooths out jarring
    jumps between quiet and loud tracks."""


class VolumeNormalizer:
    """Attach to a player to smooth volume transitions between tracks.

    This does not analyze audio loudness (Lavalink doesn't expose that);
    it simply ensures the configured target volume is approached gradually
    rather than snapped to, so back-to-back tracks with different source
    mastering don't feel like a jarring volume jump. For real loudness
    normalization (e.g. ReplayGain-style analysis), pair this with a
    Lavalink plugin that provides it and skip client-side ramping.

    Usage::

        normalizer = VolumeNormalizer(player)
        await normalizer.on_track_start()  # call from a TrackStartEvent handler
    """

    def __init__(self, player, config: NormalizationConfig | None = None) -> None:  # type: ignore[no-untyped-def]
        self.player = player
        self.config = config or NormalizationConfig()
        self._ramp_task: asyncio.Task[None] | None = None

    def set_target(self, volume: int) -> None:
        self.config.target_volume = max(0, min(1000, volume))

    def cancel(self) -> None:
        if self._ramp_task is not None and not self._ramp_task.done():
            self._ramp_task.cancel()
        self._ramp_task = None

    async def on_track_start(self) -> None:
        """Call when a new track starts to ease volume toward the target."""

        self.cancel()
        current = self.player.volume
        target = self.config.target_volume

        if abs(target - current) <= self.config.max_jump:
            # Small enough change to just apply directly — no visible jump.
            if current != target:
                await self.player.set_volume(target)
            return

        self._ramp_task = asyncio.create_task(self._ramp(current, target))

    async def _ramp(self, start: int, target: int) -> None:
        try:
            steps = max(1, self.config.ramp_steps)
            interval = (self.config.ramp_duration_ms / 1000) / steps
            for i in range(1, steps + 1):
                value = int(start + (target - start) * (i / steps))
                await self.player.set_volume(value)
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            logger.exception("Volume ramp failed for guild %s", self.player.guild_id)
        finally:
            self._ramp_task = None
