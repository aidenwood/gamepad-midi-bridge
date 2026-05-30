"""Tests for note-timing accuracy meter."""

import pytest
from gamepad_midi_bridge.note_timing_accuracy import (
    TimingAccuracyConfig,
    TimingAccuracy,
    NoteTimingAccuracy,
)


class TestTimingAccuracyConfig:
    """Tests for TimingAccuracyConfig dataclass."""

    def test_default_config(self):
        """Default config should have sensible defaults."""
        cfg = TimingAccuracyConfig()
        assert cfg.bpm == 120.0
        assert cfg.subdivision == "1/16"
        assert cfg.tolerance_ms == 20.0
        assert cfg.max_samples == 1000

    def test_custom_config(self):
        """Custom config should respect provided values."""
        cfg = TimingAccuracyConfig(bpm=140, subdivision="1/8", tolerance_ms=30, max_samples=500)
        assert cfg.bpm == 140.0
        assert cfg.subdivision == "1/8"
        assert cfg.tolerance_ms == 30.0
        assert cfg.max_samples == 500

    def test_bpm_clamping_low(self):
        """BPM below 20 should clamp to 20."""
        cfg = TimingAccuracyConfig(bpm=10)
        assert cfg.bpm == 20.0

    def test_bpm_clamping_high(self):
        """BPM above 400 should clamp to 400."""
        cfg = TimingAccuracyConfig(bpm=500)
        assert cfg.bpm == 400.0

    def test_bpm_valid_range(self):
        """Valid BPM should pass through unchanged."""
        cfg = TimingAccuracyConfig(bpm=100)
        assert cfg.bpm == 100.0

    def test_invalid_subdivision_defaults(self):
        """Invalid subdivision should default to '1/16'."""
        cfg = TimingAccuracyConfig(subdivision="1/7")
        assert cfg.subdivision == "1/16"

    def test_valid_subdivision(self):
        """Valid subdivision should be preserved."""
        cfg = TimingAccuracyConfig(subdivision="1/4d")
        assert cfg.subdivision == "1/4d"

    def test_tolerance_clamping_low(self):
        """Tolerance below 1 should clamp to 1."""
        cfg = TimingAccuracyConfig(tolerance_ms=0.5)
        assert cfg.tolerance_ms == 1.0

    def test_tolerance_clamping_high(self):
        """Tolerance above 500 should clamp to 500."""
        cfg = TimingAccuracyConfig(tolerance_ms=600)
        assert cfg.tolerance_ms == 500.0

    def test_max_samples_clamping_low(self):
        """max_samples below 10 should clamp to 10."""
        cfg = TimingAccuracyConfig(max_samples=5)
        assert cfg.max_samples == 10

    def test_max_samples_clamping_high(self):
        """max_samples above 1000000 should clamp to 1000000."""
        cfg = TimingAccuracyConfig(max_samples=2000000)
        assert cfg.max_samples == 1000000

    def test_to_dict(self):
        """Config should serialize to dict."""
        cfg = TimingAccuracyConfig(bpm=140, subdivision="1/8", tolerance_ms=25, max_samples=500)
        data = cfg.to_dict()
        assert data["bpm"] == 140.0
        assert data["subdivision"] == "1/8"
        assert data["tolerance_ms"] == 25.0
        assert data["max_samples"] == 500

    def test_from_dict(self):
        """Config should deserialise from dict."""
        data = {"bpm": 140, "subdivision": "1/8", "tolerance_ms": 25, "max_samples": 500}
        cfg = TimingAccuracyConfig.from_dict(data)
        assert cfg.bpm == 140.0
        assert cfg.subdivision == "1/8"
        assert cfg.tolerance_ms == 25.0
        assert cfg.max_samples == 500

    def test_round_trip_serialization(self):
        """Config should round-trip through dict serialization."""
        original = TimingAccuracyConfig(bpm=150, subdivision="1/4d", tolerance_ms=35, max_samples=800)
        data = original.to_dict()
        restored = TimingAccuracyConfig.from_dict(data)
        assert restored.bpm == original.bpm
        assert restored.subdivision == original.subdivision
        assert restored.tolerance_ms == original.tolerance_ms
        assert restored.max_samples == original.max_samples

    def test_from_dict_with_clamping(self):
        """Deserialization should apply validation."""
        data = {"bpm": 500, "subdivision": "1/9", "tolerance_ms": 600, "max_samples": 5}
        cfg = TimingAccuracyConfig.from_dict(data)
        assert cfg.bpm == 400.0
        assert cfg.subdivision == "1/16"
        assert cfg.tolerance_ms == 500.0
        assert cfg.max_samples == 10


