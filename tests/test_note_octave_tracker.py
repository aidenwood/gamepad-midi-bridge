"""Tests for per-octave note usage tracker.

NoteOctaveTracker records MIDI notes bucketed by octave (-1..9), computes
frequency distribution, detects transitions, and identifies dominant octave.
Pure stdlib, no Qt.
"""
from __future__ import annotations

import pytest


class TestOctaveStats:
    """OctaveStats dataclass — serialize/deserialize."""

    def test_stats_default_construction(self):
        from gamepad_midi_bridge.note_octave_tracker import OctaveStats
        stats = OctaveStats()
        assert len(stats.octave_counts) == 11
        assert all(c == 0 for c in stats.octave_counts)
        assert stats.total_plays == 0
        assert stats.dominant_octave is None
        assert stats.octave_transitions == 0
        assert stats.most_common_transition is None

    def test_stats_with_data(self):
        from gamepad_midi_bridge.note_octave_tracker import OctaveStats
        counts = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        stats = OctaveStats(
            octave_counts=counts,
            total_plays=55,
            dominant_octave=9,
            octave_transitions=5,
            most_common_transition=(4, 5),
        )
        assert stats.octave_counts == counts
        assert stats.total_plays == 55
        assert stats.dominant_octave == 9
        assert stats.octave_transitions == 5
        assert stats.most_common_transition == (4, 5)

    def test_stats_to_dict(self):
        from gamepad_midi_bridge.note_octave_tracker import OctaveStats
        counts = [1] * 11
        stats = OctaveStats(
            octave_counts=counts,
            total_plays=11,
            dominant_octave=3,
            octave_transitions=2,
            most_common_transition=(2, 3),
        )
        d = stats.to_dict()
        assert d["octave_counts"] == counts
        assert d["total_plays"] == 11
        assert d["dominant_octave"] == 3
        assert d["octave_transitions"] == 2
        assert d["most_common_transition"] == [2, 3]

    def test_stats_to_dict_with_none_transition(self):
        from gamepad_midi_bridge.note_octave_tracker import OctaveStats
        stats = OctaveStats(most_common_transition=None)
        d = stats.to_dict()
        assert d["most_common_transition"] is None

    def test_stats_from_dict(self):
        from gamepad_midi_bridge.note_octave_tracker import OctaveStats
        d = {
            "octave_counts": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            "total_plays": 55,
            "dominant_octave": 5,
            "octave_transitions": 8,
            "most_common_transition": [3, 4],
        }
        stats = OctaveStats.from_dict(d)
        assert stats.octave_counts == d["octave_counts"]
        assert stats.total_plays == 55
        assert stats.dominant_octave == 5
        assert stats.octave_transitions == 8
        assert stats.most_common_transition == (3, 4)

    def test_stats_round_trip(self):
        from gamepad_midi_bridge.note_octave_tracker import OctaveStats
        original = OctaveStats(
            octave_counts=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            total_plays=55,
            dominant_octave=7,
            octave_transitions=10,
            most_common_transition=(6, 7),
        )
        d = original.to_dict()
        restored = OctaveStats.from_dict(d)
        assert restored.octave_counts == original.octave_counts
        assert restored.total_plays == original.total_plays
        assert restored.dominant_octave == original.dominant_octave
        assert restored.octave_transitions == original.octave_transitions
        assert restored.most_common_transition == original.most_common_transition


class TestOctaveTrackerConfig:
    """OctaveTrackerConfig — clamp parameters on construction."""

    def test_config_defaults(self):
        from gamepad_midi_bridge.note_octave_tracker import OctaveTrackerConfig
        cfg = OctaveTrackerConfig()
        assert cfg.max_samples == 10000

    def test_config_clamp_max_samples_below_100(self):
        from gamepad_midi_bridge.note_octave_tracker import OctaveTrackerConfig
        cfg = OctaveTrackerConfig(max_samples=50)
        assert cfg.max_samples == 100
        cfg = OctaveTrackerConfig(max_samples=0)
        assert cfg.max_samples == 100

    def test_config_clamp_max_samples_above_1000000(self):
        from gamepad_midi_bridge.note_octave_tracker import OctaveTrackerConfig
        cfg = OctaveTrackerConfig(max_samples=1000001)
        assert cfg.max_samples == 1000000
        cfg = OctaveTrackerConfig(max_samples=9999999)
        assert cfg.max_samples == 1000000

    def test_config_no_clamp_max_samples_in_range(self):
        from gamepad_midi_bridge.note_octave_tracker import OctaveTrackerConfig
        cfg = OctaveTrackerConfig(max_samples=50000)
        assert cfg.max_samples == 50000

    def test_config_to_dict(self):
        from gamepad_midi_bridge.note_octave_tracker import OctaveTrackerConfig
        cfg = OctaveTrackerConfig(max_samples=5000)
        d = cfg.to_dict()
        assert d["max_samples"] == 5000

    def test_config_from_dict(self):
        from gamepad_midi_bridge.note_octave_tracker import OctaveTrackerConfig
        d = {"max_samples": 20000}
        cfg = OctaveTrackerConfig.from_dict(d)
        assert cfg.max_samples == 20000

    def test_config_from_dict_applies_clamping(self):
        from gamepad_midi_bridge.note_octave_tracker import OctaveTrackerConfig
        d = {"max_samples": 50}
        cfg = OctaveTrackerConfig.from_dict(d)
        assert cfg.max_samples == 100

    def test_config_round_trip(self):
        from gamepad_midi_bridge.note_octave_tracker import OctaveTrackerConfig
        original = OctaveTrackerConfig(max_samples=15000)
        d = original.to_dict()
        restored = OctaveTrackerConfig.from_dict(d)
        assert restored.max_samples == original.max_samples


