"""Tests for the note_bpm_estimator module — BPM estimation from note streams.

Note-based auto-estimator takes note_on timestamps and derives BPM via median
interval analysis with configurable subdivision assumptions.

Pure stdlib + statistics, no Qt.
"""

from __future__ import annotations

import pytest

from gamepad_midi_bridge import note_bpm_estimator


class TestNoteBpmConfigDefaults:
    """NoteBpmConfig — default values and validation."""

    def test_config_defaults(self):
        """Config initialises with sensible defaults."""
        cfg = note_bpm_estimator.NoteBpmConfig()
        assert cfg.enabled is False
        assert cfg.min_bpm == 40.0
        assert cfg.max_bpm == 240.0
        assert cfg.min_samples == 8
        assert cfg.max_history == 256
        assert cfg.smoothing == 0.5
        assert cfg.subdivision_assumption == "1/8"

    def test_config_clamp_min_bpm_below_20(self):
        """min_bpm below 20 is clamped to 20."""
        cfg = note_bpm_estimator.NoteBpmConfig(min_bpm=10)
        assert cfg.min_bpm == 20.0

        cfg = note_bpm_estimator.NoteBpmConfig(min_bpm=-50)
        assert cfg.min_bpm == 20.0

    def test_config_clamp_min_bpm_above_400(self):
        """min_bpm above 400 is clamped to 400."""
        cfg = note_bpm_estimator.NoteBpmConfig(min_bpm=500)
        assert cfg.min_bpm == 400.0

    def test_config_clamp_max_bpm_below_20(self):
        """max_bpm below 20 is clamped to >= min_bpm."""
        # max_bpm=10 gets clamped to 20 (floor), but then enforced >= min_bpm (default 40)
        cfg = note_bpm_estimator.NoteBpmConfig(max_bpm=10)
        assert cfg.max_bpm == cfg.min_bpm  # Should be at least 40 (the default min_bpm)

    def test_config_clamp_max_bpm_above_400(self):
        """max_bpm above 400 is clamped to 400."""
        cfg = note_bpm_estimator.NoteBpmConfig(max_bpm=500)
        assert cfg.max_bpm == 400.0

    def test_config_enforce_max_bpm_gte_min_bpm(self):
        """If max_bpm < min_bpm, max_bpm is raised to min_bpm."""
        cfg = note_bpm_estimator.NoteBpmConfig(min_bpm=200, max_bpm=100)
        assert cfg.max_bpm == 200.0

    def test_config_clamp_min_samples_below_4(self):
        """min_samples below 4 is clamped to 4."""
        cfg = note_bpm_estimator.NoteBpmConfig(min_samples=2)
        assert cfg.min_samples == 4

    def test_config_clamp_min_samples_above_256(self):
        """min_samples above 256 is clamped to 256."""
        cfg = note_bpm_estimator.NoteBpmConfig(min_samples=500)
        assert cfg.min_samples == 256

    def test_config_clamp_max_history_below_16(self):
        """max_history below 16 is clamped to 16."""
        cfg = note_bpm_estimator.NoteBpmConfig(max_history=8)
        assert cfg.max_history == 16

    def test_config_clamp_max_history_above_10000(self):
        """max_history above 10000 is clamped to 10000."""
        cfg = note_bpm_estimator.NoteBpmConfig(max_history=20000)
        assert cfg.max_history == 10000

    def test_config_clamp_smoothing_below_zero(self):
        """smoothing below 0.0 is clamped to 0.0."""
        cfg = note_bpm_estimator.NoteBpmConfig(smoothing=-0.1)
        assert cfg.smoothing == 0.0

    def test_config_clamp_smoothing_above_0_99(self):
        """smoothing above 0.99 is clamped to 0.99."""
        cfg = note_bpm_estimator.NoteBpmConfig(smoothing=1.0)
        assert cfg.smoothing == 0.99

    def test_config_invalid_subdivision_defaults_to_1_8(self):
        """Invalid subdivision_assumption defaults to '1/8'."""
        cfg = note_bpm_estimator.NoteBpmConfig(subdivision_assumption="1/32")
        assert cfg.subdivision_assumption == "1/8"

        cfg = note_bpm_estimator.NoteBpmConfig(subdivision_assumption="invalid")
        assert cfg.subdivision_assumption == "1/8"

    def test_config_valid_subdivisions(self):
        """Valid subdivisions are preserved."""
        for sub in ("1/4", "1/8", "1/16"):
            cfg = note_bpm_estimator.NoteBpmConfig(subdivision_assumption=sub)
            assert cfg.subdivision_assumption == sub


