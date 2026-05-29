"""Tests for the tempo_tap module — BPM estimation from tapped intervals.

Pure stdlib implementation for "tap to set tempo" workflows. Tests cover:
- Single and multi-tap BPM estimation
- History management and reset timeouts
- Stability metrics for tap consistency
- Min/max BPM clamping
"""
from __future__ import annotations

import pytest

from gamepad_midi_bridge import tempo_tap


class TestTempoTapBasics:
    """Basic tap and BPM estimation."""

    def test_single_tap_returns_none(self):
        """One tap alone has no interval, returns None."""
        tapper = tempo_tap.TempoTap()
        result = tapper.tap(0.0)
        assert result is None

    def test_two_taps_half_second_apart_returns_120_bpm(self):
        """0.5s interval = 120 BPM (60 / 0.5 = 120)."""
        tapper = tempo_tap.TempoTap()
        tapper.tap(0.0)
        result = tapper.tap(0.5)
        assert result == pytest.approx(120.0, abs=1e-6)

    def test_two_taps_one_second_apart_returns_60_bpm(self):
        """1.0s interval = 60 BPM (60 / 1.0 = 60)."""
        tapper = tempo_tap.TempoTap()
        tapper.tap(0.0)
        result = tapper.tap(1.0)
        assert result == pytest.approx(60.0, abs=1e-6)

    def test_four_taps_uniform_half_second_spacing_returns_120_bpm(self):
        """Four taps spaced 0.5s apart → 3 intervals, all 0.5s → 120 BPM."""
        tapper = tempo_tap.TempoTap()
        times = [0.0, 0.5, 1.0, 1.5]
        bpm_history = [tapper.tap(t) for t in times]
        assert bpm_history[-1] == pytest.approx(120.0, abs=1e-6)


class TestTempoTapReset:
    """History management and reset timeout."""

    def test_tap_after_reset_timeout_clears_history(self):
        """Gap > reset_timeout_s clears previous taps."""
        tapper = tempo_tap.TempoTap(reset_timeout_s=2.0)
        tapper.tap(0.0)
        tapper.tap(0.5)  # Should have 2 taps, 120 BPM
        assert tapper.bpm() == pytest.approx(120.0, abs=1e-6)

        # Gap of 2.1s > timeout, clears history.
        tapper.tap(2.6)
        assert len(tapper._taps) == 1  # Only the new tap
        assert tapper.bpm() is None  # Only 1 tap

    def test_explicit_reset_clears_taps(self):
        """reset() method clears all taps."""
        tapper = tempo_tap.TempoTap()
        tapper.tap(0.0)
        tapper.tap(0.5)
        assert tapper.bpm() is not None
        tapper.reset()
        assert len(tapper._taps) == 0
        assert tapper.bpm() is None


class TestTempoTapMaxHistory:
    """History capping."""

    def test_max_history_caps_memory(self):
        """Adding taps beyond max_history drops oldest."""
        tapper = tempo_tap.TempoTap(max_history=3)
        times = [0.0, 0.5, 1.0, 1.5, 2.0]
        for t in times:
            tapper.tap(t)
        assert len(tapper._taps) == 3
        # Should be the last 3: [1.0, 1.5, 2.0]
        assert tapper._taps[0] == pytest.approx(1.0, abs=1e-6)


class TestTempoTapIntervals:
    """Inter-tap interval calculations."""

    def test_intervals_from_three_taps(self):
        """Three taps → two intervals."""
        tapper = tempo_tap.TempoTap()
        tapper.tap(0.0)
        tapper.tap(0.5)
        tapper.tap(1.5)
        intervals = tapper.intervals()
        assert len(intervals) == 2
        assert intervals[0] == pytest.approx(0.5, abs=1e-6)
        assert intervals[1] == pytest.approx(1.0, abs=1e-6)

    def test_intervals_empty_with_single_tap(self):
        """Single tap → no intervals."""
        tapper = tempo_tap.TempoTap()
        tapper.tap(0.0)
        assert tapper.intervals() == []

    def test_intervals_empty_with_no_taps(self):
        """No taps → no intervals."""
        tapper = tempo_tap.TempoTap()
        assert tapper.intervals() == []


