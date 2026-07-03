"""waterlink — a modern, async Lavalink v4 client for Python Discord bots.

waterlink auto-detects discord.py, py-cord, nextcord, or disnake and wires
up voice connections, node pooling with load-aware routing, a rich queue
model, typed audio filters, autoplay, crossfade, state persistence, and
plugin helpers (LavaSrc, SponsorBlock) — all built for Lavalink v4's REST
and websocket protocol.

Quick start
-----------
::

    import waterlink

    client = waterlink.WaterlinkClient(bot=bot)

    @bot.event
    async def on_ready():
        await client.add_node(host="localhost", port=2333, password="youshallnotpass")

    player = await client.connect(guild_id, channel_id)
    result = await client.search("rick astley never gonna give you up")
    if isinstance(result, waterlink.SearchTracksResult):
        await player.enqueue(result.tracks[0])
"""

from __future__ import annotations

from ._version import __version__, __version_info__
from .autoplay import AutoplayEngine, AutoplayStrategy, related_track_strategy
from .cache import TTLCache
from .crossfade import CrossfadeConfig, CrossfadeController
from .errors import (
    ConfigurationError,
    FilterError,
    InvalidFilterValueError,
    InvalidQueueIndexError,
    LibraryNotSupportedError,
    NodeConnectionError,
    NodeError,
    NodeNotReadyError,
    NoAvailableNodeError,
    PersistenceError,
    PlayerAlreadyConnectedError,
    PlayerError,
    PlayerNotConnectedError,
    PluginError,
    PluginNotLoadedError,
    QueueEmptyError,
    QueueError,
    RESTError,
    RESTRequestError,
    RESTResponseError,
    SearchError,
    SessionNotResumedError,
    TrackDecodeError,
    TrackLoadError,
    VoiceStateError,
    WaterlinkError,
)
from .events import (
    Event,
    EventBus,
    NodeDisconnectedEvent,
    NodeErrorEvent,
    NodeReadyEvent,
    NodeReconnectingEvent,
    NodeStatsUpdateEvent,
    PlayerUpdateEvent,
    QueueEndEvent,
    TrackEndEvent,
    TrackExceptionEvent,
    TrackStartEvent,
    TrackStuckEvent,
    WebSocketClosedEvent,
)
from .filters import (
    ChannelMix,
    Distortion,
    Equalizer,
    EqualizerBand,
    FilterChain,
    Karaoke,
    LowPass,
    Rotation,
    Timescale,
    Tremolo,
    Vibrato,
)
from .formatting import format_duration, now_playing_summary, progress_bar, queue_page, track_line
from .manager import WaterlinkClient
from .metadata import CleanedMetadata, TitleCleaner, clean_track
from .metrics import MetricsCollector
from .node import Node, NodeStats
from .normalize import NormalizationConfig, VolumeNormalizer
from .persistence import (
    InMemoryBackend,
    JSONFileBackend,
    PersistenceBackend,
    PlayerSnapshot,
)
from .player import Player
from .plugins import LavaSrcHelper, PluginInfo, PluginRegistry, SponsorBlockHelper
from .pool import NodePool, RoutingStrategy
from .queue import LoopMode, Queue
from .rest import RESTClient
from .search import SearchPrefix, build_query
from .tracing import ContextLogger, configure_logging, get_logger
from .tracks import (
    EmptyResult,
    ErrorResult,
    Playlist,
    PlaylistResult,
    SearchResult,
    SearchTracksResult,
    Track,
    TrackResult,
)
from .watchdog import Watchdog, WatchdogConfig

__all__ = [
    "__version__",
    "__version_info__",
    # manager
    "WaterlinkClient",
    # pool / node
    "NodePool",
    "RoutingStrategy",
    "Node",
    "NodeStats",
    # player / queue
    "Player",
    "Queue",
    "LoopMode",
    # tracks / search
    "Track",
    "Playlist",
    "SearchResult",
    "TrackResult",
    "PlaylistResult",
    "SearchTracksResult",
    "EmptyResult",
    "ErrorResult",
    "SearchPrefix",
    "build_query",
    # filters
    "FilterChain",
    "Equalizer",
    "EqualizerBand",
    "Karaoke",
    "Timescale",
    "Tremolo",
    "Vibrato",
    "Rotation",
    "Distortion",
    "ChannelMix",
    "LowPass",
    # events
    "Event",
    "EventBus",
    "NodeReadyEvent",
    "NodeDisconnectedEvent",
    "NodeReconnectingEvent",
    "NodeErrorEvent",
    "NodeStatsUpdateEvent",
    "TrackStartEvent",
    "TrackEndEvent",
    "TrackExceptionEvent",
    "TrackStuckEvent",
    "WebSocketClosedEvent",
    "QueueEndEvent",
    "PlayerUpdateEvent",
    # autoplay / crossfade
    "AutoplayEngine",
    "AutoplayStrategy",
    "related_track_strategy",
    "CrossfadeController",
    "CrossfadeConfig",
    # normalization
    "NormalizationConfig",
    "VolumeNormalizer",
    # metadata cleaning
    "TitleCleaner",
    "CleanedMetadata",
    "clean_track",
    # persistence
    "PersistenceBackend",
    "InMemoryBackend",
    "JSONFileBackend",
    "PlayerSnapshot",
    # plugins
    "PluginRegistry",
    "PluginInfo",
    "LavaSrcHelper",
    "SponsorBlockHelper",
    # observability
    "MetricsCollector",
    "Watchdog",
    "WatchdogConfig",
    "configure_logging",
    "get_logger",
    "ContextLogger",
    # rest
    "RESTClient",
    # caching
    "TTLCache",
    # formatting
    "format_duration",
    "progress_bar",
    "track_line",
    "queue_page",
    "now_playing_summary",
    # errors
    "WaterlinkError",
    "ConfigurationError",
    "NodeError",
    "NodeConnectionError",
    "NodeNotReadyError",
    "NoAvailableNodeError",
    "RESTError",
    "RESTRequestError",
    "RESTResponseError",
    "TrackLoadError",
    "TrackDecodeError",
    "SearchError",
    "PlayerError",
    "PlayerNotConnectedError",
    "PlayerAlreadyConnectedError",
    "QueueError",
    "QueueEmptyError",
    "InvalidQueueIndexError",
    "FilterError",
    "InvalidFilterValueError",
    "PluginError",
    "PluginNotLoadedError",
    "PersistenceError",
    "SessionNotResumedError",
    "VoiceStateError",
    "LibraryNotSupportedError",
]
