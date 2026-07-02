"""A single Lavalink node: REST client + websocket + live stats."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import aiohttp

from .errors import NodeNotReadyError
from .events import (
    EventBus,
    NodeDisconnectedEvent,
    NodeErrorEvent,
    NodeReadyEvent,
    NodeReconnectingEvent,
    NodeStatsUpdateEvent,
    PlayerUpdateEvent,
    TrackEndEvent,
    TrackExceptionEvent,
    TrackStartEvent,
    TrackStuckEvent,
    WebSocketClosedEvent,
)
from .rest import RESTClient
from .tracks import Track
from .typing import JSONDict
from .websocket import NodeWebSocket

if TYPE_CHECKING:
    from .player import Player

logger = logging.getLogger("waterlink.node")

__all__ = ["Node", "NodeStats"]


@dataclass(slots=True)
class NodeStats:
    """Latest ``stats`` OP payload from a node, kept for load balancing."""

    players: int = 0
    playing_players: int = 0
    uptime_ms: int = 0
    cpu_system_load: float = 0.0
    cpu_lavalink_load: float = 0.0
    memory_used_bytes: int = 0
    memory_free_bytes: int = 0
    frames_sent: int | None = None
    frames_nulled: int | None = None
    frames_deficit: int | None = None

    @classmethod
    def from_payload(cls, payload: JSONDict) -> "NodeStats":
        cpu = payload.get("cpu", {})
        memory = payload.get("memory", {})
        frame_stats = payload.get("frameStats") or {}
        return cls(
            players=payload.get("players", 0),
            playing_players=payload.get("playingPlayers", 0),
            uptime_ms=payload.get("uptime", 0),
            cpu_system_load=cpu.get("systemLoad", 0.0),
            cpu_lavalink_load=cpu.get("lavalinkLoad", 0.0),
            memory_used_bytes=memory.get("used", 0),
            memory_free_bytes=memory.get("free", 0),
            frames_sent=frame_stats.get("sent"),
            frames_nulled=frame_stats.get("nulled"),
            frames_deficit=frame_stats.get("deficit"),
        )

    @property
    def penalty_score(self) -> float:
        """A lower-is-better load heuristic used by the node pool.

        Weighs playing players most heavily, then CPU load, then any
        frame loss reported by the node (a sign of audio glitches).
        """

        score = self.playing_players * 2.0
        score += self.cpu_lavalink_load * 10.0
        if self.frames_deficit and self.frames_deficit > 0:
            score += self.frames_deficit * 0.05
        return score


class Node:
    """A managed connection to one Lavalink server.

    A :class:`Node` is not usually constructed directly — use
    :meth:`waterlink.pool.NodePool.add_node`, which wires it up to the
    pool's shared event bus and player registry.
    """

    def __init__(
        self,
        *,
        name: str,
        host: str,
        port: int,
        password: str,
        user_id: int,
        secure: bool = False,
        session: aiohttp.ClientSession,
        events: EventBus,
        region: str | None = None,
        resume_timeout_seconds: int = 60,
    ) -> None:
        self.name = name
        self.host = host
        self.port = port
        self.secure = secure
        self.region = region
        self._password = password
        self._user_id = user_id
        self._events = events
        self._resume_timeout = resume_timeout_seconds

        self.rest = RESTClient(
            host=host, port=port, password=password, secure=secure, session=session
        )
        self._ws = NodeWebSocket(
            host=host,
            port=port,
            password=password,
            user_id=user_id,
            secure=secure,
            session=session,
            on_message=self._handle_message,
            on_open=self._handle_open,
            on_close=self._handle_close,
            on_reconnecting=self._handle_reconnecting,
        )

        self.session_id: str | None = None
        self.stats: NodeStats = NodeStats()
        self._ready = False
        self._players: dict[int, "Player"] = {}

    # -- lifecycle ----------------------------------------------------------- #

    async def connect(self) -> None:
        await self._ws.connect()

    async def close(self) -> None:
        await self._ws.close()
        self._ready = False

    @property
    def is_connected(self) -> bool:
        return self._ws.is_connected

    @property
    def is_ready(self) -> bool:
        return self._ready and self.session_id is not None

    @property
    def player_count(self) -> int:
        return len(self._players)

    def register_player(self, guild_id: int, player: "Player") -> None:
        self._players[guild_id] = player

    def unregister_player(self, guild_id: int) -> None:
        self._players.pop(guild_id, None)

    def get_player(self, guild_id: int) -> "Player | None":
        return self._players.get(guild_id)

    def require_session(self) -> str:
        if self.session_id is None:
            raise NodeNotReadyError("Node has no active session yet", node_name=self.name)
        return self.session_id

    # -- websocket callbacks --------------------------------------------------- #

    async def _handle_open(self) -> None:
        logger.debug("Node %s: websocket opened, awaiting ready OP", self.name)

    async def _handle_close(self, code: int, reason: str) -> None:
        self._ready = False
        self._events.dispatch(
            NodeDisconnectedEvent(node=self, code=code, reason=reason, will_reconnect=True)
        )

    async def _handle_reconnecting(self, attempt: int, delay: float) -> None:
        self._events.dispatch(NodeReconnectingEvent(node=self, attempt=attempt, delay=delay))

    async def _handle_message(self, payload: JSONDict) -> None:
        op = payload.get("op")
        try:
            if op == "ready":
                await self._on_ready(payload)
            elif op == "stats":
                self._on_stats(payload)
            elif op == "playerUpdate":
                self._on_player_update(payload)
            elif op == "event":
                self._on_event(payload)
            else:
                logger.debug("Node %s: unhandled OP %r", self.name, op)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Node %s: error handling OP %r", self.name, op)
            self._events.dispatch(NodeErrorEvent(node=self, error=exc))

    async def _on_ready(self, payload: JSONDict) -> None:
        self.session_id = payload.get("sessionId")
        resumed = bool(payload.get("resumed", False))
        self._ready = True
        self._ws.set_resume_session_id(self.session_id)

        if self.session_id:
            try:
                await self.rest.update_session(
                    self.session_id,
                    payload={"resuming": True, "timeout": self._resume_timeout},
                )
            except Exception:  # noqa: BLE001
                logger.warning("Node %s: failed to enable session resuming", self.name)

        logger.info("Node %s ready (session=%s, resumed=%s)", self.name, self.session_id, resumed)
        self._events.dispatch(
            NodeReadyEvent(node=self, resumed=resumed, session_id=self.session_id or "")
        )

    def _on_stats(self, payload: JSONDict) -> None:
        self.stats = NodeStats.from_payload(payload)
        self._events.dispatch(NodeStatsUpdateEvent(node=self))

    def _on_player_update(self, payload: JSONDict) -> None:
        guild_id = int(payload.get("guildId", 0))
        player = self._players.get(guild_id)
        if player is None:
            return
        state = payload.get("state", {})
        position = int(state.get("position", 0))
        connected = bool(state.get("connected", False))
        ping = int(state.get("ping", -1))
        player._on_state_update(position_ms=position, connected=connected, ping_ms=ping)
        self._events.dispatch(
            PlayerUpdateEvent(player=player, position_ms=position, connected=connected, ping_ms=ping)
        )

    def _on_event(self, payload: JSONDict) -> None:
        guild_id = int(payload.get("guildId", 0))
        player = self._players.get(guild_id)
        if player is None:
            logger.debug("Node %s: event for unknown guild %s ignored", self.name, guild_id)
            return

        event_type = payload.get("type")

        if event_type == "TrackStartEvent":
            track = Track.from_payload(payload["track"])
            player._on_track_start(track)
            self._events.dispatch(TrackStartEvent(player=player, track=track))

        elif event_type == "TrackEndEvent":
            track = Track.from_payload(payload["track"])
            reason = payload.get("reason", "FINISHED")
            player._on_track_end(track, reason)
            self._events.dispatch(TrackEndEvent(player=player, track=track, reason=reason))

        elif event_type == "TrackExceptionEvent":
            track = Track.from_payload(payload["track"])
            exception = payload.get("exception", {})
            self._events.dispatch(
                TrackExceptionEvent(
                    player=player,
                    track=track,
                    message=exception.get("message"),
                    severity=exception.get("severity", "UNKNOWN"),
                    cause=exception.get("cause", "unknown"),
                )
            )

        elif event_type == "TrackStuckEvent":
            track = Track.from_payload(payload["track"])
            self._events.dispatch(
                TrackStuckEvent(
                    player=player, track=track, threshold_ms=payload.get("thresholdMs", 0)
                )
            )

        elif event_type == "WebSocketClosedEvent":
            player._on_voice_ws_closed()
            self._events.dispatch(
                WebSocketClosedEvent(
                    player=player,
                    code=payload.get("code", 0),
                    reason=payload.get("reason", ""),
                    by_remote=bool(payload.get("byRemote", False)),
                )
            )
        else:
            logger.debug("Node %s: unhandled event type %r", self.name, event_type)

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        state = "ready" if self.is_ready else ("connected" if self.is_connected else "disconnected")
        return f"<Node name={self.name!r} host={self.host}:{self.port} state={state}>"
