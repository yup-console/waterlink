# Changelog

All notable changes to this project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [1.0.3] - 2026-07-03

### Fixed

- `RESTResponseError` now includes Lavalink's actual error response body
  in its message instead of just the HTTP status code — the previous
  `HTTP 400: PATCH ... failed` message hid the real reason and made the
  voice-update 400 reported against the public jirayu.net node
  undiagnosable from the traceback alone.
- `VoiceServerUpdate.endpoint` is now defensively stripped of a
  `wss://`/`https://` scheme prefix if present, since Lavalink v4 rejects
  a scheme-prefixed endpoint and some library/proxy combinations have
  been observed to include one.
- Guarded against dispatching a voice update to Lavalink with a missing
  endpoint (Discord sends `endpoint: null` briefly during voice server
  region migration) instead of forwarding a broken payload.
- Added debug logging around voice update dispatch so connection issues
  are diagnosable from bot logs going forward.

## [1.0.2] - 2026-07-03

### Fixed

- **Critical, actually fixed this time:** the 1.0.1 fix for voice
  connections was incomplete — it changed how the channel was looked up
  but the `VoiceProtocol.connect()` override still no-op'd instead of
  sending the gateway voice-state update, so the bot stopped joining
  voice channels at all. The real issue was twofold:
  1. `VoiceProtocol.connect()` must actually call
     `guild.change_voice_state(channel=..., ...)` itself — waterlink
     intentionally skips the base class's UDP audio socket setup (Lavalink
     handles audio transport), but still needs to trigger the initial
     gateway OP 4 that causes Discord to send back
     `VOICE_STATE_UPDATE`/`VOICE_SERVER_UPDATE`.
  2. The `Player` must be bound to its `VoiceProtocol` *before*
     `channel.connect(cls=...)` can possibly dispatch those gateway
     callbacks, or they arrive with no player to receive them and are
     silently dropped. The player is now constructed and bound inside the
     voice protocol's own `__init__`, which always runs before any
     callback can fire, closing the race entirely.
  3. Fixed `Player.connect()` (channel-move path) and `Player.disconnect()`,
     which referenced a nonexistent `voice_protocol.guild` attribute —
     corrected to `voice_protocol.channel.guild`, matching the real
     `VoiceProtocol` contract (which only exposes `.channel`).
  This was verified against a simulated gateway timing harness covering
  connect → search → enqueue → play → move-channel → disconnect, not just
  imports/syntax.

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