class TestTempoTapStability:
    """Tap consistency (coefficient of variation)."""

    def test_stability_none_with_two_taps(self):
        """Stability requires at least 3 taps (to compute stddev)."""
        tapper = tempo_tap.TempoTap()
        tapper.tap(0.0)
        tapper.tap(0.5)
        assert tapper.stability() is None

    def test_stability_uniform_taps_is_zero(self):
        """Perfectly uniform intervals → CV = 0."""
        tapper = tempo_tap.TempoTap()
        tapper.tap(0.0)
        tapper.tap(0.5)
        tapper.tap(1.0)
        tapper.tap(1.5)
        stability = tapper.stability()
        assert stability == pytest.approx(0.0, abs=1e-6)

    def test_stability_lower_with_uniform_tapping(self):
        """More uniform tapping → lower stability (CV)."""
        # Uniform tapping: 0.5s each
        uniform_tapper = tempo_tap.TempoTap()
        for i in range(5):
            uniform_tapper.tap(i * 0.5)
        uniform_stability = uniform_tapper.stability()

        # Variable tapping: 0.3, 0.7, 0.3, 0.7, ...
        variable_tapper = tempo_tap.TempoTap()
        time = 0.0
        intervals_var = [0.3, 0.7, 0.3, 0.7, 0.3]
        for interval in intervals_var:
            variable_tapper.tap(time)
            time += interval
        variable_tapper.tap(time)  # One final tap for final interval
        variable_stability = variable_tapper.stability()

        assert uniform_stability is not None
        assert variable_stability is not None
        assert uniform_stability < variable_stability


class TestTempoTapClamping:
    """Min/max BPM clamping."""

    def test_min_bpm_clamping(self):
        """BPM below min_bpm is clamped to min_bpm."""
        # 2 taps 1.0s apart = 60 BPM, but set min_bpm=90 to clamp
        tapper = tempo_tap.TempoTap(min_bpm=90.0, max_bpm=300.0, reset_timeout_s=10.0)
        tapper.tap(0.0)
        tapper.tap(1.0)  # 60 BPM raw
        bpm = tapper.bpm()
        assert bpm == pytest.approx(90.0, abs=1e-6)

    def test_max_bpm_clamping(self):
        """BPM above max_bpm is clamped to max_bpm."""
        # 2 taps 0.1s apart = 600 BPM, clamped to 200
        tapper = tempo_tap.TempoTap(min_bpm=30.0, max_bpm=200.0)
        tapper.tap(0.0)
        tapper.tap(0.1)
        bpm = tapper.bpm()
        assert bpm == pytest.approx(200.0, abs=1e-6)

    def test_unclamped_bpm_returns_as_is(self):
        """BPM within range returns as-is."""
        tapper = tempo_tap.TempoTap(min_bpm=30.0, max_bpm=300.0)
        tapper.tap(0.0)
        tapper.tap(0.5)  # 120 BPM
        bpm = tapper.bpm()
        assert bpm == pytest.approx(120.0, abs=1e-6)


class TestTempoTapEdgeCases:
    """Edge cases and error handling."""

    def test_zero_interval_returns_none(self):
        """Two taps at the same time → 0 interval → None."""
        tapper = tempo_tap.TempoTap()
        tapper.tap(0.0)
        tapper.tap(0.0)
        # Mean interval = 0, can't compute BPM, return None
        bpm = tapper.bpm()
        assert bpm is None

    def test_tap_method_returns_same_as_bpm_method(self):
        """tap() return value matches bpm() after tap."""
        tapper = tempo_tap.TempoTap()
        tapper.tap(0.0)
        tap_result = tapper.tap(0.5)
        bpm_result = tapper.bpm()
        assert tap_result == bpm_result

    def test_multiple_resets(self):
        """Multiple resets work correctly."""
        tapper = tempo_tap.TempoTap()
        tapper.tap(0.0)
        tapper.reset()
        assert tapper.bpm() is None
        tapper.tap(10.0)
        tapper.reset()
        assert tapper.bpm() is None
        tapper.tap(20.0)
        tapper.tap(20.5)
        assert tapper.bpm() == pytest.approx(120.0, abs=1e-6)

    def test_stability_with_many_uniform_taps(self):
        """Stability → 0 as taps become more uniform."""
        tapper = tempo_tap.TempoTap(max_history=20)
        # 10 taps at 0.5s intervals
        for i in range(10):
            tapper.tap(i * 0.5)
        stability = tapper.stability()
        assert stability == pytest.approx(0.0, abs=1e-6)
