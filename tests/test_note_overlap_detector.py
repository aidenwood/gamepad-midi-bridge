"""Note overlap detector — collision detection, history, and stats."""
from __future__ import annotations

import pytest

from gamepad_midi_bridge.note_overlap_detector import (
    NoteOverlapConfig,
    NoteOverlapDetector,
    OverlapEvent,
)


class TestNoteOverlapConfigDefaults:
    """NoteOverlapConfig dataclass — defaults and clamping."""

    def test_defaults(self):
        """Default config is disabled with standard max_overlaps."""
        cfg = NoteOverlapConfig()
        assert cfg.enabled is False
        assert cfg.max_overlaps == 100

    def test_enabled_flag(self):
        """Enabled flag can be set."""
        cfg = NoteOverlapConfig(enabled=True)
        assert cfg.enabled is True

    def test_max_overlaps_clamped_lower_bound(self):
        """max_overlaps clamped to 10 (lower bound)."""
        cfg = NoteOverlapConfig(max_overlaps=5)
        assert cfg.max_overlaps == 10

    def test_max_overlaps_clamped_upper_bound(self):
        """max_overlaps clamped to 10000 (upper bound)."""
        cfg = NoteOverlapConfig(max_overlaps=50000)
        assert cfg.max_overlaps == 10000

    def test_max_overlaps_valid_range(self):
        """Valid max_overlaps stay as-is."""
        cfg = NoteOverlapConfig(max_overlaps=250)
        assert cfg.max_overlaps == 250


class TestNoteOverlapConfigSerialization:
    """NoteOverlapConfig round-trip serialization."""

    def test_to_dict_round_trip(self):
        """to_dict and from_dict preserve config."""
        cfg = NoteOverlapConfig(enabled=True, max_overlaps=150)
        data = cfg.to_dict()
        cfg2 = NoteOverlapConfig.from_dict(data)
        assert cfg2.enabled == cfg.enabled
        assert cfg2.max_overlaps == cfg.max_overlaps

    def test_from_dict_clamps_max_overlaps(self):
        """from_dict clamps max_overlaps during deserialization."""
        data = {"enabled": True, "max_overlaps": 5}
        cfg = NoteOverlapConfig.from_dict(data)
        assert cfg.max_overlaps == 10

        data2 = {"enabled": True, "max_overlaps": 20000}
        cfg2 = NoteOverlapConfig.from_dict(data2)
        assert cfg2.max_overlaps == 10000

    def test_from_dict_missing_fields_defaults(self):
        """from_dict with missing fields uses defaults."""
        cfg = NoteOverlapConfig.from_dict({})
        assert cfg.enabled is False
        assert cfg.max_overlaps == 100


class TestOverlapEventSerialization:
    """OverlapEvent round-trip serialization."""

    def test_to_dict_round_trip(self):
        """to_dict and from_dict preserve event."""
        event = OverlapEvent(
            note=60,
            channel=1,
            first_press_at_s=0.5,
            second_press_at_s=0.6,
        )
        data = event.to_dict()
        event2 = OverlapEvent.from_dict(data)
        assert event2 == event

    def test_from_dict_with_floats(self):
        """from_dict converts timestamps to floats."""
        data = {
            "note": "60",
            "channel": "1",
            "first_press_at_s": "0.5",
            "second_press_at_s": "0.6",
        }
        event = OverlapEvent.from_dict(data)
        assert event.note == 60
        assert event.channel == 1
        assert event.first_press_at_s == 0.5
        assert event.second_press_at_s == 0.6


class TestNoteOverlapDetectorDisabled:
    """Detector when disabled."""

    def test_disabled_returns_none(self):
        """Disabled detector always returns None, no recording."""
        cfg = NoteOverlapConfig(enabled=False)
        detector = NoteOverlapDetector(cfg)

        result = detector.on_note_on(60, 1, 0.0)
        assert result is None
        assert detector.count() == 0

    def test_disabled_no_state(self):
        """Disabled detector doesn't track state."""
        cfg = NoteOverlapConfig(enabled=False)
        detector = NoteOverlapDetector(cfg)

        detector.on_note_on(60, 1, 0.0)
        detector.on_note_on(60, 1, 0.1)
        assert detector.count() == 0
        assert detector.currently_overlapping() == []


