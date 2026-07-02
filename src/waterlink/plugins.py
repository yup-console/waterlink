"""Detection and typed helpers for common Lavalink server plugins.

waterlink doesn't require any plugin, but it can detect what's loaded on
a node (via ``/v4/info``) and offer small conveniences for well-known ones
like LavaSrc (Spotify/Apple Music/Deezer resolution) and SponsorBlock.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from .errors import PluginNotLoadedError
from .node import Node
from .search import SearchPrefix
from .typing import JSONDict

logger = logging.getLogger("waterlink.plugins")

__all__ = ["PluginInfo", "PluginRegistry", "LavaSrcHelper", "SponsorBlockHelper"]


@dataclass(slots=True, frozen=True)
class PluginInfo:
    name: str
    version: str


class PluginRegistry:
    """Caches the set of plugins reported by a node's ``/v4/info``."""

    def __init__(self, node: Node) -> None:
        self.node = node
        self._plugins: dict[str, PluginInfo] = {}
        self._loaded = False

    async def refresh(self) -> None:
        info = await self.node.rest.get_info()
        plugins = info.get("plugins", [])
        self._plugins = {p["name"]: PluginInfo(name=p["name"], version=p.get("version", "")) for p in plugins}
        self._loaded = True

    def is_loaded(self, name: str) -> bool:
        return name in self._plugins

    def require(self, name: str) -> PluginInfo:
        plugin = self._plugins.get(name)
        if plugin is None:
            raise PluginNotLoadedError(f"Plugin {name!r} is not loaded on node {self.node.name!r}")
        return plugin

    @property
    def loaded_plugins(self) -> tuple[PluginInfo, ...]:
        return tuple(self._plugins.values())


class LavaSrcHelper:
    """Convenience search-prefix helpers assuming the LavaSrc plugin.

    LavaSrc adds Spotify/Apple Music/Deezer/Yandex search support to
    Lavalink. This helper just centralizes the prefix strings so callers
    don't need to remember them, and validates the plugin is present
    before use.
    """

    PLUGIN_NAME = "lavasrc-plugin"

    def __init__(self, registry: PluginRegistry) -> None:
        self._registry = registry

    def _require(self) -> None:
        self._registry.require(self.PLUGIN_NAME)

    def spotify_query(self, query: str) -> str:
        self._require()
        return f"{SearchPrefix.SPOTIFY}:{query}"

    def apple_music_query(self, query: str) -> str:
        self._require()
        return f"{SearchPrefix.APPLE_MUSIC}:{query}"

    def deezer_query(self, query: str) -> str:
        self._require()
        return f"{SearchPrefix.DEEZER}:{query}"


class SponsorBlockHelper:
    """Configures the SponsorBlock plugin's segment-skipping categories
    for a player, if the plugin is loaded on its node.
    """

    PLUGIN_NAME = "sponsorblock-plugin"

    DEFAULT_CATEGORIES = ("sponsor", "selfpromo", "interaction")

    def __init__(self, registry: PluginRegistry) -> None:
        self._registry = registry

    async def set_categories(self, player, categories: tuple[str, ...] = DEFAULT_CATEGORIES) -> None:  # type: ignore[no-untyped-def]
        self._registry.require(self.PLUGIN_NAME)
        session_id = player.node.require_session()
        await player.node.rest.update_player(
            session_id,
            player.guild_id,
            payload={"pluginInfo": {"sponsorblock": {"categories": list(categories)}}},
        )