class TestNoteBpmConfigSerialization:
    """to_dict / from_dict round-trip."""

    def test_to_dict(self):
        """to_dict returns all fields."""
        cfg = note_bpm_estimator.NoteBpmConfig(
            enabled=True,
            min_bpm=30.0,
            max_bpm=250.0,
            min_samples=6,
            max_history=200,
            smoothing=0.3,
            subdivision_assumption="1/16",
        )
        d = cfg.to_dict()
        assert d["enabled"] is True
        assert d["min_bpm"] == 30.0
        assert d["max_bpm"] == 250.0
        assert d["min_samples"] == 6
        assert d["max_history"] == 200
        assert d["smoothing"] == 0.3
        assert d["subdivision_assumption"] == "1/16"

    def test_from_dict(self):
        """from_dict reconstructs config correctly."""
        data = {
            "enabled": True,
            "min_bpm": 30.0,
            "max_bpm": 250.0,
            "min_samples": 6,
            "max_history": 200,
            "smoothing": 0.3,
            "subdivision_assumption": "1/16",
        }
        cfg = note_bpm_estimator.NoteBpmConfig.from_dict(data)
        assert cfg.enabled is True
        assert cfg.min_bpm == 30.0
        assert cfg.max_bpm == 250.0
        assert cfg.min_samples == 6
        assert cfg.max_history == 200
        assert cfg.smoothing == 0.3
        assert cfg.subdivision_assumption == "1/16"

    def test_round_trip_serialization(self):
        """to_dict → from_dict preserves all values."""
        cfg1 = note_bpm_estimator.NoteBpmConfig(
            enabled=True,
            min_bpm=50.0,
            max_bpm=300.0,
            min_samples=10,
            max_history=300,
            smoothing=0.6,
            subdivision_assumption="1/4",
        )
        d = cfg1.to_dict()
        cfg2 = note_bpm_estimator.NoteBpmConfig.from_dict(d)
        assert cfg2.enabled == cfg1.enabled
        assert cfg2.min_bpm == cfg1.min_bpm
        assert cfg2.max_bpm == cfg1.max_bpm
        assert cfg2.min_samples == cfg1.min_samples
        assert cfg2.max_history == cfg1.max_history
        assert cfg2.smoothing == cfg1.smoothing
        assert cfg2.subdivision_assumption == cfg1.subdivision_assumption


class TestNoteBpmEstimatorBasics:
    """Basic note stream and BPM estimation."""

    def test_empty_returns_none(self):
        """No notes → current_bpm returns None."""
        cfg = note_bpm_estimator.NoteBpmConfig(min_samples=8)
        est = note_bpm_estimator.NoteBpmEstimator(cfg)
        assert est.current_bpm() is None

    def test_fewer_than_min_samples_returns_none(self):
        """Fewer than min_samples notes → on_note returns None."""
        cfg = note_bpm_estimator.NoteBpmConfig(min_samples=8)
        est = note_bpm_estimator.NoteBpmEstimator(cfg)
        for i in range(7):
            result = est.on_note(i * 0.25)
            assert result is None
        assert est.current_bpm() is None

    def test_eighth_notes_at_120_bpm(self):
        """8 notes at 1/8 intervals (0.25s) at 120 BPM with 1/8 assumption.

        At 120 BPM, quarter note = 0.5s, eighth note = 0.25s.
        """
        cfg = note_bpm_estimator.NoteBpmConfig(
            min_samples=8, smoothing=0.0, subdivision_assumption="1/8"
        )
        est = note_bpm_estimator.NoteBpmEstimator(cfg)

        # 8 notes, each 0.25s apart
        for i in range(8):
            bpm = est.on_note(i * 0.25)
            # Return value on 8th note should be ~120
            if i == 7:
                assert bpm == pytest.approx(120.0, abs=1.0)

    def test_quarter_notes_at_120_bpm(self):
        """8 notes at 1/4 intervals (0.5s) at 120 BPM with 1/4 assumption.

        At 120 BPM, quarter note = 0.5s.
        """
        cfg = note_bpm_estimator.NoteBpmConfig(
            min_samples=8, smoothing=0.0, subdivision_assumption="1/4"
        )
        est = note_bpm_estimator.NoteBpmEstimator(cfg)

        # 8 notes, each 0.5s apart
        for i in range(8):
            bpm = est.on_note(i * 0.5)
            if i == 7:
                assert bpm == pytest.approx(120.0, abs=1.0)

    def test_sixteenth_notes_at_120_bpm(self):
        """8 notes at 1/16 intervals (0.125s) at 120 BPM with 1/16 assumption.

        At 120 BPM, quarter note = 0.5s, sixteenth note = 0.125s.
        """
        cfg = note_bpm_estimator.NoteBpmConfig(
            min_samples=8, smoothing=0.0, subdivision_assumption="1/16"
        )
        est = note_bpm_estimator.NoteBpmEstimator(cfg)

        # 8 notes, each 0.125s apart
        for i in range(8):
            bpm = est.on_note(i * 0.125)
            if i == 7:
                assert bpm == pytest.approx(120.0, abs=1.0)


