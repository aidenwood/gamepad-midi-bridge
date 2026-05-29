"""Tests for performance_stats aggregator module."""
from __future__ import annotations

import pytest

from gamepad_midi_bridge.performance_stats import (
    PerformanceStatsTracker,
    PerformanceReport,
    PITCH_CLASS_NAMES,
)


class TestPerformanceReportDataclass:
    """Test PerformanceReport dataclass."""

    def test_to_dict_round_trip(self):
        """Report should serialize/deserialize to/from dict."""
        report = PerformanceReport(
            session_start_s=0.0,
            session_end_s=10.0,
            duration_s=10.0,
            total_notes_played=5,
            unique_notes_count=3,
            top_notes=[(60, 2.0), (64, 1.0)],
            key_center_guess=2,
            mean_note_duration_s=0.5,
            note_duration_category="medium",
            velocity_peak_bucket=4,
            velocity_mean=80.0,
            stuck_notes_count=0,
            summary_text="Test summary",
        )

        # Serialize to dict
        data = report.to_dict()
        assert isinstance(data, dict)
        assert data["total_notes_played"] == 5
        assert data["key_center_guess"] == 2

        # Deserialize from dict
        report2 = PerformanceReport.from_dict(data)
        assert report2.total_notes_played == 5
        assert report2.key_center_guess == 2
        assert report2.summary_text == "Test summary"


class TestTrackerInitialization:
    """Test PerformanceStatsTracker initialization."""

    def test_init_with_defaults(self):
        """Tracker should initialize with default configs."""
        tracker = PerformanceStatsTracker()
        assert tracker._session_start_s is None
        assert tracker._frequency is not None
        assert tracker._duration is not None
        assert tracker._histogram is not None
        assert tracker._stuck is not None

    def test_report_before_session_start(self):
        """Report before session_start should use now_s as session_start."""
        tracker = PerformanceStatsTracker()
        report = tracker.report(10.0)
        assert report.session_start_s == 10.0
        assert report.session_end_s == 10.0
        assert report.duration_s == 0.0
        assert report.total_notes_played == 0
        assert report.summary_text == "No session data yet"


class TestSessionTiming:
    """Test session timing and duration."""

    def test_on_session_start_sets_start_time(self):
        """on_session_start should record the session start time."""
        tracker = PerformanceStatsTracker()
        tracker.on_session_start(5.0)
        report = tracker.report(15.0)
        assert report.session_start_s == 5.0
        assert report.session_end_s == 15.0
        assert report.duration_s == 10.0

    def test_duration_s_equals_end_minus_start(self):
        """duration_s should be computed as session_end - session_start."""
        tracker = PerformanceStatsTracker()
        tracker.on_session_start(2.0)
        report = tracker.report(7.5)
        assert abs(report.duration_s - 5.5) < 0.01


class TestNoteTracking:
    """Test note-on/note-off tracking."""

    def test_single_note_on_off(self):
        """Recording one note should update all trackers."""
        tracker = PerformanceStatsTracker()
        tracker.on_session_start(0.0)
        tracker.on_note_on(60, 1, 100, 0.0)
        tracker.on_note_off(60, 1, 0.5)

        report = tracker.report(1.0)
        assert report.total_notes_played == 1
        assert report.unique_notes_count == 1

    def test_multiple_notes(self):
        """Recording multiple notes should populate trackers correctly."""
        tracker = PerformanceStatsTracker()
        tracker.on_session_start(0.0)

        # Note 1: C4 (60)
        tracker.on_note_on(60, 1, 100, 0.0)
        tracker.on_note_off(60, 1, 0.5)

        # Note 2: E4 (64)
        tracker.on_note_on(64, 1, 90, 1.0)
        tracker.on_note_off(64, 1, 1.2)

        report = tracker.report(2.0)
        assert report.total_notes_played == 2
        assert report.unique_notes_count == 2

    def test_top_notes_extracted(self):
        """Report should include top_notes from frequency tracker."""
        tracker = PerformanceStatsTracker()
        tracker.on_session_start(0.0)

        # Play C4 three times
        for i in range(3):
            tracker.on_note_on(60, 1, 100, float(i) * 1.0)
            tracker.on_note_off(60, 1, float(i) * 1.0 + 0.1)

        # Play E4 once
        tracker.on_note_on(64, 1, 90, 3.0)
        tracker.on_note_off(64, 1, 3.1)

        report = tracker.report(4.0)
        assert len(report.top_notes) > 0
        # C4 (60) should be first (count=3)
        assert report.top_notes[0][0] == 60
        assert report.top_notes[0][1] == 3.0


