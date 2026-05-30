"""Tests for stick drift detector module."""

import pytest
from gamepad_midi_bridge.stick_drift_detector import (
    DriftDetectorConfig,
    DriftReport,
    StickDriftDetector,
)


class TestDriftDetectorConfig:
    """Tests for DriftDetectorConfig dataclass."""

    def test_default_config(self):
        """Default config has standard thresholds."""
        cfg = DriftDetectorConfig()
        assert cfg.min_samples == 50
        assert cfg.minor_threshold == 0.05
        assert cfg.moderate_threshold == 0.15
        assert cfg.severe_threshold == 0.3

    def test_custom_config(self):
        """Can construct with custom values."""
        cfg = DriftDetectorConfig(
            min_samples=100,
            minor_threshold=0.08,
            moderate_threshold=0.2,
            severe_threshold=0.4,
        )
        assert cfg.min_samples == 100
        assert cfg.minor_threshold == 0.08
        assert cfg.moderate_threshold == 0.2
        assert cfg.severe_threshold == 0.4

    def test_min_samples_clamped_lower(self):
        """min_samples clamped to minimum 10."""
        cfg = DriftDetectorConfig(min_samples=5)
        assert cfg.min_samples == 10

    def test_min_samples_clamped_upper(self):
        """min_samples clamped to maximum 10000."""
        cfg = DriftDetectorConfig(min_samples=20000)
        assert cfg.min_samples == 10000

    def test_minor_threshold_clamped_lower(self):
        """minor_threshold clamped to minimum 0.0."""
        cfg = DriftDetectorConfig(minor_threshold=-0.1)
        assert cfg.minor_threshold == 0.0

    def test_minor_threshold_clamped_upper(self):
        """minor_threshold clamped to maximum 0.5."""
        cfg = DriftDetectorConfig(minor_threshold=1.0)
        assert cfg.minor_threshold == 0.5

    def test_moderate_threshold_clamped(self):
        """moderate_threshold clamped to 0..0.5."""
        cfg = DriftDetectorConfig(moderate_threshold=0.8)
        assert cfg.moderate_threshold == 0.5

    def test_severe_threshold_clamped(self):
        """severe_threshold clamped to 0..1.0."""
        cfg = DriftDetectorConfig(severe_threshold=2.0)
        assert cfg.severe_threshold == 1.0

    def test_to_dict(self):
        """to_dict serializes config to dictionary."""
        cfg = DriftDetectorConfig(
            min_samples=75,
            minor_threshold=0.08,
            moderate_threshold=0.2,
            severe_threshold=0.4,
        )
        d = cfg.to_dict()
        assert d["min_samples"] == 75
        assert d["minor_threshold"] == 0.08
        assert d["moderate_threshold"] == 0.2
        assert d["severe_threshold"] == 0.4

    def test_from_dict(self):
        """from_dict deserializes config from dictionary."""
        d = {
            "min_samples": 60,
            "minor_threshold": 0.06,
            "moderate_threshold": 0.18,
            "severe_threshold": 0.35,
        }
        cfg = DriftDetectorConfig.from_dict(d)
        assert cfg.min_samples == 60
        assert cfg.minor_threshold == 0.06
        assert cfg.moderate_threshold == 0.18
        assert cfg.severe_threshold == 0.35

    def test_from_dict_round_trip(self):
        """Round-trip: to_dict → from_dict preserves values."""
        original = DriftDetectorConfig(
            min_samples=80,
            minor_threshold=0.07,
            moderate_threshold=0.22,
            severe_threshold=0.38,
        )
        d = original.to_dict()
        restored = DriftDetectorConfig.from_dict(d)
        assert restored.min_samples == original.min_samples
        assert restored.minor_threshold == original.minor_threshold
        assert restored.moderate_threshold == original.moderate_threshold
        assert restored.severe_threshold == original.severe_threshold

    def test_from_dict_partial(self):
        """from_dict fills missing keys with defaults."""
        d = {"min_samples": 30}
        cfg = DriftDetectorConfig.from_dict(d)
        assert cfg.min_samples == 30
        assert cfg.minor_threshold == 0.05
        assert cfg.moderate_threshold == 0.15
        assert cfg.severe_threshold == 0.3