class TestNoteOverlapDetectorBasic:
    """Basic overlap detection scenarios."""

    def test_empty_detector_count_is_zero(self):
        """Empty detector returns 0 overlaps."""
        cfg = NoteOverlapConfig(enabled=True)
        detector = NoteOverlapDetector(cfg)
        assert detector.count() == 0

    def test_single_note_on_no_overlap(self):
        """First note_on with no prior press returns None."""
        cfg = NoteOverlapConfig(enabled=True)
        detector = NoteOverlapDetector(cfg)

        result = detector.on_note_on(60, 1, 0.0)
        assert result is None
        assert detector.count() == 0

    def test_same_note_twice_is_overlap(self):
        """Pressing same (note, channel) twice detects overlap."""
        cfg = NoteOverlapConfig(enabled=True)
        detector = NoteOverlapDetector(cfg)

        detector.on_note_on(60, 1, 0.0)
        result = detector.on_note_on(60, 1, 0.1)

        assert result is not None
        assert result.note == 60
        assert result.channel == 1
        assert result.first_press_at_s == 0.0
        assert result.second_press_at_s == 0.1
        assert detector.count() == 1

    def test_different_channels_no_overlap(self):
        """Same note, different channels does not overlap."""
        cfg = NoteOverlapConfig(enabled=True)
        detector = NoteOverlapDetector(cfg)

        detector.on_note_on(60, 1, 0.0)
        result = detector.on_note_on(60, 2, 0.1)

        assert result is None
        assert detector.count() == 0

    def test_different_notes_no_overlap(self):
        """Different notes on same channel do not overlap."""
        cfg = NoteOverlapConfig(enabled=True)
        detector = NoteOverlapDetector(cfg)

        detector.on_note_on(60, 1, 0.0)
        result = detector.on_note_on(64, 1, 0.1)

        assert result is None
        assert detector.count() == 0


class TestNoteOverlapDetectorNoteOff:
    """Note-off behavior and hold tracking."""

    def test_note_off_clears_hold(self):
        """on_note_off removes the note from open holds."""
        cfg = NoteOverlapConfig(enabled=True)
        detector = NoteOverlapDetector(cfg)

        detector.on_note_on(60, 1, 0.0)
        assert (60, 1) in detector.currently_overlapping()

        detector.on_note_off(60, 1)
        assert (60, 1) not in detector.currently_overlapping()

    def test_note_off_then_on_no_overlap(self):
        """Releasing and re-pressing the same note is not an overlap."""
        cfg = NoteOverlapConfig(enabled=True)
        detector = NoteOverlapDetector(cfg)

        detector.on_note_on(60, 1, 0.0)
        detector.on_note_off(60, 1)
        result = detector.on_note_on(60, 1, 0.2)

        assert result is None
        assert detector.count() == 0

    def test_note_off_nonexistent_key_safe(self):
        """on_note_off on non-existent key is safe."""
        cfg = NoteOverlapConfig(enabled=True)
        detector = NoteOverlapDetector(cfg)

        # Should not raise
        detector.on_note_off(60, 1)
        assert detector.count() == 0


class TestNoteOverlapDetectorRecent:
    """Recent event retrieval."""

    def test_recent_default_20(self):
        """recent() defaults to last 20 events."""
        cfg = NoteOverlapConfig(enabled=True)
        detector = NoteOverlapDetector(cfg)

        for i in range(30):
            detector.on_note_on(60 + (i % 5), 1, 0.0)
            detector.on_note_on(60 + (i % 5), 1, 0.1)
            detector.on_note_off(60 + (i % 5), 1)

        recent = detector.recent()
        assert len(recent) == 20

    def test_recent_n_parameter(self):
        """recent(n) returns last n events."""
        cfg = NoteOverlapConfig(enabled=True)
        detector = NoteOverlapDetector(cfg)

        for i in range(10):
            detector.on_note_on(60, 1, 0.0)
            detector.on_note_on(60, 1, 0.1)
            detector.on_note_off(60, 1)

        recent = detector.recent(5)
        assert len(recent) == 5

    def test_recent_empty(self):
        """recent() on empty detector returns empty list."""
        cfg = NoteOverlapConfig(enabled=True)
        detector = NoteOverlapDetector(cfg)

        recent = detector.recent()
        assert recent == []

    def test_recent_preserves_order(self):
        """recent() returns events in chronological order."""
        cfg = NoteOverlapConfig(enabled=True)
        detector = NoteOverlapDetector(cfg)

        # Each new press on held note creates overlap, so 4 presses = 3 overlaps
        detector.on_note_on(60, 1, 0.0)  # No overlap
        detector.on_note_on(60, 1, 0.1)  # Overlap 1
        detector.on_note_on(60, 1, 0.2)  # Overlap 2
        detector.on_note_on(60, 1, 0.3)  # Overlap 3

        recent = detector.recent()
        assert len(recent) == 3
        assert recent[0].first_press_at_s == 0.0
        assert recent[1].first_press_at_s == 0.1
        assert recent[2].first_press_at_s == 0.2


