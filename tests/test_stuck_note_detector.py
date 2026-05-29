"""Stuck note detector — detects and optionally auto-releases held notes."""
from __future__ import annotations

import pytest

from gamepad_midi_bridge.stuck_note_detector import StuckNoteConfig, StuckNoteDetector


class TestStuckNoteConfig:
    """StuckNoteConfig dataclass — serialization and clamping."""

    def test_defaults(self):
        """Default config is disabled."""
        cfg = StuckNoteConfig()
        assert cfg.enabled is False
        assert cfg.stuck_after_s == 10.0
        assert cfg.auto_release is False

    def test_to_dict_round_trip(self):
        """to_dict and from_dict preserve config."""
        cfg = StuckNoteConfig(
            enabled=True,
            stuck_after_s=5.5,
            auto_release=True,
        )
        data = cfg.to_dict()
        cfg2 = StuckNoteConfig.from_dict(data)
        assert cfg2 == cfg

    def test_stuck_after_s_clamped_lower(self):
        """stuck_after_s < 0.5 is clamped to 0.5."""
        cfg = StuckNoteConfig(stuck_after_s=0.1)
        assert cfg.stuck_after_s == 0.5

    def test_stuck_after_s_clamped_upper(self):
        """stuck_after_s > 3600 is clamped to 3600."""
        cfg = StuckNoteConfig(stuck_after_s=5000.0)
        assert cfg.stuck_after_s == 3600.0

    def test_stuck_after_s_not_clamped_when_in_range(self):
        """stuck_after_s in [0.5, 3600] is not clamped."""
        cfg = StuckNoteConfig(stuck_after_s=1.5)
        assert cfg.stuck_after_s == 1.5

        cfg2 = StuckNoteConfig(stuck_after_s=0.5)
        assert cfg2.stuck_after_s == 0.5

        cfg3 = StuckNoteConfig(stuck_after_s=3600.0)
        assert cfg3.stuck_after_s == 3600.0

    def test_from_dict_clamps_stuck_after_s(self):
        """from_dict clamps stuck_after_s."""
        cfg = StuckNoteConfig.from_dict({"stuck_after_s": 10000.0})
        assert cfg.stuck_after_s == 3600.0

        cfg2 = StuckNoteConfig.from_dict({"stuck_after_s": 0.01})
        assert cfg2.stuck_after_s == 0.5


class TestDetectorDisabled:
    """Disabled detector returns empty stuck_notes."""

    def test_disabled_returns_empty_stuck_notes(self):
        """When disabled, stuck_notes() always returns []."""
        cfg = StuckNoteConfig(enabled=False, stuck_after_s=1.0)
        detector = StuckNoteDetector(cfg)

        detector.on_note_on(60, 1, 0.0)
        # At t=10, note is held 10s, but detector is disabled
        assert detector.stuck_notes(10.0) == []

    def test_disabled_detector_still_tracks_notes_internally(self):
        """Disabled detector still tracks notes in _open."""
        cfg = StuckNoteConfig(enabled=False)
        detector = StuckNoteDetector(cfg)

        detector.on_note_on(60, 1, 0.0)
        assert detector.open_count() == 1
        # But stuck_notes returns nothing
        assert detector.stuck_notes(100.0) == []


class TestNoteTracking:
    """Basic note-on/-off tracking."""

    def test_on_note_on_adds_to_open(self):
        """on_note_on adds note to _open."""
        cfg = StuckNoteConfig(enabled=True, stuck_after_s=10.0)
        detector = StuckNoteDetector(cfg)

        detector.on_note_on(60, 1, 0.0)
        assert detector.open_count() == 1

    def test_on_note_off_removes_from_open(self):
        """on_note_off removes note from _open."""
        cfg = StuckNoteConfig(enabled=True)
        detector = StuckNoteDetector(cfg)

        detector.on_note_on(60, 1, 0.0)
        assert detector.open_count() == 1

        detector.on_note_off(60, 1, 1.0)
        assert detector.open_count() == 0

    def test_on_note_on_replaces_start_time(self):
        """on_note_on twice replaces the start time (resets stuck timer)."""
        cfg = StuckNoteConfig(enabled=True, stuck_after_s=5.0)
        detector = StuckNoteDetector(cfg)

        detector.on_note_on(60, 1, 0.0)
        assert detector.stuck_notes(6.0) == [(60, 1, 6.0)]

        # Note on again at t=2, resets timer
        detector.on_note_on(60, 1, 2.0)
        # At t=6, only 4s have passed since reset
        assert detector.stuck_notes(6.0) == []
        # At t=7.1, 5.1s have passed
        assert detector.stuck_notes(7.1) == [(60, 1, 5.1)]

    def test_off_non_existent_note_does_nothing(self):
        """Calling on_note_off for a non-existent note is safe."""
        cfg = StuckNoteConfig(enabled=True)
        detector = StuckNoteDetector(cfg)

        detector.on_note_off(60, 1, 1.0)  # No error
        assert detector.open_count() == 0


