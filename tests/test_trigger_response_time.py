"""Tests for trigger response time analysis.

TriggerResponseAnalyzer records trigger pull durations (time from first pressure
to peak), providing metrics on how snappy/soft a player's touch is. Pure stdlib, no Qt.
"""
from __future__ import annotations

import pytest


class TestPullEvent:
    """PullEvent dataclass — serialize/deserialize."""

    def test_pull_event_construction(self):
        from gamepad_midi_bridge.trigger_response_time import PullEvent
        event = PullEvent(
            trigger="L2",
            start_at_s=100.0,
            peak_at_s=100.15,
            peak_pressure=0.95,
            duration_ms=150.0,
        )
        assert event.trigger == "L2"
        assert event.start_at_s == 100.0
        assert event.peak_at_s == 100.15
        assert event.peak_pressure == 0.95
        assert event.duration_ms == 150.0

    def test_pull_event_to_dict(self):
        from gamepad_midi_bridge.trigger_response_time import PullEvent
        event = PullEvent(
            trigger="R2",
            start_at_s=200.0,
            peak_at_s=200.1,
            peak_pressure=0.85,
            duration_ms=100.0,
        )
        d = event.to_dict()
        assert d["trigger"] == "R2"
        assert d["start_at_s"] == 200.0
        assert d["peak_at_s"] == 200.1
        assert d["peak_pressure"] == 0.85
        assert d["duration_ms"] == 100.0

    def test_pull_event_from_dict(self):
        from gamepad_midi_bridge.trigger_response_time import PullEvent
        d = {
            "trigger": "L2",
            "start_at_s": 50.0,
            "peak_at_s": 50.12,
            "peak_pressure": 0.75,
            "duration_ms": 120.0,
        }
        event = PullEvent.from_dict(d)
        assert event.trigger == "L2"
        assert event.start_at_s == 50.0
        assert event.peak_at_s == 50.12
        assert event.peak_pressure == 0.75
        assert event.duration_ms == 120.0

    def test_pull_event_round_trip(self):
        from gamepad_midi_bridge.trigger_response_time import PullEvent
        original = PullEvent(
            trigger="R2",
            start_at_s=75.5,
            peak_at_s=75.65,
            peak_pressure=0.9,
            duration_ms=150.0,
        )
        d = original.to_dict()
        restored = PullEvent.from_dict(d)
        assert restored.trigger == original.trigger
        assert restored.start_at_s == original.start_at_s
        assert restored.peak_at_s == original.peak_at_s
        assert restored.peak_pressure == original.peak_pressure
        assert restored.duration_ms == original.duration_ms


class TestTriggerResponseConfig:
    """TriggerResponseConfig — clamp parameters on construction."""

    def test_config_defaults(self):
        from gamepad_midi_bridge.trigger_response_time import TriggerResponseConfig
        cfg = TriggerResponseConfig()
        assert cfg.release_threshold == 0.05
        assert cfg.peak_min == 0.7
        assert cfg.max_pulls == 1000

    def test_config_clamp_release_threshold_below_zero(self):
        from gamepad_midi_bridge.trigger_response_time import TriggerResponseConfig
        cfg = TriggerResponseConfig(release_threshold=-0.1)
        assert cfg.release_threshold == 0.0

    def test_config_clamp_release_threshold_above_one(self):
        from gamepad_midi_bridge.trigger_response_time import TriggerResponseConfig
        cfg = TriggerResponseConfig(release_threshold=1.5)
        assert cfg.release_threshold == 1.0

    def test_config_no_clamp_release_threshold_in_range(self):
        from gamepad_midi_bridge.trigger_response_time import TriggerResponseConfig
        cfg = TriggerResponseConfig(release_threshold=0.15)
        assert cfg.release_threshold == 0.15

    def test_config_clamp_peak_min_below_zero(self):
        from gamepad_midi_bridge.trigger_response_time import TriggerResponseConfig
        cfg = TriggerResponseConfig(peak_min=-0.5)
        assert cfg.peak_min == 0.0

    def test_config_clamp_peak_min_above_one(self):
        from gamepad_midi_bridge.trigger_response_time import TriggerResponseConfig
        cfg = TriggerResponseConfig(peak_min=1.2)
        assert cfg.peak_min == 1.0

    def test_config_no_clamp_peak_min_in_range(self):
        from gamepad_midi_bridge.trigger_response_time import TriggerResponseConfig
        cfg = TriggerResponseConfig(peak_min=0.8)
        assert cfg.peak_min == 0.8

    def test_config_clamp_max_pulls_below_10(self):
        from gamepad_midi_bridge.trigger_response_time import TriggerResponseConfig
        cfg = TriggerResponseConfig(max_pulls=5)
        assert cfg.max_pulls == 10

    def test_config_clamp_max_pulls_above_100000(self):
        from gamepad_midi_bridge.trigger_response_time import TriggerResponseConfig
        cfg = TriggerResponseConfig(max_pulls=100001)
        assert cfg.max_pulls == 100000

    def test_config_no_clamp_max_pulls_in_range(self):
        from gamepad_midi_bridge.trigger_response_time import TriggerResponseConfig
        cfg = TriggerResponseConfig(max_pulls=5000)
        assert cfg.max_pulls == 5000

    def test_config_to_dict(self):
        from gamepad_midi_bridge.trigger_response_time import TriggerResponseConfig
        cfg = TriggerResponseConfig(
            release_threshold=0.1, peak_min=0.75, max_pulls=2000
        )
        d = cfg.to_dict()
        assert d["release_threshold"] == 0.1
        assert d["peak_min"] == 0.75
        assert d["max_pulls"] == 2000

    def test_config_from_dict(self):
        from gamepad_midi_bridge.trigger_response_time import TriggerResponseConfig
        d = {
            "release_threshold": 0.08,
            "peak_min": 0.65,
            "max_pulls": 500,
        }
        cfg = TriggerResponseConfig.from_dict(d)
        assert cfg.release_threshold == 0.08
        assert cfg.peak_min == 0.65
        assert cfg.max_pulls == 500

    def test_config_round_trip(self):
        from gamepad_midi_bridge.trigger_response_time import TriggerResponseConfig
        original = TriggerResponseConfig(
            release_threshold=0.12, peak_min=0.6, max_pulls=3000
        )
        d = original.to_dict()
        restored = TriggerResponseConfig.from_dict(d)
        assert restored.release_threshold == original.release_threshold
        assert restored.peak_min == original.peak_min
        assert restored.max_pulls == original.max_pulls


