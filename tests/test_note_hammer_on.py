"""Hammer-on and pull-off detection — guitar-style technique recognition."""
from __future__ import annotations

import pytest

from gamepad_midi_bridge.note_hammer_on import (
    HammerEvent,
    HammerOnConfig,
    HammerOnDetector,
)


class TestHammerEventSerialization:
    """HammerEvent dataclass — serialization and deserialization."""

    def test_hammer_event_to_dict(self):
        """to_dict serializes all fields correctly."""
        event = HammerEvent(
            kind="hammer_on",
            first_note=60,
            second_note=64,
            channel=1,
            time_s=1.5,
        )
        data = event.to_dict()
        assert data == {
            "kind": "hammer_on",
            "first_note": 60,
            "second_note": 64,
            "channel": 1,
            "time_s": 1.5,
        }

    def test_hammer_event_from_dict(self):
        """from_dict deserializes correctly."""
        data = {
            "kind": "pull_off",
            "first_note": 64,
            "second_note": 67,
            "channel": 2,
            "time_s": 2.3,
        }
        event = HammerEvent.from_dict(data)
        assert event.kind == "pull_off"
        assert event.first_note == 64
        assert event.second_note == 67
        assert event.channel == 2
        assert event.time_s == 2.3

    def test_hammer_event_round_trip(self):
        """to_dict and from_dict preserve event exactly."""
        original = HammerEvent(
            kind="hammer_on",
            first_note=60,
            second_note=64,
            channel=0,
            time_s=0.5,
        )
        data = original.to_dict()
        restored = HammerEvent.from_dict(data)
        assert original == restored

    def test_hammer_event_from_dict_defaults(self):
        """from_dict uses defaults for missing keys."""
        event = HammerEvent.from_dict({})
        assert event.kind == "hammer_on"
        assert event.first_note == 0
        assert event.second_note == 0
        assert event.channel == 0
        assert event.time_s == 0.0


class TestHammerOnConfigDefaults:
    """HammerOnConfig dataclass — defaults and clamping."""

    def test_default_config_disabled(self):
        """Default config is disabled."""
        cfg = HammerOnConfig()
        assert cfg.enabled is False
        assert cfg.max_history == 200
        assert cfg.min_interval_semitones == 1
        assert cfg.max_interval_semitones == 12

    def test_max_history_clamped_below_min(self):
        """max_history is clamped to >= 10."""
        cfg = HammerOnConfig(max_history=5)
        assert cfg.max_history == 10

    def test_max_history_clamped_above_max(self):
        """max_history is clamped to <= 100000."""
        cfg = HammerOnConfig(max_history=200000)
        assert cfg.max_history == 100000

    def test_min_interval_semitones_clamped_below_min(self):
        """min_interval_semitones is clamped to >= 1."""
        cfg = HammerOnConfig(min_interval_semitones=0)
        assert cfg.min_interval_semitones == 1

    def test_min_interval_semitones_clamped_above_max(self):
        """min_interval_semitones is clamped to <= 24."""
        cfg = HammerOnConfig(min_interval_semitones=30)
        assert cfg.min_interval_semitones == 24

    def test_max_interval_semitones_clamped_below_min(self):
        """max_interval_semitones is clamped to >= 1."""
        cfg = HammerOnConfig(max_interval_semitones=0)
        assert cfg.max_interval_semitones == 1

    def test_max_interval_semitones_clamped_above_max(self):
        """max_interval_semitones is clamped to <= 36."""
        cfg = HammerOnConfig(max_interval_semitones=40)
        assert cfg.max_interval_semitones == 36


class TestHammerOnConfigSerialization:
    """HammerOnConfig — serialization and deserialization."""

    def test_config_to_dict(self):
        """to_dict serializes all fields."""
        cfg = HammerOnConfig(
            enabled=True,
            max_history=150,
            min_interval_semitones=2,
            max_interval_semitones=10,
        )
        data = cfg.to_dict()
        assert data == {
            "enabled": True,
            "max_history": 150,
            "min_interval_semitones": 2,
            "max_interval_semitones": 10,
        }

    def test_config_from_dict(self):
        """from_dict deserializes correctly."""
        data = {
            "enabled": True,
            "max_history": 100,
            "min_interval_semitones": 3,
            "max_interval_semitones": 8,
        }
        cfg = HammerOnConfig.from_dict(data)
        assert cfg.enabled is True
        assert cfg.max_history == 100
        assert cfg.min_interval_semitones == 3
        assert cfg.max_interval_semitones == 8

    def test_config_round_trip(self):
        """to_dict and from_dict preserve config exactly."""
        original = HammerOnConfig(
            enabled=True,
            max_history=250,
            min_interval_semitones=2,
            max_interval_semitones=15,
        )
        data = original.to_dict()
        restored = HammerOnConfig.from_dict(data)
        assert original == restored

    def test_config_from_dict_clamps(self):
        """from_dict clamps values to valid ranges."""
        data = {
            "max_history": 5,
            "min_interval_semitones": 0,
            "max_interval_semitones": 50,
        }
        cfg = HammerOnConfig.from_dict(data)
        assert cfg.max_history == 10
        assert cfg.min_interval_semitones == 1
        assert cfg.max_interval_semitones == 36


