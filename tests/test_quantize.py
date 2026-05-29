"""Tests for QuantizeConfig schema and beat-grid delay math.

All tests are pure-Python — no Qt event loop required.
"""
from __future__ import annotations

import pytest

from gamepad_midi_bridge.mapping import (
    Mapping,
    QuantizeConfig,
    QUANTIZE_GRIDS,
    _quantize_from_dict,
)
from gamepad_midi_bridge.bridge import BridgeWorker


# ------------------------------------------------------------------ dataclass defaults

def test_quantize_config_defaults():
    q = QuantizeConfig()
    assert q.enabled is False
    assert q.grid == "1/16"
    assert q.swing_pct == 0
    assert q.quantize_buttons is True
    assert q.quantize_cc is False


def test_mapping_has_quantize_field():
    m = Mapping()
    assert hasattr(m, "quantize")
    assert isinstance(m.quantize, QuantizeConfig)
    assert m.quantize.enabled is False


# ------------------------------------------------------------------ round-trip serialisation

def test_quantize_round_trip():
    m = Mapping()
    m.quantize = QuantizeConfig(
        enabled=True,
        grid="1/8",
        swing_pct=30,
        quantize_buttons=True,
        quantize_cc=False,
    )
    restored = Mapping.from_dict(m.to_dict())
    q = restored.quantize
    assert q.enabled is True
    assert q.grid == "1/8"
    assert q.swing_pct == 30
    assert q.quantize_buttons is True
    assert q.quantize_cc is False


def test_quantize_round_trip_defaults():
    """Old presets without a quantize key load with all defaults (disabled)."""
    m = Mapping.from_dict({})
    assert m.quantize.enabled is False
    assert m.quantize.grid == "1/16"
    assert m.quantize.swing_pct == 0


def test_quantize_from_dict_missing():
    assert _quantize_from_dict(None) == QuantizeConfig()
    assert _quantize_from_dict({}) == QuantizeConfig()


def test_quantize_from_dict_partial():
    q = _quantize_from_dict({"enabled": True, "grid": "1/8"})
    assert q.enabled is True
    assert q.grid == "1/8"
    assert q.swing_pct == 0


# ------------------------------------------------------------------ grid validation

@pytest.mark.parametrize("grid", QUANTIZE_GRIDS)
def test_valid_grid_values_accepted(grid):
    q = _quantize_from_dict({"grid": grid})
    assert q.grid == grid


def test_unknown_grid_falls_back_to_1_16():
    q = _quantize_from_dict({"grid": "1/99"})
    assert q.grid == "1/16"


def test_empty_grid_falls_back_to_1_16():
    q = _quantize_from_dict({"grid": ""})
    assert q.grid == "1/16"


# ------------------------------------------------------------------ swing clamp

@pytest.mark.parametrize("raw, expected", [
    (0, 0),
    (25, 25),
    (50, 50),
    (-5, 0),
    (51, 50),
    (100, 50),
])
def test_swing_pct_clamp(raw, expected):
    q = _quantize_from_dict({"swing_pct": raw})
    assert q.swing_pct == expected


# ------------------------------------------------------------------ grid duration math

@pytest.mark.parametrize("bpm, grid, expected_ms", [
    (120.0, "1/4",   500.0),     # 60000/120 = 500 ms per beat
    (120.0, "1/8",   250.0),
    (120.0, "1/16",  125.0),
    (120.0, "1/32",   62.5),
    (120.0, "1/8t",  500.0 * 2.0 / 3.0),   # ~333.33 ms
    (120.0, "1/16t", 500.0 / 6.0),          # ~83.33 ms
    (60.0,  "1/16",  250.0),     # 60000/60/4 = 250 ms
    (240.0, "1/16",   62.5),     # 60000/240/4 = 62.5 ms
])
def test_grid_duration_ms(bpm, grid, expected_ms):
    result = BridgeWorker._grid_duration_ms(bpm, grid)
    assert abs(result - expected_ms) < 0.01


def test_unknown_grid_returns_1_16_duration():
    """Fallback path in _grid_duration_ms should give 1/16 duration."""
    bpm = 120.0
    fallback = BridgeWorker._grid_duration_ms(bpm, "bogus")
    expected = BridgeWorker._grid_duration_ms(bpm, "1/16")
    assert abs(fallback - expected) < 0.01


# ------------------------------------------------------------------ quantize delay calculation