class TestTimingAccuracy:
    """Tests for TimingAccuracy dataclass."""

    def test_default_report(self):
        """Default report should be empty."""
        report = TimingAccuracy()
        assert report.on_count == 0
        assert report.ahead_count == 0
        assert report.behind_count == 0
        assert report.total == 0
        assert report.mean_offset_ms == 0.0
        assert report.worst_offset_ms == 0.0
        assert report.accuracy_pct == 0.0

    def test_to_dict(self):
        """Report should serialize to dict."""
        report = TimingAccuracy(on_count=5, ahead_count=2, behind_count=1, total=8,
                               mean_offset_ms=5.5, worst_offset_ms=15.0, accuracy_pct=62.5)
        data = report.to_dict()
        assert data["on_count"] == 5
        assert data["ahead_count"] == 2
        assert data["behind_count"] == 1
        assert data["total"] == 8
        assert data["mean_offset_ms"] == 5.5
        assert data["worst_offset_ms"] == 15.0
        assert data["accuracy_pct"] == 62.5

    def test_from_dict(self):
        """Report should deserialise from dict."""
        data = {"on_count": 5, "ahead_count": 2, "behind_count": 1, "total": 8,
                "mean_offset_ms": 5.5, "worst_offset_ms": 15.0, "accuracy_pct": 62.5}
        report = TimingAccuracy.from_dict(data)
        assert report.on_count == 5
        assert report.ahead_count == 2
        assert report.behind_count == 1
        assert report.total == 8
        assert report.mean_offset_ms == 5.5
        assert report.worst_offset_ms == 15.0
        assert report.accuracy_pct == 62.5

    def test_round_trip_serialization(self):
        """Report should round-trip through dict serialization."""
        original = TimingAccuracy(on_count=10, ahead_count=3, behind_count=2, total=15,
                                 mean_offset_ms=2.5, worst_offset_ms=12.0, accuracy_pct=66.67)
        data = original.to_dict()
        restored = TimingAccuracy.from_dict(data)
        assert restored.on_count == original.on_count
        assert restored.ahead_count == original.ahead_count
        assert restored.behind_count == original.behind_count
        assert restored.total == original.total
        assert restored.mean_offset_ms == original.mean_offset_ms
        assert restored.worst_offset_ms == original.worst_offset_ms
        assert restored.accuracy_pct == original.accuracy_pct