class TestHammerOnDetectorInit:
    """HammerOnDetector — initialization."""

    def test_detector_init_enabled(self):
        """Detector initializes with config."""
        cfg = HammerOnConfig(enabled=True)
        detector = HammerOnDetector(cfg)
        assert detector.cfg.enabled is True
        assert detector.count() == 0

    def test_detector_init_disabled(self):
        """Detector works when disabled."""
        cfg = HammerOnConfig(enabled=False)
        detector = HammerOnDetector(cfg)
        assert detector.cfg.enabled is False


class TestHammerOnDetection:
    """HammerOnDetector.on_note_on — hammer-on detection logic."""

    def test_on_note_on_empty_first_note_returns_none(self):
        """First note on a channel returns None (no hammer-on possible)."""
        cfg = HammerOnConfig(enabled=True)
        detector = HammerOnDetector(cfg)
        event = detector.on_note_on(60, 1, 0.0)
        assert event is None

    def test_on_note_on_second_higher_note_emits_hammer_on(self):
        """Second higher note while first held emits hammer-on."""
        cfg = HammerOnConfig(enabled=True, min_interval_semitones=1, max_interval_semitones=12)
        detector = HammerOnDetector(cfg)
        detector.on_note_on(60, 1, 0.0)
        event = detector.on_note_on(64, 1, 0.1)
        assert event is not None
        assert event.kind == "hammer_on"
        assert event.first_note == 60
        assert event.second_note == 64
        assert event.channel == 1
        assert event.time_s == 0.1

    def test_on_note_on_second_lower_note_no_event(self):
        """Second lower note does not emit hammer-on."""
        cfg = HammerOnConfig(enabled=True)
        detector = HammerOnDetector(cfg)
        detector.on_note_on(64, 1, 0.0)
        event = detector.on_note_on(60, 1, 0.1)
        assert event is None

    def test_on_note_on_interval_below_min(self):
        """Interval below min_interval_semitones does not emit."""
        cfg = HammerOnConfig(enabled=True, min_interval_semitones=5, max_interval_semitones=12)
        detector = HammerOnDetector(cfg)
        detector.on_note_on(60, 1, 0.0)
        event = detector.on_note_on(62, 1, 0.1)  # 2 semitones < 5
        assert event is None

    def test_on_note_on_interval_above_max(self):
        """Interval above max_interval_semitones does not emit."""
        cfg = HammerOnConfig(enabled=True, min_interval_semitones=1, max_interval_semitones=5)
        detector = HammerOnDetector(cfg)
        detector.on_note_on(60, 1, 0.0)
        event = detector.on_note_on(72, 1, 0.1)  # 12 semitones > 5
        assert event is None

    def test_on_note_on_interval_at_min_boundary(self):
        """Interval exactly at min_interval_semitones emits."""
        cfg = HammerOnConfig(enabled=True, min_interval_semitones=4, max_interval_semitones=12)
        detector = HammerOnDetector(cfg)
        detector.on_note_on(60, 1, 0.0)
        event = detector.on_note_on(64, 1, 0.1)  # Exactly 4 semitones
        assert event is not None
        assert event.kind == "hammer_on"

    def test_on_note_on_interval_at_max_boundary(self):
        """Interval exactly at max_interval_semitones emits."""
        cfg = HammerOnConfig(enabled=True, min_interval_semitones=1, max_interval_semitones=12)
        detector = HammerOnDetector(cfg)
        detector.on_note_on(60, 1, 0.0)
        event = detector.on_note_on(72, 1, 0.1)  # Exactly 12 semitones
        assert event is not None
        assert event.kind == "hammer_on"

    def test_on_note_on_disabled_no_event(self):
        """When disabled, no hammer-on event emits."""
        cfg = HammerOnConfig(enabled=False)
        detector = HammerOnDetector(cfg)
        detector.on_note_on(60, 1, 0.0)
        event = detector.on_note_on(64, 1, 0.1)
        assert event is None

    def test_on_note_on_disabled_still_tracks_notes(self):
        """When disabled, notes are still tracked for pull-offs after enable."""
        cfg = HammerOnConfig(enabled=False)
        detector = HammerOnDetector(cfg)
        detector.on_note_on(60, 1, 0.0)
        detector.on_note_on(64, 1, 0.1)
        detector.cfg.enabled = True
        event = detector.on_note_on(67, 1, 0.2)
        assert event is not None
        assert event.kind == "hammer_on"
        assert event.first_note == 64
        assert event.second_note == 67

    def test_on_note_on_different_channels_isolated(self):
        """Different channels don't interact."""
        cfg = HammerOnConfig(enabled=True, min_interval_semitones=5, max_interval_semitones=12)
        detector = HammerOnDetector(cfg)
        detector.on_note_on(60, 1, 0.0)
        detector.on_note_on(64, 2, 0.1)
        event = detector.on_note_on(62, 1, 0.2)  # On channel 1, only 60 is held
        assert event is None  # 62 > 60 but interval is 2 semitones, below min of 5

    def test_on_note_on_multiple_held_uses_first_match(self):
        """With multiple held notes, uses first one that matches interval."""
        cfg = HammerOnConfig(enabled=True, min_interval_semitones=1, max_interval_semitones=12)
        detector = HammerOnDetector(cfg)
        detector.on_note_on(60, 1, 0.0)
        detector.on_note_on(62, 1, 0.05)
        event = detector.on_note_on(65, 1, 0.1)
        assert event is not None
        assert event.first_note == 60
        assert event.second_note == 65


