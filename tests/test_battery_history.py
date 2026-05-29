"""Tests for battery history tracking.

BatteryHistory records battery level samples with timestamps and charging status,
then estimates drain rate and predicts remaining time. Pure stdlib, no Qt.
"""
from __future__ import annotations

import time

import pytest


class TestBatterySample:
    """BatterySample dataclass — serialize/deserialize."""

    def test_sample_default_construction(self):
        from gamepad_midi_bridge.battery_history import BatterySample
        sample = BatterySample(percent=75, timestamp_s=12345.0)
        assert sample.percent == 75
        assert sample.timestamp_s == 12345.0
        assert sample.is_charging is False

    def test_sample_with_charging(self):
        from gamepad_midi_bridge.battery_history import BatterySample
        sample = BatterySample(percent=100, timestamp_s=12345.0, is_charging=True)
        assert sample.percent == 100
        assert sample.is_charging is True

    def test_sample_to_dict(self):
        from gamepad_midi_bridge.battery_history import BatterySample
        sample = BatterySample(percent=80, timestamp_s=99999.0, is_charging=False)
        d = sample.to_dict()
        assert d["percent"] == 80
        assert d["timestamp_s"] == 99999.0
        assert d["is_charging"] is False

    def test_sample_from_dict(self):
        from gamepad_midi_bridge.battery_history import BatterySample
        d = {"percent": 50, "timestamp_s": 55555.0, "is_charging": True}
        sample = BatterySample.from_dict(d)
        assert sample.percent == 50
        assert sample.timestamp_s == 55555.0
        assert sample.is_charging is True

    def test_sample_round_trip(self):
        from gamepad_midi_bridge.battery_history import BatterySample
        original = BatterySample(percent=60, timestamp_s=12345.6, is_charging=True)
        d = original.to_dict()
        restored = BatterySample.from_dict(d)
        assert restored.percent == original.percent
        assert restored.timestamp_s == original.timestamp_s
        assert restored.is_charging == original.is_charging


class TestBatteryHistoryConfig:
    """BatteryHistoryConfig — clamp parameters on construction."""

    def test_config_defaults(self):
        from gamepad_midi_bridge.battery_history import BatteryHistoryConfig
        cfg = BatteryHistoryConfig()
        assert cfg.max_samples == 1000
        assert cfg.min_samples_for_estimate == 3

    def test_config_clamp_max_samples_below_10(self):
        from gamepad_midi_bridge.battery_history import BatteryHistoryConfig
        cfg = BatteryHistoryConfig(max_samples=5)
        assert cfg.max_samples == 10
        cfg = BatteryHistoryConfig(max_samples=0)
        assert cfg.max_samples == 10

    def test_config_clamp_max_samples_above_100000(self):
        from gamepad_midi_bridge.battery_history import BatteryHistoryConfig
        cfg = BatteryHistoryConfig(max_samples=100001)
        assert cfg.max_samples == 100000
        cfg = BatteryHistoryConfig(max_samples=999999)
        assert cfg.max_samples == 100000

    def test_config_no_clamp_max_samples_in_range(self):
        from gamepad_midi_bridge.battery_history import BatteryHistoryConfig
        cfg = BatteryHistoryConfig(max_samples=5000)
        assert cfg.max_samples == 5000

    def test_config_clamp_min_samples_below_2(self):
        from gamepad_midi_bridge.battery_history import BatteryHistoryConfig
        cfg = BatteryHistoryConfig(min_samples_for_estimate=1)
        assert cfg.min_samples_for_estimate == 2
        cfg = BatteryHistoryConfig(min_samples_for_estimate=0)
        assert cfg.min_samples_for_estimate == 2

    def test_config_clamp_min_samples_above_100(self):
        from gamepad_midi_bridge.battery_history import BatteryHistoryConfig
        cfg = BatteryHistoryConfig(min_samples_for_estimate=101)
        assert cfg.min_samples_for_estimate == 100
        cfg = BatteryHistoryConfig(min_samples_for_estimate=200)
        assert cfg.min_samples_for_estimate == 100

    def test_config_no_clamp_min_samples_in_range(self):
        from gamepad_midi_bridge.battery_history import BatteryHistoryConfig
        cfg = BatteryHistoryConfig(min_samples_for_estimate=5)
        assert cfg.min_samples_for_estimate == 5

    def test_config_to_dict(self):
        from gamepad_midi_bridge.battery_history import BatteryHistoryConfig
        cfg = BatteryHistoryConfig(max_samples=500, min_samples_for_estimate=4)
        d = cfg.to_dict()
        assert d["max_samples"] == 500
        assert d["min_samples_for_estimate"] == 4

    def test_config_from_dict(self):
        from gamepad_midi_bridge.battery_history import BatteryHistoryConfig
        d = {"max_samples": 2000, "min_samples_for_estimate": 5}
        cfg = BatteryHistoryConfig.from_dict(d)
        assert cfg.max_samples == 2000
        assert cfg.min_samples_for_estimate == 5

    def test_config_round_trip(self):
        from gamepad_midi_bridge.battery_history import BatteryHistoryConfig
        original = BatteryHistoryConfig(max_samples=800, min_samples_for_estimate=6)
        d = original.to_dict()
        restored = BatteryHistoryConfig.from_dict(d)
        assert restored.max_samples == original.max_samples
        assert restored.min_samples_for_estimate == original.min_samples_for_estimate


