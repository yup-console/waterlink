"""Exception hierarchy used throughout waterlink.

All exceptions raised by this library inherit from :class:`WaterlinkError`,
so callers who want a single ``except`` clause to catch "anything waterlink
raised" can do so safely without accidentally swallowing unrelated errors
from asyncio, aiohttp, or their Discord library of choice.
"""

from __future__ import annotations

from typing import Any

__all__ = [
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


class WaterlinkError(Exception):
    """Base class for every exception raised by waterlink."""


class ConfigurationError(WaterlinkError):
    """Raised when the library is configured in an invalid or incomplete way."""


# --------------------------------------------------------------------------- #
# Node / connectivity
# --------------------------------------------------------------------------- #


class NodeError(WaterlinkError):
    """Base class for errors related to a single Lavalink node."""

    def __init__(self, message: str, *, node_name: str | None = None) -> None:
        self.node_name = node_name
        super().__init__(f"[{node_name}] {message}" if node_name else message)


class NodeConnectionError(NodeError):
    """Raised when a node's websocket or REST connection fails."""


class NodeNotReadyError(NodeError):
    """Raised when an operation is attempted on a node that has not
    finished its initial handshake (i.e. no ``ready`` OP has been received).
    """


class NoAvailableNodeError(WaterlinkError):
    """Raised when a node pool has no healthy node to satisfy a request."""


# --------------------------------------------------------------------------- #
# REST / track loading
# --------------------------------------------------------------------------- #


class RESTError(WaterlinkError):
    """Base class for errors talking to a node's REST API."""


class RESTRequestError(RESTError):
    """Raised when an HTTP request to a node could not be completed at all
    (connection refused, timeout, DNS failure, etc.).
    """


class RESTResponseError(RESTError):
    """Raised when a node's REST API returns a non-success HTTP status."""

    def __init__(
        self,
        message: str,
        *,
        status: int,
        body: Any = None,
    ) -> None:
        self.status = status
        self.body = body
        super().__init__(f"HTTP {status}: {message}")


class TrackLoadError(WaterlinkError):
    """Raised when Lavalink reports a ``loadFailed`` / ``error`` result."""

    def __init__(self, message: str, *, severity: str | None = None, cause: str | None = None) -> None:
        self.severity = severity
        self.cause = cause
        super().__init__(message)


class TrackDecodeError(WaterlinkError):
    """Raised when a base64 track string could not be decoded."""


class SearchError(WaterlinkError):
    """Raised when a search query could not be resolved to any results."""


# --------------------------------------------------------------------------- #
# Player / queue / filters
# --------------------------------------------------------------------------- #


class PlayerError(WaterlinkError):
    """Base class for player-related errors."""


class PlayerNotConnectedError(PlayerError):
    """Raised when an action requires an active voice connection but none exists."""


class PlayerAlreadyConnectedError(PlayerError):
    """Raised when attempting to connect a player that is already connected
    to a different channel, and no override was requested.
    """


class QueueError(WaterlinkError):
    """Base class for queue-related errors."""


class QueueEmptyError(QueueError):
    """Raised when an operation requires at least one queued track."""


class InvalidQueueIndexError(QueueError):
    """Raised when a queue index is out of range."""


class FilterError(WaterlinkError):
    """Base class for audio filter errors."""


class InvalidFilterValueError(FilterError):
    """Raised when a filter is configured with an out-of-range value."""


# --------------------------------------------------------------------------- #
# Plugins / persistence / voice
# --------------------------------------------------------------------------- #


class PluginError(WaterlinkError):
    """Base class for plugin-related errors."""


class PluginNotLoadedError(PluginError):
    """Raised when a plugin-specific action is used but the plugin is not
    reported as loaded on the target node.
    """


class PersistenceError(WaterlinkError):
    """Base class for state persistence/backup errors."""


class SessionNotResumedError(PersistenceError):
    """Raised when a resume attempt is rejected by Lavalink."""


class VoiceStateError(WaterlinkError):
    """Raised when Discord voice state/server update handling fails."""


class LibraryNotSupportedError(WaterlinkError):
    """Raised when no supported Discord library could be detected or the
    detected one is an unsupported version.
    """
