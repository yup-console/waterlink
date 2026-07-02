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
Lavalink session where possible.