class TestDurationAnalysis:
    """Test note duration statistics."""

    def test_mean_note_duration(self):
        """Report should include mean note duration."""
        tracker = PerformanceStatsTracker()
        tracker.on_session_start(0.0)

        # Two notes: 0.5s and 0.3s
        tracker.on_note_on(60, 1, 100, 0.0)
        tracker.on_note_off(60, 1, 0.5)

        tracker.on_note_on(64, 1, 90, 1.0)
        tracker.on_note_off(64, 1, 1.3)

        report = tracker.report(2.0)
        assert report.mean_note_duration_s is not None
        # Mean should be (0.5 + 0.3) / 2 = 0.4
        assert abs(report.mean_note_duration_s - 0.4) < 0.01

    def test_note_duration_category(self):
        """Report should include duration category (stab/short/medium/long/sustained)."""
        tracker = PerformanceStatsTracker()
        tracker.on_session_start(0.0)

        # Record a medium-duration note (0.5s)
        tracker.on_note_on(60, 1, 100, 0.0)
        tracker.on_note_off(60, 1, 0.5)

        report = tracker.report(1.0)
        assert report.note_duration_category == "medium"


class TestVelocityAnalysis:
    """Test velocity histogram."""

    def test_velocity_peak_bucket(self):
        """Report should include peak velocity bucket."""
        tracker = PerformanceStatsTracker()
        tracker.on_session_start(0.0)

        # Record notes with different velocities
        tracker.on_note_on(60, 1, 100, 0.0)  # High velocity
        tracker.on_note_off(60, 1, 0.1)

        tracker.on_note_on(64, 1, 101, 1.0)  # High velocity
        tracker.on_note_off(64, 1, 1.1)

        tracker.on_note_on(67, 1, 30, 2.0)  # Low velocity
        tracker.on_note_off(67, 1, 2.1)

        report = tracker.report(3.0)
        assert report.velocity_peak_bucket is not None
        # High velocities should have higher count

    def test_velocity_mean(self):
        """Report should include mean velocity."""
        tracker = PerformanceStatsTracker()
        tracker.on_session_start(0.0)

        # Record notes with known velocities: 100, 90, 80
        tracker.on_note_on(60, 1, 100, 0.0)
        tracker.on_note_off(60, 1, 0.1)

        tracker.on_note_on(64, 1, 90, 1.0)
        tracker.on_note_off(64, 1, 1.1)

        tracker.on_note_on(67, 1, 80, 2.0)
        tracker.on_note_off(67, 1, 2.1)

        report = tracker.report(3.0)
        assert report.velocity_mean is not None
        # Mean should be (100 + 90 + 80) / 3 = 90
        assert abs(report.velocity_mean - 90.0) < 1.0


class TestStuckNoteDetection:
    """Test stuck note detection."""

    def test_no_stuck_notes_in_normal_session(self):
        """Well-behaved notes should not be marked stuck."""
        tracker = PerformanceStatsTracker()
        tracker.on_session_start(0.0)

        tracker.on_note_on(60, 1, 100, 0.0)
        tracker.on_note_off(60, 1, 0.5)

        report = tracker.report(1.0)
        assert report.stuck_notes_count == 0

    def test_stuck_notes_count_with_long_held_note(self):
        """Notes held longer than stuck_after_s should be counted."""
        from gamepad_midi_bridge.stuck_note_detector import StuckNoteConfig

        stuck_config = StuckNoteConfig(enabled=True, stuck_after_s=0.5)
        tracker = PerformanceStatsTracker(stuck_config=stuck_config)
        tracker.on_session_start(0.0)

        # Hold a note for 1.0s (longer than stuck_after_s=0.5)
        tracker.on_note_on(60, 1, 100, 0.0)
        # Don't call on_note_off yet
        report = tracker.report(1.1)
        assert report.stuck_notes_count == 1


class TestKeyCenterAnalysis:
    """Test key center detection."""

    def test_key_center_guess_present(self):
        """Report should include key_center_guess."""
        tracker = PerformanceStatsTracker()
        tracker.on_session_start(0.0)

        # Play notes in D major (D, F#, A)
        # D = pitch class 2
        tracker.on_note_on(62, 1, 100, 0.0)  # D4
        tracker.on_note_off(62, 1, 0.1)
        tracker.on_note_on(62, 1, 100, 0.2)  # D4 again
        tracker.on_note_off(62, 1, 0.3)

        tracker.on_note_on(66, 1, 100, 0.4)  # F#4
        tracker.on_note_off(66, 1, 0.5)

        tracker.on_note_on(69, 1, 100, 0.6)  # A4
        tracker.on_note_off(69, 1, 0.7)

        report = tracker.report(1.0)
        # Key center should be D (pitch class 2) since it appears twice
        assert report.key_center_guess == 2

    def test_pitch_class_name_lookup(self):
        """PITCH_CLASS_NAMES should map indices to note names."""
        assert len(PITCH_CLASS_NAMES) == 12
        assert PITCH_CLASS_NAMES[0] == "C"
        assert PITCH_CLASS_NAMES[2] == "D"
        assert PITCH_CLASS_NAMES[7] == "G"