class TestNoteOctaveTracker:
    """NoteOctaveTracker — record notes and compute octave statistics."""

    def test_tracker_empty_analyze(self):
        from gamepad_midi_bridge.note_octave_tracker import NoteOctaveTracker, OctaveTrackerConfig
        tracker = NoteOctaveTracker(OctaveTrackerConfig())
        stats = tracker.analyze()
        assert stats.total_plays == 0
        assert stats.dominant_octave is None
        assert stats.octave_transitions == 0
        assert stats.most_common_transition is None
        assert all(c == 0 for c in stats.octave_counts)

    def test_tracker_record_single_note_octave_4(self):
        from gamepad_midi_bridge.note_octave_tracker import NoteOctaveTracker, OctaveTrackerConfig
        tracker = NoteOctaveTracker(OctaveTrackerConfig())
        tracker.record(60)  # Middle C, octave 4 (index 5)
        stats = tracker.analyze()
        assert stats.total_plays == 1
        assert stats.octave_counts[5] == 1  # octave 4 is at index 5
        assert stats.dominant_octave == 4

    def test_tracker_record_note_octave_minus_1(self):
        from gamepad_midi_bridge.note_octave_tracker import NoteOctaveTracker, OctaveTrackerConfig
        tracker = NoteOctaveTracker(OctaveTrackerConfig())
        tracker.record(0)  # C-1 = octave -1 (index 0)
        stats = tracker.analyze()
        assert stats.total_plays == 1
        assert stats.octave_counts[0] == 1
        assert stats.dominant_octave == -1

    def test_tracker_dominant_octave_highest_count(self):
        from gamepad_midi_bridge.note_octave_tracker import NoteOctaveTracker, OctaveTrackerConfig
        tracker = NoteOctaveTracker(OctaveTrackerConfig())
        # Record notes in octave 4 (index 5): 60, 62, 64
        for note in [60, 62, 64]:
            tracker.record(note)
        # Record notes in octave 5 (index 6): 72, 74
        for note in [72, 74]:
            tracker.record(note)
        stats = tracker.analyze()
        assert stats.dominant_octave == 4
        assert stats.octave_counts[5] == 3
        assert stats.octave_counts[6] == 2

    def test_tracker_transitions_same_octave_no_count(self):
        from gamepad_midi_bridge.note_octave_tracker import NoteOctaveTracker, OctaveTrackerConfig
        tracker = NoteOctaveTracker(OctaveTrackerConfig())
        # Record multiple notes in the same octave
        for note in [60, 62, 64]:
            tracker.record(note)
        stats = tracker.analyze()
        assert stats.octave_transitions == 0

    def test_tracker_transitions_octave_change(self):
        from gamepad_midi_bridge.note_octave_tracker import NoteOctaveTracker, OctaveTrackerConfig
        tracker = NoteOctaveTracker(OctaveTrackerConfig())
        # octave 4, octave 5, octave 4 → 2 transitions
        tracker.record(60)  # octave 4
        tracker.record(72)  # octave 5
        tracker.record(64)  # octave 4
        stats = tracker.analyze()
        assert stats.octave_transitions == 2

    def test_tracker_most_common_transition(self):
        from gamepad_midi_bridge.note_octave_tracker import NoteOctaveTracker, OctaveTrackerConfig
        tracker = NoteOctaveTracker(OctaveTrackerConfig())
        # Alternate between octaves 4 and 5: 60, 72, 60, 72, 60
        tracker.record(60)  # octave 4 (index 5)
        tracker.record(72)  # octave 5 (index 6) — transition 5->6
        tracker.record(60)  # octave 4 — transition 6->5
        tracker.record(72)  # octave 5 — transition 5->6
        tracker.record(60)  # octave 4 — transition 6->5
        stats = tracker.analyze()
        # Both (4->5) and (5->4) occur twice — but we expect one as most common
        # (order of insertion into dict determines which is returned on tie)
        assert stats.octave_transitions == 4
        assert stats.most_common_transition is not None
        assert stats.most_common_transition in [(4, 5), (5, 4)]

    def test_tracker_clear(self):
        from gamepad_midi_bridge.note_octave_tracker import NoteOctaveTracker, OctaveTrackerConfig
        tracker = NoteOctaveTracker(OctaveTrackerConfig())
        tracker.record(60)
        tracker.record(72)
        assert tracker.total() == 2
        tracker.clear()
        stats = tracker.analyze()
        assert stats.total_plays == 0
        assert all(c == 0 for c in stats.octave_counts)
        assert stats.octave_transitions == 0

    def test_tracker_total(self):
        from gamepad_midi_bridge.note_octave_tracker import NoteOctaveTracker, OctaveTrackerConfig
        tracker = NoteOctaveTracker(OctaveTrackerConfig())
        assert tracker.total() == 0
        tracker.record(60)
        assert tracker.total() == 1
        tracker.record(72)
        assert tracker.total() == 2
        tracker.record(60)
        assert tracker.total() == 3

    def test_tracker_clamp_note_0_to_127(self):
        from gamepad_midi_bridge.note_octave_tracker import NoteOctaveTracker, OctaveTrackerConfig
        tracker = NoteOctaveTracker(OctaveTrackerConfig())
        # Below 0 should clamp to 0
        tracker.record(-10)
        # Above 127 should clamp to 127
        tracker.record(200)
        stats = tracker.analyze()
        assert stats.total_plays == 2
        # -10 clamps to 0 (octave -1, index 0)
        # 200 clamps to 127 (octave 9, index 10)
        assert stats.octave_counts[0] >= 1  # includes -10->0
        assert stats.octave_counts[10] >= 1  # includes 200->127

    def test_tracker_max_samples_fifo(self):
        from gamepad_midi_bridge.note_octave_tracker import NoteOctaveTracker, OctaveTrackerConfig
        cfg = OctaveTrackerConfig(max_samples=5)
        tracker = NoteOctaveTracker(cfg)
        # Record 10 notes in octave 4 (all same octave)
        for _ in range(10):
            tracker.record(60)
        stats = tracker.analyze()
        # Total count reflects all 10, but samples list is capped at 5
        assert tracker.total() == 10
        assert stats.total_plays == 10

    def test_tracker_octave_distribution(self):
        from gamepad_midi_bridge.note_octave_tracker import NoteOctaveTracker, OctaveTrackerConfig
        tracker = NoteOctaveTracker(OctaveTrackerConfig())
        # Record notes across multiple octaves
        # Octave -1: 0, 2
        tracker.record(0)
        tracker.record(2)
        # Octave 4: 60, 62, 64
        tracker.record(60)
        tracker.record(62)
        tracker.record(64)
        # Octave 8: 108, 110 (C8, D8)
        tracker.record(108)
        tracker.record(110)
        stats = tracker.analyze()
        assert stats.octave_counts[0] == 2  # octave -1
        assert stats.octave_counts[5] == 3  # octave 4
        assert stats.octave_counts[9] == 2  # octave 8 (index 9)
        assert stats.total_plays == 7
        assert stats.dominant_octave == 4

    def test_tracker_transition_pairs_distinct(self):
        from gamepad_midi_bridge.note_octave_tracker import NoteOctaveTracker, OctaveTrackerConfig
        tracker = NoteOctaveTracker(OctaveTrackerConfig())
        # Record: 1->2 three times (via alternation), 2->3 twice (via alternation)
        # Start at octave 1 (note 24, C1)
        tracker.record(24)  # octave 1
        # Alternate 1->2->1 three times
        for _ in range(3):
            tracker.record(36)  # octave 2 (C2)
            tracker.record(24)  # octave 1
        # Transition to octave 2, then octave 3 twice
        tracker.record(36)  # octave 2
        tracker.record(48)  # octave 3 (C3)
        tracker.record(36)  # octave 2
        tracker.record(48)  # octave 3
        stats = tracker.analyze()
        # Most common transition should be 1->2 (occurred 3 times)
        assert stats.most_common_transition == (1, 2)
        # Check that total transitions are correct
        # 1->2->1->2->1->2->1->2->3->2->3 = 10 transitions
        assert stats.octave_transitions == 10

    def test_tracker_complex_sequence(self):
        from gamepad_midi_bridge.note_octave_tracker import NoteOctaveTracker, OctaveTrackerConfig
        tracker = NoteOctaveTracker(OctaveTrackerConfig())
        # Sequence: 60 (oct 4), 62 (oct 4), 72 (oct 5), 84 (oct 6), 72 (oct 5), 60 (oct 4)
        sequence = [60, 62, 72, 84, 72, 60]
        for note in sequence:
            tracker.record(note)
        stats = tracker.analyze()
        assert stats.total_plays == 6
        # Octave 4: 60, 62, 60 → 3 plays
        # Octave 5: 72, 72 → 2 plays
        # Octave 6: 84 → 1 play
        assert stats.octave_counts[5] == 3  # octave 4 (index 5)
        assert stats.octave_counts[6] == 2  # octave 5 (index 6)
        assert stats.octave_counts[7] == 1  # octave 6 (index 7)
        assert stats.dominant_octave == 4
        # Transitions: 4->4 (no), 4->5 (yes), 5->6 (yes), 6->5 (yes), 5->4 (yes) = 4 transitions
        assert stats.octave_transitions == 4
