"""Top-level client tying node pool, players, and the Discord library together."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

from ._compat import DetectedLibrary, detect_library
from .errors import ConfigurationError, TrackLoadError
from .events import EventBus
from .metadata import TitleCleaner
from .node import Node
from .player import Player
from .pool import NodePool, RoutingStrategy
from .search import build_query, parse_load_result
from .tracks import ErrorResult, PlaylistResult, SearchResult, SearchTracksResult, TrackResult
from .voice import make_voice_protocol

logger = logging.getLogger("waterlink.manager")

__all__ = ["WaterlinkClient"]


class WaterlinkClient:
    """The main entry point for waterlink.

    Wraps a :class:`~waterlink.pool.NodePool` and manages one
    :class:`~waterlink.player.Player` per guild, auto-detecting whichever
    supported Discord library (discord.py, py-cord, nextcord, disnake) is
    installed to hook into its voice gateway plumbing.

    Example
    -------
    ::

        client = WaterlinkClient(bot=bot)
        await client.add_node(host="localhost", port=2333, password="youshallnotpass")

        player = await client.connect(guild_id, channel_id)
        result = await client.search("never gonna give you up")
        await player.enqueue(result.tracks[0])
    """

    def __init__(
        self,
        *,
        bot: Any,
        session: aiohttp.ClientSession | None = None,
        default_routing_strategy: RoutingStrategy = RoutingStrategy.LOWEST_LOAD,
        clean_metadata: bool = False,
        title_cleaner: TitleCleaner | None = None,
    ) -> None:
        """
        Parameters
        ----------
        clean_metadata:
            When ``True``, :meth:`search` automatically cleans noisy
            YouTube-style titles/authors (e.g. turning
            ``"Tere Liye | Arijit Singh | Viral | T-Series"`` uploaded by
            ``"T-Series"`` into title ``"Tere Liye"`` by artist
            ``"Arijit Singh"``) before returning results. Defaults to
            ``False`` so existing behavior is unchanged unless you opt in.
            Can also be requested per-call via ``search(..., clean=True)``
            regardless of this default.
        title_cleaner:
            Optionally supply a custom :class:`~waterlink.metadata.TitleCleaner`
            (e.g. with extra regional label names) instead of the default.
        """

        self.bot = bot
        self._library: DetectedLibrary = detect_library()
        self._user_id = _extract_user_id(bot)

        self.events: EventBus = EventBus()
        self.pool: NodePool = NodePool(
            user_id=self._user_id,
            session=session,
            events=self.events,
            default_strategy=default_routing_strategy,
        )
        self._players: dict[int, Player] = {}
        self._voice_protocol_base = _resolve_voice_protocol_base(self._library)
        self._clean_metadata_default = clean_metadata
        self._title_cleaner = title_cleaner or TitleCleaner()

        self._register_gateway_listeners()

    @property
    def library_name(self) -> str:
        return self._library.name

    # -- node management ------------------------------------------------- #

    async def add_node(
        self,
        *,
        name: str = "default",
        host: str = "localhost",
        port: int = 2333,
        password: str = "youshallnotpass",
        secure: bool = False,
        region: str | None = None,
    ) -> Node:
        return await self.pool.add_node(
            name=name, host=host, port=port, password=password, secure=secure, region=region
        )

    async def close(self) -> None:
        for player in list(self._players.values()):
            await player.destroy()
        await self.pool.close()

    # -- players ----------------------------------------------------------- #

    def get_player(self, guild_id: int) -> Player | None:
        return self._players.get(guild_id)

    async def connect(
        self,
        guild_id: int,
        channel_id: int,
        *,
        self_deaf: bool = True,
        self_mute: bool = False,
        strategy: RoutingStrategy | None = None,
        region: str | None = None,
    ) -> Player:
        """Create (if needed) and connect a player for ``guild_id``."""

        existing = self._players.get(guild_id)
        if existing is not None:
            await existing.connect(channel_id, self_deaf=self_deaf, self_mute=self_mute, move=True)
            return existing

        guild = self._get_guild(guild_id)
        if guild is None:
            raise ConfigurationError(f"Guild {guild_id} not found in the bot's cache")

        channel = guild.get_channel(channel_id)
        if channel is None:
            raise ConfigurationError(
                f"Channel {channel_id} not found in guild {guild_id}'s cache. "
                "Make sure the bot has the Guilds intent enabled."
            )

        node = self.pool.best_node(strategy=strategy, region=region)

        # Any stale voice client on this guild (e.g. leftover from a crash)
        # must be cleared first, or discord.py will refuse to register a
        # new one for the same guild.
        existing_vc = getattr(guild, "voice_client", None)
        if existing_vc is not None:
            try:
                await existing_vc.disconnect(force=True)
            except Exception:  # noqa: BLE001
                pass

        player_box: dict[str, Player] = {}

        def _bind_player(voice_protocol: Any) -> Player:
            # Called synchronously from WaterlinkVoiceProtocol.__init__,
            # which itself runs inside channel.connect() below — i.e.
            # strictly before the library can dispatch any
            # VOICE_STATE_UPDATE/VOICE_SERVER_UPDATE to this instance.
            # This guarantees no gateway callback ever arrives before a
            # Player exists to receive it.
            player = Player(guild_id=guild_id, pool=self.pool, node=node, voice_protocol=None)
            player.voice_protocol = voice_protocol
            player.channel_id = channel_id
            player_box["player"] = player
            return player

        voice_protocol_cls = make_voice_protocol(self._voice_protocol_base, _bind_player)

        # channel.connect(cls=...) is the library's documented, supported
        # way to register a custom VoiceProtocol: it constructs the class,
        # stores it in the guild's internal voice-client registry (which is
        # what the gateway dispatcher looks up by guild ID to route
        # VOICE_STATE_UPDATE / VOICE_SERVER_UPDATE), and calls its
        # .connect(). Constructing a VoiceProtocol manually skips that
        # registration and events are silently dropped, so this call must
        # go through the library rather than being done by hand.
        await channel.connect(
            cls=voice_protocol_cls,
            self_deaf=self_deaf,
            self_mute=self_mute,
            reconnect=False,
            timeout=15.0,
        )

        player = player_box["player"]
        self._players[guild_id] = player

        try:
            await asyncio.wait_for(player._pending_voice_update.wait(), timeout=15.0)
        except asyncio.TimeoutError:
            logger.warning(
                "Guild %s: voice connection did not confirm within timeout", guild_id
            )

        return player

    async def disconnect(self, guild_id: int) -> None:
        player = self._players.pop(guild_id, None)
        if player is not None:
            await player.destroy()

    # -- search -------------------------------------------------------------- #

    async def search(
        self,
        query: str,
        *,
        prefix: str | None = None,
        node: Node | None = None,
        clean: bool | None = None,
    ) -> SearchResult:
        """Resolve a search query or URI into a :class:`SearchResult`.

        Raises :class:`~waterlink.errors.TrackLoadError` if Lavalink
        reports a load error for the query.

        Parameters
        ----------
        clean:
            Overrides the client-level ``clean_metadata`` default for
            this call. When effectively ``True``, every :class:`Track` in
            the result has its title/author run through the configured
            :class:`~waterlink.metadata.TitleCleaner` (see
            :meth:`WaterlinkClient.__init__`) — useful for YouTube results
            where the uploader is a record label rather than the artist.
        """

        target_node = node or self.pool.best_node()
        identifier = build_query(query, prefix=prefix)
        payload = await target_node.rest.load_tracks(identifier)
        result = parse_load_result(payload)
        if isinstance(result, ErrorResult):
            raise TrackLoadError(result.message, severity=result.severity, cause=result.cause)

        should_clean = self._clean_metadata_default if clean is None else clean
        if should_clean:
            result = self._clean_result(result)

        return result

    def _clean_result(self, result: SearchResult) -> SearchResult:
        from dataclasses import replace as _replace

        if isinstance(result, TrackResult):
            return TrackResult(track=self._title_cleaner.clean_track(result.track))
        if isinstance(result, SearchTracksResult):
            return SearchTracksResult(
                tracks=tuple(self._title_cleaner.clean_track(t) for t in result.tracks)
            )
        if isinstance(result, PlaylistResult):
            cleaned_tracks = tuple(
                self._title_cleaner.clean_track(t) for t in result.playlist.tracks
            )
            cleaned_playlist = _replace(result.playlist, tracks=cleaned_tracks)
            return PlaylistResult(playlist=cleaned_playlist)
        return result

    # -- gateway wiring -------------------------------------------------------- #

    def _register_gateway_listeners(self) -> None:
        """Hook raw voice gateway dispatches into the active players.

        Most libraries deliver ``VOICE_SERVER_UPDATE`` / ``VOICE_STATE_UPDATE``
        straight to the attached ``VoiceProtocol`` automatically once a
        player's voice_protocol is registered via ``guild.change_voice_state``,
        so no extra listener is usually required. This hook exists for
        libraries/setups that need an explicit dispatch bridge.
        """

        return None

    def _get_guild(self, guild_id: int) -> Any:
        get_guild = getattr(self.bot, "get_guild", None)
        if get_guild is None:
            return None
        return get_guild(guild_id)


def _extract_user_id(bot: Any) -> int:
    user = getattr(bot, "user", None)
    if user is not None and getattr(user, "id", None):
        return int(user.id)
    application_id = getattr(bot, "application_id", None)
    if application_id:
        return int(application_id)
    raise ConfigurationError(
        "Could not determine the bot's user ID. Ensure the bot is logged in "
        "(has a `.user`) before constructing WaterlinkClient, or pass a bot "
        "with `.application_id` set."
    )


def _resolve_voice_protocol_base(library: DetectedLibrary) -> type:
    module = library.module
    base = getattr(module, "VoiceProtocol", None)
    if base is None:
        raise ConfigurationError(
            f"Detected library {library.name!r} does not expose a VoiceProtocol class"
        )
    return base
