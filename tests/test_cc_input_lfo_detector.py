"""
Tests for CC Input LFO Detector.
"""

import pytest
import math
from gamepad_midi_bridge.cc_input_lfo_detector import (
    LfoDetection,
    LfoDetectorConfig,
    CcInputLfoDetector,
)


class TestLfoDetection:
    """Tests for LfoDetection dataclass."""

    def test_to_dict(self):
        """Test serialization to dict."""
        det = LfoDetection(
            is_oscillating=True,
            estimated_period_s=0.5,
            estimated_amplitude=50.0,
            confidence=0.9,
            sample_count=100,
        )
        d = det.to_dict()
        assert d["is_oscillating"] is True
        assert d["estimated_period_s"] == 0.5
        assert d["estimated_amplitude"] == 50.0
        assert d["confidence"] == 0.9
        assert d["sample_count"] == 100

    def test_from_dict(self):
        """Test deserialization from dict."""
        d = {
            "is_oscillating": False,
            "estimated_period_s": None,
            "estimated_amplitude": None,
            "confidence": 0.0,
            "sample_count": 5,
        }
        det = LfoDetection.from_dict(d)
        assert det.is_oscillating is False
        assert det.estimated_period_s is None
        assert det.estimated_amplitude is None
        assert det.confidence == 0.0
        assert det.sample_count == 5

    def test_round_trip(self):
        """Test round-trip serialization."""
        original = LfoDetection(
            is_oscillating=True,
            estimated_period_s=1.0,
            estimated_amplitude=64.0,
            confidence=0.75,
            sample_count=250,
        )
        recovered = LfoDetection.from_dict(original.to_dict())
        assert recovered == original


class TestLfoDetectorConfig:
    """Tests for LfoDetectorConfig dataclass."""

    def test_defaults(self):
        """Test default config values."""
        cfg = LfoDetectorConfig()
        assert cfg.min_samples == 20
        assert cfg.max_samples == 500
        assert cfg.min_amplitude == 8.0
        assert cfg.min_zero_crossings == 4

    def test_clamping_min_samples(self):
        """Test min_samples is clamped to 4..1000."""
        cfg = LfoDetectorConfig(min_samples=2)
        assert cfg.min_samples == 4
        cfg = LfoDetectorConfig(min_samples=2000)
        assert cfg.min_samples == 1000

    def test_clamping_max_samples(self):
        """Test max_samples is clamped to 10..100000."""
        cfg = LfoDetectorConfig(max_samples=5)
        assert cfg.max_samples == 10
        cfg = LfoDetectorConfig(max_samples=200000)
        assert cfg.max_samples == 100000

    def test_clamping_min_amplitude(self):
        """Test min_amplitude is clamped to 1..127."""
        cfg = LfoDetectorConfig(min_amplitude=0.5)
        assert cfg.min_amplitude == 1.0
        cfg = LfoDetectorConfig(min_amplitude=200.0)
        assert cfg.min_amplitude == 127.0

    def test_clamping_min_zero_crossings(self):
        """Test min_zero_crossings is clamped to 2..100."""
        cfg = LfoDetectorConfig(min_zero_crossings=1)
        assert cfg.min_zero_crossings == 2
        cfg = LfoDetectorConfig(min_zero_crossings=150)
        assert cfg.min_zero_crossings == 100

    def test_to_dict(self):
        """Test config serialization."""
        cfg = LfoDetectorConfig(
            min_samples=30, max_samples=600, min_amplitude=10.0, min_zero_crossings=5
        )
        d = cfg.to_dict()
        assert d["min_samples"] == 30
        assert d["max_samples"] == 600
        assert d["min_amplitude"] == 10.0
        assert d["min_zero_crossings"] == 5

    def test_from_dict(self):
        """Test config deserialization."""
        d = {
            "min_samples": 25,
            "max_samples": 400,
            "min_amplitude": 12.0,
            "min_zero_crossings": 3,
        }
        cfg = LfoDetectorConfig.from_dict(d)
        assert cfg.min_samples == 25
        assert cfg.max_samples == 400
        assert cfg.min_amplitude == 12.0
        assert cfg.min_zero_crossings == 3

    def test_config_round_trip(self):
        """Test config round-trip serialization."""
        original = LfoDetectorConfig(
            min_samples=50, max_samples=800, min_amplitude=15.0, min_zero_crossings=6
        )
        recovered = LfoDetectorConfig.from_dict(original.to_dict())
        assert recovered.min_samples == original.min_samples
        assert recovered.max_samples == original.max_samples
        assert recovered.min_amplitude == original.min_amplitude
        assert recovered.min_zero_crossings == original.min_zero_crossings


