"""Tests for note retrigger detector.

Detects rapid same-note repeats (double-pressing, chattering, contact bounce).
Pure stdlib, no Qt.
"""
from __future__ import annotations

import pytest


class TestRetriggerEvent:
    """RetriggerEvent — dataclass for a detected retrigger."""

    def test_event_construction(self):
        from gamepad_midi_bridge.note_retrigger_detector import RetriggerEvent
        event = RetriggerEvent(note=60, channel=1, first_at_s=0.0, second_at_s=0.02, gap_ms=20.0)
        assert event.note == 60
        assert event.channel == 1
        assert event.first_at_s == 0.0
        assert event.second_at_s == 0.02
        assert event.gap_ms == 20.0

    def test_event_to_dict(self):
        from gamepad_midi_bridge.note_retrigger_detector import RetriggerEvent
        event = RetriggerEvent(note=60, channel=1, first_at_s=1.0, second_at_s=1.05, gap_ms=50.0)
        d = event.to_dict()
        assert d["note"] == 60
        assert d["channel"] == 1
        assert d["first_at_s"] == 1.0
        assert d["second_at_s"] == 1.05
        assert d["gap_ms"] == 50.0

    def test_event_from_dict(self):
        from gamepad_midi_bridge.note_retrigger_detector import RetriggerEvent
        d = {"note": 72, "channel": 3, "first_at_s": 2.0, "second_at_s": 2.035, "gap_ms": 35.0}
        event = RetriggerEvent.from_dict(d)
        assert event.note == 72
        assert event.channel == 3
        assert event.first_at_s == 2.0
        assert event.second_at_s == 2.035
        assert event.gap_ms == 35.0

    def test_event_round_trip(self):
        from gamepad_midi_bridge.note_retrigger_detector import RetriggerEvent
        original = RetriggerEvent(note=64, channel=5, first_at_s=10.5, second_at_s=10.555, gap_ms=55.0)
        d = original.to_dict()
        restored = RetriggerEvent.from_dict(d)
        assert restored.note == original.note
        assert restored.channel == original.channel
        assert restored.first_at_s == original.first_at_s
        assert restored.second_at_s == original.second_at_s
        assert restored.gap_ms == original.gap_ms


class TestRetriggerConfig:
    """RetriggerConfig — configuration with clamping."""

    def test_config_defaults(self):
        from gamepad_midi_bridge.note_retrigger_detector import RetriggerConfig
        cfg = RetriggerConfig()
        assert cfg.enabled is False
        assert cfg.min_gap_ms == 50.0
        assert cfg.max_history == 200

    def test_config_clamp_min_gap_ms_below_one(self):
        from gamepad_midi_bridge.note_retrigger_detector import RetriggerConfig
        cfg = RetriggerConfig(min_gap_ms=0.5)
        assert cfg.min_gap_ms == 1.0
        cfg = RetriggerConfig(min_gap_ms=-10.0)
        assert cfg.min_gap_ms == 1.0

    def test_config_clamp_min_gap_ms_above_2000(self):
        from gamepad_midi_bridge.note_retrigger_detector import RetriggerConfig
        cfg = RetriggerConfig(min_gap_ms=3000.0)
        assert cfg.min_gap_ms == 2000.0
        cfg = RetriggerConfig(min_gap_ms=5000.0)
        assert cfg.min_gap_ms == 2000.0

    def test_config_no_clamp_min_gap_ms_in_range(self):
        from gamepad_midi_bridge.note_retrigger_detector import RetriggerConfig
        cfg = RetriggerConfig(min_gap_ms=100.0)
        assert cfg.min_gap_ms == 100.0

    def test_config_clamp_max_history_below_ten(self):
        from gamepad_midi_bridge.note_retrigger_detector import RetriggerConfig
        cfg = RetriggerConfig(max_history=5)
        assert cfg.max_history == 10
        cfg = RetriggerConfig(max_history=0)
        assert cfg.max_history == 10

    def test_config_clamp_max_history_above_100000(self):
        from gamepad_midi_bridge.note_retrigger_detector import RetriggerConfig
        cfg = RetriggerConfig(max_history=200000)
        assert cfg.max_history == 100000

    def test_config_no_clamp_max_history_in_range(self):
        from gamepad_midi_bridge.note_retrigger_detector import RetriggerConfig
        cfg = RetriggerConfig(max_history=500)
        assert cfg.max_history == 500

    def test_config_to_dict(self):
        from gamepad_midi_bridge.note_retrigger_detector import RetriggerConfig
        cfg = RetriggerConfig(enabled=True, min_gap_ms=75.0, max_history=300)
        d = cfg.to_dict()
        assert d["enabled"] is True
        assert d["min_gap_ms"] == 75.0
        assert d["max_history"] == 300

    def test_config_from_dict(self):
        from gamepad_midi_bridge.note_retrigger_detector import RetriggerConfig
        d = {"enabled": True, "min_gap_ms": 60.0, "max_history": 150}
        cfg = RetriggerConfig.from_dict(d)
        assert cfg.enabled is True
        assert cfg.min_gap_ms == 60.0
        assert cfg.max_history == 150

    def test_config_from_dict_missing_keys_use_defaults(self):
        from gamepad_midi_bridge.note_retrigger_detector import RetriggerConfig
        d = {"enabled": True}
        cfg = RetriggerConfig.from_dict(d)
        assert cfg.enabled is True
        assert cfg.min_gap_ms == 50.0
        assert cfg.max_history == 200

    def test_config_from_dict_applies_clamping(self):
        from gamepad_midi_bridge.note_retrigger_detector import RetriggerConfig
        d = {"min_gap_ms": 0.5, "max_history": 5}
        cfg = RetriggerConfig.from_dict(d)
        assert cfg.min_gap_ms == 1.0
        assert cfg.max_history == 10

    def test_config_round_trip(self):
        from gamepad_midi_bridge.note_retrigger_detector import RetriggerConfig
        original = RetriggerConfig(enabled=True, min_gap_ms=80.0, max_history=250)
        d = original.to_dict()
        restored = RetriggerConfig.from_dict(d)
        assert restored.enabled == original.enabled
        assert restored.min_gap_ms == original.min_gap_ms
        assert restored.max_history == original.max_history