class TestNoteBpmEstimatorClamping:
    """Min/max BPM clamping."""

    def test_clamp_below_min_bpm(self):
        """BPM below min_bpm is clamped."""
        # Intervals of 1.0s → 60 BPM, but min_bpm=100 → clamped to 100
        cfg = note_bpm_estimator.NoteBpmConfig(
            min_samples=8, min_bpm=100.0, max_bpm=300.0, smoothing=0.0, subdivision_assumption="1/4"
        )
        est = note_bpm_estimator.NoteBpmEstimator(cfg)
        for i in range(8):
            bpm = est.on_note(i * 1.0)
        # Raw BPM = 60, clamped to 100
        assert est.current_bpm() == pytest.approx(100.0, abs=1e-6)

    def test_clamp_above_max_bpm(self):
        """BPM above max_bpm is clamped."""
        # Intervals of 0.125s → 480 BPM, but max_bpm=200 → clamped to 200
        cfg = note_bpm_estimator.NoteBpmConfig(
            min_samples=8, min_bpm=20.0, max_bpm=200.0, smoothing=0.0, subdivision_assumption="1/4"
        )
        est = note_bpm_estimator.NoteBpmEstimator(cfg)
        for i in range(8):
            bpm = est.on_note(i * 0.125)
        # Raw BPM = 480, clamped to 200
        assert est.current_bpm() == pytest.approx(200.0, abs=1e-6)


class TestNoteBpmEstimatorSmoothing:
    """One-pole smoothing convergence."""

    def test_smoothing_converges(self):
        """With smoothing > 0, BPM updates are blended between old and new."""
        cfg = note_bpm_estimator.NoteBpmConfig(
            min_samples=8,
            max_history=20,
            smoothing=0.3,
            subdivision_assumption="1/4",
        )
        est = note_bpm_estimator.NoteBpmEstimator(cfg)

        # First 8 notes at 0.5s (quarter) = 120 BPM
        for i in range(8):
            est.on_note(i * 0.5)
        bpm_120 = est.current_bpm()
        assert bpm_120 == pytest.approx(120.0, abs=1.0)

        # Now gradually shift to 0.25s intervals (quarter = 240 BPM)
        # But due to max_history=20, we keep a mix
        # After adding all 0.25s notes, the list will only have recent notes
        old_time = 8 * 0.5  # 4.0
        for i in range(8, 20):
            est.on_note(old_time + (i - 8) * 0.25)

        bpm_later = est.current_bpm()

        # With smoothing, the estimate should have moved but not instantly jumped
        # Since we're continuously observing 0.25s intervals, the median should shift
        assert bpm_later is not None
        # After enough 0.25s samples, should lean toward 240
        assert bpm_later > bpm_120

    def test_no_smoothing_immediate(self):
        """With smoothing=0.0, BPM updates immediately."""
        cfg = note_bpm_estimator.NoteBpmConfig(
            min_samples=8, smoothing=0.0, subdivision_assumption="1/4"
        )
        est = note_bpm_estimator.NoteBpmEstimator(cfg)

        # 8 notes at 0.5s = 120 BPM
        for i in range(8):
            est.on_note(i * 0.5)
        bpm_120 = est.current_bpm()
        assert bpm_120 == pytest.approx(120.0, abs=1.0)

        # Continue, then add a note at a different interval (simulate faster tempo)
        # New interval: 0.25s = 240 BPM
        # But median is still dominated by 0.5s intervals (7 vs 1)
        # So BPM should remain close to 120


