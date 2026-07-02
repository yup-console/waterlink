# Filters

All filters are validated dataclasses; invalid values raise
`InvalidFilterValueError` immediately rather than silently failing on the
node.

```python
chain = waterlink.FilterChain()
chain.set_timescale(waterlink.Timescale(speed=1.25, pitch=1.1))
chain.set_equalizer(waterlink.Equalizer.bass_boost())
chain.set_low_pass(waterlink.LowPass(smoothing=15))
await player.set_filters(chain)

await player.clear_filters()
```

Available filters: `Equalizer`, `Karaoke`, `Timescale`, `Tremolo`,
`Vibrato`, `Rotation`, `Distortion`, `ChannelMix`, `LowPass`.
