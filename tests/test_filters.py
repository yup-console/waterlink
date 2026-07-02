from __future__ import annotations

import pytest

from waterlink.errors import InvalidFilterValueError
from waterlink.filters import (
    ChannelMix,
    Distortion,
    Equalizer,
    EqualizerBand,
    FilterChain,
    Karaoke,
    LowPass,
    Rotation,
    Timescale,
    Tremolo,
    Vibrato,
)


def test_equalizer_bass_boost_has_15_bands():
    eq = Equalizer.bass_boost()
    assert len(eq.bands) == 15
    payload = eq.to_payload()
    assert payload[0]["gain"] == 0.6


def test_equalizer_band_validates_range():
    with pytest.raises(InvalidFilterValueError):
        EqualizerBand(band=20, gain=0.0)
    with pytest.raises(InvalidFilterValueError):
        EqualizerBand(band=0, gain=5.0)


def test_timescale_validates_range():
    Timescale(speed=1.0, pitch=1.0, rate=1.0)  # no raise
    with pytest.raises(InvalidFilterValueError):
        Timescale(speed=0.0, pitch=1.0, rate=1.0)


def test_channel_mix_validates_range():
    with pytest.raises(InvalidFilterValueError):
        ChannelMix(left_to_left=1.5)


def test_low_pass_validates_minimum():
    with pytest.raises(InvalidFilterValueError):
        LowPass(smoothing=0.5)


def test_filter_chain_to_payload_includes_only_set_filters():
    chain = FilterChain()
    assert chain.to_payload() == {}
    assert chain.is_empty()

    chain.set_timescale(Timescale(speed=1.25))
    chain.set_karaoke(Karaoke())
    payload = chain.to_payload()
    assert set(payload.keys()) == {"timescale", "karaoke"}
    assert not chain.is_empty()


def test_filter_chain_clear_resets_everything():
    chain = FilterChain()
    chain.set_tremolo(Tremolo())
    chain.set_vibrato(Vibrato())
    chain.set_rotation(Rotation())
    chain.set_distortion(Distortion())
    chain.clear()
    assert chain.to_payload() == {}


def test_filter_chain_volume_validates_range():
    chain = FilterChain()
    with pytest.raises(InvalidFilterValueError):
        chain.set_volume(10.0)
    chain.set_volume(2.0)
    assert chain.to_payload()["volume"] == 2.0