class TestPullOffDetection:
    """HammerOnDetector.on_note_off — pull-off detection logic."""

    def test_on_note_off_no_held_higher_note(self):
        """Note off with no higher note held returns None."""
        cfg = HammerOnConfig(enabled=True)
        detector = HammerOnDetector(cfg)
        detector.on_note_on(60, 1, 0.0)
        event = detector.on_note_off(60, 1, 0.1)
        assert event is None

    def test_on_note_off_with_higher_held_emits_pull_off(self):
        """Note off while higher note held emits pull-off."""
        cfg = HammerOnConfig(enabled=True)
        detector = HammerOnDetector(cfg)
        detector.on_note_on(60, 1, 0.0)
        detector.on_note_on(64, 1, 0.05)
        event = detector.on_note_off(60, 1, 0.1)
        assert event is not None
        assert event.kind == "pull_off"
        assert event.first_note == 60
        assert event.second_note == 64
        assert event.channel == 1
        assert event.time_s == 0.1

    def test_on_note_off_disabled_no_event(self):
        """When disabled, no pull-off event emits."""
        cfg = HammerOnConfig(enabled=False)
        detector = HammerOnDetector(cfg)
        detector.on_note_on(60, 1, 0.0)
        detector.on_note_on(64, 1, 0.05)
        event = detector.on_note_off(60, 1, 0.1)
        assert event is None

    def test_on_note_off_uses_highest_held_note(self):
        """Pull-off uses the highest remaining note."""
        cfg = HammerOnConfig(enabled=True)
        detector = HammerOnDetector(cfg)
        detector.on_note_on(60, 1, 0.0)
        detector.on_note_on(64, 1, 0.05)
        detector.on_note_on(67, 1, 0.1)
        event = detector.on_note_off(60, 1, 0.15)
        assert event is not None
        assert event.second_note == 67
        assert event.first_note == 60

    def test_on_note_off_nonexistent_channel_returns_none(self):
        """Note off on nonexistent channel returns None."""
        cfg = HammerOnConfig(enabled=True)
        detector = HammerOnDetector(cfg)
        event = detector.on_note_off(60, 1, 0.0)
        assert event is None

    def test_on_note_off_different_channels_isolated(self):
        """Note off on different channel doesn't affect other channels."""
        cfg = HammerOnConfig(enabled=True)
        detector = HammerOnDetector(cfg)
        detector.on_note_on(60, 1, 0.0)
        detector.on_note_on(64, 1, 0.05)
        detector.on_note_on(60, 2, 0.1)
        detector.on_note_on(67, 2, 0.15)
        event = detector.on_note_off(60, 2, 0.2)
        assert event is not None
        assert event.channel == 2
        assert event.second_note == 67
        assert 60 in detector._held[1]
        assert 64 in detector._held[1]