class TestNoteOverlapDetectorCountPerNote:
    """Per-note overlap statistics."""

    def test_count_per_note_empty(self):
        """count_per_note on empty detector returns empty dict."""
        cfg = NoteOverlapConfig(enabled=True)
        detector = NoteOverlapDetector(cfg)
        assert detector.count_per_note() == {}

    def test_count_per_note_single_note(self):
        """count_per_note tallies overlaps per note."""
        cfg = NoteOverlapConfig(enabled=True)
        detector = NoteOverlapDetector(cfg)

        # 3 overlaps on note 60: press, overlap, release, press, overlap, release, press, overlap
        detector.on_note_on(60, 1, 0.0)   # No overlap
        detector.on_note_on(60, 1, 0.1)   # Overlap 1
        detector.on_note_off(60, 1)

        detector.on_note_on(60, 1, 0.2)   # No overlap (released)
        detector.on_note_on(60, 1, 0.3)   # Overlap 2
        detector.on_note_off(60, 1)

        detector.on_note_on(60, 1, 0.4)   # No overlap (released)
        detector.on_note_on(60, 1, 0.5)   # Overlap 3

        tally = detector.count_per_note()
        assert tally[60] == 3

    def test_count_per_note_multiple_notes(self):
        """count_per_note tallies across different notes."""
        cfg = NoteOverlapConfig(enabled=True)
        detector = NoteOverlapDetector(cfg)

        # 2 overlaps on note 60
        detector.on_note_on(60, 1, 0.0)
        detector.on_note_on(60, 1, 0.1)
        detector.on_note_off(60, 1)

        detector.on_note_on(60, 1, 0.2)
        detector.on_note_on(60, 1, 0.3)
        detector.on_note_off(60, 1)

        # 1 overlap on note 64
        detector.on_note_on(64, 1, 0.4)
        detector.on_note_on(64, 1, 0.5)

        tally = detector.count_per_note()
        assert tally[60] == 2
        assert tally[64] == 1


class TestNoteOverlapDetectorClear:
    """Clear functionality."""

    def test_clear_empties_history(self):
        """clear() empties overlap history."""
        cfg = NoteOverlapConfig(enabled=True)
        detector = NoteOverlapDetector(cfg)

        detector.on_note_on(60, 1, 0.0)
        detector.on_note_on(60, 1, 0.1)

        assert detector.count() == 1

        detector.clear()
        assert detector.count() == 0
        assert detector.recent() == []

    def test_clear_empties_open_holds(self):
        """clear() empties currently open holds."""
        cfg = NoteOverlapConfig(enabled=True)
        detector = NoteOverlapDetector(cfg)

        detector.on_note_on(60, 1, 0.0)
        detector.on_note_on(64, 2, 0.0)

        assert len(detector.currently_overlapping()) == 2

        detector.clear()
        assert detector.currently_overlapping() == []


class TestNoteOverlapDetectorCurrentlyOverlapping:
    """Track of currently-held notes."""

    def test_currently_overlapping_empty(self):
        """currently_overlapping on empty detector returns empty list."""
        cfg = NoteOverlapConfig(enabled=True)
        detector = NoteOverlapDetector(cfg)
        assert detector.currently_overlapping() == []

    def test_currently_overlapping_tracks_holds(self):
        """currently_overlapping lists all held (note, channel) pairs."""
        cfg = NoteOverlapConfig(enabled=True)
        detector = NoteOverlapDetector(cfg)

        detector.on_note_on(60, 1, 0.0)
        detector.on_note_on(64, 2, 0.0)

        overlapping = detector.currently_overlapping()
        assert (60, 1) in overlapping
        assert (64, 2) in overlapping
        assert len(overlapping) == 2

    def test_currently_overlapping_after_note_off(self):
        """currently_overlapping excludes released notes."""
        cfg = NoteOverlapConfig(enabled=True)
        detector = NoteOverlapDetector(cfg)

        detector.on_note_on(60, 1, 0.0)
        detector.on_note_on(64, 2, 0.0)
        detector.on_note_off(60, 1)

        overlapping = detector.currently_overlapping()
        assert (60, 1) not in overlapping
        assert (64, 2) in overlapping


