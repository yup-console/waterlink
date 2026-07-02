# Getting Started

## Prerequisites

- Python 3.11+
- A running [Lavalink](https://github.com/lavalink-devs/Lavalink) v4 server
- A Discord bot using discord.py, py-cord, nextcord, or disnake

## Install

```bash
pip install waterlink[discordpy]
```

## Minimal bot

```python
import discord
from discord.ext import commands
import waterlink

bot = commands.Bot(command_prefix="!", intents=discord.Intents.default())
client: waterlink.WaterlinkClient | None = None

@bot.event
async def on_ready():
    global client
    client = waterlink.WaterlinkClient(bot=bot)
    await client.add_node(host="localhost", port=2333, password="youshallnotpass")

@bot.command()
async def play(ctx, *, query: str):
    player = await client.connect(ctx.guild.id, ctx.author.voice.channel.id)
    result = await client.search(query)
    track = result.track if isinstance(result, waterlink.TrackResult) else result.tracks[0]
    await player.enqueue(track)

bot.run("TOKEN")
```

That's the whole setup. See the `docs/guide/` folder for queue management,
filters, events, persistence, and plugin usage.