class TestEventCounting:
    """HammerOnDetector.count and recent — event tracking."""

    def test_count_empty_detector(self):
        """Empty detector returns 0 count."""
        cfg = HammerOnConfig(enabled=True)
        detector = HammerOnDetector(cfg)
        assert detector.count() == 0

    def test_count_after_hammer_on(self):
        """Count increments after hammer-on."""
        cfg = HammerOnConfig(enabled=True)
        detector = HammerOnDetector(cfg)
        detector.on_note_on(60, 1, 0.0)
        detector.on_note_on(64, 1, 0.1)
        assert detector.count() == 1

    def test_count_after_pull_off(self):
        """Count increments after pull-off."""
        cfg = HammerOnConfig(enabled=True)
        detector = HammerOnDetector(cfg)
        detector.on_note_on(60, 1, 0.0)
        detector.on_note_on(64, 1, 0.05)
        detector.on_note_off(60, 1, 0.1)
        assert detector.count() == 2

    def test_count_kind_filter_hammer_on(self):
        """count with kind='hammer_on' filters correctly."""
        cfg = HammerOnConfig(enabled=True)
        detector = HammerOnDetector(cfg)
        detector.on_note_on(60, 1, 0.0)
        detector.on_note_on(64, 1, 0.05)
        detector.on_note_off(60, 1, 0.1)
        assert detector.count(kind="hammer_on") == 1
        assert detector.count(kind="pull_off") == 1

    def test_count_kind_filter_pull_off(self):
        """count with kind='pull_off' filters correctly."""
        cfg = HammerOnConfig(enabled=True)
        detector = HammerOnDetector(cfg)
        detector.on_note_on(60, 1, 0.0)
        detector.on_note_on(64, 1, 0.05)
        detector.on_note_off(60, 1, 0.1)
        assert detector.count(kind="pull_off") == 1

    def test_recent_default_returns_last_20(self):
        """recent() returns up to 20 most recent events."""
        cfg = HammerOnConfig(enabled=True)
        detector = HammerOnDetector(cfg)
        for i in range(30):
            detector.on_note_on(60, 1, float(i * 0.1))
            detector.on_note_on(64 + (i % 5), 1, float(i * 0.1 + 0.05))
        recent = detector.recent()
        assert len(recent) == 20
        assert recent[-1].time_s == 29 * 0.1 + 0.05

    def test_recent_custom_n(self):
        """recent(n) returns up to n most recent events."""
        cfg = HammerOnConfig(enabled=True)
        detector = HammerOnDetector(cfg)
        for i in range(10):
            detector.on_note_on(60, 1, float(i * 0.1))
            detector.on_note_on(64, 1, float(i * 0.1 + 0.05))
        recent = detector.recent(n=5)
        assert len(recent) == 5

    def test_recent_less_than_n_available(self):
        """recent(n) returns all available if fewer than n exist."""
        cfg = HammerOnConfig(enabled=True)
        detector = HammerOnDetector(cfg)
        detector.on_note_on(60, 1, 0.0)
        detector.on_note_on(64, 1, 0.05)
        recent = detector.recent(n=10)
        assert len(recent) == 1


class TestMaxHistoryEviction:
    """HammerOnDetector — max_history FIFO truncation."""

    def test_max_history_truncation_hammer_on_then_releases(self):
        """Events are truncated to max_history after multiple complete sequences."""
        cfg = HammerOnConfig(enabled=True, max_history=12)
        detector = HammerOnDetector(cfg)
        for i in range(10):
            detector.on_note_on(60, 1, float(i * 0.1))
            detector.on_note_on(64, 1, float(i * 0.1 + 0.05))
            detector.on_note_off(60, 1, float(i * 0.1 + 0.1))
        assert detector.count() == 12

    def test_max_history_respects_limit(self):
        """Total event count never exceeds max_history."""
        cfg = HammerOnConfig(enabled=True, max_history=15)
        detector = HammerOnDetector(cfg)
        for i in range(20):
            detector.on_note_on(60, 1, float(i * 0.1))
            detector.on_note_on(65, 1, float(i * 0.1 + 0.05))
        assert detector.count() <= 15

    def test_most_recent_events_retained(self):
        """Most recent events are kept after truncation."""
        cfg = HammerOnConfig(enabled=True, max_history=50)
        detector = HammerOnDetector(cfg)
        for i in range(10):
            detector.on_note_on(60, 1, float(i * 0.1))
            detector.on_note_on(64, 1, float(i * 0.1 + 0.05))
        events = detector.recent(n=10)
        # Last event should be from the last hammer-on
        assert events[-1].time_s == 9 * 0.1 + 0.05