class TestNoteOverlapDetectorMaxOverlapsFIFO:
    """FIFO eviction when max_overlaps exceeded."""

    def test_max_overlaps_fifo_eviction(self):
        """When overlaps exceed max_overlaps, oldest is removed."""
        cfg = NoteOverlapConfig(enabled=True, max_overlaps=50)
        detector = NoteOverlapDetector(cfg)

        # Generate 100 overlaps on different notes (release between each to get clean overlaps)
        for i in range(100):
            note = 60 + (i % 3)
            detector.on_note_on(note, 1, float(i * 0.01))
            detector.on_note_on(note, 1, float(i * 0.01 + 0.005))
            detector.on_note_off(note, 1)

        # Should keep only the last 50 (clamped from 50 stays at 50)
        assert detector.count() == 50
        recent = detector.recent(100)
        assert len(recent) == 50

    def test_max_overlaps_clamped_10_10000(self):
        """max_overlaps clamped at construction."""
        cfg = NoteOverlapConfig(enabled=True, max_overlaps=150)
        detector = NoteOverlapDetector(cfg)

        # Create 200 overlaps
        for i in range(200):
            detector.on_note_on(60, 1, float(i * 0.1))
            detector.on_note_on(60, 1, float(i * 0.1 + 0.05))

        # Should keep only the last 150
        assert detector.count() == 150


class TestNoteOverlapDetectorMultipleTaps:
    """Multi-tap scenarios (3+ presses of same note)."""

    def test_triple_tap_two_overlaps(self):
        """Three presses of same note records two overlaps."""
        cfg = NoteOverlapConfig(enabled=True)
        detector = NoteOverlapDetector(cfg)

        result1 = detector.on_note_on(60, 1, 0.0)
        result2 = detector.on_note_on(60, 1, 0.1)
        result3 = detector.on_note_on(60, 1, 0.2)

        assert result1 is None
        assert result2 is not None
        assert result3 is not None
        assert detector.count() == 2

        # Check that second overlap recorded the updated time
        recent = detector.recent()
        assert recent[1].first_press_at_s == 0.1


class TestNoteOverlapDetectorIntegration:
    """Integration tests with realistic scenarios."""

    def test_full_workflow(self):
        """Full workflow: press, overlap, release, press again."""
        cfg = NoteOverlapConfig(enabled=True, max_overlaps=50)
        detector = NoteOverlapDetector(cfg)

        # First press
        r1 = detector.on_note_on(60, 1, 0.0)
        assert r1 is None
        assert detector.count() == 0

        # Collision
        r2 = detector.on_note_on(60, 1, 0.1)
        assert r2 is not None
        assert detector.count() == 1

        # Release
        detector.on_note_off(60, 1)
        assert (60, 1) not in detector.currently_overlapping()

        # Press again (no collision)
        r3 = detector.on_note_on(60, 1, 0.2)
        assert r3 is None
        assert detector.count() == 1  # Still only 1 collision

    def test_multiple_channels_independent(self):
        """Multiple channels tracked independently."""
        cfg = NoteOverlapConfig(enabled=True)
        detector = NoteOverlapDetector(cfg)

        # Channel 1: collision
        detector.on_note_on(60, 1, 0.0)
        r1 = detector.on_note_on(60, 1, 0.1)
        detector.on_note_off(60, 1)

        # Channel 2: collision (independent from Channel 1)
        detector.on_note_on(60, 2, 0.2)
        r2 = detector.on_note_on(60, 2, 0.3)

        assert r1 is not None  # Ch 1 collision
        assert r2 is not None  # Ch 2 collision (on its own channel)
        assert detector.count() == 2

    def test_realistic_drum_pattern(self):
        """Realistic drum pattern with multiple simultaneous notes."""
        cfg = NoteOverlapConfig(enabled=True)
        detector = NoteOverlapDetector(cfg)

        # Kick (note 36), snare (note 38), hihat (note 42)
        detector.on_note_on(36, 1, 0.0)
        detector.on_note_on(38, 1, 0.0)
        detector.on_note_on(42, 1, 0.0)

        # All release
        detector.on_note_off(36, 1)
        detector.on_note_off(38, 1)
        detector.on_note_off(42, 1)

        # No overlaps (all different notes)
        assert detector.count() == 0

        # Accidental double-tap on kick
        detector.on_note_on(36, 1, 0.5)
        r = detector.on_note_on(36, 1, 0.6)

        assert r is not None
        assert detector.count() == 1
        assert detector.count_per_note()[36] == 1
