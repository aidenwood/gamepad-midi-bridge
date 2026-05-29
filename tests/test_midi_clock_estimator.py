"""Tests for MIDI Clock BPM estimator.

MidiClockEstimator takes MIDI Clock ticks (24 per quarter note) and derives BPM.
Pure stdlib, no Qt.
"""

from __future__ import annotations

import pytest


class TestMidiClockEstimatorConfig:
    """MidiClockEstimatorConfig — clamp values on construction."""

    def test_config_defaults(self):
        from gamepad_midi_bridge.midi_clock_estimator import MidiClockEstimatorConfig

        cfg = MidiClockEstimatorConfig()
        assert cfg.enabled is False
        assert cfg.window_size == 96
        assert cfg.smoothing == 0.3
        assert cfg.min_bpm == 20.0
        assert cfg.max_bpm == 300.0

    def test_config_clamp_window_size_below_24(self):
        from gamepad_midi_bridge.midi_clock_estimator import MidiClockEstimatorConfig

        cfg = MidiClockEstimatorConfig(window_size=10)
        assert cfg.window_size == 24

        cfg = MidiClockEstimatorConfig(window_size=0)
        assert cfg.window_size == 24

    def test_config_clamp_window_size_above_480(self):
        from gamepad_midi_bridge.midi_clock_estimator import MidiClockEstimatorConfig

        cfg = MidiClockEstimatorConfig(window_size=500)
        assert cfg.window_size == 480

        cfg = MidiClockEstimatorConfig(window_size=1000)
        assert cfg.window_size == 480

    def test_config_no_clamp_window_size_in_range(self):
        from gamepad_midi_bridge.midi_clock_estimator import MidiClockEstimatorConfig

        cfg = MidiClockEstimatorConfig(window_size=96)
        assert cfg.window_size == 96

        cfg = MidiClockEstimatorConfig(window_size=240)
        assert cfg.window_size == 240

    def test_config_clamp_smoothing_below_zero(self):
        from gamepad_midi_bridge.midi_clock_estimator import MidiClockEstimatorConfig

        cfg = MidiClockEstimatorConfig(smoothing=-0.1)
        assert cfg.smoothing == 0.0

        cfg = MidiClockEstimatorConfig(smoothing=-1.0)
        assert cfg.smoothing == 0.0

    def test_config_clamp_smoothing_above_0_99(self):
        from gamepad_midi_bridge.midi_clock_estimator import MidiClockEstimatorConfig

        cfg = MidiClockEstimatorConfig(smoothing=1.0)
        assert cfg.smoothing == 0.99

        cfg = MidiClockEstimatorConfig(smoothing=1.5)
        assert cfg.smoothing == 0.99

    def test_config_no_clamp_smoothing_in_range(self):
        from gamepad_midi_bridge.midi_clock_estimator import MidiClockEstimatorConfig

        cfg = MidiClockEstimatorConfig(smoothing=0.3)
        assert cfg.smoothing == 0.3

        cfg = MidiClockEstimatorConfig(smoothing=0.99)
        assert cfg.smoothing == 0.99

    def test_config_clamp_min_bpm_below_10(self):
        from gamepad_midi_bridge.midi_clock_estimator import MidiClockEstimatorConfig

        cfg = MidiClockEstimatorConfig(min_bpm=5)
        assert cfg.min_bpm == 10.0

        cfg = MidiClockEstimatorConfig(min_bpm=-50)
        assert cfg.min_bpm == 10.0

    def test_config_clamp_min_bpm_above_400(self):
        from gamepad_midi_bridge.midi_clock_estimator import MidiClockEstimatorConfig

        cfg = MidiClockEstimatorConfig(min_bpm=500)
        assert cfg.min_bpm == 400.0

        cfg = MidiClockEstimatorConfig(min_bpm=1000)
        assert cfg.min_bpm == 400.0

    def test_config_clamp_max_bpm_below_10(self):
        from gamepad_midi_bridge.midi_clock_estimator import MidiClockEstimatorConfig

        # max_bpm=5 clamps to 10, but then enforced >= min_bpm (default 20), so becomes 20
        cfg = MidiClockEstimatorConfig(max_bpm=5)
        assert cfg.max_bpm == cfg.min_bpm

    def test_config_clamp_max_bpm_above_400(self):
        from gamepad_midi_bridge.midi_clock_estimator import MidiClockEstimatorConfig

        cfg = MidiClockEstimatorConfig(max_bpm=500)
        assert cfg.max_bpm == 400.0

    def test_config_ensure_max_gte_min(self):
        from gamepad_midi_bridge.midi_clock_estimator import MidiClockEstimatorConfig

        cfg = MidiClockEstimatorConfig(min_bpm=200, max_bpm=100)
        assert cfg.max_bpm == cfg.min_bpm

    def test_config_to_dict(self):
        from gamepad_midi_bridge.midi_clock_estimator import MidiClockEstimatorConfig

        cfg = MidiClockEstimatorConfig(
            enabled=True, window_size=120, smoothing=0.5, min_bpm=30.0, max_bpm=250.0
        )
        d = cfg.to_dict()
        assert d["enabled"] is True
        assert d["window_size"] == 120
        assert d["smoothing"] == 0.5
        assert d["min_bpm"] == 30.0
        assert d["max_bpm"] == 250.0

    def test_config_from_dict(self):
        from gamepad_midi_bridge.midi_clock_estimator import MidiClockEstimatorConfig

        data = {
            "enabled": True,
            "window_size": 150,
            "smoothing": 0.4,
            "min_bpm": 40.0,
            "max_bpm": 280.0,
        }
        cfg = MidiClockEstimatorConfig.from_dict(data)
        assert cfg.enabled is True
        assert cfg.window_size == 150
        assert cfg.smoothing == 0.4
        assert cfg.min_bpm == 40.0
        assert cfg.max_bpm == 280.0

    def test_config_round_trip(self):
        from gamepad_midi_bridge.midi_clock_estimator import MidiClockEstimatorConfig

        original = MidiClockEstimatorConfig(
            enabled=True, window_size=120, smoothing=0.6, min_bpm=25.0, max_bpm=320.0
        )
        d = original.to_dict()
        restored = MidiClockEstimatorConfig.from_dict(d)
        assert restored.enabled == original.enabled
        assert restored.window_size == original.window_size
        assert restored.smoothing == original.smoothing
        assert restored.min_bpm == original.min_bpm
        assert restored.max_bpm == original.max_bpm


