# Changelog

All notable changes to this project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [1.0.7] - 2026-07-04

### Changed

- **`TitleCleaner` no longer guesses a "real artist" out of YouTube title
  text.** The heuristic (splitting on separators, matching "Singer:"
  labels, guessing which Title-Case segment was a person vs. a movie,
  trimming cast lists, etc.) kept needing new edge-case fixes release
  after release and could still pick the wrong segment. It's been
  replaced with a much simpler, source-aware rule:
  - **YouTube / YouTube Music**: the artist is always the uploading
    channel's name (with cosmetic `" - Topic"` / `"VEVO"` suffixes
    trimmed). Other title segments (movie name, cast, label, etc.) are
    still available on `CleanedMetadata.extra_tags` if you want them, but
    are no longer promoted to "artist".
  - **Every other source** (Spotify, Apple Music, Deezer, SoundCloud with
    proper tags, etc.): `track.author` is trusted as-is and never
    rewritten, since these platforms already report real artist metadata.
  - `TitleCleaner(extra_label_names=..., extra_movie_titles=...)` are
    still accepted for backwards compatibility but are now no-ops; use
    `extra_noise_phrases` to strip additional marketing phrases from
    displayed YouTube titles.
  - `TitleCleaner.clean()` gained a `source_name` keyword (defaults to
    `"youtube"` for existing call sites); `clean_track()` now passes
    `Track.source_name` through automatically.

### Fixed

- **Players could silently stop playing after a node websocket
  reconnect.** If a node's connection dropped for long enough that
  Lavalink's resume window expired (or the Lavalink process itself
  restarted), Lavalink would forget every player that had been attached
  to it, but waterlink kept using its own in-memory state as if nothing
  had happened — voice connections and current tracks were never
  re-sent, so playback just stopped with no error, event, or log message
  explaining why. `Node` now checks `resumed` on every `ready` OP and, if
  the session wasn't resumed, automatically re-sends each affected
  player's voice state and re-issues its current track from its last
  known position.
- The watchdog's node-staleness check was marking every ready node as
  "just reported stats" on every poll tick, regardless of whether a
  `stats` OP had actually arrived — which meant a genuinely stalled node
  (websocket open, `stats` OP no longer arriving) would never be flagged.
  It now only starts/continues the staleness clock from when the node
  actually reported stats.

## [1.0.6] - 2026-07-03

### Fixed

- `TitleCleaner` no longer reports a movie/film title as the artist when
  it appears in the artist position with no explicit label (e.g.
  `"Mulaqaat | Dream Girl | Ayushmann Khurrana | Meet Bros"` — a soundtrack
  from the movie *Dream Girl* — now correctly resolves the artist to
  `"Meet Bros"` instead of `"Dream Girl"`). A small built-in list of known
  movie titles (`DEFAULT_MOVIE_TITLES`, extendable via
  `TitleCleaner(extra_movie_titles=[...])`) is now excluded from artist
  candidates and routed to `extra_tags` instead.
- `Player.enqueue()` no longer silently does nothing when called after the
  queue has naturally finished playing. Previously, `Queue.next()` left
  `queue.current` pointing at the last-played track even once the queue
  drained, so a subsequent `enqueue()` incorrectly believed something was
  still playing and never restarted playback. Playback state is now
  tracked explicitly and no longer relies on stale `queue.current`.

## [1.0.5] - 2026-07-03

### Fixed

- `TitleCleaner` no longer picks cast/actor names over the real
  singer/composer when a title mixes both (e.g. Bollywood credits like
  `"Gehra Hua | Ranveer Singh, Sara Arjun, Shashwat Sachdev, Arijit Singh"`
  now correctly resolves to `"Shashwat Sachdev, Arijit Singh"`, not the
  actors). Explicit `"Singer: X"` labels are now detected and take
  priority outright.
- `artist` now only ever reflects the performing singer — an explicit
  `"Composed by X"` / `"Music: X"` / `"Lyrics: X"` label is recognized
  and excluded rather than being reported as the artist.

### Added

- 10 new `FilterChain` presets on top of the original set: `slowed_reverb`,
  `chipmunk`, `deep_voice`, `robot`, `underwater`, `concert_hall`, `mono`,
  `earthquake`, `soft` — alongside `nightcore`, `vaporwave`, `eight_d`,
  `karaoke_mode`, `bass_boosted`, `party`.
- `FilterChain.from_preset(name)` / `FilterChain.preset_names()` — look
  up any preset by string name, handy for slash-command choice lists.
- New `Equalizer` presets: `deep_bass`, `vocal_boost`, `treble_boost`,
  `loudness_equal`, `acoustic`, `clarity`.
- `Player.seek_forward()` / `Player.seek_backward()` — relative seeking.
- `Player.previous()` — replay the last track from history.
- `Queue.smart_shuffle()` — shuffles while avoiding back-to-back tracks
  by the same artist where possible.
- `Queue.jump_to()` / `Player.jump_to()` — skip ahead to an arbitrary
  queue position.
- `Queue.estimated_wait_ms()` — estimated time until a queued track
  would start playing.
- `waterlink.normalize` module (`VolumeNormalizer`, `NormalizationConfig`)
  — smooths jarring volume jumps between tracks mastered at different
  loudness levels.
- `waterlink.now_playing_summary()` — ready-made "now playing" text with
  progress bar, status, and loop mode for embeds.

## [1.0.4] - 2026-07-03

### Fixed

- All REST requests now send `trace=true`, so if Lavalink ever rejects a
  request the error you see includes its actual stack trace instead of a
  generic `{"message": "Bad Request"}` with no detail — this was blocking
  diagnosis of the voice-update 400 reported against the public
  jirayu.net node.
- The `voice` payload sent on player update now includes `channelId`
  alongside `token`/`endpoint`/`sessionId`, matching the full voice state
  shape rather than omitting a field some Lavalink versions/plugins may
  expect.

### Note

If a `PATCH .../players/{guildId}` request still 400s after this update,
the error message will now contain a full trace — please share that
output so the exact cause (rather than a guess) can be fixed.

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
