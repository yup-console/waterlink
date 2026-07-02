"""Optional autoplay: keep audio flowing after the queue empties.

:class:`AutoplayEngine` listens for :class:`~waterlink.events.QueueEndEvent`
and, when enabled for a guild, resolves a follow-up track using a
pluggable strategy (by default, a same-source "search for more like this"
using the last played track's author/title).
"""

from __future__ import annotations

import logging
import random
from typing import Awaitable, Callable, Protocol

from .events import EventBus, QueueEndEvent
from .search import SearchPrefix, build_query
from .tracks import SearchTracksResult
from .errors import SearchError

logger = logging.getLogger("waterlink.autoplay")

__all__ = ["AutoplayEngine", "AutoplayStrategy", "related_track_strategy"]


class AutoplayStrategy(Protocol):
    async def __call__(self, player: "object") -> "object | None": ...


async def related_track_strategy(player) -> object | None:  # type: ignore[no-untyped-def]
    """Default strategy: search ``ytsearch:{author} {title}`` and pick a
    result that isn't identical to the track that just ended, preferring
    tracks recently seen aren't repeated back to back.
    """

    history = player.queue.history
    if not history:
        return None
    seed = history[-1]

    node = player.node
    query = build_query(f"{seed.author} {seed.title}", prefix=SearchPrefix.YOUTUBE)
    try:
        payload = await node.rest.load_tracks(query)
    except Exception:  # noqa: BLE001
        logger.debug("Autoplay: search failed for guild %s", player.guild_id, exc_info=True)
        return None

    from .search import parse_load_result

    result = parse_load_result(payload)
    if not isinstance(result, SearchTracksResult) or not result.tracks:
        return None

    recent_ids = {t.identifier for t in history[-10:]}
    candidates = [t for t in result.tracks if t.identifier not in recent_ids] or list(result.tracks)
    return random.choice(candidates[:5])


class AutoplayEngine:
    """Attaches to an :class:`~waterlink.events.EventBus` and keeps
    opted-in guilds playing after their queue empties.
    """

    def __init__(
        self,
        events: EventBus,
        *,
        strategy: AutoplayStrategy = related_track_strategy,
    ) -> None:
        self._events = events
        self._strategy = strategy
        self._enabled_guilds: set[int] = set()
        events.add_listener(QueueEndEvent, self._on_queue_end)

    def enable(self, guild_id: int) -> None:
        self._enabled_guilds.add(guild_id)

    def disable(self, guild_id: int) -> None:
        self._enabled_guilds.discard(guild_id)

    def is_enabled(self, guild_id: int) -> bool:
        return guild_id in self._enabled_guilds

    def set_strategy(self, strategy: AutoplayStrategy) -> None:
        self._strategy = strategy

    async def _on_queue_end(self, event: QueueEndEvent) -> None:
        player = event.player
        if player.guild_id not in self._enabled_guilds:
            return

        try:
            track = await self._strategy(player)
        except Exception:  # noqa: BLE001
            logger.exception("Autoplay strategy raised for guild %s", player.guild_id)
            return

        if track is None:
            logger.debug("Autoplay: no candidate track found for guild %s", player.guild_id)
            return

        await player.enqueue(track)