class TestDriftReport:
    """Tests for DriftReport dataclass."""

    def test_to_dict(self):
        """to_dict serializes report to dictionary."""
        report = DriftReport(
            is_drifting=True,
            drift_magnitude=0.15,
            drift_x=0.1,
            drift_y=0.1,
            severity="moderate",
            sample_count=50,
        )
        d = report.to_dict()
        assert d["is_drifting"] is True
        assert d["drift_magnitude"] == 0.15
        assert d["drift_x"] == 0.1
        assert d["drift_y"] == 0.1
        assert d["severity"] == "moderate"
        assert d["sample_count"] == 50

    def test_from_dict(self):
        """from_dict deserializes report from dictionary."""
        d = {
            "is_drifting": True,
            "drift_magnitude": 0.2,
            "drift_x": 0.15,
            "drift_y": 0.1,
            "severity": "moderate",
            "sample_count": 60,
        }
        report = DriftReport.from_dict(d)
        assert report.is_drifting is True
        assert report.drift_magnitude == 0.2
        assert report.drift_x == 0.15
        assert report.drift_y == 0.1
        assert report.severity == "moderate"
        assert report.sample_count == 60

    def test_round_trip_serialization(self):
        """Round-trip: to_dict → from_dict preserves values."""
        original = DriftReport(
            is_drifting=True,
            drift_magnitude=0.25,
            drift_x=0.2,
            drift_y=0.15,
            severity="severe",
            sample_count=100,
        )
        d = original.to_dict()
        restored = DriftReport.from_dict(d)
        assert restored.is_drifting == original.is_drifting
        assert restored.drift_magnitude == original.drift_magnitude
        assert restored.drift_x == original.drift_x
        assert restored.drift_y == original.drift_y
        assert restored.severity == original.severity
        assert restored.sample_count == original.sample_count


class TestStickDriftDetectorBasic:
    """Basic tests for StickDriftDetector."""

    def test_init(self):
        """StickDriftDetector initializes with config."""
        cfg = DriftDetectorConfig(min_samples=30)
        detector = StickDriftDetector(cfg)
        assert detector.cfg == cfg
        assert detector.sample_count() == 0

    def test_empty_analyze(self):
        """Analyze on empty detector returns no drift."""
        cfg = DriftDetectorConfig(min_samples=10)
        detector = StickDriftDetector(cfg)
        report = detector.analyze()
        assert report.is_drifting is False
        assert report.severity == "none"
        assert report.drift_magnitude == 0.0
        assert report.sample_count == 0

    def test_insufficient_samples_analyze(self):
        """Analyze with fewer than min_samples returns no drift."""
        cfg = DriftDetectorConfig(min_samples=50)
        detector = StickDriftDetector(cfg)
        for _ in range(10):
            detector.add_sample(0.0, 0.0)
        report = detector.analyze()
        assert report.is_drifting is False
        assert report.severity == "none"
        assert report.sample_count == 10


class TestStickDriftDetectorClamping:
    """Tests for sample clamping."""

    def test_add_sample_clamps_positive(self):
        """Samples beyond 1.0 are clamped to 1.0."""
        cfg = DriftDetectorConfig(min_samples=10)
        detector = StickDriftDetector(cfg)
        detector.add_sample(2.0, 1.5)
        detector.add_sample(0.5, 0.5)
        # Verify clamped values via analyze
        report = detector.analyze()
        assert report.drift_x < 1.0
        assert report.drift_y < 1.0

    def test_add_sample_clamps_negative(self):
        """Samples below -1.0 are clamped to -1.0."""
        cfg = DriftDetectorConfig(min_samples=10)
        detector = StickDriftDetector(cfg)
        detector.add_sample(-2.0, -1.5)
        detector.add_sample(0.0, 0.0)
        report = detector.analyze()
        assert report.drift_x >= -1.0
        assert report.drift_y >= -1.0


class TestStickDriftDetectorPerfectlycentred:
    """Tests for perfectly centred samples."""

    def test_all_zero_samples(self):
        """All samples at (0, 0) result in no drift."""
        cfg = DriftDetectorConfig(min_samples=20)
        detector = StickDriftDetector(cfg)
        for _ in range(20):
            detector.add_sample(0.0, 0.0)
        report = detector.analyze()
        assert report.is_drifting is False
        assert report.severity == "none"
        assert abs(report.drift_magnitude) < 0.001  # Floating point tolerance
        assert abs(report.drift_x) < 0.001
        assert abs(report.drift_y) < 0.001


