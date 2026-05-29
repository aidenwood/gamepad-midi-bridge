"""Tests for the latency_test module."""
from __future__ import annotations

import time

import pytest

from gamepad_midi_bridge import latency_test
from gamepad_midi_bridge.latency_test import LatencyMeasurement, LatencyTracker


# ---------------------------------------------------------------------------
# LatencyTracker basics
# ---------------------------------------------------------------------------

def test_round_trip_produces_measurement() -> None:
    """record_input + record_output creates one LatencyMeasurement."""
    t = LatencyTracker()
    t0 = time.perf_counter()
    t.record_input(t0)
    t1 = time.perf_counter()
    t.record_output(t1)
    assert len(t.samples) == 1
    m = t.samples[0]
    assert isinstance(m, LatencyMeasurement)
    assert m.button_press_ts == pytest.approx(t0)
    assert m.midi_send_ts == pytest.approx(t1)
    assert m.delta_ms >= 0.0


def test_last_delta_ms_returns_none_when_no_samples() -> None:
    t = LatencyTracker()
    assert t.last_delta_ms() is None


def test_last_delta_ms_after_one_sample() -> None:
    t = LatencyTracker()
    t.record_input(1.0)
    t.record_output(1.005)   # 5 ms later
    result = t.last_delta_ms()
    assert result is not None
    assert result == pytest.approx(5.0, abs=1e-6)


def test_mean_ms_with_five_samples() -> None:
    """mean_ms returns the arithmetic mean over all samples."""
    t = LatencyTracker()
    deltas = [1.0, 2.0, 3.0, 4.0, 5.0]   # ms
    base = 0.0
    for d in deltas:
        t.record_input(base)
        t.record_output(base + d / 1_000.0)
        base += 0.1
    result = t.mean_ms()
    assert result is not None
    assert result == pytest.approx(3.0, abs=1e-6)


def test_mean_ms_returns_none_when_no_samples() -> None:
    t = LatencyTracker()
    assert t.mean_ms() is None


def test_reset_clears_samples() -> None:
    t = LatencyTracker()
    t.record_input(0.0)
    t.record_output(0.001)
    assert len(t.samples) == 1
    t.reset()
    assert len(t.samples) == 0
    assert t.last_delta_ms() is None
    assert t.mean_ms() is None


def test_reset_clears_pending_input() -> None:
    """reset() should also clear an un-paired pending input timestamp."""
    t = LatencyTracker()
    t.record_input(0.0)
    t.reset()
    # recording output after reset should not produce a sample
    t.record_output(0.001)
    assert len(t.samples) == 0


def test_record_output_without_input_is_noop() -> None:
    t = LatencyTracker()
    t.record_output(1.0)
    assert len(t.samples) == 0


def test_min_max_ms() -> None:
    t = LatencyTracker()
    for d_ms in [10.0, 20.0, 5.0]:
        t.record_input(0.0)
        t.record_output(d_ms / 1_000.0)
    assert t.min_ms() == pytest.approx(5.0, abs=1e-6)
    assert t.max_ms() == pytest.approx(20.0, abs=1e-6)


def test_std_ms_returns_none_for_single_sample() -> None:
    t = LatencyTracker()
    t.record_input(0.0)
    t.record_output(0.001)
    assert t.std_ms() is None


def test_std_ms_with_two_samples() -> None:
    t = LatencyTracker()
    t.record_input(0.0)
    t.record_output(0.001)   # 1 ms
    t.record_input(0.1)
    t.record_output(0.103)   # 3 ms
    std = t.std_ms()
    assert std is not None
    # population std of [1, 3] = 1.0
    assert std == pytest.approx(1.0, abs=1e-6)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

def test_singleton_returns_same_instance() -> None:
    a = latency_test.tracker()
    b = latency_test.tracker()
    assert a is b


def test_singleton_is_latency_tracker_instance() -> None:
    assert isinstance(latency_test.tracker(), LatencyTracker)
