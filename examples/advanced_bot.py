"""Advanced waterlink example: filters, autoplay, persistence, watchdog, metrics."""

from __future__ import annotations

import discord
from discord.ext import commands

import waterlink

waterlink.configure_logging()

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

client: waterlink.WaterlinkClient | None = None
autoplay: waterlink.AutoplayEngine | None = None
watchdog: waterlink.Watchdog | None = None
metrics: waterlink.MetricsCollector | None = None
persistence = waterlink.JSONFileBackend("state/")


@bot.event
async def on_ready() -> None:
    global client, autoplay, watchdog, metrics

    client = waterlink.WaterlinkClient(bot=bot)
    await client.add_node(name="main", host="localhost", port=2333, password="youshallnotpass")
    await client.add_node(name="backup", host="localhost", port=2334, password="youshallnotpass")

    autoplay = waterlink.AutoplayEngine(client.events)
    metrics = waterlink.MetricsCollector(client.events)

    watchdog = waterlink.Watchdog(client.pool)
    watchdog.on_stalled_player(_handle_stalled_player)
    await watchdog.start()

    @client.events.on(waterlink.TrackStartEvent)
    async def on_track_start(event: waterlink.TrackStartEvent) -> None:
        print(f"[guild {event.player.guild_id}] now playing: {event.track.title}")

    print(f"Ready. Using {client.library_name}.")


async def _handle_stalled_player(player: waterlink.Player) -> None:
    print(f"Player for guild {player.guild_id} looks stalled; attempting a resume nudge.")
    await player.pause(True)
    await player.pause(False)


@bot.command()
async def play(ctx: commands.Context, *, query: str) -> None:
    if ctx.author.voice is None:
        await ctx.send("Join a voice channel first.")
        return
    player = await client.connect(ctx.guild.id, ctx.author.voice.channel.id)
    result = await client.search(query)
    if isinstance(result, waterlink.TrackResult):
        track = result.track
    elif isinstance(result, waterlink.SearchTracksResult) and result.tracks:
        track = result.tracks[0]
    else:
        await ctx.send("No results found.")
        return
    await player.enqueue(track.with_requester(ctx.author.id))
    await ctx.send(f"Queued **{track.title}**")


@bot.command()
async def autoplay_toggle(ctx: commands.Context) -> None:
    if autoplay.is_enabled(ctx.guild.id):
        autoplay.disable(ctx.guild.id)
        await ctx.send("Autoplay disabled.")
    else:
        autoplay.enable(ctx.guild.id)
        await ctx.send("Autoplay enabled.")


@bot.command()
async def bassboost(ctx: commands.Context) -> None:
    player = client.get_player(ctx.guild.id)
    if player is None:
        return
    chain = waterlink.FilterChain().set_equalizer(waterlink.Equalizer.bass_boost())
    await player.set_filters(chain)
    await ctx.send("Bass boost enabled.")


@bot.command()
async def nightcore(ctx: commands.Context) -> None:
    player = client.get_player(ctx.guild.id)
    if player is None:
        return
    chain = waterlink.FilterChain().set_timescale(waterlink.Timescale(speed=1.2, pitch=1.2))
    await player.set_filters(chain)
    await ctx.send("Nightcore filter enabled.")


@bot.command()
async def save_state(ctx: commands.Context) -> None:
    player = client.get_player(ctx.guild.id)
    if player is None:
        await ctx.send("Nothing to save.")
        return
    snapshot = waterlink.PlayerSnapshot.capture(player)
    await persistence.save(snapshot)
    await ctx.send("Saved current player state.")


@bot.command()
async def restore_state(ctx: commands.Context) -> None:
    snapshot = await persistence.load(ctx.guild.id)
    if snapshot is None or snapshot.channel_id is None:
        await ctx.send("No saved state found.")
        return
    player = await client.connect(ctx.guild.id, snapshot.channel_id)
    player.queue = snapshot.restore_queue()
    if snapshot.current is not None:
        await player.play(snapshot.current, start_ms=snapshot.position_ms)
    await player.set_volume(snapshot.volume)
    await ctx.send("Restored previous session.")


@bot.command()
async def stats(ctx: commands.Context) -> None:
    data = metrics.snapshot()
    await ctx.send(f"```{data}```")


bot.run("YOUR_BOT_TOKEN")
