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
from typing import TYPE_CHECKING, Any

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
        return cls(
            token=data["token"],
            endpoint=data.get("endpoint"),
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


def make_voice_protocol(base_cls: type) -> type:
    """Build a ``VoiceProtocol``-compatible class bound to a specific
    library's base class (e.g. ``discord.VoiceProtocol``).

    The returned class forwards ``on_voice_server_update`` and
    ``on_voice_state_update`` callbacks to the :class:`Player` stashed on
    ``self.player`` by :mod:`waterlink.player` when it connects.
    """

    class WaterlinkVoiceProtocol(base_cls):  # type: ignore[misc,valid-type]
        player: "Player | None" = None

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
            # Actual channel join is driven by Player.connect(), which
            # calls the library's own gateway voice-state-change API
            # before this VoiceProtocol is attached. This override exists
            # only to satisfy the library's VoiceProtocol contract.
            return None

        async def disconnect(self, *, force: bool = False) -> None:
            if self.player is not None:
                await self.player._on_voice_disconnect(force=force)

    WaterlinkVoiceProtocol.__name__ = "WaterlinkVoiceProtocol"
    WaterlinkVoiceProtocol.__qualname__ = "WaterlinkVoiceProtocol"
    return WaterlinkVoiceProtocol
