"""Presentation helpers for building bot commands and embeds.

Nothing here touches the network; these are pure functions that turn
:class:`~waterlink.tracks.Track` / :class:`~waterlink.player.Player` state
into strings suitable for Discord messages.
"""

from __future__ import annotations

from .tracks import Track

__all__ = ["format_duration", "progress_bar", "track_line", "queue_page", "now_playing_summary"]


def format_duration(ms: int) -> str:
    """Format milliseconds as ``H:MM:SS`` or ``M:SS``."""

    if ms < 0:
        return "LIVE"
    total_seconds = ms // 1000
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def progress_bar(position_ms: int, length_ms: int, *, width: int = 20, marker: str = "\N{RADIO BUTTON}", track_char: str = "\N{BOX DRAWINGS LIGHT HORIZONTAL}") -> str:
    """Render a text progress bar, e.g. ``──●───────── 1:23 / 3:45``."""

    if length_ms <= 0:
        return f"{marker}{track_char * (width - 1)} LIVE"

    ratio = max(0.0, min(1.0, position_ms / length_ms))
    filled = int(ratio * width)
    filled = min(filled, width - 1)
    bar = track_char * filled + marker + track_char * (width - filled - 1)
    return f"{bar} {format_duration(position_ms)} / {format_duration(length_ms)}"


def track_line(track: Track, *, index: int | None = None, show_requester: bool = False) -> str:
    """A single-line summary for use in queue listings."""

    prefix = f"`{index}.` " if index is not None else ""
    duration = "LIVE" if track.is_stream else format_duration(track.length_ms)
    line = f"{prefix}**{track.title}** by {track.author} `[{duration}]`"
    if show_requester and track.requester_id is not None:
        line += f" — <@{track.requester_id}>"
    return line


def queue_page(
    tracks: list[Track],
    *,
    page: int = 1,
    per_page: int = 10,
    show_requester: bool = False,
) -> tuple[str, int]:
    """Render one page of a queue listing.

    Returns ``(text, total_pages)``. ``page`` is 1-indexed and clamped
    into range.
    """

    total_pages = max(1, (len(tracks) + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    start = (page - 1) * per_page

    lines = [
        track_line(t, index=start + i + 1, show_requester=show_requester)
        for i, t in enumerate(tracks[start : start + per_page])
    ]
    if not lines:
        return "The queue is empty.", total_pages
    return "\n".join(lines), total_pages


def now_playing_summary(
    track: Track,
    *,
    position_ms: int,
    paused: bool = False,
    volume: int | None = None,
    loop_mode: str | None = None,
) -> str:
    """A multi-line "now playing" summary suitable for a Discord embed
    description — title, artist, progress bar, and status flags.
    """

    status = "⏸️ Paused" if paused else "▶️ Playing"
    lines = [
        f"**{track.title}**",
        f"by {track.author}",
        "",
        progress_bar(position_ms, track.length_ms),
        status + (f" • 🔊 {volume}%" if volume is not None else ""),
    ]
    if loop_mode and loop_mode != "off":
        lines.append(f"🔁 Loop: {loop_mode}")
    return "\n".join(lines)
