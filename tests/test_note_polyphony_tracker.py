"""Polyphony tracker — max simultaneous notes, mean, median, and serialization."""
from __future__ import annotations

import pytest

from gamepad_midi_bridge.note_polyphony_tracker import (
    PolyphonyConfig,
    PolyphonyReport,
    NotePolyphonyTracker,
)


class TestPolyphonyConfig:
    """PolyphonyConfig dataclass — serialization and clamping."""

    def test_defaults(self):
        """Default config has max_samples=20000."""
        cfg = PolyphonyConfig()
        assert cfg.max_samples == 20000

    def test_max_samples_clamped_100_to_1000000(self):
        """max_samples is clamped to 100..1000000."""
        cfg1 = PolyphonyConfig(max_samples=10)
        assert cfg1.max_samples == 100

        cfg2 = PolyphonyConfig(max_samples=2000000)
        assert cfg2.max_samples == 1000000

        cfg3 = PolyphonyConfig(max_samples=5000)
        assert cfg3.max_samples == 5000

    def test_to_dict_round_trip(self):
        """to_dict and from_dict preserve config."""
        cfg = PolyphonyConfig(max_samples=50000)
        data = cfg.to_dict()
        cfg2 = PolyphonyConfig.from_dict(data)
        assert cfg2.max_samples == cfg.max_samples

    def test_from_dict_with_missing_key(self):
        """from_dict with missing max_samples uses default."""
        cfg = PolyphonyConfig.from_dict({})
        assert cfg.max_samples == 20000

    def test_from_dict_clamps_on_deserialize(self):
        """from_dict clamps max_samples on deserialize."""
        cfg = PolyphonyConfig.from_dict({"max_samples": 50})
        assert cfg.max_samples == 100


class TestPolyphonyReport:
    """PolyphonyReport dataclass — serialization."""

    def test_to_dict_round_trip(self):
        """to_dict and from_dict preserve report."""
        report = PolyphonyReport(
            peak_polyphony=5,
            peak_at_s=1.5,
            mean_polyphony=3.2,
            median_polyphony=3.0,
            current_held=2,
            total_samples=100,
        )
        data = report.to_dict()
        report2 = PolyphonyReport.from_dict(data)
        assert report2 == report

    def test_peak_at_s_can_be_none(self):
        """peak_at_s can be None."""
        report = PolyphonyReport(
            peak_polyphony=0,
            peak_at_s=None,
            mean_polyphony=0.0,
            median_polyphony=0.0,
            current_held=0,
            total_samples=0,
        )
        data = report.to_dict()
        report2 = PolyphonyReport.from_dict(data)
        assert report2.peak_at_s is None


class TestNotePolyphonyTrackerEmpty:
    """Empty tracker edge cases."""

    def test_empty_tracker_has_zero_peak(self):
        """Empty tracker reports peak_polyphony=0."""
        cfg = PolyphonyConfig()
        tracker = NotePolyphonyTracker(cfg)
        report = tracker.report()
        assert report.peak_polyphony == 0
        assert report.current_held == 0
        assert report.total_samples == 0
        assert report.peak_at_s is None

    def test_current_empty(self):
        """current() returns 0 for empty tracker."""
        cfg = PolyphonyConfig()
        tracker = NotePolyphonyTracker(cfg)
        assert tracker.current() == 0


class TestNotePolyphonyTrackerSingleNote:
    """Single note on/off."""

    def test_single_note_on(self):
        """Single note_on yields peak=1, current=1."""
        cfg = PolyphonyConfig()
        tracker = NotePolyphonyTracker(cfg)
        tracker.on_note_on(60, 1, 0.0)
        report = tracker.report()
        assert report.peak_polyphony == 1
        assert report.current_held == 1
        assert report.peak_at_s == 0.0

    def test_single_note_on_then_off(self):
        """Single note_on then note_off yields current=0."""
        cfg = PolyphonyConfig()
        tracker = NotePolyphonyTracker(cfg)
        tracker.on_note_on(60, 1, 0.0)
        tracker.on_note_off(60, 1, 0.1)
        report = tracker.report()
        assert report.peak_polyphony == 1
        assert report.current_held == 0


class TestNotePolyphonyTrackerMultipleNotes:
    """Multiple simultaneous notes."""

    def test_three_notes_held(self):
        """Three notes held simultaneously."""
        cfg = PolyphonyConfig()
        tracker = NotePolyphonyTracker(cfg)
        tracker.on_note_on(60, 1, 0.0)
        tracker.on_note_on(64, 1, 0.1)
        tracker.on_note_on(67, 1, 0.2)
        report = tracker.report()
        assert report.peak_polyphony == 3
        assert report.current_held == 3
        assert report.peak_at_s == 0.2

    def test_three_notes_then_release_one(self):
        """Three notes held, then one released."""
        cfg = PolyphonyConfig()
        tracker = NotePolyphonyTracker(cfg)
        tracker.on_note_on(60, 1, 0.0)
        tracker.on_note_on(64, 1, 0.1)
        tracker.on_note_on(67, 1, 0.2)
        tracker.on_note_off(64, 1, 0.3)
        report = tracker.report()
        assert report.peak_polyphony == 3
        assert report.current_held == 2

    def test_peak_at_s_updates_on_new_peak(self):
        """peak_at_s updates when peak rises."""
        cfg = PolyphonyConfig()
        tracker = NotePolyphonyTracker(cfg)
        tracker.on_note_on(60, 1, 0.5)
        tracker.on_note_on(64, 1, 1.0)
        tracker.on_note_on(67, 1, 1.5)
        tracker.on_note_on(71, 1, 2.0)
        report = tracker.report()
        assert report.peak_polyphony == 4
        assert report.peak_at_s == 2.0


