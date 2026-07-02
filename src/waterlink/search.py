"""Helpers for building search queries and parsing ``loadtracks`` results."""

from __future__ import annotations

import re

from .errors import TrackLoadError
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
from .typing import JSONDict

__all__ = ["SearchPrefix", "build_query", "parse_load_result"]

_URI_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://")


class SearchPrefix:
    """Well-known Lavalink search prefixes.

    Additional prefixes exposed by plugins (e.g. ``spsearch:`` from
    LavaSrc) can simply be passed as plain strings to :func:`build_query`.
    """

    YOUTUBE = "ytsearch"
    YOUTUBE_MUSIC = "ytmsearch"
    SOUNDCLOUD = "scsearch"
    SPOTIFY = "spsearch"
    APPLE_MUSIC = "amsearch"
    DEEZER = "dzsearch"


def build_query(query: str, *, prefix: str | None = None) -> str:
    """Return a Lavalink-ready identifier for ``/loadtracks``.

    If ``query`` already looks like a URI (has a scheme, e.g. ``https://``
    or ``spotify:``) it is returned unchanged and ``prefix`` is ignored,
    since Lavalink resolves URIs directly. Otherwise the given prefix
    (default: :data:`SearchPrefix.YOUTUBE`) is prepended as ``prefix:query``.
    """

    if _URI_RE.match(query):
        return query
    return f"{prefix or SearchPrefix.YOUTUBE}:{query}"


def parse_load_result(payload: JSONDict) -> SearchResult:
    """Convert a raw ``/v4/loadtracks`` response into a :class:`SearchResult`."""

    load_type = payload.get("loadType")
    data = payload.get("data")

    if load_type == "track":
        return TrackResult(track=Track.from_payload(data))

    if load_type == "playlist":
        return PlaylistResult(playlist=Playlist.from_payload(data))

    if load_type == "search":
        tracks = tuple(Track.from_payload(t) for t in (data or []))
        return SearchTracksResult(tracks=tracks)

    if load_type == "empty":
        return EmptyResult()

    if load_type == "error":
        error = data or {}
        return ErrorResult(
            message=error.get("message", "Unknown load error"),
            severity=error.get("severity", "COMMON"),
            cause=error.get("cause", "unknown"),
        )

    raise TrackLoadError(f"Unrecognized loadType: {load_type!r}")
