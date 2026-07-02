# Player & Queue

## Connecting

```python
player = await client.connect(guild_id, channel_id)
```

Reconnecting to a different channel: pass `move=True` implicitly handled —
calling `client.connect()` again on an existing player moves it.

## Playback control

```python
await player.enqueue(track)          # add + auto-start if idle
await player.enqueue(track, play_now=True)  # jump the queue
await player.skip()
await player.pause()
await player.resume()
await player.seek(30_000)
await player.set_volume(80)          # 0-1000
```

## Queue

```python
player.queue.shuffle()
player.queue.deduplicate()
player.queue.move(3, 0)
player.set_loop_mode(waterlink.LoopMode.QUEUE)  # OFF / TRACK / QUEUE
```

`player.position_ms` gives an interpolated current playback position
between `playerUpdate` ticks, so it's safe to poll for progress bars.
