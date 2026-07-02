"""Minimal waterlink example bot using discord.py."""

from __future__ import annotations

import discord
from discord.ext import commands

import waterlink

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

client: waterlink.WaterlinkClient | None = None


@bot.event
async def on_ready() -> None:
    global client
    client = waterlink.WaterlinkClient(bot=bot)
    await client.add_node(host="localhost", port=2333, password="youshallnotpass")
    print(f"Logged in as {bot.user} (waterlink using {client.library_name})")


@bot.command()
async def play(ctx: commands.Context, *, query: str) -> None:
    if ctx.author.voice is None or ctx.author.voice.channel is None:
        await ctx.send("Join a voice channel first.")
        return

    player = await client.connect(ctx.guild.id, ctx.author.voice.channel.id)

    result = await client.search(query)
    if isinstance(result, waterlink.TrackResult):
        track = result.track
    elif isinstance(result, waterlink.SearchTracksResult) and result.tracks:
        track = result.tracks[0]
    elif isinstance(result, waterlink.PlaylistResult):
        for t in result.playlist.tracks:
            await player.enqueue(t.with_requester(ctx.author.id))
        await ctx.send(f"Queued playlist **{result.playlist.name}** ({len(result.playlist)} tracks)")
        return
    else:
        await ctx.send("No results found.")
        return

    await player.enqueue(track.with_requester(ctx.author.id))
    await ctx.send(f"Queued **{track.title}** by {track.author}")


@bot.command()
async def skip(ctx: commands.Context) -> None:
    player = client.get_player(ctx.guild.id)
    if player is None:
        await ctx.send("Nothing is playing.")
        return
    track = await player.skip()
    await ctx.send(f"Skipped **{track.title}**" if track else "Nothing to skip.")


@bot.command()
async def queue(ctx: commands.Context) -> None:
    player = client.get_player(ctx.guild.id)
    if player is None or player.queue.is_empty:
        await ctx.send("Queue is empty.")
        return
    text, _ = waterlink.queue_page(player.queue.to_list())
    await ctx.send(text)


@bot.command()
async def leave(ctx: commands.Context) -> None:
    await client.disconnect(ctx.guild.id)
    await ctx.send("Disconnected.")


bot.run("YOUR_BOT_TOKEN")
