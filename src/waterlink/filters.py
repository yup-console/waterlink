"""Typed audio filter builders for Lavalink's ``filters`` player payload.

Each filter is its own small, validated dataclass. :class:`FilterChain`
composes any number of them and serializes to the JSON shape Lavalink
expects. Values are validated eagerly so mistakes surface at call time
rather than as a silent no-op on the node.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .errors import InvalidFilterValueError
from .typing import JSONDict

__all__ = [
    "Equalizer",
    "EqualizerBand",
    "Karaoke",
    "Timescale",
    "Tremolo",
    "Vibrato",
    "Rotation",
    "Distortion",
    "ChannelMix",
    "LowPass",
    "FilterChain",
]


def _check_range(name: str, value: float, lo: float, hi: float) -> None:
    if not (lo <= value <= hi):
        raise InvalidFilterValueError(f"{name} must be between {lo} and {hi}, got {value}")


@dataclass(slots=True, frozen=True)
class EqualizerBand:
    band: int
    gain: float = 0.0

    def __post_init__(self) -> None:
        _check_range("band", self.band, 0, 14)
        _check_range("gain", self.gain, -0.25, 1.0)


@dataclass(slots=True, frozen=True)
class Equalizer:
    """A 15-band (0-14) equalizer. Bands default to 0 gain (flat)."""

    bands: tuple[EqualizerBand, ...] = field(default_factory=tuple)

    @classmethod
    def flat(cls) -> "Equalizer":
        return cls()

    @classmethod
    def bass_boost(cls) -> "Equalizer":
        gains = [0.6, 0.5, 0.4, 0.3, 0.2, 0.1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        return cls(bands=tuple(EqualizerBand(i, g) for i, g in enumerate(gains)))

    def to_payload(self) -> list[JSONDict]:
        return [{"band": b.band, "gain": b.gain} for b in self.bands]


@dataclass(slots=True, frozen=True)
class Karaoke:
    level: float = 1.0
    mono_level: float = 1.0
    filter_band: float = 220.0
    filter_width: float = 100.0

    def to_payload(self) -> JSONDict:
        return {
            "level": self.level,
            "monoLevel": self.mono_level,
            "filterBand": self.filter_band,
            "filterWidth": self.filter_width,
        }


@dataclass(slots=True, frozen=True)
class Timescale:
    speed: float = 1.0
    pitch: float = 1.0
    rate: float = 1.0

    def __post_init__(self) -> None:
        _check_range("speed", self.speed, 0.01, 5.0)
        _check_range("pitch", self.pitch, 0.01, 5.0)
        _check_range("rate", self.rate, 0.01, 5.0)

    def to_payload(self) -> JSONDict:
        return {"speed": self.speed, "pitch": self.pitch, "rate": self.rate}


@dataclass(slots=True, frozen=True)
class Tremolo:
    frequency: float = 2.0
    depth: float = 0.5

    def __post_init__(self) -> None:
        _check_range("frequency", self.frequency, 0.01, 100.0)
        _check_range("depth", self.depth, 0.01, 1.0)

    def to_payload(self) -> JSONDict:
        return {"frequency": self.frequency, "depth": self.depth}


@dataclass(slots=True, frozen=True)
class Vibrato:
    frequency: float = 2.0
    depth: float = 0.5

    def __post_init__(self) -> None:
        _check_range("frequency", self.frequency, 0.01, 14.0)
        _check_range("depth", self.depth, 0.01, 1.0)

    def to_payload(self) -> JSONDict:
        return {"frequency": self.frequency, "depth": self.depth}


@dataclass(slots=True, frozen=True)
class Rotation:
    rotation_hz: float = 0.2

    def to_payload(self) -> JSONDict:
        return {"rotationHz": self.rotation_hz}


@dataclass(slots=True, frozen=True)
class Distortion:
    sin_offset: float = 0.0
    sin_scale: float = 1.0
    cos_offset: float = 0.0
    cos_scale: float = 1.0
    tan_offset: float = 0.0
    tan_scale: float = 1.0
    offset: float = 0.0
    scale: float = 1.0

    def to_payload(self) -> JSONDict:
        return {
            "sinOffset": self.sin_offset,
            "sinScale": self.sin_scale,
            "cosOffset": self.cos_offset,
            "cosScale": self.cos_scale,
            "tanOffset": self.tan_offset,
            "tanScale": self.tan_scale,
            "offset": self.offset,
            "scale": self.scale,
        }


@dataclass(slots=True, frozen=True)
class ChannelMix:
    left_to_left: float = 1.0
    left_to_right: float = 0.0
    right_to_left: float = 0.0
    right_to_right: float = 1.0

    def __post_init__(self) -> None:
        for name in ("left_to_left", "left_to_right", "right_to_left", "right_to_right"):
            _check_range(name, getattr(self, name), 0.0, 1.0)

    def to_payload(self) -> JSONDict:
        return {
            "leftToLeft": self.left_to_left,
            "leftToRight": self.left_to_right,
            "rightToLeft": self.right_to_left,
            "rightToRight": self.right_to_right,
        }


@dataclass(slots=True, frozen=True)
class LowPass:
    smoothing: float = 20.0

    def __post_init__(self) -> None:
        if self.smoothing < 1.0:
            raise InvalidFilterValueError("smoothing must be >= 1.0")

    def to_payload(self) -> JSONDict:
        return {"smoothing": self.smoothing}


@dataclass(slots=True)
class FilterChain:
    """A mutable collection of active filters for a player.

    Use the ``set_*`` methods to fluently configure filters, then pass the
    chain to :meth:`Player.set_filters`. Setting a filter to ``None``
    removes it from the outgoing payload.
    """

    volume: float | None = None
    equalizer: Equalizer | None = None
    karaoke: Karaoke | None = None
    timescale: Timescale | None = None
    tremolo: Tremolo | None = None
    vibrato: Vibrato | None = None
    rotation: Rotation | None = None
    distortion: Distortion | None = None
    channel_mix: ChannelMix | None = None
    low_pass: LowPass | None = None
    plugin_filters: JSONDict = field(default_factory=dict)

    def set_volume(self, volume: float | None) -> "FilterChain":
        if volume is not None:
            _check_range("volume", volume, 0.0, 5.0)
        self.volume = volume
        return self

    def set_equalizer(self, eq: Equalizer | None) -> "FilterChain":
        self.equalizer = eq
        return self

    def set_karaoke(self, karaoke: Karaoke | None) -> "FilterChain":
        self.karaoke = karaoke
        return self

    def set_timescale(self, timescale: Timescale | None) -> "FilterChain":
        self.timescale = timescale
        return self

    def set_tremolo(self, tremolo: Tremolo | None) -> "FilterChain":
        self.tremolo = tremolo
        return self

    def set_vibrato(self, vibrato: Vibrato | None) -> "FilterChain":
        self.vibrato = vibrato
        return self

    def set_rotation(self, rotation: Rotation | None) -> "FilterChain":
        self.rotation = rotation
        return self

    def set_distortion(self, distortion: Distortion | None) -> "FilterChain":
        self.distortion = distortion
        return self

    def set_channel_mix(self, mix: ChannelMix | None) -> "FilterChain":
        self.channel_mix = mix
        return self

    def set_low_pass(self, low_pass: LowPass | None) -> "FilterChain":
        self.low_pass = low_pass
        return self

    def clear(self) -> "FilterChain":
        """Reset every filter, producing a flat/neutral chain."""

        self.volume = None
        self.equalizer = None
        self.karaoke = None
        self.timescale = None
        self.tremolo = None
        self.vibrato = None
        self.rotation = None
        self.distortion = None
        self.channel_mix = None
        self.low_pass = None
        self.plugin_filters = {}
        return self

    def to_payload(self) -> JSONDict:
        payload: JSONDict = {}
        if self.volume is not None:
            payload["volume"] = self.volume
        if self.equalizer is not None:
            payload["equalizer"] = self.equalizer.to_payload()
        if self.karaoke is not None:
            payload["karaoke"] = self.karaoke.to_payload()
        if self.timescale is not None:
            payload["timescale"] = self.timescale.to_payload()
        if self.tremolo is not None:
            payload["tremolo"] = self.tremolo.to_payload()
        if self.vibrato is not None:
            payload["vibrato"] = self.vibrato.to_payload()
        if self.rotation is not None:
            payload["rotation"] = self.rotation.to_payload()
        if self.distortion is not None:
            payload["distortion"] = self.distortion.to_payload()
        if self.channel_mix is not None:
            payload["channelMix"] = self.channel_mix.to_payload()
        if self.low_pass is not None:
            payload["lowPass"] = self.low_pass.to_payload()
        payload.update(self.plugin_filters)
        return payload

    def is_empty(self) -> bool:
        return not self.to_payload()