class TestStickDriftDetectorMinorSeverity:
    """Tests for minor severity threshold."""

    def test_minor_x_drift(self):
        """Samples at (0.1, 0) result in minor severity."""
        cfg = DriftDetectorConfig(min_samples=10, minor_threshold=0.05)
        detector = StickDriftDetector(cfg)
        for _ in range(10):
            detector.add_sample(0.1, 0.0)
        report = detector.analyze()
        assert report.is_drifting is True
        assert report.severity == "minor"
        assert abs(report.drift_x - 0.1) < 0.001
        assert abs(report.drift_y - 0.0) < 0.001
        assert abs(report.drift_magnitude - 0.1) < 0.001

    def test_minor_y_drift(self):
        """Samples at (0, 0.1) result in minor severity."""
        cfg = DriftDetectorConfig(min_samples=10, minor_threshold=0.05)
        detector = StickDriftDetector(cfg)
        for _ in range(10):
            detector.add_sample(0.0, 0.1)
        report = detector.analyze()
        assert report.is_drifting is True
        assert report.severity == "minor"
        assert abs(report.drift_x - 0.0) < 0.001
        assert abs(report.drift_y - 0.1) < 0.001


class TestStickDriftDetectorModerateSeverity:
    """Tests for moderate severity threshold."""

    def test_moderate_drift(self):
        """Samples at (0.2, 0) result in moderate severity."""
        cfg = DriftDetectorConfig(
            min_samples=10, minor_threshold=0.05, moderate_threshold=0.15
        )
        detector = StickDriftDetector(cfg)
        for _ in range(10):
            detector.add_sample(0.2, 0.0)
        report = detector.analyze()
        assert report.is_drifting is True
        assert report.severity == "moderate"
        assert abs(report.drift_magnitude - 0.2) < 0.001


class TestStickDriftDetectorSevereSeverity:
    """Tests for severe severity threshold."""

    def test_severe_drift(self):
        """Samples at (0.5, 0) result in severe severity."""
        cfg = DriftDetectorConfig(
            min_samples=10,
            minor_threshold=0.05,
            moderate_threshold=0.15,
            severe_threshold=0.3,
        )
        detector = StickDriftDetector(cfg)
        for _ in range(10):
            detector.add_sample(0.5, 0.0)
        report = detector.analyze()
        assert report.is_drifting is True
        assert report.severity == "severe"
        assert abs(report.drift_magnitude - 0.5) < 0.001


class TestStickDriftDetectorDiagonalDrift:
    """Tests for diagonal drift (both x and y non-zero)."""

    def test_diagonal_drift_computed_correctly(self):
        """Diagonal samples (0.07, 0.07) magnitude is sqrt(0.07^2 + 0.07^2)."""
        cfg = DriftDetectorConfig(min_samples=10, minor_threshold=0.05)
        detector = StickDriftDetector(cfg)
        for _ in range(10):
            detector.add_sample(0.07, 0.07)
        report = detector.analyze()
        expected_magnitude = (0.07 ** 2 + 0.07 ** 2) ** 0.5  # ~0.099
        assert abs(report.drift_magnitude - expected_magnitude) < 0.001
        assert abs(report.drift_x - 0.07) < 0.001
        assert abs(report.drift_y - 0.07) < 0.001


class TestStickDriftDetectorMixedDrift:
    """Tests for mixed samples with different offsets."""

    def test_mixed_samples_mean_drift(self):
        """Mean is computed across varied samples."""
        cfg = DriftDetectorConfig(min_samples=10)
        detector = StickDriftDetector(cfg)
        # Add 10 samples with varying drift
        detector.add_sample(0.1, 0.0)
        detector.add_sample(0.2, 0.1)
        detector.add_sample(0.1, 0.2)
        detector.add_sample(0.0, 0.1)
        detector.add_sample(0.0, 0.0)
        detector.add_sample(0.15, 0.05)
        detector.add_sample(0.05, 0.15)
        detector.add_sample(0.1, 0.1)
        detector.add_sample(0.0, 0.0)
        detector.add_sample(0.1, 0.0)
        report = detector.analyze()
        # Mean x = (0.1 + 0.2 + 0.1 + 0.0 + 0.0 + 0.15 + 0.05 + 0.1 + 0.0 + 0.1) / 10 = 0.08
        # Mean y = (0.0 + 0.1 + 0.2 + 0.1 + 0.0 + 0.05 + 0.15 + 0.1 + 0.0 + 0.0) / 10 = 0.07
        expected_x = (0.1 + 0.2 + 0.1 + 0.0 + 0.0 + 0.15 + 0.05 + 0.1 + 0.0 + 0.1) / 10
        expected_y = (0.0 + 0.1 + 0.2 + 0.1 + 0.0 + 0.05 + 0.15 + 0.1 + 0.0 + 0.0) / 10
        assert abs(report.drift_x - expected_x) < 0.001
        assert abs(report.drift_y - expected_y) < 0.001


