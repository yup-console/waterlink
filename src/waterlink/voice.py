"""Voice connection glue between a Discord library and a Lavalink player.

waterlink registers a small ``VoiceProtocol``-compatible class with the
detected Discord library. When the library establishes or updates a voice
session it calls back into this class, which forwards the resulting voice
server/state payload to the associated :class:`~waterlink.player.Player`
so it can update the node.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable

from .errors import VoiceStateError

if TYPE_CHECKING:
    from .player import Player

logger = logging.getLogger("waterlink.voice")

__all__ = ["VoiceServerUpdate", "VoiceStateUpdate", "make_voice_protocol"]


@dataclass(slots=True, frozen=True)
class VoiceServerUpdate:
    token: str
    endpoint: str | None
    guild_id: int

    @classmethod
    def from_payload(cls, data: dict[str, Any]) -> "VoiceServerUpdate":
        endpoint = data.get("endpoint")
        if endpoint:
            # Lavalink v4 expects a bare host[:port] with no URI scheme.
            # Discord's gateway payload normally already omits the scheme,
            # but guard against it anyway since some library versions /
            # proxies have been observed to include "wss://".
            endpoint = endpoint.removeprefix("wss://").removeprefix("https://").rstrip("/")
        return cls(
            token=data["token"],
            endpoint=endpoint,
            guild_id=int(data["guild_id"]),
        )


@dataclass(slots=True, frozen=True)
class VoiceStateUpdate:
    session_id: str
    channel_id: int | None
    guild_id: int
    user_id: int

    @classmethod
    def from_payload(cls, data: dict[str, Any]) -> "VoiceStateUpdate":
        channel_id = data.get("channel_id")
        return cls(
            session_id=data["session_id"],
            channel_id=int(channel_id) if channel_id is not None else None,
            guild_id=int(data["guild_id"]),
            user_id=int(data["user_id"]),
        )


def make_voice_protocol(base_cls: type, player_factory: "Callable[[Any], Any]") -> type:
    """Build a ``VoiceProtocol``-compatible class bound to a specific
    library's base class (e.g. ``discord.VoiceProtocol``).

    ``player_factory`` is called with the constructed voice-protocol
    instance as soon as ``__init__`` runs (before ``connect()`` can
    possibly be invoked by the library) and must return the
    :class:`~waterlink.player.Player` to bind. This guarantees the player
    is attached before any gateway callback (``on_voice_state_update`` /
    ``on_voice_server_update``) can fire — those are dispatched by the
    library only once the voice client is registered via
    ``channel.connect(cls=...)``, and construction always happens inside
    that call before any event can arrive.
    """

    class WaterlinkVoiceProtocol(base_cls):  # type: ignore[misc,valid-type]
        player: "Player | None" = None

        def __init__(self, client: Any, channel: Any) -> None:
            super().__init__(client, channel)
            self.player = player_factory(self)

        async def on_voice_server_update(self, data: dict[str, Any]) -> None:
            if self.player is None:
                logger.debug("Voice server update received with no bound player")
                return
            try:
                update = VoiceServerUpdate.from_payload(data)
            except KeyError as exc:
                raise VoiceStateError(f"Malformed voice server payload: missing {exc}") from exc
            await self.player._on_voice_server_update(update)

        async def on_voice_state_update(self, data: dict[str, Any]) -> None:
            if self.player is None:
                return
            try:
                update = VoiceStateUpdate.from_payload(data)
            except KeyError as exc:
                raise VoiceStateError(f"Malformed voice state payload: missing {exc}") from exc
            await self.player._on_voice_state_update(update)

        async def connect(
            self,
            *,
            timeout: float,
            reconnect: bool,
            self_deaf: bool = True,
            self_mute: bool = False,
        ) -> None:
            # We intentionally do NOT run the base VoiceClient's UDP/voice
            # websocket connection logic — Lavalink owns actual audio
            # transport, not us. We do still need to perform the same
            # first step the base implementation does: sending the
            # gateway OP 4 voice state update, which is what causes
            # Discord to send back VOICE_STATE_UPDATE / VOICE_SERVER_UPDATE.
            await self.channel.guild.change_voice_state(
                channel=self.channel, self_mute=self_mute, self_deaf=self_deaf
            )

        async def disconnect(self, *, force: bool = False) -> None:
            if self.player is not None:
                await self.player._on_voice_disconnect(force=force)
            try:
                await self.channel.guild.change_voice_state(channel=None)
            except Exception:  # noqa: BLE001
                pass
            self.cleanup()

    WaterlinkVoiceProtocol.__name__ = "WaterlinkVoiceProtocol"
    WaterlinkVoiceProtocol.__qualname__ = "WaterlinkVoiceProtocol"
    return WaterlinkVoiceProtocol
