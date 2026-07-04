# Nodes & Pooling

```python
await client.add_node(name="main", host="lavalink1.example.com", port=443, password="secret", secure=True, region="us-east")
await client.add_node(name="eu", host="lavalink2.example.com", port=443, password="secret", secure=True, region="eu-west")
```

`client.connect()` selects a node automatically using the pool's routing
strategy:

- `RoutingStrategy.LOWEST_LOAD` (default) — picks the node with the lowest
  computed penalty score (playing players, CPU load, frame loss).
- `RoutingStrategy.ROUND_ROBIN` — cycles through ready nodes.
- `RoutingStrategy.REGION` — prefers a node matching a requested region,
  falling back to load-based selection.

```python
player = await client.connect(guild_id, channel_id, strategy=waterlink.RoutingStrategy.REGION, region="eu-west")
```

Nodes reconnect automatically with exponential backoff and resume their
Lavalink session where possible. If the resume window has expired or the
Lavalink process itself restarted, the session can't be resumed — in
that case Lavalink has forgotten about every player that was attached to
it. waterlink detects this (`NodeReadyEvent.resumed` is `False`) and
automatically re-sends each affected player's voice state and current
track (from its last known position) so playback picks back up instead
of silently going quiet. You don't need to do anything for this to
happen, but you can observe it via:

```python
@client.events.on(waterlink.NodeReadyEvent)
async def on_node_ready(event: waterlink.NodeReadyEvent):
    if not event.resumed:
        print(f"{event.node.name} reconnected without resuming a session; players were resynced")
```