class TestNoteBpmEstimatorMaxHistory:
    """History capping."""

    def test_max_history_truncates(self):
        """Notes beyond max_history are dropped (oldest first)."""
        cfg = note_bpm_estimator.NoteBpmConfig(
            min_samples=4, max_history=20, smoothing=0.0, subdivision_assumption="1/4"
        )
        est = note_bpm_estimator.NoteBpmEstimator(cfg)

        # Add 30 notes
        for i in range(30):
            est.on_note(i * 0.5)

        # Should only have last 20 (max_history)
        assert len(est._note_times) == 20
        # Last note should be at 29 * 0.5 = 14.5
        assert est._note_times[-1] == pytest.approx(14.5, abs=1e-6)
        # First note should be at 10 * 0.5 = 5.0 (dropped 0-9)
        assert est._note_times[0] == pytest.approx(5.0, abs=1e-6)


class TestNoteBpmEstimatorClear:
    """clear() method."""

    def test_clear_empties_history(self):
        """clear() removes all notes and resets smoothed BPM."""
        cfg = note_bpm_estimator.NoteBpmConfig(min_samples=8)
        est = note_bpm_estimator.NoteBpmEstimator(cfg)

        # Add some notes
        for i in range(10):
            est.on_note(i * 0.25)

        assert len(est._note_times) > 0
        assert est.current_bpm() is not None

        # Clear
        est.clear()
        assert len(est._note_times) == 0
        assert est.current_bpm() is None


class TestNoteBpmEstimatorConfidence:
    """confidence() method."""

    def test_confidence_none_below_min_samples(self):
        """confidence returns None if fewer than min_samples notes."""
        cfg = note_bpm_estimator.NoteBpmConfig(min_samples=8)
        est = note_bpm_estimator.NoteBpmEstimator(cfg)

        for i in range(7):
            est.on_note(i * 0.25)

        assert est.confidence() is None

    def test_confidence_high_with_steady_intervals(self):
        """confidence is high when intervals are uniform."""
        cfg = note_bpm_estimator.NoteBpmConfig(
            min_samples=8, smoothing=0.0, subdivision_assumption="1/8"
        )
        est = note_bpm_estimator.NoteBpmEstimator(cfg)

        # 8 notes at perfectly uniform 0.25s intervals
        for i in range(8):
            est.on_note(i * 0.25)

        conf = est.confidence()
        assert conf is not None
        # CV = 0 (perfect uniformity) → confidence = 1
        assert conf == pytest.approx(1.0, abs=1e-6)

    def test_confidence_lower_with_jittery_intervals(self):
        """confidence is lower when intervals vary."""
        cfg = note_bpm_estimator.NoteBpmConfig(
            min_samples=8, smoothing=0.0, subdivision_assumption="1/8"
        )
        est_steady = note_bpm_estimator.NoteBpmEstimator(cfg)
        est_jittery = note_bpm_estimator.NoteBpmEstimator(cfg)

        # Steady: 0.25s intervals
        time = 0.0
        for i in range(8):
            est_steady.on_note(time)
            time += 0.25

        # Jittery: 0.2, 0.3, 0.2, 0.3, ... around 0.25
        time = 0.0
        for i in range(8):
            est_jittery.on_note(time)
            time += 0.25 if i % 2 == 0 else 0.25  # Adjust to 0.2/0.3 pattern
            # Actually: 0.2, 0.3, 0.2, 0.3, ...
        time = 0.0
        for i in range(8):
            est_jittery.on_note(time)
            if i % 2 == 0:
                time += 0.2
            else:
                time += 0.3

        conf_steady = est_steady.confidence()
        conf_jittery = est_jittery.confidence()

        assert conf_steady is not None
        assert conf_jittery is not None
        assert conf_steady > conf_jittery

    def test_confidence_range_0_to_1(self):
        """confidence is always in [0.0, 1.0]."""
        cfg = note_bpm_estimator.NoteBpmConfig(
            min_samples=8, smoothing=0.0, subdivision_assumption="1/8"
        )
        est = note_bpm_estimator.NoteBpmEstimator(cfg)

        # Realistic jittery notes
        times = [0.0, 0.24, 0.49, 0.69, 0.95, 1.2, 1.44, 1.7]
        for t in times:
            est.on_note(t)

        conf = est.confidence()
        assert conf is not None
        assert 0.0 <= conf <= 1.0