class TestStuckNotesDetection:
    """Detecting stuck notes based on threshold."""

    def test_empty_detector_returns_empty(self):
        """Empty detector returns []."""
        cfg = StuckNoteConfig(enabled=True, stuck_after_s=10.0)
        detector = StuckNoteDetector(cfg)
        assert detector.stuck_notes(0.0) == []

    def test_one_note_not_stuck(self):
        """Note held briefly is not stuck."""
        cfg = StuckNoteConfig(enabled=True, stuck_after_s=10.0)
        detector = StuckNoteDetector(cfg)

        detector.on_note_on(60, 1, 0.0)
        # At t=5, only 5s held
        assert detector.stuck_notes(5.0) == []

    def test_one_note_held_at_threshold_is_stuck(self):
        """Note held exactly at threshold is stuck."""
        cfg = StuckNoteConfig(enabled=True, stuck_after_s=10.0)
        detector = StuckNoteDetector(cfg)

        detector.on_note_on(60, 1, 0.0)
        # At t=10, exactly 10s held
        assert detector.stuck_notes(10.0) == [(60, 1, 10.0)]

    def test_one_note_held_longer_than_threshold(self):
        """Note held longer than threshold is stuck."""
        cfg = StuckNoteConfig(enabled=True, stuck_after_s=10.0)
        detector = StuckNoteDetector(cfg)

        detector.on_note_on(60, 1, 0.0)
        # At t=15, 15s held
        assert detector.stuck_notes(15.0) == [(60, 1, 15.0)]

    def test_multiple_stuck_notes_sorted_by_age(self):
        """Multiple stuck notes are returned sorted by age (descending)."""
        cfg = StuckNoteConfig(enabled=True, stuck_after_s=5.0)
        detector = StuckNoteDetector(cfg)

        detector.on_note_on(60, 1, 0.0)  # Will be 10s old at t=10
        detector.on_note_on(64, 1, 3.0)  # Will be 7s old at t=10
        detector.on_note_on(67, 1, 6.0)  # Will be 4s old at t=10 (not stuck)

        stuck = detector.stuck_notes(10.0)
        # Should have 60 (10s) and 64 (7s), sorted by age descending
        assert len(stuck) == 2
        assert stuck[0] == (60, 1, 10.0)
        assert stuck[1] == (64, 1, 7.0)

    def test_notes_on_different_channels_tracked_separately(self):
        """Same note on different channels are tracked separately."""
        cfg = StuckNoteConfig(enabled=True, stuck_after_s=5.0)
        detector = StuckNoteDetector(cfg)

        detector.on_note_on(60, 1, 0.0)
        detector.on_note_on(60, 2, 2.0)

        stuck = detector.stuck_notes(8.0)
        # Both (60, 1) at 8s and (60, 2) at 6s should be stuck
        assert len(stuck) == 2
        assert (60, 1, 8.0) in stuck
        assert (60, 2, 6.0) in stuck