class TestSummaryTextGeneration:
    """Test summary_text generation."""

    def test_summary_with_no_data(self):
        """Summary should be brief when no notes played."""
        tracker = PerformanceStatsTracker()
        report = tracker.report(1.0)
        assert report.summary_text == "No session data yet"

    def test_summary_contains_duration(self):
        """Summary should mention session duration."""
        tracker = PerformanceStatsTracker()
        tracker.on_session_start(0.0)
        tracker.on_note_on(60, 1, 100, 0.0)
        tracker.on_note_off(60, 1, 0.5)

        # 3 minutes 24 seconds
        report = tracker.report(204.0)
        assert "3m 24s" in report.summary_text

    def test_summary_contains_note_count(self):
        """Summary should mention total and unique notes."""
        tracker = PerformanceStatsTracker()
        tracker.on_session_start(0.0)

        tracker.on_note_on(60, 1, 100, 0.0)
        tracker.on_note_off(60, 1, 0.1)
        tracker.on_note_on(60, 1, 100, 0.2)
        tracker.on_note_off(60, 1, 0.3)

        report = tracker.report(1.0)
        assert "2 notes played" in report.summary_text
        assert "1 unique" in report.summary_text

    def test_summary_contains_key_center(self):
        """Summary should mention key center when present."""
        tracker = PerformanceStatsTracker()
        tracker.on_session_start(0.0)

        # Play D notes (pitch class 2)
        tracker.on_note_on(62, 1, 100, 0.0)
        tracker.on_note_off(62, 1, 0.1)

        report = tracker.report(1.0)
        assert "D" in report.summary_text  # D is pitch class 2

    def test_summary_contains_duration_category(self):
        """Summary should mention note duration category."""
        tracker = PerformanceStatsTracker()
        tracker.on_session_start(0.0)

        tracker.on_note_on(60, 1, 100, 0.0)
        tracker.on_note_off(60, 1, 0.5)

        report = tracker.report(1.0)
        assert "medium" in report.summary_text

    def test_summary_contains_velocity_info(self):
        """Summary should mention velocity peak range."""
        tracker = PerformanceStatsTracker()
        tracker.on_session_start(0.0)

        tracker.on_note_on(60, 1, 100, 0.0)
        tracker.on_note_off(60, 1, 0.1)

        report = tracker.report(1.0)
        assert "Velocity peak" in report.summary_text

    def test_summary_mentions_stuck_notes(self):
        """Summary should mention stuck note count (0 or >0)."""
        tracker = PerformanceStatsTracker()
        tracker.on_session_start(0.0)

        tracker.on_note_on(60, 1, 100, 0.0)
        tracker.on_note_off(60, 1, 0.1)

        report = tracker.report(1.0)
        assert "stuck notes" in report.summary_text


class TestTrackerClear:
    """Test clear() method."""

    def test_clear_resets_all_trackers(self):
        """clear() should reset all trackers and session state."""
        tracker = PerformanceStatsTracker()
        tracker.on_session_start(0.0)
        tracker.on_note_on(60, 1, 100, 0.0)
        tracker.on_note_off(60, 1, 0.5)

        # Verify state before clear
        report_before = tracker.report(1.0)
        assert report_before.total_notes_played == 1

        # Clear
        tracker.clear()

        # Verify state after clear
        report_after = tracker.report(2.0)
        assert report_after.session_start_s == 2.0  # Now using current time
        assert report_after.total_notes_played == 0
        assert report_after.summary_text == "No session data yet"


class TestMultipleNotesScenario:
    """Test realistic multi-note scenarios."""

    def test_full_performance_session(self):
        """Comprehensive scenario: start -> play notes -> generate report."""
        tracker = PerformanceStatsTracker()
        tracker.on_session_start(0.0)

        # Play a short melodic pattern
        times = [0.0, 0.5, 1.0, 1.5]
        notes = [60, 64, 67, 65]  # C, E, G, F#
        velocities = [80, 90, 100, 95]

        for t, note, vel in zip(times, notes, velocities):
            tracker.on_note_on(note, 1, vel, t)
            tracker.on_note_off(note, 1, t + 0.3)

        report = tracker.report(2.0)

        # Verify all fields are populated
        assert report.session_start_s == 0.0
        assert report.session_end_s == 2.0
        assert report.duration_s == 2.0
        assert report.total_notes_played == 4
        assert report.unique_notes_count == 4
        assert len(report.top_notes) == 4
        assert report.key_center_guess is not None
        assert report.mean_note_duration_s is not None
        assert report.note_duration_category is not None
        assert report.velocity_peak_bucket is not None
        assert report.velocity_mean is not None
        assert report.stuck_notes_count == 0
        assert len(report.summary_text) > 0
        assert "No session data yet" not in report.summary_text
