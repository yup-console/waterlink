"""The per-guild playback controller.

:class:`Player` is the main object application code interacts with day to
day: connecting to a voice channel, queueing tracks, controlling playback,
and applying filters. It owns a :class:`~waterlink.queue.Queue`, talks to
its assigned :class:`~waterlink.node.Node` over REST, and receives voice
state updates via :mod:`waterlink.voice`.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any

from .errors import (
    PlayerAlreadyConnectedError,
    PlayerNotConnectedError,
    QueueEmptyError,
)
from .events import QueueEndEvent, TrackEndEvent, TrackStartEvent
from .filters import FilterChain
from .queue import LoopMode, Queue
from .tracks import Track
from .voice import VoiceServerUpdate, VoiceStateUpdate

if TYPE_CHECKING:
    from .node import Node
    from .pool import NodePool

logger = logging.getLogger("waterlink.player")

__all__ = ["Player"]


class Player:
    """Owns playback state for a single guild.

    Instances are created and looked up through
    :class:`waterlink.manager.WaterlinkClient`; you generally won't
    construct one directly.
    """

    def __init__(
        self,
        *,
        guild_id: int,
        pool: "NodePool",
        node: "Node",
        voice_protocol: Any,
    ) -> None:
        self.guild_id = guild_id
        self.pool = pool
        self.node = node
        self.voice_protocol = voice_protocol
        if voice_protocol is not None:
            self.voice_protocol.player = self

        self.queue: Queue = Queue()
        self.filters: FilterChain = FilterChain()
        self.volume: int = 100
        self.paused: bool = False

        self.channel_id: int | None = None
        self._voice_session_id: str | None = None
        self._voice_token: str | None = None
        self._voice_endpoint: str | None = None

        self._last_position_ms: int = 0
        self._last_position_at: float = time.monotonic()
        self._connected_to_voice_gateway: bool = False
        self._ping_ms: int = -1

        self._pending_voice_update: asyncio.Event = asyncio.Event()
        self._destroyed: bool = False

        self.node.register_player(guild_id, self)

    # -- connection ------------------------------------------------------- #

    @property
    def is_connected(self) -> bool:
        return self.channel_id is not None

    @property
    def is_playing(self) -> bool:
        return self.queue.current is not None and not self.paused

    async def connect(
        self,
        channel_id: int,
        *,
        self_deaf: bool = True,
        self_mute: bool = False,
        move: bool = False,
    ) -> None:
        """Join (or move to) a voice channel.

        Raises :class:`PlayerAlreadyConnectedError` if already connected to
        a *different* channel and ``move`` is not set.
        """

        if self.channel_id is not None and self.channel_id != channel_id and not move:
            raise PlayerAlreadyConnectedError(
                f"Player already connected to channel {self.channel_id}; pass move=True to switch"
            )

        guild = self.voice_protocol.channel.guild
        channel = guild.get_channel(channel_id)
        if channel is None:
            raise PlayerNotConnectedError(
                f"Could not find channel {channel_id} in guild {guild.id}'s cache. "
                "Make sure the bot's Guilds intent is enabled and the channel exists."
            )

        self._pending_voice_update.clear()
        await guild.change_voice_state(channel=channel, self_deaf=self_deaf, self_mute=self_mute)
        self.channel_id = channel_id
        self.voice_protocol.channel = channel

        try:
            await asyncio.wait_for(self._pending_voice_update.wait(), timeout=15.0)
        except asyncio.TimeoutError:
            logger.warning(
                "Guild %s: voice connection did not confirm within timeout", self.guild_id
            )

    async def disconnect(self) -> None:
        guild = self.voice_protocol.channel.guild
        await guild.change_voice_state(channel=None)
        self.channel_id = None
        self._connected_to_voice_gateway = False

    async def destroy(self) -> None:
        """Tear down this player: stop audio, leave voice, remove from node."""

        if self._destroyed:
            return
        self._destroyed = True
        try:
            if self.channel_id is not None:
                await self.disconnect()
            session_id = self.node.session_id
            if session_id:
                await self.node.rest.destroy_player(session_id, self.guild_id)
        finally:
            self.node.unregister_player(self.guild_id)

    # -- voice callbacks (invoked by waterlink.voice) ----------------------- #

    async def _on_voice_server_update(self, update: VoiceServerUpdate) -> None:
        self._voice_token = update.token
        self._voice_endpoint = update.endpoint
        await self._maybe_dispatch_voice_update()

    async def _on_voice_state_update(self, update: VoiceStateUpdate) -> None:
        self._voice_session_id = update.session_id
        if update.channel_id is None:
            self.channel_id = None
            self._connected_to_voice_gateway = False
        else:
            self.channel_id = update.channel_id
        await self._maybe_dispatch_voice_update()

    async def _on_voice_disconnect(self, *, force: bool) -> None:
        self.channel_id = None
        self._connected_to_voice_gateway = False

    async def _maybe_dispatch_voice_update(self) -> None:
        if not (self._voice_token and self._voice_endpoint and self._voice_session_id):
            logger.debug(
                "Guild %s: skipping voice dispatch, missing field(s) (token=%s endpoint=%s session=%s)",
                self.guild_id,
                bool(self._voice_token),
                bool(self._voice_endpoint),
                bool(self._voice_session_id),
            )
            return

        session_id = self.node.require_session()
        payload = {
            "voice": {
                "token": self._voice_token,
                "endpoint": self._voice_endpoint,
                "sessionId": self._voice_session_id,
            }
        }
        if self.channel_id is not None:
            payload["voice"]["channelId"] = str(self.channel_id)
        try:
            await self.node.rest.update_player(session_id, self.guild_id, payload=payload)
        except Exception:
            logger.exception(
                "Guild %s: failed to dispatch voice update to node %s (session=%s)",
                self.guild_id,
                self.node.name,
                self._voice_session_id,
            )
            raise
        self._connected_to_voice_gateway = True
        self._pending_voice_update.set()

    # -- node event callbacks ------------------------------------------------ #

    def _on_state_update(self, *, position_ms: int, connected: bool, ping_ms: int) -> None:
        self._last_position_ms = position_ms
        self._last_position_at = time.monotonic()
        self._connected_to_voice_gateway = connected
        self._ping_ms = ping_ms

    def _on_track_start(self, track: Track) -> None:
        logger.debug("Guild %s: track started: %s", self.guild_id, track.title)

    def _on_track_end(self, track: Track, reason: str) -> None:
        event = TrackEndEvent(player=self, track=track, reason=reason)
        if event.may_start_next:
            asyncio.create_task(self._advance_queue())

    def _on_voice_ws_closed(self) -> None:
        self._connected_to_voice_gateway = False

    async def _advance_queue(self) -> None:
        try:
            next_track = self.queue.next()
        except QueueEmptyError:
            self.pool.events.dispatch(QueueEndEvent(player=self))
            return
        await self.play(next_track, replace=True)

    # -- playback control --------------------------------------------------- #

    async def play(
        self,
        track: Track | None = None,
        *,
        replace: bool = True,
        start_ms: int = 0,
        end_ms: int | None = None,
        pause: bool = False,
    ) -> Track:
        """Start playback of ``track``, or dequeue the next one if omitted.

        If ``track`` is given, it does not go through the queue — pass it
        through :meth:`Queue.add` beforehand if you want normal queueing
        semantics. This method is the low-level "tell the node to play X"
        primitive; most callers should use :meth:`enqueue` instead.
        """

        if track is None:
            track = self.queue.next()

        session_id = self.node.require_session()
        payload: dict[str, Any] = {
            "track": {"encoded": track.encoded},
            "position": start_ms,
            "paused": pause,
        }
        if end_ms is not None:
            payload["track"]["endTime"] = end_ms

        await self.node.rest.update_player(
            session_id, self.guild_id, payload=payload, no_replace=not replace
        )
        self.paused = pause
        return track

    async def enqueue(self, track: Track, *, play_now: bool = False) -> None:
        """Add a track to the queue, starting playback if nothing is playing."""

        if play_now:
            self.queue.push_front(track)
        else:
            self.queue.add(track)

        if self.queue.current is None and not self.is_playing:
            await self._advance_queue()

    async def skip(self) -> Track | None:
        """Stop the current track, letting the queue advance naturally."""

        if self.queue.current is None:
            return None
        session_id = self.node.require_session()
        await self.node.rest.update_player(
            session_id, self.guild_id, payload={"track": {"encoded": None}}
        )
        return self.queue.current

    async def stop(self) -> None:
        """Stop playback without advancing the queue."""

        session_id = self.node.require_session()
        await self.node.rest.update_player(
            session_id, self.guild_id, payload={"track": {"encoded": None}}
        )
        self.queue.requeue_current()

    async def pause(self, paused: bool = True) -> None:
        session_id = self.node.require_session()
        await self.node.rest.update_player(session_id, self.guild_id, payload={"paused": paused})
        self.paused = paused

    async def resume(self) -> None:
        await self.pause(False)

    async def seek(self, position_ms: int) -> None:
        session_id = self.node.require_session()
        await self.node.rest.update_player(
            session_id, self.guild_id, payload={"position": position_ms}
        )
        self._last_position_ms = position_ms
        self._last_position_at = time.monotonic()

    async def set_volume(self, volume: int) -> None:
        volume = max(0, min(1000, volume))
        session_id = self.node.require_session()
        await self.node.rest.update_player(session_id, self.guild_id, payload={"volume": volume})
        self.volume = volume

    async def set_filters(self, filters: FilterChain) -> None:
        session_id = self.node.require_session()
        await self.node.rest.update_player(
            session_id, self.guild_id, payload={"filters": filters.to_payload()}
        )
        self.filters = filters

    async def clear_filters(self) -> None:
        await self.set_filters(FilterChain())

    def set_loop_mode(self, mode: LoopMode) -> None:
        self.queue.loop_mode = mode

    @property
    def position_ms(self) -> int:
        """Estimated current playback position, interpolated between
        the last ``playerUpdate`` OP and now.
        """

        if self.paused or self.queue.current is None:
            return self._last_position_ms
        elapsed = (time.monotonic() - self._last_position_at) * 1000
        estimated = self._last_position_ms + elapsed
        track = self.queue.current
        if track.is_finite:
            estimated = min(estimated, track.length_ms)
        return int(estimated)

    @property
    def ping_ms(self) -> int:
        return self._ping_ms

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        current = self.queue.current.title if self.queue.current else None
        return f"<Player guild={self.guild_id} node={self.node.name!r} current={current!r}>"