class TestBatteryHistory:
    """BatteryHistory — record, query, estimate drain rate and remaining time."""

    def test_empty_current_none(self):
        from gamepad_midi_bridge.battery_history import BatteryHistory, BatteryHistoryConfig
        cfg = BatteryHistoryConfig()
        hist = BatteryHistory(cfg)
        assert hist.current() is None

    def test_empty_drain_rate_none(self):
        from gamepad_midi_bridge.battery_history import BatteryHistory, BatteryHistoryConfig
        cfg = BatteryHistoryConfig()
        hist = BatteryHistory(cfg)
        assert hist.drain_rate_per_hour() is None

    def test_empty_remaining_minutes_none(self):
        from gamepad_midi_bridge.battery_history import BatteryHistory, BatteryHistoryConfig
        cfg = BatteryHistoryConfig()
        hist = BatteryHistory(cfg)
        assert hist.predicted_remaining_minutes() is None

    def test_record_and_current(self):
        from gamepad_midi_bridge.battery_history import BatteryHistory, BatteryHistoryConfig
        cfg = BatteryHistoryConfig()
        hist = BatteryHistory(cfg)
        hist.record(75, 12345.0)
        current = hist.current()
        assert current is not None
        assert current.percent == 75
        assert current.timestamp_s == 12345.0
        assert current.is_charging is False

    def test_record_multiple_returns_last(self):
        from gamepad_midi_bridge.battery_history import BatteryHistory, BatteryHistoryConfig
        cfg = BatteryHistoryConfig()
        hist = BatteryHistory(cfg)
        hist.record(100, 0)
        hist.record(90, 1000)
        hist.record(80, 2000)
        current = hist.current()
        assert current.percent == 80
        assert current.timestamp_s == 2000

    def test_record_clamps_percent_below_zero(self):
        from gamepad_midi_bridge.battery_history import BatteryHistory, BatteryHistoryConfig
        cfg = BatteryHistoryConfig()
        hist = BatteryHistory(cfg)
        hist.record(-10, 0)
        assert hist.current().percent == 0

    def test_record_clamps_percent_above_100(self):
        from gamepad_midi_bridge.battery_history import BatteryHistory, BatteryHistoryConfig
        cfg = BatteryHistoryConfig()
        hist = BatteryHistory(cfg)
        hist.record(150, 0)
        assert hist.current().percent == 100

    def test_three_samples_one_hour_10_percent_drain(self):
        """100% -> 95% -> 90% over 1 hour = 10%/hour drain."""
        from gamepad_midi_bridge.battery_history import BatteryHistory, BatteryHistoryConfig
        cfg = BatteryHistoryConfig(min_samples_for_estimate=2)
        hist = BatteryHistory(cfg)
        hist.record(100, 0)
        hist.record(95, 1800)  # 30 min, 5% drain
        hist.record(90, 3600)  # 60 min total, 10% drain
        drain = hist.drain_rate_per_hour()
        assert drain is not None
        assert round(drain, 1) == 10.0

    def test_drain_rate_fewer_than_min_samples(self):
        from gamepad_midi_bridge.battery_history import BatteryHistory, BatteryHistoryConfig
        cfg = BatteryHistoryConfig(min_samples_for_estimate=5)
        hist = BatteryHistory(cfg)
        hist.record(100, 0)
        hist.record(95, 1800)
        hist.record(90, 3600)
        # Only 3 samples, but min is 5
        assert hist.drain_rate_per_hour() is None

    def test_drain_rate_with_charging_sample_returns_none(self):
        from gamepad_midi_bridge.battery_history import BatteryHistory, BatteryHistoryConfig
        cfg = BatteryHistoryConfig(min_samples_for_estimate=2)
        hist = BatteryHistory(cfg)
        hist.record(50, 0, is_charging=False)
        hist.record(60, 1800, is_charging=True)
        hist.record(70, 3600, is_charging=False)
        # Mixed with charging; drain rate should be None
        assert hist.drain_rate_per_hour() is None

    def test_drain_rate_negative_trend_returns_zero(self):
        """Battery increased (charging detected); return 0 instead of negative."""
        from gamepad_midi_bridge.battery_history import BatteryHistory, BatteryHistoryConfig
        cfg = BatteryHistoryConfig(min_samples_for_estimate=2)
        hist = BatteryHistory(cfg)
        hist.record(50, 0)
        hist.record(90, 3600)  # Increased 40% over 1 hour
        drain = hist.drain_rate_per_hour()
        assert drain == 0.0

    def test_predicted_remaining_minutes_math(self):
        """90% battery with 10%/hour drain = 9 * 60 = 540 minutes."""
        from gamepad_midi_bridge.battery_history import BatteryHistory, BatteryHistoryConfig
        cfg = BatteryHistoryConfig(min_samples_for_estimate=2)
        hist = BatteryHistory(cfg)
        hist.record(100, 0)
        hist.record(90, 3600)  # 10%/hour drain
        remaining = hist.predicted_remaining_minutes()
        assert remaining is not None
        assert round(remaining, 1) == 540.0

    def test_predicted_remaining_no_current_sample(self):
        from gamepad_midi_bridge.battery_history import BatteryHistory, BatteryHistoryConfig
        cfg = BatteryHistoryConfig()
        hist = BatteryHistory(cfg)
        assert hist.predicted_remaining_minutes() is None

    def test_predicted_remaining_zero_drain_rate(self):
        """If drain rate is 0 or negative, remaining is None."""
        from gamepad_midi_bridge.battery_history import BatteryHistory, BatteryHistoryConfig
        cfg = BatteryHistoryConfig(min_samples_for_estimate=2)
        hist = BatteryHistory(cfg)
        hist.record(50, 0)
        hist.record(60, 3600)  # Charging trend (negative drain)
        assert hist.predicted_remaining_minutes() is None

    def test_peak_drain_rate_two_samples(self):
        """Peak drain over a 2-sample window."""
        from gamepad_midi_bridge.battery_history import BatteryHistory, BatteryHistoryConfig
        cfg = BatteryHistoryConfig()
        hist = BatteryHistory(cfg)
        hist.record(100, 0)
        hist.record(90, 3600)
        peak = hist.peak_drain_rate()
        assert peak is not None
        assert round(peak, 1) == 10.0

    def test_peak_drain_rate_multiple_windows(self):
        """Peak drain across multiple windows; return max."""
        from gamepad_midi_bridge.battery_history import BatteryHistory, BatteryHistoryConfig
        cfg = BatteryHistoryConfig()
        hist = BatteryHistory(cfg)
        hist.record(100, 0)
        hist.record(95, 1800)  # 5% in 30 min = 10%/hour
        hist.record(80, 5400)  # 15% in 60 min = 15%/hour (peak)
        hist.record(70, 7200)  # 10% in 30 min = 20%/hour (new peak)
        peak = hist.peak_drain_rate()
        assert peak is not None
        assert round(peak, 1) == 20.0

    def test_peak_drain_rate_no_samples(self):
        from gamepad_midi_bridge.battery_history import BatteryHistory, BatteryHistoryConfig
        cfg = BatteryHistoryConfig()
        hist = BatteryHistory(cfg)
        assert hist.peak_drain_rate() is None

    def test_peak_drain_rate_one_sample(self):
        from gamepad_midi_bridge.battery_history import BatteryHistory, BatteryHistoryConfig
        cfg = BatteryHistoryConfig()
        hist = BatteryHistory(cfg)
        hist.record(75, 0)
        assert hist.peak_drain_rate() is None

    def test_peak_drain_rate_skips_charging_windows(self):
        """Windows with charging samples are skipped."""
        from gamepad_midi_bridge.battery_history import BatteryHistory, BatteryHistoryConfig
        cfg = BatteryHistoryConfig()
        hist = BatteryHistory(cfg)
        hist.record(50, 0, is_charging=True)  # Charging, skip next window
        hist.record(40, 1800)  # Non-charging
        hist.record(30, 3600)  # 10% in 30 min = 20%/hour (not skipped)
        peak = hist.peak_drain_rate()
        assert peak is not None
        assert round(peak, 1) == 20.0

    def test_last_charge_time_found(self):
        from gamepad_midi_bridge.battery_history import BatteryHistory, BatteryHistoryConfig
        cfg = BatteryHistoryConfig()
        hist = BatteryHistory(cfg)
        hist.record(100, 1000, is_charging=True)
        hist.record(95, 2000, is_charging=False)
        hist.record(90, 3000, is_charging=False)
        assert hist.last_charge_time() == 1000.0

    def test_last_charge_time_most_recent(self):
        """Return timestamp of most recent charging sample."""
        from gamepad_midi_bridge.battery_history import BatteryHistory, BatteryHistoryConfig
        cfg = BatteryHistoryConfig()
        hist = BatteryHistory(cfg)
        hist.record(100, 1000, is_charging=True)
        hist.record(95, 2000, is_charging=False)
        hist.record(100, 3000, is_charging=True)
        hist.record(99, 4000, is_charging=False)
        assert hist.last_charge_time() == 3000.0

    def test_last_charge_time_none_if_never_charging(self):
        from gamepad_midi_bridge.battery_history import BatteryHistory, BatteryHistoryConfig
        cfg = BatteryHistoryConfig()
        hist = BatteryHistory(cfg)
        hist.record(100, 1000)
        hist.record(95, 2000)
        hist.record(90, 3000)
        assert hist.last_charge_time() is None

    def test_max_samples_fifo_eviction(self):
        from gamepad_midi_bridge.battery_history import BatteryHistory, BatteryHistoryConfig
        cfg = BatteryHistoryConfig(max_samples=20)  # Will stay at 20 after clamping
        hist = BatteryHistory(cfg)
        # Add 22 samples to trigger eviction
        for i in range(22):
            hist.record(100 - i, i * 100)
        samples = [s for s in hist._samples]
        assert len(samples) == 20
        assert samples[0].percent == 100 - 2  # First two should be evicted
        assert samples[-1].percent == 100 - 21

    def test_clear(self):
        from gamepad_midi_bridge.battery_history import BatteryHistory, BatteryHistoryConfig
        cfg = BatteryHistoryConfig()
        hist = BatteryHistory(cfg)
        hist.record(100, 0)
        hist.record(90, 1000)
        assert hist.current() is not None
        hist.clear()
        assert hist.current() is None
        assert len(hist._samples) == 0

    def test_summary_empty(self):
        from gamepad_midi_bridge.battery_history import BatteryHistory, BatteryHistoryConfig
        cfg = BatteryHistoryConfig()
        hist = BatteryHistory(cfg)
        summary = hist.summary()
        assert summary["current"] is None
        assert summary["drain_per_hour"] is None
        assert summary["remaining_min"] is None
        assert summary["samples"] == 0
        assert summary["is_charging"] is False

    def test_summary_with_data(self):
        from gamepad_midi_bridge.battery_history import BatteryHistory, BatteryHistoryConfig
        cfg = BatteryHistoryConfig(min_samples_for_estimate=2)
        hist = BatteryHistory(cfg)
        hist.record(100, 0)
        hist.record(90, 3600)
        summary = hist.summary()
        assert summary["current"] == 90
        assert summary["drain_per_hour"] is not None
        assert round(summary["drain_per_hour"], 1) == 10.0
        assert summary["remaining_min"] is not None
        assert round(summary["remaining_min"], 1) == 540.0
        assert summary["samples"] == 2
        assert summary["is_charging"] is False

    def test_summary_charging(self):
        from gamepad_midi_bridge.battery_history import BatteryHistory, BatteryHistoryConfig
        cfg = BatteryHistoryConfig()
        hist = BatteryHistory(cfg)
        hist.record(80, 1000, is_charging=True)
        summary = hist.summary()
        assert summary["current"] == 80
        assert summary["is_charging"] is True

    def test_summary_all_keys_present(self):
        """Verify all expected keys in summary dict."""
        from gamepad_midi_bridge.battery_history import BatteryHistory, BatteryHistoryConfig
        cfg = BatteryHistoryConfig()
        hist = BatteryHistory(cfg)
        hist.record(75, 0)
        summary = hist.summary()
        assert "current" in summary
        assert "drain_per_hour" in summary
        assert "remaining_min" in summary
        assert "samples" in summary
        assert "is_charging" in summary