class TestMidiClockEstimator:
    """MidiClockEstimator — tick processing and BPM estimation."""

    def test_estimator_init(self):
        from gamepad_midi_bridge.midi_clock_estimator import (
            MidiClockEstimator,
            MidiClockEstimatorConfig,
        )

        cfg = MidiClockEstimatorConfig(enabled=True)
        est = MidiClockEstimator(cfg)
        assert est.current_bpm() is None
        assert est.intervals() == []

    def test_first_tick_returns_none(self):
        from gamepad_midi_bridge.midi_clock_estimator import (
            MidiClockEstimator,
            MidiClockEstimatorConfig,
        )

        cfg = MidiClockEstimatorConfig()
        est = MidiClockEstimator(cfg)
        result = est.tick(0.0)
        assert result is None
        assert est.current_bpm() is None

    def test_two_ticks_at_120_bpm(self):
        from gamepad_midi_bridge.midi_clock_estimator import (
            MidiClockEstimator,
            MidiClockEstimatorConfig,
        )

        # At 120 BPM: quarter note = 0.5s, tick = 0.5 / 24 ~= 0.0208333s
        cfg = MidiClockEstimatorConfig(smoothing=0.0)  # No smoothing for exact BPM
        est = MidiClockEstimator(cfg)

        est.tick(0.0)
        bpm = est.tick(0.0208333333)  # One tick interval

        assert bpm is not None
        assert round(bpm, 1) == 120.0

    def test_tick_at_60_bpm(self):
        from gamepad_midi_bridge.midi_clock_estimator import (
            MidiClockEstimator,
            MidiClockEstimatorConfig,
        )

        # At 60 BPM: quarter note = 1.0s, tick = 1.0 / 24 ~= 0.04166667s
        cfg = MidiClockEstimatorConfig(smoothing=0.0)
        est = MidiClockEstimator(cfg)

        est.tick(0.0)
        bpm = est.tick(0.04166667)

        assert bpm is not None
        assert round(bpm, 1) == 60.0

    def test_constant_rate_converges_to_bpm(self):
        from gamepad_midi_bridge.midi_clock_estimator import (
            MidiClockEstimator,
            MidiClockEstimatorConfig,
        )

        # 140 BPM: quarter = 0.42857s, tick = 0.42857 / 24 ~= 0.0178571s
        cfg = MidiClockEstimatorConfig(smoothing=0.0, window_size=96)
        est = MidiClockEstimator(cfg)

        tick_interval = 60.0 / (140.0 * 24.0)  # ~0.0178571s
        for i in range(50):  # Many ticks to let it settle
            est.tick(i * tick_interval)

        bpm = est.current_bpm()
        assert bpm is not None
        assert round(bpm, 0) == 140.0

    def test_smoothing_factor_influences_convergence(self):
        from gamepad_midi_bridge.midi_clock_estimator import (
            MidiClockEstimator,
            MidiClockEstimatorConfig,
        )

        # High smoothing = slow convergence; low smoothing = fast convergence
        cfg_high = MidiClockEstimatorConfig(smoothing=0.95)
        est_high = MidiClockEstimator(cfg_high)

        cfg_low = MidiClockEstimatorConfig(smoothing=0.05)
        est_low = MidiClockEstimator(cfg_low)

        tick_interval = 60.0 / (120.0 * 24.0)

        # Feed ticks at slightly wrong interval first, then correct
        est_high.tick(0.0)
        est_high.tick(tick_interval * 0.8)  # 150 BPM initially
        est_low.tick(0.0)
        est_low.tick(tick_interval * 0.8)

        # Continue with correct interval
        for i in range(2, 50):
            t = i * tick_interval
            est_high.tick(t)
            est_low.tick(t)

        high_bpm = est_high.current_bpm()
        low_bpm = est_low.current_bpm()

        assert high_bpm is not None
        assert low_bpm is not None
        # Low smoothing converges faster (closer to 120 target)
        assert abs(low_bpm - 120.0) < abs(high_bpm - 120.0)

    def test_window_size_caps_history(self):
        from gamepad_midi_bridge.midi_clock_estimator import (
            MidiClockEstimator,
            MidiClockEstimatorConfig,
        )

        cfg = MidiClockEstimatorConfig(window_size=30)
        est = MidiClockEstimator(cfg)

        # Add 50 ticks
        for i in range(50):
            est.tick(i * 0.02)

        # Should only have last 30 ticks (29 intervals)
        intervals = est.intervals()
        assert len(intervals) == 29

    def test_reset_clears_state(self):
        from gamepad_midi_bridge.midi_clock_estimator import (
            MidiClockEstimator,
            MidiClockEstimatorConfig,
        )

        cfg = MidiClockEstimatorConfig()
        est = MidiClockEstimator(cfg)

        # Feed some ticks
        est.tick(0.0)
        est.tick(0.02)
        est.tick(0.04)

        assert est.current_bpm() is not None
        assert len(est.intervals()) > 0

        # Reset
        est.reset()

        assert est.current_bpm() is None
        assert est.intervals() == []

    def test_is_locked_false_with_too_few_samples(self):
        from gamepad_midi_bridge.midi_clock_estimator import (
            MidiClockEstimator,
            MidiClockEstimatorConfig,
        )

        cfg = MidiClockEstimatorConfig()
        est = MidiClockEstimator(cfg)

        est.tick(0.0)
        est.tick(0.02)
        est.tick(0.04)

        # Fewer than 6 ticks = fewer than 5 intervals
        assert est.is_locked() is False

    def test_is_locked_true_with_steady_ticks(self):
        from gamepad_midi_bridge.midi_clock_estimator import (
            MidiClockEstimator,
            MidiClockEstimatorConfig,
        )

        cfg = MidiClockEstimatorConfig()
        est = MidiClockEstimator(cfg)

        # Feed 10 ticks at perfectly constant interval
        tick_interval = 0.02
        for i in range(10):
            est.tick(i * tick_interval)

        assert est.is_locked() is True

    def test_is_locked_false_with_jittery_ticks(self):
        from gamepad_midi_bridge.midi_clock_estimator import (
            MidiClockEstimator,
            MidiClockEstimatorConfig,
        )

        cfg = MidiClockEstimatorConfig()
        est = MidiClockEstimator(cfg)

        # Feed ticks with large jitter
        times = [0.0, 0.01, 0.03, 0.035, 0.055, 0.06, 0.08, 0.09]
        for t in times:
            est.tick(t)

        # Large variation should not be locked
        assert est.is_locked() is False

    def test_bpm_clamping_to_min(self):
        from gamepad_midi_bridge.midi_clock_estimator import (
            MidiClockEstimator,
            MidiClockEstimatorConfig,
        )

        # Set min_bpm high, feed slow ticks
        cfg = MidiClockEstimatorConfig(smoothing=0.0, min_bpm=100.0, max_bpm=300.0)
        est = MidiClockEstimator(cfg)

        # Very slow tick interval (would be 20 BPM)
        tick_interval = 60.0 / (20.0 * 24.0)
        est.tick(0.0)
        bpm = est.tick(tick_interval)

        assert bpm is not None
        assert bpm >= 100.0

    def test_bpm_clamping_to_max(self):
        from gamepad_midi_bridge.midi_clock_estimator import (
            MidiClockEstimator,
            MidiClockEstimatorConfig,
        )

        # Set max_bpm low, feed fast ticks
        cfg = MidiClockEstimatorConfig(smoothing=0.0, min_bpm=20.0, max_bpm=150.0)
        est = MidiClockEstimator(cfg)

        # Very fast tick interval (would be 300 BPM)
        tick_interval = 60.0 / (300.0 * 24.0)
        est.tick(0.0)
        bpm = est.tick(tick_interval)

        assert bpm is not None
        assert bpm <= 150.0

    def test_intervals_empty_before_two_ticks(self):
        from gamepad_midi_bridge.midi_clock_estimator import (
            MidiClockEstimator,
            MidiClockEstimatorConfig,
        )

        cfg = MidiClockEstimatorConfig()
        est = MidiClockEstimator(cfg)

        est.tick(0.0)
        assert est.intervals() == []

    def test_intervals_populated_after_two_ticks(self):
        from gamepad_midi_bridge.midi_clock_estimator import (
            MidiClockEstimator,
            MidiClockEstimatorConfig,
        )

        cfg = MidiClockEstimatorConfig()
        est = MidiClockEstimator(cfg)

        est.tick(0.0)
        est.tick(0.02)
        est.tick(0.04)

        intervals = est.intervals()
        assert len(intervals) == 2
        assert abs(intervals[0] - 0.02) < 1e-9
        assert abs(intervals[1] - 0.02) < 1e-9

    def test_clamp_window_size_applied_in_config(self):
        from gamepad_midi_bridge.midi_clock_estimator import (
            MidiClockEstimator,
            MidiClockEstimatorConfig,
        )

        # Out-of-range window_size should be clamped
        cfg = MidiClockEstimatorConfig(window_size=10)
        assert cfg.window_size == 24

        cfg = MidiClockEstimatorConfig(window_size=600)
        assert cfg.window_size == 480

    def test_clamp_smoothing_applied_in_config(self):
        from gamepad_midi_bridge.midi_clock_estimator import (
            MidiClockEstimator,
            MidiClockEstimatorConfig,
        )

        cfg = MidiClockEstimatorConfig(smoothing=-0.1)
        assert cfg.smoothing == 0.0

        cfg = MidiClockEstimatorConfig(smoothing=1.5)
        assert cfg.smoothing == 0.99

    def test_bpm_calculation_with_multiple_quarter_notes(self):
        from gamepad_midi_bridge.midi_clock_estimator import (
            MidiClockEstimator,
            MidiClockEstimatorConfig,
        )

        # 100 BPM: quarter = 0.6s, tick = 0.6/24 = 0.025s
        cfg = MidiClockEstimatorConfig(smoothing=0.0)
        est = MidiClockEstimator(cfg)

        tick_interval = 60.0 / (100.0 * 24.0)
        est.tick(0.0)
        bpm = est.tick(tick_interval)

        assert bpm is not None
        assert round(bpm, 1) == 100.0

    def test_estimate_after_multiple_ticks(self):
        from gamepad_midi_bridge.midi_clock_estimator import (
            MidiClockEstimator,
            MidiClockEstimatorConfig,
        )

        cfg = MidiClockEstimatorConfig(smoothing=0.0)
        est = MidiClockEstimator(cfg)

        tick_interval = 60.0 / (160.0 * 24.0)
        for i in range(10):
            est.tick(i * tick_interval)

        bpm = est.current_bpm()
        assert bpm is not None
        assert round(bpm, 0) == 160.0