class TestNotePolyphonyTrackerPolyphonyStats:
    """Mean and median polyphony."""

    def test_mean_polyphony(self):
        """mean_polyphony approximates average held notes."""
        cfg = PolyphonyConfig()
        tracker = NotePolyphonyTracker(cfg)
        # on_note_on(60) → [1]
        # on_note_on(64) → [1, 2]
        # on_note_off(64) → [1, 2, 1]
        # mean = (1+2+1)/3 = 1.333...
        tracker.on_note_on(60, 1, 0.0)
        tracker.on_note_on(64, 1, 0.1)
        tracker.on_note_off(64, 1, 0.2)
        report = tracker.report()
        assert report.mean_polyphony == pytest.approx(1.333, rel=0.01)

    def test_median_polyphony(self):
        """median_polyphony is middle value."""
        cfg = PolyphonyConfig()
        tracker = NotePolyphonyTracker(cfg)
        # Samples: [1, 2, 1] = median 1
        tracker.on_note_on(60, 1, 0.0)
        tracker.on_note_on(64, 1, 0.1)
        tracker.on_note_off(64, 1, 0.2)
        report = tracker.report()
        assert report.median_polyphony == 1

    def test_mean_median_with_outlier(self):
        """median more robust than mean to outliers."""
        cfg = PolyphonyConfig()
        tracker = NotePolyphonyTracker(cfg)
        # 4 notes, then down to 1 note many times
        tracker.on_note_on(60, 1, 0.0)
        tracker.on_note_on(64, 1, 0.1)
        tracker.on_note_on(67, 1, 0.2)
        tracker.on_note_on(71, 1, 0.3)
        for i in range(20):
            tracker.on_note_off(60 + i, 1, 0.4 + i * 0.01)
            tracker.on_note_on(60 + i, 1, 0.45 + i * 0.01)
        report = tracker.report()
        # Mean pulled up by peak, median more stable
        assert report.median_polyphony < report.mean_polyphony


class TestNotePolyphonyTrackerDuplicates:
    """Duplicate note_on and unheld note_off."""

    def test_duplicate_note_on_same_channel(self):
        """Duplicate note_on (same note+channel) doesn't double-count."""
        cfg = PolyphonyConfig()
        tracker = NotePolyphonyTracker(cfg)
        tracker.on_note_on(60, 1, 0.0)
        tracker.on_note_on(60, 1, 0.1)
        report = tracker.report()
        # Should still be 1, not 2
        assert report.current_held == 1
        assert report.peak_polyphony == 1

    def test_note_off_unheld_note_noop(self):
        """note_off for unheld note is no-op."""
        cfg = PolyphonyConfig()
        tracker = NotePolyphonyTracker(cfg)
        tracker.on_note_on(60, 1, 0.0)
        tracker.on_note_off(64, 1, 0.1)  # 64 never held
        report = tracker.report()
        # 60 still held, no crash
        assert report.current_held == 1
        assert report.peak_polyphony == 1

    def test_different_channels_same_note(self):
        """Same note on different channels counts separately."""
        cfg = PolyphonyConfig()
        tracker = NotePolyphonyTracker(cfg)
        tracker.on_note_on(60, 1, 0.0)
        tracker.on_note_on(60, 2, 0.1)
        report = tracker.report()
        # (60, 1) and (60, 2) are different
        assert report.current_held == 2
        assert report.peak_polyphony == 2


class TestNotePolyphonyTrackerSamples:
    """Sample buffer and FIFO behavior."""

    def test_max_samples_fifo(self):
        """max_samples FIFO: oldest samples drop when limit exceeded."""
        # Note: max_samples is clamped to min=100, so use a larger value to test FIFO
        cfg = PolyphonyConfig(max_samples=150)
        tracker = NotePolyphonyTracker(cfg)
        # Generate 160 note_on events (each creates one sample snapshot)
        for i in range(160):
            tracker.on_note_on(60 + (i % 5), 1, float(i))
        report = tracker.report()
        # FIFO should keep at most max_samples (150) samples
        assert report.total_samples <= 150

    def test_samples_captures_polyphony_over_time(self):
        """_samples captures polyphony snapshots."""
        cfg = PolyphonyConfig()
        tracker = NotePolyphonyTracker(cfg)
        tracker.on_note_on(60, 1, 0.0)  # sample: [1]
        tracker.on_note_on(64, 1, 0.1)  # sample: [1, 2]
        tracker.on_note_on(67, 1, 0.2)  # sample: [1, 2, 3]
        tracker.on_note_off(64, 1, 0.3)  # sample: [1, 2, 3, 2]
        report = tracker.report()
        assert report.total_samples == 4


class TestNotePolyphonyTrackerClear:
    """Clear and reset."""

    def test_clear_resets_all(self):
        """clear() resets peak, current_held, samples."""
        cfg = PolyphonyConfig()
        tracker = NotePolyphonyTracker(cfg)
        tracker.on_note_on(60, 1, 0.0)
        tracker.on_note_on(64, 1, 0.1)
        assert tracker.current() == 2
        tracker.clear()
        report = tracker.report()
        assert report.peak_polyphony == 0
        assert report.current_held == 0
        assert report.total_samples == 0
        assert report.peak_at_s is None

    def test_clear_allows_restart(self):
        """After clear(), can start fresh."""
        cfg = PolyphonyConfig()
        tracker = NotePolyphonyTracker(cfg)
        tracker.on_note_on(60, 1, 0.0)
        tracker.clear()
        tracker.on_note_on(72, 2, 1.0)
        report = tracker.report()
        assert report.peak_polyphony == 1
        assert report.peak_at_s == 1.0
