"""Tests for MidiClockConfig schema and tap-tempo math."""
from __future__ import annotations

import time

import pytest

from gamepad_midi_bridge.mapping import (
    Mapping,
    MidiClockConfig,
    _midi_clock_from_dict,
)


# ------------------------------------------------------------------ dataclass defaults

def test_midi_clock_defaults():
    cfg = MidiClockConfig()
    assert cfg.enabled is False
    assert cfg.bpm == 120.0
    assert cfg.send_start_stop is True
    assert cfg.tap_button == -1
    assert cfg.start_button == -1
    assert cfg.stop_button == -1


def test_mapping_has_midi_clock_field():
    m = Mapping()
    assert hasattr(m, "midi_clock")
    assert isinstance(m.midi_clock, MidiClockConfig)
    assert m.midi_clock.enabled is False


# ------------------------------------------------------------------ round-trip serialisation

def test_midi_clock_round_trip():
    m = Mapping()
    m.midi_clock = MidiClockConfig(
        enabled=True,
        bpm=140.0,
        send_start_stop=False,
        tap_button=3,
        start_button=4,
        stop_button=5,
    )
    restored = Mapping.from_dict(m.to_dict())
    clk = restored.midi_clock
    assert clk.enabled is True
    assert clk.bpm == 140.0
    assert clk.send_start_stop is False
    assert clk.tap_button == 3
    assert clk.start_button == 4
    assert clk.stop_button == 5


def test_midi_clock_round_trip_defaults():
    """Old presets without a midi_clock key load with all defaults."""
    m = Mapping.from_dict({})
    assert m.midi_clock.enabled is False
    assert m.midi_clock.bpm == 120.0


def test_midi_clock_from_dict_missing():
    assert _midi_clock_from_dict(None) == MidiClockConfig()
    assert _midi_clock_from_dict({}) == MidiClockConfig()


def test_midi_clock_from_dict_partial():
    cfg = _midi_clock_from_dict({"enabled": True, "bpm": 100.0})
    assert cfg.enabled is True
    assert cfg.bpm == 100.0
    # Unspecified fields get their defaults
    assert cfg.tap_button == -1
    assert cfg.start_button == -1
    assert cfg.stop_button == -1


# ------------------------------------------------------------------ BPM clamp

@pytest.mark.parametrize("raw, expected", [
    (59.9, 60.0),
    (60.0, 60.0),
    (120.0, 120.0),
    (240.0, 240.0),
    (300.0, 240.0),
    (0.0, 60.0),
    (-10.0, 60.0),
])
def test_bpm_clamp_on_load(raw, expected):
    cfg = _midi_clock_from_dict({"bpm": raw})
    assert cfg.bpm == expected


# ------------------------------------------------------------------ tap-tempo math

def _tap_bpm(intervals_s):
    """Return BPM given a list of inter-tap intervals in seconds.

    Mirrors the exact formula in BridgeWorker._record_tap:
        bpm = clamp(60 / mean(diffs), 60, 240)
    """
    avg = sum(intervals_s) / len(intervals_s)
    return max(60.0, min(240.0, 60.0 / avg))


def test_tap_tempo_4_taps_at_500ms():
    """4 taps at 500 ms apart → 3 diffs of 0.5 s → BPM = 60/0.5 = 120."""
    intervals = [0.5, 0.5, 0.5]
    bpm = _tap_bpm(intervals)
    assert abs(bpm - 120.0) < 0.01


def test_tap_tempo_4_taps_at_250ms():
    """4 taps at 250 ms → 3 diffs of 0.25 s → BPM = 60/0.25 = 240."""
    intervals = [0.25, 0.25, 0.25]
    bpm = _tap_bpm(intervals)
    assert abs(bpm - 240.0) < 0.01


def test_tap_tempo_4_taps_at_1000ms():
    """4 taps at 1000 ms → BPM = 60 (clamped at floor)."""
    intervals = [1.0, 1.0, 1.0]
    bpm = _tap_bpm(intervals)
    assert abs(bpm - 60.0) < 0.01


def test_tap_tempo_slow_clamped_to_60():
    """Very slow taps (2 s apart) → raw 30 BPM → clamped to 60."""
    intervals = [2.0, 2.0, 2.0]
    bpm = _tap_bpm(intervals)
    assert bpm == 60.0


def test_tap_tempo_fast_clamped_to_240():
    """Very fast taps (100 ms apart) → raw 600 BPM → clamped to 240."""
    intervals = [0.1, 0.1, 0.1]
    bpm = _tap_bpm(intervals)
    assert bpm == 240.0


def test_tap_tempo_uneven_averages():
    """Uneven taps average correctly."""
    # 3 diffs: 0.4 + 0.6 + 0.5 = 1.5 / 3 = 0.5 → 120 BPM
    intervals = [0.4, 0.6, 0.5]
    bpm = _tap_bpm(intervals)
    assert abs(bpm - 120.0) < 0.01


def test_tap_tempo_two_taps():
    """Two taps are the minimum — single diff used directly."""
    intervals = [0.5]  # one diff between two taps
    bpm = _tap_bpm(intervals)
    assert abs(bpm - 120.0) < 0.01


# ------------------------------------------------------------------ clock interval formula

@pytest.mark.parametrize("bpm, expected_interval", [
    (120.0, 60.0 / (120.0 * 24)),
    (60.0,  60.0 / (60.0  * 24)),
    (240.0, 60.0 / (240.0 * 24)),
])
def test_clock_interval_formula(bpm, expected_interval):
    """Verify the 24 PPQN interval formula used in _run_midi_clock_loop."""
    interval = 60.0 / (bpm * 24.0)
    assert abs(interval - expected_interval) < 1e-10