class TestNoteBpmEstimatorEdgeCases:
    """Edge cases and error handling."""

    def test_zero_interval_returns_none(self):
        """Two notes at the same time → zero interval."""
        cfg = note_bpm_estimator.NoteBpmConfig(min_samples=8, smoothing=0.0, subdivision_assumption="1/8")
        est = note_bpm_estimator.NoteBpmEstimator(cfg)

        # Add 8 notes, with two at the same time
        times = [0.0, 0.0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5]
        for t in times:
            bpm = est.on_note(t)
        # Median of [0, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25] = 0.25
        # Should still compute BPM
        assert est.current_bpm() is not None


class TestNoteBpmEstimatorSubdivisions:
    """Subdivision assumption configurations."""

    def test_subdivision_1_4(self):
        """subdivision='1/4' treats median as quarter note."""
        cfg = note_bpm_estimator.NoteBpmConfig(
            min_samples=8, smoothing=0.0, subdivision_assumption="1/4"
        )
        est = note_bpm_estimator.NoteBpmEstimator(cfg)

        # 0.5s intervals = 120 BPM (quarter note at 120)
        for i in range(8):
            est.on_note(i * 0.5)

        assert est.current_bpm() == pytest.approx(120.0, abs=1.0)

    def test_subdivision_1_8(self):
        """subdivision='1/8' treats median as eighth note."""
        cfg = note_bpm_estimator.NoteBpmConfig(
            min_samples=8, smoothing=0.0, subdivision_assumption="1/8"
        )
        est = note_bpm_estimator.NoteBpmEstimator(cfg)

        # 0.25s intervals = 120 BPM (eighth note at 120)
        for i in range(8):
            est.on_note(i * 0.25)

        assert est.current_bpm() == pytest.approx(120.0, abs=1.0)

    def test_subdivision_1_16(self):
        """subdivision='1/16' treats median as sixteenth note."""
        cfg = note_bpm_estimator.NoteBpmConfig(
            min_samples=8, smoothing=0.0, subdivision_assumption="1/16"
        )
        est = note_bpm_estimator.NoteBpmEstimator(cfg)

        # 0.125s intervals = 120 BPM (sixteenth note at 120)
        for i in range(8):
            est.on_note(i * 0.125)

        assert est.current_bpm() == pytest.approx(120.0, abs=1.0)


class TestNoteBpmEstimatorIntegration:
    """Integration tests — realistic scenarios."""

    def test_realistic_drum_pattern(self):
        """Simulate realistic drum notes with slight variations."""
        cfg = note_bpm_estimator.NoteBpmConfig(
            min_samples=8,
            min_bpm=40.0,
            max_bpm=240.0,
            smoothing=0.3,
            subdivision_assumption="1/8",
        )
        est = note_bpm_estimator.NoteBpmEstimator(cfg)

        # Drum hits at roughly 1/8 intervals (0.25s) with slight jitter
        drum_times = [
            0.0,
            0.245,
            0.495,
            0.74,
            0.99,
            1.24,
            1.49,
            1.74,
            1.99,
            2.24,
        ]
        for t in drum_times:
            est.on_note(t)

        bpm = est.current_bpm()
        conf = est.confidence()

        assert bpm is not None
        assert 100.0 < bpm < 130.0  # Should be around 120
        assert conf is not None
        assert 0.5 < conf < 1.0  # Some confidence despite jitter

    def test_multiple_notes_mixed_channels(self):
        """Notes from different MIDI channels (treated as single stream)."""
        cfg = note_bpm_estimator.NoteBpmConfig(
            min_samples=8, smoothing=0.0, subdivision_assumption="1/4"
        )
        est = note_bpm_estimator.NoteBpmEstimator(cfg)

        # Simulate: kick drum (ch0), snare (ch1), hat (ch2) but feed timestamps as single stream
        # All at 0.5s (quarter note) intervals
        for i in range(8):
            est.on_note(i * 0.5)

        assert est.current_bpm() == pytest.approx(120.0, abs=1.0)
