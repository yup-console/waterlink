# Changelog

All notable changes to this project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [1.0.1] - 2026-07-03

### Added

- `waterlink.metadata` module with `TitleCleaner` for cleaning noisy
  YouTube-style track titles/authors (e.g. turning
  `"Tere Liye | Arijit Singh | Viral | T-Series"` uploaded by `"T-Series"`
  into title `"Tere Liye"` by artist `"Arijit Singh"`), plus a
  `clean_track()` convenience function.
- `WaterlinkClient(clean_metadata=True)` and `client.search(..., clean=True)`
  to opt into automatic metadata cleaning on search results.
- Recognizes YouTube's auto-generated `"<Artist> - Topic"` and
  `"<Artist>VEVO"` channel naming conventions.

### Fixed

- **Critical:** `WaterlinkClient.connect()` was joining voice channels
  incorrectly — it called `guild.change_voice_state()` directly with a
  fake channel stand-in instead of using the library's own
  `channel.connect(cls=...)` API. This meant a voice client was never
  properly registered with discord.py/py-cord/nextcord/disnake's internal
  connection state, so `VOICE_SERVER_UPDATE`/`VOICE_STATE_UPDATE` gateway
  events were never delivered to the player. Tracks would enqueue
  successfully (REST calls to Lavalink succeeded) but no audio would ever
  play. Fixed to use `channel.connect(cls=WaterlinkVoiceProtocol, ...)`,
  the documented cross-library-compatible way to attach a custom voice
  protocol.

## [1.0.0] - 2026-07-02

### Added

- Initial public release of waterlink.
- Lavalink v4 REST client with session resuming support.
- Websocket connection handling with automatic exponential-backoff reconnects.
- `NodePool` with `LOWEST_LOAD`, `ROUND_ROBIN`, and `REGION` routing strategies.
- Auto-detection of discord.py, py-cord, nextcord, and disnake.
- `Player` with connect/disconnect, play/pause/resume/stop/skip/seek, and volume control.
- `Queue` with history, shuffle, deduplication, and track/queue loop modes.
- Typed `FilterChain` covering equalizer, karaoke, timescale, tremolo, vibrato,
  rotation, distortion, channel mix, and low-pass filters.
- `AutoplayEngine` with a pluggable related-track strategy.
- `CrossfadeController` for client-side volume-ramped track transitions.
- State persistence via `PlayerSnapshot` with `JSONFileBackend` and `InMemoryBackend`.
- `PluginRegistry` plus `LavaSrcHelper` and `SponsorBlockHelper` convenience wrappers.
- `MetricsCollector` with Prometheus text export, and a `Watchdog` for detecting
  stalled players and stale nodes.
- Structured, context-aware logging via `configure_logging` / `get_logger`.
- Full type hints and a `py.typed` marker.
