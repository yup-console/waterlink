# waterlink

**A modern, fully-typed, async Lavalink v4 client for Python Discord bots.**

waterlink wraps Lavalink's REST and websocket protocol behind a clean,
Pythonic API: node pooling with load-aware routing, a rich queue engine,
typed audio filters, autoplay, crossfade, state persistence across
restarts, and helpers for popular Lavalink plugins — all with full type
hints and zero required dependencies beyond `aiohttp`.

It auto-detects whichever Discord library you're already using —
**discord.py**, **py-cord**, **nextcord**, or **disnake** — so you don't
install anything extra for voice support.

[![PyPI](https://img.shields.io/pypi/v/waterlink)](https://pypi.org/project/waterlink/)
[![Python](https://img.shields.io/pypi/pyversions/waterlink)](https://pypi.org/project/waterlink/)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![GitHub](https://img.shields.io/badge/github-yup--console%2Fwaterlink-black)](https://github.com/yup-console/waterlink)

---

## Features

- **Lavalink v4 native** — REST + websocket built against the current protocol, including session resuming.
- **Multi-node pooling** with pluggable routing strategies (lowest load, round robin, region-aware).
- **Multi-library support** — auto-detects discord.py, py-cord, nextcord, or disnake.
- **Rich queue engine** — history, shuffle, dedupe, track/queue loop modes, priority insertion.
- **Typed audio filters** — equalizer, timescale, karaoke, tremolo, vibrato, rotation, distortion, channel mix, low-pass, all validated.
- **Autoplay** — keeps audio flowing with a pluggable "related track" strategy once the queue empties.
- **Source-aware metadata** — for YouTube results, shows the uploading channel as the artist instead of guessing a name out of the title text; for Spotify/Apple Music/Deezer/etc. it trusts the platform's real artist metadata as-is. Opt-in per client or per search call.
- **Crossfade** — smooth client-side volume ramping across track transitions.
- **State persistence** — snapshot and restore queues/players across bot restarts (JSON file backend included, or bring your own).
- **Plugin helpers** — typed convenience wrappers for LavaSrc and SponsorBlock.
- **Observability** — structured logging, an in-process metrics collector (with Prometheus text export), and a watchdog for stalled playback/stale nodes.
- **Reconnect-resilient** — automatically resyncs voice state and resumes playback if a node's websocket drops and reconnects without a resumed Lavalink session, instead of silently going quiet.
- **Fully typed** — ships a `py.typed` marker; passes `mypy --strict`.

## Installation

```bash
pip install waterlink[discordpy]
# or: waterlink[pycord] / waterlink[nextcord] / waterlink[disnake]
```

waterlink only requires `aiohttp` itself — the extras above just also
install a supported Discord library if you don't already have one.

You'll also need a running [Lavalink](https://github.com/lavalink-devs/Lavalink)
v4 server.

## Quick start

```python
import discord
from discord.ext import commands
import waterlink

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
client: waterlink.WaterlinkClient | None = None

@bot.event
async def on_ready():
    global client
    client = waterlink.WaterlinkClient(bot=bot)
    await client.add_node(host="localhost", port=2333, password="youshallnotpass")
    print(f"waterlink ready, using {client.library_name}")

@bot.command()
async def play(ctx: commands.Context, *, query: str):
    if ctx.author.voice is None:
        return await ctx.send("Join a voice channel first.")

    player = await client.connect(ctx.guild.id, ctx.author.voice.channel.id)

    result = await client.search(query)
    if isinstance(result, waterlink.TrackResult):
        track = result.track
    elif isinstance(result, waterlink.SearchTracksResult) and result.tracks:
        track = result.tracks[0]
    else:
        return await ctx.send("No results found.")

    await player.enqueue(track.with_requester(ctx.author.id))
    await ctx.send(f"Queued **{track.title}**")

bot.run("YOUR_TOKEN")
```

See [`examples/`](examples/) for a fuller bot with queue management,
filters, autoplay, and persistence wired up.

## Core concepts

### Node pool

```python
node = await client.add_node(
    name="main",
    host="lavalink.example.com",
    port=443,
    password="secret",
    secure=True,
    region="us-east",
)
```

Add as many nodes as you like; `client.connect()` picks the best one
automatically (`RoutingStrategy.LOWEST_LOAD` by default).

### Queue & playback

```python
player = client.get_player(guild_id)
await player.enqueue(track)
await player.skip()
await player.pause()
await player.resume()
await player.seek(30_000)
player.set_loop_mode(waterlink.LoopMode.QUEUE)
```

### Filters

```python
chain = waterlink.FilterChain()
chain.set_timescale(waterlink.Timescale(speed=1.25, pitch=1.1))
chain.set_equalizer(waterlink.Equalizer.bass_boost())
await player.set_filters(chain)
```

### Autoplay

```python
autoplay = waterlink.AutoplayEngine(client.events)
autoplay.enable(guild_id)
```

### Clean metadata

Different sources report the artist differently, so waterlink handles
them differently instead of guessing with one heuristic for everything:

- **YouTube**: there's no real "artist" field, only a video title and an
  uploader/channel name — so the **channel name is used as the artist**.
  Title text is cleaned up for display but never mined to guess a
  performer's name (that's unreliable — a title segment could be a
  singer, a movie name, or a cast list, with no way to tell from text
  alone).
- **Spotify, Apple Music, Deezer, and other tagged sources**: these
  already carry real artist metadata, so `track.author` is **trusted
  as-is** and never rewritten.

Enable automatic cleanup:

```python
client = waterlink.WaterlinkClient(bot=bot, clean_metadata=True)
# or per call:
result = await client.search(query, clean=True)
```

```python
track = result.tracks[0]

# YouTube result:
print(track.title)   # "Tere Liye"
print(track.author)  # "T-Series"  <- the channel name
print(track.extra["raw_title"])   # original, untouched, if you need it
print(track.extra["raw_author"])

# Spotify result: author is left exactly as Spotify reported it.
```

You can also clean a single track directly:

```python
cleaned = waterlink.clean_track(track)
```

`TitleCleaner` also accepts `extra_noise_phrases` if there are extra
marketing phrases (e.g. regional "New Song 2026"-style tags) you want
stripped from displayed YouTube titles:

```python
cleaner = waterlink.TitleCleaner(extra_noise_phrases=("official channel",))
cleaned = cleaner.clean_track(track)
```

### Events

```python
@client.events.on(waterlink.TrackStartEvent)
async def on_track_start(event: waterlink.TrackStartEvent):
    print(f"Now playing {event.track.title} in guild {event.player.guild_id}")
```

### Persistence

```python
backend = waterlink.JSONFileBackend("state/")
snapshot = waterlink.PlayerSnapshot.capture(player)
await backend.save(snapshot)
```

## Documentation

Full API reference and guides live in [`docs/`](docs/). Highlights:

- [Getting started](docs/getting-started.md)
- [Player & queue](docs/guide/player.md)
- [Filters](docs/guide/filters.md)
- [Nodes & pooling](docs/guide/nodes.md)
- [Events](docs/guide/events.md)
- [Persistence & observability](docs/guide/persistence-observability.md)

## Contributing

Contributions are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

```bash
git clone https://github.com/yup-console/waterlink
cd waterlink
pip install -e ".[dev]"
pytest
```

## License

MIT — see [LICENSE](LICENSE).