class TestCcInputLfoDetector:
    """Tests for CcInputLfoDetector."""

    def test_empty(self):
        """Test empty detector returns not oscillating."""
        cfg = LfoDetectorConfig(min_samples=20)
        detector = CcInputLfoDetector(cfg)
        result = detector.analyze()
        assert result.is_oscillating is False
        assert result.estimated_period_s is None
        assert result.estimated_amplitude is None
        assert result.confidence == 0.0
        assert result.sample_count == 0

    def test_constant_values(self):
        """Test constant values do not oscillate."""
        cfg = LfoDetectorConfig(min_samples=20, min_zero_crossings=4)
        detector = CcInputLfoDetector(cfg)
        # Record 25 constant values
        for i in range(25):
            detector.record(64, float(i))
        result = detector.analyze()
        assert result.is_oscillating is False
        assert result.sample_count == 25

    def test_sine_like_input(self):
        """Test sine-like oscillation is detected."""
        cfg = LfoDetectorConfig(min_samples=20, min_zero_crossings=4, min_amplitude=5.0)
        detector = CcInputLfoDetector(cfg)
        # Square wave alternating 40..100, which clearly oscillates
        for i in range(30):
            if i % 2 == 0:
                detector.record(40, float(i))
            else:
                detector.record(100, float(i))
        result = detector.analyze()
        assert result.is_oscillating is True
        assert result.sample_count == 30

    def test_period_estimation(self):
        """Test period estimation is reasonable."""
        cfg = LfoDetectorConfig(min_samples=20, min_zero_crossings=4, min_amplitude=5.0)
        detector = CcInputLfoDetector(cfg)
        # Square wave alternating every 5 timesteps: period ~10
        for i in range(50):
            t = float(i)
            if (i // 5) % 2 == 0:
                detector.record(40, t)
            else:
                detector.record(100, t)
        result = detector.analyze()
        assert result.is_oscillating is True
        assert result.estimated_period_s is not None
        # 50 samples over 49 time units, ~5 zero-crossings = ~2.5 cycles
        # period = 49 / 2.5 ≈ 19.6 (or close)
        assert result.estimated_period_s > 0

    def test_amplitude_calculation(self):
        """Test amplitude is max - min."""
        cfg = LfoDetectorConfig(min_samples=20, min_zero_crossings=4, min_amplitude=5.0)
        detector = CcInputLfoDetector(cfg)
        # Oscillate between 40 and 100, amplitude = 60
        for i in range(30):
            if i % 2 == 0:
                detector.record(40, float(i))
            else:
                detector.record(100, float(i))
        result = detector.analyze()
        assert result.is_oscillating is True
        assert result.estimated_amplitude == 60

    def test_small_amplitude_rejected(self):
        """Test oscillation below min_amplitude is rejected."""
        cfg = LfoDetectorConfig(min_samples=20, min_zero_crossings=4, min_amplitude=20.0)
        detector = CcInputLfoDetector(cfg)
        # Oscillate between 60 and 65, amplitude = 5 < 20
        for i in range(30):
            if i % 2 == 0:
                detector.record(60, float(i))
            else:
                detector.record(65, float(i))
        result = detector.analyze()
        assert result.is_oscillating is False
        assert result.estimated_amplitude is None

    def test_confidence(self):
        """Test confidence increases with zero-crossings."""
        cfg = LfoDetectorConfig(min_samples=20, min_zero_crossings=4, min_amplitude=5.0)

        # Square wave: 30 samples alternating gives many zero-crossings, high confidence
        detector = CcInputLfoDetector(cfg)
        for i in range(30):
            if i % 2 == 0:
                detector.record(40, float(i))
            else:
                detector.record(100, float(i))
        result = detector.analyze()
        assert result.is_oscillating is True
        assert result.confidence > 0.5  # High confidence with lots of zero-crossings

        # Lower amplitude (but above threshold) still counts
        detector2 = CcInputLfoDetector(cfg)
        for i in range(20):
            if i % 2 == 0:
                detector2.record(60, float(i))
            else:
                detector2.record(80, float(i))  # Only 20 amplitude
        result2 = detector2.analyze()
        assert result2.is_oscillating is True
        assert result2.confidence > 0

    def test_value_clamping(self):
        """Test CC values are clamped to 0..127."""
        cfg = LfoDetectorConfig(min_samples=20)
        detector = CcInputLfoDetector(cfg)
        detector.record(-10, 0.0)
        detector.record(200, 1.0)
        detector.record(50, 2.0)
        # Check samples are clamped
        samples = detector._samples
        assert samples[0][1] == 0  # -10 clamped to 0
        assert samples[1][1] == 127  # 200 clamped to 127
        assert samples[2][1] == 50

    def test_max_samples_fifo(self):
        """Test FIFO eviction when exceeding max_samples."""
        cfg = LfoDetectorConfig(min_samples=5, max_samples=10)
        detector = CcInputLfoDetector(cfg)
        # Add 15 samples
        for i in range(15):
            detector.record(i % 128, float(i))
        # Only last 10 should remain
        assert len(detector._samples) == 10
        # First remaining should be at timestamp 5.0
        assert detector._samples[0] == (5.0, 5)
        assert detector._samples[-1] == (14.0, 14)

    def test_clear(self):
        """Test clear() empties samples."""
        cfg = LfoDetectorConfig(min_samples=20)
        detector = CcInputLfoDetector(cfg)
        for i in range(20):
            detector.record(64, float(i))
        assert detector.total() == 20
        detector.clear()
        assert detector.total() == 0
        result = detector.analyze()
        assert result.is_oscillating is False

    def test_total(self):
        """Test total() returns sample count."""
        cfg = LfoDetectorConfig()
        detector = CcInputLfoDetector(cfg)
        assert detector.total() == 0
        detector.record(50, 0.0)
        assert detector.total() == 1
        detector.record(60, 1.0)
        assert detector.total() == 2