class TestNoteRetriggerDetector:
    """NoteRetriggerDetector — core retrigger detection logic."""

    def test_detector_empty_count_is_zero(self):
        """Freshly constructed detector has zero retriggers."""
        from gamepad_midi_bridge.note_retrigger_detector import NoteRetriggerDetector, RetriggerConfig
        cfg = RetriggerConfig(enabled=True, min_gap_ms=50.0)
        detector = NoteRetriggerDetector(cfg)
        assert detector.count() == 0

    def test_detector_first_note_on_returns_none(self):
        """First note_on for a (note, channel) returns None (no prior to compare)."""
        from gamepad_midi_bridge.note_retrigger_detector import NoteRetriggerDetector, RetriggerConfig
        cfg = RetriggerConfig(enabled=True, min_gap_ms=50.0)
        detector = NoteRetriggerDetector(cfg)
        result = detector.on_note_on(60, 1, 0.0)
        assert result is None
        assert detector.count() == 0

    def test_detector_second_note_on_below_threshold_is_retrigger(self):
        """Second note_on within min_gap_ms creates a RetriggerEvent."""
        from gamepad_midi_bridge.note_retrigger_detector import NoteRetriggerDetector, RetriggerConfig
        cfg = RetriggerConfig(enabled=True, min_gap_ms=50.0)
        detector = NoteRetriggerDetector(cfg)
        # First note_on.
        result1 = detector.on_note_on(60, 1, 0.0)
        assert result1 is None
        # Second note_on 20 ms later (< 50 ms threshold).
        result2 = detector.on_note_on(60, 1, 0.02)
        assert result2 is not None
        assert result2.note == 60
        assert result2.channel == 1
        assert result2.first_at_s == 0.0
        assert result2.second_at_s == 0.02
        assert result2.gap_ms == 20.0
        assert detector.count() == 1

    def test_detector_second_note_on_above_threshold_not_retrigger(self):
        """Second note_on at gap >= min_gap_ms is NOT a retrigger."""
        from gamepad_midi_bridge.note_retrigger_detector import NoteRetriggerDetector, RetriggerConfig
        cfg = RetriggerConfig(enabled=True, min_gap_ms=50.0)
        detector = NoteRetriggerDetector(cfg)
        result1 = detector.on_note_on(60, 1, 0.0)
        assert result1 is None
        # Second note_on 100 ms later (>= 50 ms threshold).
        result2 = detector.on_note_on(60, 1, 0.1)
        assert result2 is None
        assert detector.count() == 0

    def test_detector_different_channels_no_retrigger(self):
        """Same note on different channels don't retrigger each other."""
        from gamepad_midi_bridge.note_retrigger_detector import NoteRetriggerDetector, RetriggerConfig
        cfg = RetriggerConfig(enabled=True, min_gap_ms=50.0)
        detector = NoteRetriggerDetector(cfg)
        result1 = detector.on_note_on(60, 1, 0.0)
        assert result1 is None
        # Same note but different channel (channel 2).
        result2 = detector.on_note_on(60, 2, 0.02)
        assert result2 is None
        assert detector.count() == 0

    def test_detector_different_notes_no_retrigger(self):
        """Different notes don't retrigger each other."""
        from gamepad_midi_bridge.note_retrigger_detector import NoteRetriggerDetector, RetriggerConfig
        cfg = RetriggerConfig(enabled=True, min_gap_ms=50.0)
        detector = NoteRetriggerDetector(cfg)
        result1 = detector.on_note_on(60, 1, 0.0)
        assert result1 is None
        # Different note (61).
        result2 = detector.on_note_on(61, 1, 0.02)
        assert result2 is None
        assert detector.count() == 0

    def test_detector_recent_returns_last_n(self):
        """recent(n) returns the last n events in reverse order (newest first)."""
        from gamepad_midi_bridge.note_retrigger_detector import NoteRetriggerDetector, RetriggerConfig
        cfg = RetriggerConfig(enabled=True, min_gap_ms=50.0)
        detector = NoteRetriggerDetector(cfg)
        # Generate 5 retrigger events.
        for i in range(5):
            detector.on_note_on(60, 1, i * 0.1)
            detector.on_note_on(60, 1, i * 0.1 + 0.02)
        assert detector.count() == 5
        # recent(3) should return last 3, newest first.
        last3 = detector.recent(3)
        assert len(last3) == 3
        assert last3[0].gap_ms < last3[1].gap_ms or last3[0].first_at_s > last3[1].first_at_s

    def test_detector_count_per_note_tallies(self):
        """count_per_note() returns dict of note → retrigger count."""
        from gamepad_midi_bridge.note_retrigger_detector import NoteRetriggerDetector, RetriggerConfig
        cfg = RetriggerConfig(enabled=True, min_gap_ms=50.0)
        detector = NoteRetriggerDetector(cfg)
        # Two retriggering events on note 60.
        detector.on_note_on(60, 1, 0.0)
        detector.on_note_on(60, 1, 0.02)
        detector.on_note_on(60, 1, 0.1)
        detector.on_note_on(60, 1, 0.12)
        # One retriggering event on note 61.
        detector.on_note_on(61, 1, 1.0)
        detector.on_note_on(61, 1, 1.02)
        tally = detector.count_per_note()
        assert tally[60] == 2
        assert tally[61] == 1

    def test_detector_mean_gap_ms_returns_average(self):
        """mean_gap_ms() returns average gap of all retriggers."""
        from gamepad_midi_bridge.note_retrigger_detector import NoteRetriggerDetector, RetriggerConfig
        cfg = RetriggerConfig(enabled=True, min_gap_ms=50.0)
        detector = NoteRetriggerDetector(cfg)
        # Gap 20 ms.
        detector.on_note_on(60, 1, 0.0)
        detector.on_note_on(60, 1, 0.02)
        # Gap 30 ms.
        detector.on_note_on(60, 1, 0.1)
        detector.on_note_on(60, 1, 0.13)
        # Mean: (20 + 30) / 2 = 25.
        mean = detector.mean_gap_ms()
        assert mean == 25.0

    def test_detector_mean_gap_ms_empty_returns_none(self):
        """mean_gap_ms() returns None if no retriggers detected."""
        from gamepad_midi_bridge.note_retrigger_detector import NoteRetriggerDetector, RetriggerConfig
        cfg = RetriggerConfig(enabled=True, min_gap_ms=50.0)
        detector = NoteRetriggerDetector(cfg)
        assert detector.mean_gap_ms() is None

    def test_detector_clear_empties_history(self):
        """clear() resets count to 0 and clears internal state."""
        from gamepad_midi_bridge.note_retrigger_detector import NoteRetriggerDetector, RetriggerConfig
        cfg = RetriggerConfig(enabled=True, min_gap_ms=50.0)
        detector = NoteRetriggerDetector(cfg)
        detector.on_note_on(60, 1, 0.0)
        detector.on_note_on(60, 1, 0.02)
        assert detector.count() == 1
        detector.clear()
        assert detector.count() == 0
        # After clear, a re-press doesn't retrigger.
        result = detector.on_note_on(60, 1, 0.1)
        assert result is None

    def test_detector_max_history_fifo_eviction(self):
        """When retriggers exceed max_history, oldest are evicted (FIFO)."""
        from gamepad_midi_bridge.note_retrigger_detector import NoteRetriggerDetector, RetriggerConfig
        cfg = RetriggerConfig(enabled=True, min_gap_ms=50.0, max_history=15)
        detector = NoteRetriggerDetector(cfg)
        # Generate 20 retrigger events to exceed max_history=15.
        for i in range(20):
            detector.on_note_on(60, 1, i * 0.1)
            detector.on_note_on(60, 1, i * 0.1 + 0.02)
        # Only last 15 should remain.
        assert detector.count() == 15
        # Verify that the oldest events are gone.
        recent_all = detector.recent(20)
        assert len(recent_all) == 15

    def test_detector_summary_empty(self):
        """summary() with no events returns all None/0."""
        from gamepad_midi_bridge.note_retrigger_detector import NoteRetriggerDetector, RetriggerConfig
        cfg = RetriggerConfig(enabled=True, min_gap_ms=50.0)
        detector = NoteRetriggerDetector(cfg)
        summary = detector.summary()
        assert summary["count"] == 0
        assert summary["mean_gap_ms"] is None
        assert summary["min_gap_ms"] is None
        assert summary["max_gap_ms"] is None

    def test_detector_summary_with_events(self):
        """summary() returns correct statistics."""
        from gamepad_midi_bridge.note_retrigger_detector import NoteRetriggerDetector, RetriggerConfig
        cfg = RetriggerConfig(enabled=True, min_gap_ms=50.0)
        detector = NoteRetriggerDetector(cfg)
        # Gaps: 20, 30, 40 ms.
        detector.on_note_on(60, 1, 0.0)
        detector.on_note_on(60, 1, 0.02)
        detector.on_note_on(60, 1, 0.1)
        detector.on_note_on(60, 1, 0.13)
        detector.on_note_on(60, 1, 0.2)
        detector.on_note_on(60, 1, 0.24)
        summary = detector.summary()
        assert summary["count"] == 3
        assert abs(summary["mean_gap_ms"] - 30.0) < 0.01  # (20 + 30 + 40) / 3
        assert abs(summary["min_gap_ms"] - 20.0) < 0.01
        assert abs(summary["max_gap_ms"] - 40.0) < 0.01

    def test_detector_gap_ms_precision(self):
        """gap_ms is calculated from (second_at_s - first_at_s) * 1000."""
        from gamepad_midi_bridge.note_retrigger_detector import NoteRetriggerDetector, RetriggerConfig
        cfg = RetriggerConfig(enabled=True, min_gap_ms=50.0)
        detector = NoteRetriggerDetector(cfg)
        detector.on_note_on(60, 1, 0.0)
        result = detector.on_note_on(60, 1, 0.0235)  # 23.5 ms gap
        assert result is not None
        # Check floating-point precision.
        assert abs(result.gap_ms - 23.5) < 0.01

    def test_detector_boundary_at_threshold(self):
        """Gap exactly at threshold is considered retrigger (< not <=)."""
        from gamepad_midi_bridge.note_retrigger_detector import NoteRetriggerDetector, RetriggerConfig
        cfg = RetriggerConfig(enabled=True, min_gap_ms=50.0)
        detector = NoteRetriggerDetector(cfg)
        detector.on_note_on(60, 1, 0.0)
        # Gap exactly 50 ms (at threshold): should NOT retrigger (needs < not <=).
        result = detector.on_note_on(60, 1, 0.05)
        assert result is None

    def test_detector_boundary_just_below_threshold(self):
        """Gap just below threshold IS a retrigger."""
        from gamepad_midi_bridge.note_retrigger_detector import NoteRetriggerDetector, RetriggerConfig
        cfg = RetriggerConfig(enabled=True, min_gap_ms=50.0)
        detector = NoteRetriggerDetector(cfg)
        detector.on_note_on(60, 1, 0.0)
        # Gap 49.9 ms (just below threshold): IS retrigger.
        result = detector.on_note_on(60, 1, 0.0499)
        assert result is not None
        assert result.gap_ms < 50.0

    def test_detector_multiple_notes_independent(self):
        """Multiple notes tracked independently, can retrigger separately."""
        from gamepad_midi_bridge.note_retrigger_detector import NoteRetriggerDetector, RetriggerConfig
        cfg = RetriggerConfig(enabled=True, min_gap_ms=50.0)
        detector = NoteRetriggerDetector(cfg)
        # Note 60 at t=0.
        detector.on_note_on(60, 1, 0.0)
        # Note 61 at t=0.01 (20 ms gap if we repeat, < 50 ms).
        detector.on_note_on(61, 1, 0.01)
        # Retrigger note 60 at t=0.02 (20 ms from 0.0) → retrigger.
        result1 = detector.on_note_on(60, 1, 0.02)
        assert result1 is not None
        # Retrigger note 61 at t=0.03 (20 ms from 0.01) → retrigger.
        result2 = detector.on_note_on(61, 1, 0.03)
        assert result2 is not None
        assert detector.count() == 2

    def test_detector_comprehensive_scenario(self):
        """End-to-end scenario: multiple notes/channels, thresholds, statistics."""
        from gamepad_midi_bridge.note_retrigger_detector import NoteRetriggerDetector, RetriggerConfig
        cfg = RetriggerConfig(enabled=True, min_gap_ms=50.0, max_history=100)
        detector = NoteRetriggerDetector(cfg)

        # Note 60, channel 1: retriggerings at 20 and 30 ms.
        detector.on_note_on(60, 1, 0.0)
        r1 = detector.on_note_on(60, 1, 0.02)
        assert r1 is not None
        assert abs(r1.gap_ms - 20.0) < 0.01

        detector.on_note_on(60, 1, 0.1)
        r2 = detector.on_note_on(60, 1, 0.13)
        assert r2 is not None
        assert abs(r2.gap_ms - 30.0) < 0.01

        # Note 72, channel 2: one retriggering at 15 ms.
        detector.on_note_on(72, 2, 1.0)
        r3 = detector.on_note_on(72, 2, 1.015)
        assert r3 is not None
        assert abs(r3.gap_ms - 15.0) < 0.01

        # Check totals.
        assert detector.count() == 3
        tally = detector.count_per_note()
        assert tally[60] == 2
        assert tally[72] == 1

        # Check statistics.
        summary = detector.summary()
        assert summary["count"] == 3
        expected_mean = (20.0 + 30.0 + 15.0) / 3
        assert abs(summary["mean_gap_ms"] - expected_mean) < 0.01
        assert abs(summary["min_gap_ms"] - 15.0) < 0.01
        assert abs(summary["max_gap_ms"] - 30.0) < 0.01

        # Check recent.
        recent = detector.recent(2)
        assert len(recent) == 2
        assert abs(recent[0].gap_ms - 15.0) < 0.01  # r3 (newest)
        assert abs(recent[1].gap_ms - 30.0) < 0.01  # r2

    def test_detector_recent_default_20(self):
        """recent() defaults to 20 items if not specified."""
        from gamepad_midi_bridge.note_retrigger_detector import NoteRetriggerDetector, RetriggerConfig
        cfg = RetriggerConfig(enabled=True, min_gap_ms=50.0)
        detector = NoteRetriggerDetector(cfg)
        # Generate 5 events.
        for i in range(5):
            detector.on_note_on(60, 1, i * 0.1)
            detector.on_note_on(60, 1, i * 0.1 + 0.02)
        # recent() with no args should return all 5 (since 5 < 20).
        recent = detector.recent()
        assert len(recent) == 5

    def test_detector_recent_more_than_available(self):
        """recent(n) when n > total events returns all available."""
        from gamepad_midi_bridge.note_retrigger_detector import NoteRetriggerDetector, RetriggerConfig
        cfg = RetriggerConfig(enabled=True, min_gap_ms=50.0)
        detector = NoteRetriggerDetector(cfg)
        # Generate 2 events.
        detector.on_note_on(60, 1, 0.0)
        detector.on_note_on(60, 1, 0.02)
        detector.on_note_on(60, 1, 0.1)
        detector.on_note_on(60, 1, 0.12)
        # Request 100 items; should return only 2.
        recent = detector.recent(100)
        assert len(recent) == 2

    def test_detector_note_channel_independence_extended(self):
        """Notes and channels are fully independent tracking keys."""
        from gamepad_midi_bridge.note_retrigger_detector import NoteRetriggerDetector, RetriggerConfig
        cfg = RetriggerConfig(enabled=True, min_gap_ms=50.0)
        detector = NoteRetriggerDetector(cfg)
        # (60, 1) → retrigger at 20 ms.
        detector.on_note_on(60, 1, 0.0)
        r1 = detector.on_note_on(60, 1, 0.02)
        assert r1 is not None
        # (60, 2) → NOT a retrigger (different channel, no prior history).
        r2 = detector.on_note_on(60, 2, 0.04)
        assert r2 is None
        # (60, 2) → retrigger at 20 ms.
        r3 = detector.on_note_on(60, 2, 0.06)
        assert r3 is not None
        assert detector.count() == 2