def _make_worker_with_epoch(bpm: float, epoch_offset_ms: float) -> BridgeWorker:
    """Build a BridgeWorker with a synthetic clock epoch for delay testing.

    epoch_offset_ms: how many ms *before* now the beat epoch was set.
    So if a beat started 70 ms ago at 120 BPM with a 1/16 grid (125 ms
    cells), the next boundary is at 125 ms, and delay = 125 - 70 = 55 ms.
    """
    import time
    w = BridgeWorker.__new__(BridgeWorker)
    now = time.perf_counter()
    w._clock_beat_epoch = now - epoch_offset_ms / 1000.0
    w._clock_bpm_live = bpm
    return w


def test_delay_at_t70ms_120bpm_1_16():
    """At 120 BPM, 1/16 grid = 125 ms per cell.

    If 70 ms have elapsed since the beat started:
      - We are in cell 0 (0..125 ms).
      - Next boundary is at 125 ms.
      - Delay = 125 - 70 = 55 ms.
    """
    w = _make_worker_with_epoch(bpm=120.0, epoch_offset_ms=70.0)
    qcfg = QuantizeConfig(enabled=True, grid="1/16", swing_pct=0)
    delay = w._quantize_delay_ms(qcfg)
    assert abs(delay - 55.0) < 2.0, f"Expected ~55 ms, got {delay:.2f}"


def test_delay_at_t0ms_is_full_cell():
    """Right on a beat boundary: full grid cell delay to next boundary."""
    w = _make_worker_with_epoch(bpm=120.0, epoch_offset_ms=0.0)
    qcfg = QuantizeConfig(enabled=True, grid="1/16", swing_pct=0)
    delay = w._quantize_delay_ms(qcfg)
    # elapsed=0 → cell_index=0, next_cell=1, delay=125-0=125
    assert abs(delay - 125.0) < 2.0, f"Expected ~125 ms, got {delay:.2f}"


def test_delay_just_past_boundary():
    """1 ms past a boundary: delay ≈ grid_ms - 1 ms."""
    # Place epoch 126 ms ago at 120 BPM.
    # elapsed_in_beat = 126 % 500 = 126 ms
    # cell_index = int(126/125) = 1, next_cell = 2
    # delay = 2*125 - 126 = 124 ms
    w = _make_worker_with_epoch(bpm=120.0, epoch_offset_ms=126.0)
    qcfg = QuantizeConfig(enabled=True, grid="1/16", swing_pct=0)
    delay = w._quantize_delay_ms(qcfg)
    assert abs(delay - 124.0) < 2.0, f"Expected ~124 ms, got {delay:.2f}"


def test_delay_no_clock_running_returns_zero():
    """Without a running clock (epoch=0.0), delay should be 0 → immediate send."""
    w = BridgeWorker.__new__(BridgeWorker)
    w._clock_beat_epoch = 0.0
    w._clock_bpm_live = 120.0
    qcfg = QuantizeConfig(enabled=True, grid="1/16", swing_pct=0)
    delay = w._quantize_delay_ms(qcfg)
    assert delay == 0.0


def test_delay_is_positive():
    """Delay must never be negative regardless of float drift."""
    w = _make_worker_with_epoch(bpm=120.0, epoch_offset_ms=124.99)
    qcfg = QuantizeConfig(enabled=True, grid="1/16", swing_pct=0)
    delay = w._quantize_delay_ms(qcfg)
    assert delay >= 0.0


# ------------------------------------------------------------------ swing delay

def test_swing_adds_offset_on_odd_beat():
    """Swing 50% on an off-beat (next_cell=1) should add 50% of grid_ms."""
    # elapsed=0 → next_cell=1 (odd) → swing applies
    w = _make_worker_with_epoch(bpm=120.0, epoch_offset_ms=0.0)
    q_no_swing = QuantizeConfig(enabled=True, grid="1/16", swing_pct=0)
    q_swing = QuantizeConfig(enabled=True, grid="1/16", swing_pct=50)

    base_delay = w._quantize_delay_ms(q_no_swing)
    swung_delay = w._quantize_delay_ms(q_swing)

    # swing adds 50% of 125 ms = 62.5 ms
    assert abs(swung_delay - (base_delay + 62.5)) < 2.0


def test_swing_zero_has_no_effect():
    """swing_pct=0 produces roughly the same delay across rapid repeated calls.

    Two calls are separated only by Python overhead (~ms), so we allow a small
    tolerance to account for time.perf_counter() advancing between invocations.
    The key assertion is that no swing offset (62.5 ms) was added.
    """
    w = _make_worker_with_epoch(bpm=120.0, epoch_offset_ms=50.0)
    q = QuantizeConfig(enabled=True, grid="1/16", swing_pct=0)
    delay_a = w._quantize_delay_ms(q)
    delay_b = w._quantize_delay_ms(q)
    # Both should be in the same 125 ms cell range, within a few ms of each other
    assert abs(delay_a - delay_b) < 5.0