class TestTriggerResponseAnalyzer:
    """TriggerResponseAnalyzer — record pulls, compute response times."""

    def test_empty_pull_count_zero(self):
        from gamepad_midi_bridge.trigger_response_time import (
            TriggerResponseAnalyzer,
            TriggerResponseConfig,
        )
        cfg = TriggerResponseConfig()
        analyzer = TriggerResponseAnalyzer(cfg)
        assert analyzer.pull_count() == 0

    def test_empty_mean_duration_none(self):
        from gamepad_midi_bridge.trigger_response_time import (
            TriggerResponseAnalyzer,
            TriggerResponseConfig,
        )
        cfg = TriggerResponseConfig()
        analyzer = TriggerResponseAnalyzer(cfg)
        assert analyzer.mean_duration_ms() is None

    def test_record_starts_tracking_on_first_pressure(self):
        from gamepad_midi_bridge.trigger_response_time import (
            TriggerResponseAnalyzer,
            TriggerResponseConfig,
        )
        cfg = TriggerResponseConfig()
        analyzer = TriggerResponseAnalyzer(cfg)
        # First sample above threshold — should start tracking, return None
        result = analyzer.record("L2", 0.1, 0.0)
        assert result is None
        assert analyzer.pull_count() == 0  # No complete pull yet

    def test_record_updates_peak_as_pressure_increases(self):
        from gamepad_midi_bridge.trigger_response_time import (
            TriggerResponseAnalyzer,
            TriggerResponseConfig,
        )
        cfg = TriggerResponseConfig()
        analyzer = TriggerResponseAnalyzer(cfg)
        analyzer.record("L2", 0.1, 0.0)
        analyzer.record("L2", 0.5, 0.05)
        analyzer.record("L2", 0.95, 0.10)  # Peak at this point
        result = analyzer.record("L2", 0.0, 0.15)  # Release
        assert result is not None
        assert result.peak_pressure == 0.95
        assert result.peak_at_s == 0.10

    def test_record_returns_pull_event_on_release_if_peak_meets_threshold(self):
        from gamepad_midi_bridge.trigger_response_time import (
            TriggerResponseAnalyzer,
            TriggerResponseConfig,
        )
        cfg = TriggerResponseConfig(peak_min=0.7)
        analyzer = TriggerResponseAnalyzer(cfg)
        analyzer.record("L2", 0.1, 0.0)
        analyzer.record("L2", 0.8, 0.1)
        result = analyzer.record("L2", 0.0, 0.15)
        assert result is not None
        assert result.trigger == "L2"
        assert result.peak_pressure == 0.8

    def test_record_returns_none_on_release_if_peak_too_low(self):
        from gamepad_midi_bridge.trigger_response_time import (
            TriggerResponseAnalyzer,
            TriggerResponseConfig,
        )
        cfg = TriggerResponseConfig(peak_min=0.7)
        analyzer = TriggerResponseAnalyzer(cfg)
        analyzer.record("L2", 0.1, 0.0)
        analyzer.record("L2", 0.5, 0.1)  # Below 0.7 threshold
        result = analyzer.record("L2", 0.0, 0.15)
        assert result is None
        assert analyzer.pull_count() == 0  # Not recorded

    def test_duration_ms_computed_correctly(self):
        from gamepad_midi_bridge.trigger_response_time import (
            TriggerResponseAnalyzer,
            TriggerResponseConfig,
        )
        cfg = TriggerResponseConfig()
        analyzer = TriggerResponseAnalyzer(cfg)
        analyzer.record("L2", 0.1, 0.0)
        analyzer.record("L2", 0.6, 0.05)
        analyzer.record("L2", 0.95, 0.1)
        event = analyzer.record("L2", 0.0, 0.15)
        # Duration from 0.0 to 0.1 = 0.1 seconds = 100 milliseconds
        assert event.duration_ms == 100.0

    def test_mean_duration_ms_over_multiple_pulls(self):
        from gamepad_midi_bridge.trigger_response_time import (
            TriggerResponseAnalyzer,
            TriggerResponseConfig,
        )
        cfg = TriggerResponseConfig()
        analyzer = TriggerResponseAnalyzer(cfg)

        # First pull: 100 ms (0.0 -> 0.1)
        analyzer.record("L2", 0.1, 0.0)
        analyzer.record("L2", 0.95, 0.1)
        analyzer.record("L2", 0.0, 0.15)

        # Second pull: 200 ms (0.5 -> 0.7)
        analyzer.record("L2", 0.1, 0.5)
        analyzer.record("L2", 0.95, 0.7)
        analyzer.record("L2", 0.0, 0.75)

        mean = analyzer.mean_duration_ms()
        assert mean is not None
        assert round(mean, 1) == 150.0

    def test_filter_by_trigger_l2(self):
        from gamepad_midi_bridge.trigger_response_time import (
            TriggerResponseAnalyzer,
            TriggerResponseConfig,
        )
        cfg = TriggerResponseConfig()
        analyzer = TriggerResponseAnalyzer(cfg)

        # L2 pull: 100 ms
        analyzer.record("L2", 0.1, 0.0)
        analyzer.record("L2", 0.95, 0.1)
        analyzer.record("L2", 0.0, 0.15)

        # R2 pull: 150 ms
        analyzer.record("R2", 0.1, 0.2)
        analyzer.record("R2", 0.95, 0.35)
        analyzer.record("R2", 0.0, 0.4)

        l2_mean = analyzer.mean_duration_ms("L2")
        assert l2_mean == 100.0
        assert analyzer.pull_count("L2") == 1

        r2_mean = analyzer.mean_duration_ms("R2")
        assert round(r2_mean, 1) == 150.0
        assert analyzer.pull_count("R2") == 1

    def test_pull_count_tracks(self):
        from gamepad_midi_bridge.trigger_response_time import (
            TriggerResponseAnalyzer,
            TriggerResponseConfig,
        )
        cfg = TriggerResponseConfig()
        analyzer = TriggerResponseAnalyzer(cfg)
        assert analyzer.pull_count() == 0

        analyzer.record("L2", 0.1, 0.0)
        analyzer.record("L2", 0.95, 0.1)
        analyzer.record("L2", 0.0, 0.15)
        assert analyzer.pull_count() == 1

        analyzer.record("L2", 0.1, 0.2)
        analyzer.record("L2", 0.95, 0.3)
        analyzer.record("L2", 0.0, 0.4)
        assert analyzer.pull_count() == 2

    def test_max_pulls_fifo_eviction(self):
        from gamepad_midi_bridge.trigger_response_time import (
            TriggerResponseAnalyzer,
            TriggerResponseConfig,
        )
        cfg = TriggerResponseConfig(max_pulls=15)
        analyzer = TriggerResponseAnalyzer(cfg)

        # Record 20 pulls to trigger eviction
        for i in range(20):
            analyzer.record("L2", 0.1, i * 0.2)
            analyzer.record("L2", 0.95, i * 0.2 + 0.1)
            analyzer.record("L2", 0.0, i * 0.2 + 0.15)

        # Should only have 15 most recent pulls (FIFO eviction)
        assert analyzer.pull_count() == 15

    def test_unknown_trigger_name_ignored(self):
        from gamepad_midi_bridge.trigger_response_time import (
            TriggerResponseAnalyzer,
            TriggerResponseConfig,
        )
        cfg = TriggerResponseConfig()
        analyzer = TriggerResponseAnalyzer(cfg)
        result = analyzer.record("UNKNOWN", 0.5, 0.0)
        assert result is None
        assert analyzer.pull_count() == 0

    def test_summary_returns_expected_keys(self):
        from gamepad_midi_bridge.trigger_response_time import (
            TriggerResponseAnalyzer,
            TriggerResponseConfig,
        )
        cfg = TriggerResponseConfig()
        analyzer = TriggerResponseAnalyzer(cfg)
        summary = analyzer.summary()
        assert "L2_mean_ms" in summary
        assert "L2_count" in summary
        assert "R2_mean_ms" in summary
        assert "R2_count" in summary
        assert "fastest_ms" in summary
        assert "slowest_ms" in summary

    def test_summary_empty(self):
        from gamepad_midi_bridge.trigger_response_time import (
            TriggerResponseAnalyzer,
            TriggerResponseConfig,
        )
        cfg = TriggerResponseConfig()
        analyzer = TriggerResponseAnalyzer(cfg)
        summary = analyzer.summary()
        assert summary["L2_mean_ms"] is None
        assert summary["L2_count"] == 0
        assert summary["R2_mean_ms"] is None
        assert summary["R2_count"] == 0
        assert summary["fastest_ms"] is None
        assert summary["slowest_ms"] is None

    def test_summary_with_data(self):
        from gamepad_midi_bridge.trigger_response_time import (
            TriggerResponseAnalyzer,
            TriggerResponseConfig,
        )
        cfg = TriggerResponseConfig()
        analyzer = TriggerResponseAnalyzer(cfg)

        # L2: 100 ms
        analyzer.record("L2", 0.1, 0.0)
        analyzer.record("L2", 0.95, 0.1)
        analyzer.record("L2", 0.0, 0.15)

        # R2: 150 ms
        analyzer.record("R2", 0.1, 0.2)
        analyzer.record("R2", 0.95, 0.35)
        analyzer.record("R2", 0.0, 0.4)

        summary = analyzer.summary()
        assert summary["L2_mean_ms"] == 100.0
        assert summary["L2_count"] == 1
        assert round(summary["R2_mean_ms"], 1) == 150.0
        assert summary["R2_count"] == 1
        assert summary["fastest_ms"] == 100.0
        assert round(summary["slowest_ms"], 1) == 150.0

    def test_clear_empties_pulls(self):
        from gamepad_midi_bridge.trigger_response_time import (
            TriggerResponseAnalyzer,
            TriggerResponseConfig,
        )
        cfg = TriggerResponseConfig()
        analyzer = TriggerResponseAnalyzer(cfg)

        analyzer.record("L2", 0.1, 0.0)
        analyzer.record("L2", 0.95, 0.1)
        analyzer.record("L2", 0.0, 0.15)
        assert analyzer.pull_count() == 1

        analyzer.clear()
        assert analyzer.pull_count() == 0
        assert analyzer.mean_duration_ms() is None

    def test_min_max_duration_ms(self):
        from gamepad_midi_bridge.trigger_response_time import (
            TriggerResponseAnalyzer,
            TriggerResponseConfig,
        )
        cfg = TriggerResponseConfig()
        analyzer = TriggerResponseAnalyzer(cfg)

        # Pull 1: 50 ms
        analyzer.record("L2", 0.1, 0.0)
        analyzer.record("L2", 0.95, 0.05)
        analyzer.record("L2", 0.0, 0.1)

        # Pull 2: 200 ms
        analyzer.record("L2", 0.1, 0.2)
        analyzer.record("L2", 0.95, 0.4)
        analyzer.record("L2", 0.0, 0.5)

        # Pull 3: 100 ms
        analyzer.record("L2", 0.1, 0.6)
        analyzer.record("L2", 0.95, 0.7)
        analyzer.record("L2", 0.0, 0.8)

        assert analyzer.min_duration_ms() == 50.0
        assert analyzer.max_duration_ms() == 200.0

    def test_pressure_clamped_to_zero_one(self):
        from gamepad_midi_bridge.trigger_response_time import (
            TriggerResponseAnalyzer,
            TriggerResponseConfig,
        )
        cfg = TriggerResponseConfig()
        analyzer = TriggerResponseAnalyzer(cfg)

        # Test clamping of pressure values
        analyzer.record("L2", -0.5, 0.0)   # Clamps to 0.0, below release_threshold
        analyzer.record("L2", 0.2, 0.05)   # Above release_threshold, starts tracking
        analyzer.record("L2", 1.5, 0.15)   # Clamps to 1.0, updates peak
        result = analyzer.record("L2", 0.0, 0.2)  # Release

        assert result is not None
        assert result.peak_pressure == 1.0
        # From 0.05 (start) to 0.15 (peak) = 0.1 seconds = 100 ms
        assert round(result.duration_ms, 1) == 100.0
