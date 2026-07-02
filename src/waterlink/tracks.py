"""Track and playlist data models.

These are thin, immutable-by-convention wrappers around the JSON shapes
returned by Lavalink v4's ``/loadtracks`` and player APIs. Fields mirror
Lavalink's ``info`` object using Pythonic snake_case names, while
:pyattr:`Track.raw` always retains the original payload for anything not
explicitly modeled.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .typing import JSONDict

__all__ = [
    "Track",
    "Playlist",
    "SearchResult",
    "EmptyResult",
    "PlaylistResult",
    "TrackResult",
    "SearchTracksResult",
    "ErrorResult",
]


@dataclass(slots=True, frozen=True)
class Track:
    """A single playable track as reported by Lavalink.

    Instances are frozen; to attach bot-side metadata (e.g. who requested
    a track) use :meth:`with_requester` or :meth:`with_extra`, both of
    which return a new :class:`Track`.
    """

    encoded: str
    identifier: str
    is_seekable: bool
    author: str
    length_ms: int
    is_stream: bool
    position_ms: int
    title: str
    source_name: str
    uri: str | None = None
    artwork_url: str | None = None
    isrc: str | None = None
    requester_id: int | None = None
    extra: JSONDict = field(default_factory=dict)
    plugin_info: JSONDict = field(default_factory=dict)
    raw: JSONDict = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_payload(cls, payload: JSONDict) -> "Track":
        info = payload.get("info", {})
        return cls(
            encoded=payload.get("encoded", ""),
            identifier=info.get("identifier", ""),
            is_seekable=bool(info.get("isSeekable", False)),
            author=info.get("author", ""),
            length_ms=int(info.get("length", 0)),
            is_stream=bool(info.get("isStream", False)),
            position_ms=int(info.get("position", 0)),
            title=info.get("title", ""),
            source_name=info.get("sourceName", "unknown"),
            uri=info.get("uri"),
            artwork_url=info.get("artworkUrl"),
            isrc=info.get("isrc"),
            plugin_info=dict(payload.get("pluginInfo", {}) or {}),
            raw=payload,
        )

    def to_payload(self) -> JSONDict:
        """Rebuild a Lavalink-shaped payload, e.g. for persistence."""

        return {
            "encoded": self.encoded,
            "info": {
                "identifier": self.identifier,
                "isSeekable": self.is_seekable,
                "author": self.author,
                "length": self.length_ms,
                "isStream": self.is_stream,
                "position": self.position_ms,
                "title": self.title,
                "sourceName": self.source_name,
                "uri": self.uri,
                "artworkUrl": self.artwork_url,
                "isrc": self.isrc,
            },
            "pluginInfo": self.plugin_info,
        }

    def with_requester(self, user_id: int) -> "Track":
        from dataclasses import replace

        return replace(self, requester_id=user_id)

    def with_extra(self, **values: Any) -> "Track":
        from dataclasses import replace

        merged = {**self.extra, **values}
        return replace(self, extra=merged)

    @property
    def duration_seconds(self) -> float:
        return self.length_ms / 1000

    @property
    def is_finite(self) -> bool:
        return not self.is_stream

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"<Track title={self.title!r} author={self.author!r} source={self.source_name!r}>"


@dataclass(slots=True, frozen=True)
class Playlist:
    """A named collection of tracks, optionally with a selected index."""

    name: str
    tracks: tuple[Track, ...]
    selected_index: int | None = None
    plugin_info: JSONDict = field(default_factory=dict)

    @classmethod
    def from_payload(cls, payload: JSONDict) -> "Playlist":
        info = payload.get("info", {})
        tracks = tuple(Track.from_payload(t) for t in payload.get("tracks", []))
        selected = info.get("selectedTrack", -1)
        return cls(
            name=info.get("name", "Unknown playlist"),
            tracks=tracks,
            selected_index=selected if selected is not None and selected >= 0 else None,
            plugin_info=dict(payload.get("pluginInfo", {}) or {}),
        )

    @property
    def selected_track(self) -> Track | None:
        if self.selected_index is None or not (0 <= self.selected_index < len(self.tracks)):
            return None
        return self.tracks[self.selected_index]

    def __len__(self) -> int:
        return len(self.tracks)

    def __iter__(self):
        return iter(self.tracks)


# --------------------------------------------------------------------------- #
# loadtracks() discriminated result union
# --------------------------------------------------------------------------- #


class SearchResult:
    """Base class for the four possible outcomes of a ``loadtracks`` call."""

    __slots__ = ()


@dataclass(slots=True, frozen=True)
class TrackResult(SearchResult):
    """A single, directly-resolved track (``loadType == "track"``)."""

    track: Track


@dataclass(slots=True, frozen=True)
class PlaylistResult(SearchResult):
    """A playlist (``loadType == "playlist"``)."""

    playlist: Playlist


@dataclass(slots=True, frozen=True)
class SearchTracksResult(SearchResult):
    """A list of search matches (``loadType == "search"``)."""

    tracks: tuple[Track, ...]


@dataclass(slots=True, frozen=True)
class EmptyResult(SearchResult):
    """Nothing matched the query (``loadType == "empty"``)."""


@dataclass(slots=True, frozen=True)
class ErrorResult(SearchResult):
    """Lavalink reported a load error (``loadType == "error"``)."""

    message: str
    severity: str
    cause: str