class TestAutoRelease:
    """tick() with auto_release."""

    def test_tick_with_auto_release_false_returns_empty(self):
        """tick() returns [] when auto_release is False, even if stuck."""
        cfg = StuckNoteConfig(enabled=True, stuck_after_s=5.0, auto_release=False)
        detector = StuckNoteDetector(cfg)

        detector.on_note_on(60, 1, 0.0)
        detector.on_note_on(64, 1, 1.0)

        # At t=10, both should be stuck, but auto_release is False
        result = detector.tick(10.0)
        assert result == []
        # Notes should still be open
        assert detector.open_count() == 2

    def test_tick_with_auto_release_true_returns_stuck_notes(self):
        """tick() with auto_release returns and removes stuck notes."""
        cfg = StuckNoteConfig(enabled=True, stuck_after_s=5.0, auto_release=True)
        detector = StuckNoteDetector(cfg)

        detector.on_note_on(60, 1, 0.0)
        detector.on_note_on(64, 1, 2.0)

        result = detector.tick(10.0)
        # Should return both as (note, channel) tuples
        assert len(result) == 2
        assert (60, 1) in result
        assert (64, 1) in result
        # Both should be removed from open
        assert detector.open_count() == 0

    def test_tick_auto_release_leaves_not_yet_stuck(self):
        """tick() does not remove notes not yet stuck."""
        cfg = StuckNoteConfig(enabled=True, stuck_after_s=5.0, auto_release=True)
        detector = StuckNoteDetector(cfg)

        detector.on_note_on(60, 1, 0.0)  # Will be stuck
        detector.on_note_on(64, 1, 5.1)  # Will not be stuck at t=10 (only 4.9s)

        result = detector.tick(10.0)
        # Only (60, 1) should be returned
        assert result == [(60, 1)]
        # (64, 1) should still be open
        assert detector.open_count() == 1
        assert (64, 1) in detector._open

    def test_tick_auto_release_disabled_ignores_enabled_flag(self):
        """tick() respects auto_release flag, not enabled flag."""
        cfg = StuckNoteConfig(enabled=True, stuck_after_s=5.0, auto_release=False)
        detector = StuckNoteDetector(cfg)

        detector.on_note_on(60, 1, 0.0)
        result = detector.tick(10.0)
        # Even though enabled=True, auto_release=False means tick returns []
        assert result == []


class TestPanic:
    """panic() releases all notes."""

    def test_panic_releases_all_notes(self):
        """panic() returns all open notes."""
        cfg = StuckNoteConfig(enabled=True)
        detector = StuckNoteDetector(cfg)

        detector.on_note_on(60, 1, 0.0)
        detector.on_note_on(64, 2, 1.0)
        detector.on_note_on(67, 3, 2.0)

        result = detector.panic()
        assert len(result) == 3
        assert (60, 1) in result
        assert (64, 2) in result
        assert (67, 3) in result

    def test_panic_clears_open(self):
        """panic() clears _open."""
        cfg = StuckNoteConfig(enabled=True)
        detector = StuckNoteDetector(cfg)

        detector.on_note_on(60, 1, 0.0)
        detector.on_note_on(64, 1, 1.0)

        detector.panic()
        assert detector.open_count() == 0

    def test_panic_on_empty_detector_returns_empty(self):
        """panic() on empty detector returns []."""
        cfg = StuckNoteConfig(enabled=True)
        detector = StuckNoteDetector(cfg)

        result = detector.panic()
        assert result == []

    def test_panic_ignores_enabled_flag(self):
        """panic() works even if enabled=False."""
        cfg = StuckNoteConfig(enabled=False)
        detector = StuckNoteDetector(cfg)

        detector.on_note_on(60, 1, 0.0)
        result = detector.panic()
        assert result == [(60, 1)]
        assert detector.open_count() == 0


class TestOpenCount:
    """open_count() tracks open notes."""

    def test_open_count_starts_at_zero(self):
        """New detector has open_count 0."""
        cfg = StuckNoteConfig(enabled=True)
        detector = StuckNoteDetector(cfg)
        assert detector.open_count() == 0

    def test_open_count_increments_on_note_on(self):
        """open_count increments with each note-on."""
        cfg = StuckNoteConfig(enabled=True)
        detector = StuckNoteDetector(cfg)

        detector.on_note_on(60, 1, 0.0)
        assert detector.open_count() == 1

        detector.on_note_on(64, 1, 0.5)
        assert detector.open_count() == 2

    def test_open_count_decrements_on_note_off(self):
        """open_count decrements with each note-off."""
        cfg = StuckNoteConfig(enabled=True)
        detector = StuckNoteDetector(cfg)

        detector.on_note_on(60, 1, 0.0)
        detector.on_note_on(64, 1, 0.5)
        assert detector.open_count() == 2

        detector.on_note_off(60, 1, 1.0)
        assert detector.open_count() == 1

        detector.on_note_off(64, 1, 1.5)
        assert detector.open_count() == 0


