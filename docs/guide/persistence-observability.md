# Persistence & Observability

## Persistence

```python
backend = waterlink.JSONFileBackend("state/")
snapshot = waterlink.PlayerSnapshot.capture(player)
await backend.save(snapshot)

# later / after restart
snapshot = await backend.load(guild_id)
player = await client.connect(guild_id, snapshot.channel_id)
player.queue = snapshot.restore_queue()
```

Implement the `PersistenceBackend` protocol to back this with Redis,
Postgres, etc.

## Metrics

```python
metrics = waterlink.MetricsCollector(client.events)
print(metrics.snapshot())
print(metrics.to_prometheus())
```

## Watchdog

```python
watchdog = waterlink.Watchdog(client.pool)
watchdog.on_stalled_player(my_recovery_coroutine)
await watchdog.start()
```

Flags players whose position stops advancing and nodes that go stale
(no stats update within the configured window).

## Logging

```python
waterlink.configure_logging()  # or configure the "waterlink" logger yourself
```
