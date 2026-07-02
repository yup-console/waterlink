# Events

```python
@client.events.on(waterlink.TrackStartEvent)
async def on_track_start(event: waterlink.TrackStartEvent):
    ...

@client.events.on(waterlink.TrackEndEvent)
async def on_track_end(event: waterlink.TrackEndEvent):
    if event.may_start_next:
        ...  # queue auto-advances internally already; this is informational
```

Available events: `NodeReadyEvent`, `NodeDisconnectedEvent`,
`NodeReconnectingEvent`, `NodeErrorEvent`, `NodeStatsUpdateEvent`,
`TrackStartEvent`, `TrackEndEvent`, `TrackExceptionEvent`,
`TrackStuckEvent`, `WebSocketClosedEvent`, `QueueEndEvent`,
`PlayerUpdateEvent`.

Handlers may be sync or async; each is scheduled independently so a slow
handler never blocks others or the websocket read loop.