class TestStickDriftDetectorClear:
    """Tests for clear functionality."""

    def test_clear_removes_samples(self):
        """clear() empties the sample list."""
        cfg = DriftDetectorConfig(min_samples=10)
        detector = StickDriftDetector(cfg)
        for _ in range(20):
            detector.add_sample(0.1, 0.1)
        assert detector.sample_count() == 20
        detector.clear()
        assert detector.sample_count() == 0

    def test_clear_then_analyze_no_drift(self):
        """After clear(), analyze returns no drift."""
        cfg = DriftDetectorConfig(min_samples=10)
        detector = StickDriftDetector(cfg)
        for _ in range(20):
            detector.add_sample(0.5, 0.5)
        detector.clear()
        report = detector.analyze()
        assert report.is_drifting is False
        assert report.severity == "none"


class TestStickDriftDetectorSampleCount:
    """Tests for sample_count method."""

    def test_sample_count_tracks(self):
        """sample_count returns accurate count."""
        cfg = DriftDetectorConfig(min_samples=50)
        detector = StickDriftDetector(cfg)
        for i in range(1, 51):
            detector.add_sample(0.0, 0.0)
            assert detector.sample_count() == i

    def test_sample_count_after_clear(self):
        """sample_count is zero after clear()."""
        cfg = DriftDetectorConfig(min_samples=10)
        detector = StickDriftDetector(cfg)
        for _ in range(30):
            detector.add_sample(0.0, 0.0)
        detector.clear()
        assert detector.sample_count() == 0


class TestStickDriftDetectorThresholdBoundaries:
    """Tests for threshold boundary conditions."""

    def test_exactly_minor_threshold(self):
        """Drift exactly at minor_threshold is detected."""
        cfg = DriftDetectorConfig(
            min_samples=10,
            minor_threshold=0.1,
            moderate_threshold=0.2,
            severe_threshold=0.3,
        )
        detector = StickDriftDetector(cfg)
        for _ in range(10):
            detector.add_sample(0.1, 0.0)
        report = detector.analyze()
        assert report.is_drifting is True
        assert report.severity == "minor"

    def test_just_below_minor_threshold(self):
        """Drift just below minor_threshold is not detected."""
        cfg = DriftDetectorConfig(
            min_samples=10,
            minor_threshold=0.1,
            moderate_threshold=0.2,
            severe_threshold=0.3,
        )
        detector = StickDriftDetector(cfg)
        for _ in range(10):
            detector.add_sample(0.099, 0.0)
        report = detector.analyze()
        assert report.is_drifting is False
        assert report.severity == "none"

    def test_exactly_moderate_threshold(self):
        """Drift exactly at moderate_threshold is moderate."""
        cfg = DriftDetectorConfig(
            min_samples=10,
            minor_threshold=0.05,
            moderate_threshold=0.15,
            severe_threshold=0.3,
        )
        detector = StickDriftDetector(cfg)
        for _ in range(10):
            detector.add_sample(0.15, 0.0)
        report = detector.analyze()
        assert report.is_drifting is True
        assert report.severity == "moderate"

    def test_exactly_severe_threshold(self):
        """Drift exactly at severe_threshold is severe."""
        cfg = DriftDetectorConfig(
            min_samples=10,
            minor_threshold=0.05,
            moderate_threshold=0.15,
            severe_threshold=0.3,
        )
        detector = StickDriftDetector(cfg)
        for _ in range(10):
            detector.add_sample(0.3, 0.0)
        report = detector.analyze()
        assert report.is_drifting is True
        assert report.severity == "severe"


class TestStickDriftDetectorIntegration:
    """Integration tests."""

    def test_realistic_scenario(self):
        """Realistic scenario: add varying samples, clear, re-analyze."""
        cfg = DriftDetectorConfig(
            min_samples=20,
            minor_threshold=0.05,
            moderate_threshold=0.15,
            severe_threshold=0.3,
        )
        detector = StickDriftDetector(cfg)

        # Add samples with moderate drift
        for _ in range(20):
            detector.add_sample(0.18, 0.05)
        report1 = detector.analyze()
        assert report1.is_drifting is True
        assert report1.severity == "moderate"

        # Clear and add samples with no drift
        detector.clear()
        for _ in range(20):
            detector.add_sample(0.0, 0.0)
        report2 = detector.analyze()
        assert report2.is_drifting is False
        assert report2.severity == "none"

        # Clear and add severe drift samples
        detector.clear()
        for _ in range(20):
            detector.add_sample(0.6, 0.6)
        report3 = detector.analyze()
        assert report3.is_drifting is True
        assert report3.severity == "severe"