class TestDetectorClear:
    """HammerOnDetector.clear — reset state."""

    def test_clear_removes_all_events(self):
        """clear() removes all events."""
        cfg = HammerOnConfig(enabled=True)
        detector = HammerOnDetector(cfg)
        detector.on_note_on(60, 1, 0.0)
        detector.on_note_on(64, 1, 0.05)
        detector.clear()
        assert detector.count() == 0

    def test_clear_removes_held_notes(self):
        """clear() removes all held notes."""
        cfg = HammerOnConfig(enabled=True)
        detector = HammerOnDetector(cfg)
        detector.on_note_on(60, 1, 0.0)
        detector.on_note_on(64, 1, 0.05)
        detector.clear()
        event = detector.on_note_on(60, 1, 0.1)
        assert event is None

    def test_clear_allows_fresh_detection(self):
        """After clear, detector works fresh again."""
        cfg = HammerOnConfig(enabled=True)
        detector = HammerOnDetector(cfg)
        detector.on_note_on(60, 1, 0.0)
        detector.on_note_on(64, 1, 0.05)
        detector.clear()
        detector.on_note_on(67, 1, 0.1)
        event = detector.on_note_on(72, 1, 0.15)
        assert event is not None
        assert event.kind == "hammer_on"
        assert event.first_note == 67
        assert event.second_note == 72


class TestIntegration:
    """Integration tests spanning multiple operations."""

    def test_example_guitar_lick_hammer_pull_sequence(self):
        """Example: fret A, hammer-on to B, release A while B held."""
        cfg = HammerOnConfig(enabled=True, min_interval_semitones=1, max_interval_semitones=12)
        detector = HammerOnDetector(cfg)
        detector.on_note_on(60, 1, 0.0)  # Fret low note A
        event1 = detector.on_note_on(64, 1, 0.05)  # Hammer-on to B
        assert event1 is not None
        assert event1.kind == "hammer_on"
        assert event1.first_note == 60
        assert event1.second_note == 64
        event2 = detector.on_note_off(60, 1, 0.1)  # Release A while B held
        assert event2 is not None
        assert event2.kind == "pull_off"
        assert event2.first_note == 60
        assert event2.second_note == 64

    def test_example_chord_with_hammer_ons(self):
        """Example: play chord, hammer onto each note."""
        cfg = HammerOnConfig(enabled=True)
        detector = HammerOnDetector(cfg)
        detector.on_note_on(60, 1, 0.0)
        e1 = detector.on_note_on(64, 1, 0.05)
        assert e1.kind == "hammer_on"
        e2 = detector.on_note_on(67, 1, 0.1)
        assert e2.kind == "hammer_on"
        assert detector.count() == 2

    def test_example_multiple_channels_isolation(self):
        """Example: hammer-ons on separate channels don't interfere."""
        cfg = HammerOnConfig(enabled=True)
        detector = HammerOnDetector(cfg)
        detector.on_note_on(64, 1, 0.0)
        e1 = detector.on_note_on(66, 1, 0.05)
        assert e1.kind == "hammer_on"
        detector.on_note_on(60, 2, 0.1)
        e2 = detector.on_note_on(62, 2, 0.15)
        assert e2.kind == "hammer_on"
        assert e2.channel == 2
        assert detector.count() == 2

    def test_example_round_trip_config_and_event(self):
        """Example: save and restore detector state."""
        cfg = HammerOnConfig(
            enabled=True,
            max_history=100,
            min_interval_semitones=2,
            max_interval_semitones=8,
        )
        detector = HammerOnDetector(cfg)
        detector.on_note_on(60, 1, 0.0)
        detector.on_note_on(65, 1, 0.05)
        cfg_data = detector.cfg.to_dict()
        events_data = [e.to_dict() for e in detector.recent(n=1)]
        assert len(events_data) == 1
        assert events_data[0]["kind"] == "hammer_on"
        restored_cfg = HammerOnConfig.from_dict(cfg_data)
        restored_event = HammerEvent.from_dict(events_data[0])
        assert restored_cfg == cfg
        assert restored_event.second_note == 65