class TestNoteTimingAccuracy:
    """Tests for NoteTimingAccuracy class."""

    def test_empty_analyzer(self):
        """Empty analyzer should have zero samples and zero accuracy."""
        cfg = TimingAccuracyConfig(bpm=120, subdivision="1/16", tolerance_ms=20)
        meter = NoteTimingAccuracy(cfg)
        assert meter.total() == 0
        report = meter.analyze()
        assert report.total == 0
        assert report.accuracy_pct == 0.0

    def test_record_exact_grid_time(self):
        """Recording at exact grid time should give ~0 offset."""
        cfg = TimingAccuracyConfig(bpm=120, subdivision="1/16", tolerance_ms=20)
        meter = NoteTimingAccuracy(cfg, ref_start_s=0.0)
        offset = meter.record(0.125)
        assert pytest.approx(offset, abs=0.1) == 0.0

    def test_record_slightly_ahead(self):
        """Recording slightly before grid should give negative offset."""
        cfg = TimingAccuracyConfig(bpm=120, subdivision="1/16", tolerance_ms=20)
        meter = NoteTimingAccuracy(cfg, ref_start_s=0.0)
        offset = meter.record(0.115)
        assert offset < 0
        assert pytest.approx(abs(offset), abs=0.5) == 10.0

    def test_record_slightly_behind(self):
        """Recording slightly after grid should give positive offset."""
        cfg = TimingAccuracyConfig(bpm=120, subdivision="1/16", tolerance_ms=20)
        meter = NoteTimingAccuracy(cfg, ref_start_s=0.0)
        offset = meter.record(0.135)
        assert offset > 0
        assert pytest.approx(offset, abs=0.5) == 10.0

    def test_within_tolerance_on_count(self):
        """Notes within tolerance should increment on_count."""
        cfg = TimingAccuracyConfig(bpm=120, subdivision="1/16", tolerance_ms=20)
        meter = NoteTimingAccuracy(cfg, ref_start_s=0.0)
        meter.record(0.125)
        report = meter.analyze()
        assert report.on_count == 1
        assert report.ahead_count == 0
        assert report.behind_count == 0

    def test_ahead_of_tolerance_count(self):
        """Notes ahead of tolerance should increment ahead_count."""
        cfg = TimingAccuracyConfig(bpm=120, subdivision="1/16", tolerance_ms=20)
        meter = NoteTimingAccuracy(cfg, ref_start_s=0.0)
        meter.record(0.100)
        report = meter.analyze()
        assert report.on_count == 0
        assert report.ahead_count == 1
        assert report.behind_count == 0

    def test_behind_tolerance_count(self):
        """Notes behind tolerance should increment behind_count."""
        cfg = TimingAccuracyConfig(bpm=120, subdivision="1/16", tolerance_ms=20)
        meter = NoteTimingAccuracy(cfg, ref_start_s=0.0)
        meter.record(0.150)
        report = meter.analyze()
        assert report.on_count == 0
        assert report.ahead_count == 0
        assert report.behind_count == 1

    def test_mean_offset_calculation(self):
        """Mean offset should be average of all recorded offsets."""
        cfg = TimingAccuracyConfig(bpm=120, subdivision="1/16", tolerance_ms=20)
        meter = NoteTimingAccuracy(cfg, ref_start_s=0.0)
        meter.record(0.125)
        meter.record(0.135)
        meter.record(0.115)
        report = meter.analyze()
        assert pytest.approx(report.mean_offset_ms, abs=0.5) == 0.0

    def test_worst_offset_max_absolute(self):
        """Worst offset should be maximum absolute deviation."""
        cfg = TimingAccuracyConfig(bpm=120, subdivision="1/16", tolerance_ms=20)
        meter = NoteTimingAccuracy(cfg, ref_start_s=0.0)
        meter.record(0.125)
        meter.record(0.135)
        meter.record(0.090)
        report = meter.analyze()
        assert pytest.approx(report.worst_offset_ms, abs=0.5) == 35.0

    def test_accuracy_percentage(self):
        """Accuracy percentage should be (on_count / total) * 100."""
        cfg = TimingAccuracyConfig(bpm=120, subdivision="1/16", tolerance_ms=20)
        meter = NoteTimingAccuracy(cfg, ref_start_s=0.0)
        meter.record(0.125)
        meter.record(0.250)
        meter.record(0.100)
        meter.record(0.160)
        report = meter.analyze()
        assert report.total == 4
        assert report.on_count == 2
        assert pytest.approx(report.accuracy_pct, abs=0.1) == 50.0

    def test_max_samples_fifo(self):
        """Exceeding max_samples should drop oldest records (FIFO)."""
        cfg = TimingAccuracyConfig(bpm=120, subdivision="1/16", tolerance_ms=20, max_samples=50)
        meter = NoteTimingAccuracy(cfg, ref_start_s=0.0)
        # Record 51 samples; oldest should drop
        for i in range(51):
            meter.record(0.125 + i * 0.001)
        assert meter.total() == 50

    def test_clear(self):
        """Clear should remove all samples."""
        cfg = TimingAccuracyConfig(bpm=120, subdivision="1/16", tolerance_ms=20)
        meter = NoteTimingAccuracy(cfg, ref_start_s=0.0)
        meter.record(0.125)
        meter.record(0.250)
        assert meter.total() == 2
        meter.clear()
        assert meter.total() == 0
        report = meter.analyze()
        assert report.total == 0
        assert report.accuracy_pct == 0.0

    def test_total_count(self):
        """Total should return number of recorded samples."""
        cfg = TimingAccuracyConfig(bpm=120, subdivision="1/16", tolerance_ms=20)
        meter = NoteTimingAccuracy(cfg, ref_start_s=0.0)
        assert meter.total() == 0
        meter.record(0.125)
        assert meter.total() == 1
        meter.record(0.250)
        assert meter.total() == 2
        meter.record(0.375)
        assert meter.total() == 3

    def test_complex_timing_scenario(self):
        """Complex scenario with tighter tolerance."""
        cfg = TimingAccuracyConfig(bpm=120, subdivision="1/4", tolerance_ms=4)
        meter = NoteTimingAccuracy(cfg, ref_start_s=0.0)
        # At 120 BPM, 1/4 = 500ms
        meter.record(0.5)        # grid point: offset ≈ 0 (on)
        meter.record(1.0)        # grid point: offset ≈ 0 (on)
        meter.record(1.515)      # 15ms late (behind tolerance)
        meter.record(2.495)      # 5ms early (ahead)

        report = meter.analyze()
        assert report.total == 4
        assert report.on_count == 2
        assert report.ahead_count == 1
        assert report.behind_count == 1
        assert pytest.approx(report.accuracy_pct, abs=0.1) == 50.0

    def test_reference_start_time(self):
        """Reference start time should shift grid alignment."""
        cfg = TimingAccuracyConfig(bpm=120, subdivision="1/16", tolerance_ms=20)
        meter = NoteTimingAccuracy(cfg, ref_start_s=1.0)
        offset = meter.record(1.125)
        assert pytest.approx(offset, abs=0.1) == 0.0

    def test_different_subdivisions(self):
        """Different subdivisions should be measured correctly."""
        cfg = TimingAccuracyConfig(bpm=120, subdivision="1/8", tolerance_ms=20)
        meter = NoteTimingAccuracy(cfg, ref_start_s=0.0)
        offset1 = meter.record(0.250)
        offset2 = meter.record(0.260)
        assert pytest.approx(offset1, abs=0.1) == 0.0
        assert pytest.approx(offset2, abs=0.5) == 10.0

    def test_report_counts_sum_to_total(self):
        """on_count + ahead_count + behind_count should equal total."""
        cfg = TimingAccuracyConfig(bpm=120, subdivision="1/16", tolerance_ms=20)
        meter = NoteTimingAccuracy(cfg, ref_start_s=0.0)
        meter.record(0.125)
        meter.record(0.100)
        meter.record(0.150)
        meter.record(0.250)
        meter.record(0.080)
        meter.record(0.180)
        report = meter.analyze()
        assert report.on_count + report.ahead_count + report.behind_count == report.total