class TestOldestAge:
    """oldest_age() returns age of oldest held note."""

    def test_oldest_age_empty_returns_none(self):
        """oldest_age() returns None if no notes open."""
        cfg = StuckNoteConfig(enabled=True)
        detector = StuckNoteDetector(cfg)
        assert detector.oldest_age(10.0) is None

    def test_oldest_age_single_note(self):
        """oldest_age() returns age of single note."""
        cfg = StuckNoteConfig(enabled=True)
        detector = StuckNoteDetector(cfg)

        detector.on_note_on(60, 1, 0.0)
        assert detector.oldest_age(5.0) == 5.0
        assert detector.oldest_age(10.0) == 10.0

    def test_oldest_age_multiple_notes_returns_max(self):
        """oldest_age() returns age of oldest among multiple notes."""
        cfg = StuckNoteConfig(enabled=True)
        detector = StuckNoteDetector(cfg)

        detector.on_note_on(60, 1, 0.0)  # 10s old at t=10
        detector.on_note_on(64, 1, 3.0)  # 7s old at t=10
        detector.on_note_on(67, 1, 8.0)  # 2s old at t=10

        assert detector.oldest_age(10.0) == 10.0

    def test_oldest_age_after_note_off(self):
        """oldest_age() excludes released notes."""
        cfg = StuckNoteConfig(enabled=True)
        detector = StuckNoteDetector(cfg)

        detector.on_note_on(60, 1, 0.0)
        detector.on_note_on(64, 1, 2.0)

        detector.on_note_off(60, 1, 5.0)
        # Now only 64 is open, started at t=2
        assert detector.oldest_age(7.0) == 5.0


class TestIntegration:
    """Integration tests spanning multiple operations."""

    def test_realistic_stuck_note_scenario(self):
        """Realistic scenario: notes on, some off, some stuck, auto-release."""
        cfg = StuckNoteConfig(enabled=True, stuck_after_s=2.0, auto_release=True)
        detector = StuckNoteDetector(cfg)

        # t=0: press 60 and 64
        detector.on_note_on(60, 1, 0.0)
        detector.on_note_on(64, 1, 0.1)

        # t=1: release 64, press 67
        detector.on_note_off(64, 1, 1.0)
        detector.on_note_on(67, 1, 1.0)

        # t=3: check state
        stuck = detector.stuck_notes(3.0)
        # 60 has been held 3s (stuck), 67 held 2s (stuck)
        assert len(stuck) == 2
        assert (60, 1, 3.0) in stuck
        assert (67, 1, 2.0) in stuck

        # tick() should release them
        released = detector.tick(3.0)
        assert len(released) == 2
        assert detector.open_count() == 0

    def test_round_trip_serialization(self):
        """Full config serialization round-trip."""
        cfg = StuckNoteConfig(
            enabled=True,
            stuck_after_s=3.5,
            auto_release=True,
        )
        data = cfg.to_dict()
        cfg2 = StuckNoteConfig.from_dict(data)

        assert cfg == cfg2
        assert cfg2.enabled is True
        assert cfg2.stuck_after_s == 3.5
        assert cfg2.auto_release is True

    def test_multiple_detectors_independent(self):
        """Multiple detector instances are independent."""
        cfg1 = StuckNoteConfig(enabled=True, stuck_after_s=5.0)
        cfg2 = StuckNoteConfig(enabled=True, stuck_after_s=2.0)

        d1 = StuckNoteDetector(cfg1)
        d2 = StuckNoteDetector(cfg2)

        d1.on_note_on(60, 1, 0.0)
        d2.on_note_on(60, 1, 0.0)

        # At t=3: d1 not stuck (need 5), d2 is stuck (need 2)
        assert d1.stuck_notes(3.0) == []
        assert len(d2.stuck_notes(3.0)) == 1

    def test_panic_then_resume(self):
        """After panic, detector resumes normally."""
        cfg = StuckNoteConfig(enabled=True, stuck_after_s=5.0)
        detector = StuckNoteDetector(cfg)

        detector.on_note_on(60, 1, 0.0)
        detector.on_note_on(64, 1, 1.0)

        detector.panic()
        assert detector.open_count() == 0

        # Resume with new notes
        detector.on_note_on(67, 1, 10.0)
        assert detector.open_count() == 1
        assert detector.oldest_age(12.0) == 2.0

    def test_note_on_same_note_channel_multiple_times(self):
        """Rapid note-ons on same (note, channel) reset timer each time."""
        cfg = StuckNoteConfig(enabled=True, stuck_after_s=2.0)
        detector = StuckNoteDetector(cfg)

        detector.on_note_on(60, 1, 0.0)
        # At t=1, held 1s
        assert detector.stuck_notes(1.0) == []

        # Retrigger at t=1.5, resets timer
        detector.on_note_on(60, 1, 1.5)
        # At t=3, only 1.5s since reset, not stuck
        assert detector.stuck_notes(3.0) == []
        # At t=3.6, 2.1s since reset, now stuck
        assert len(detector.stuck_notes(3.6)) == 1
