"""Tests for stick calibration module."""

import math

import pytest
from gamepad_midi_bridge.stick_calibration import (
    StickCalibrationConfig,
    StickCalibrationResult,
    StickCalibrator,
)


class TestStickCalibrationConfig:
    """Tests for StickCalibrationConfig dataclass."""

    def test_default_config(self):
        """Default config has standard values."""
        cfg = StickCalibrationConfig()
        assert cfg.min_samples == 30
        assert cfg.deadzone_padding == 0.05
        assert cfg.stable_std_threshold == 0.05

    def test_custom_config(self):
        """Can construct with custom values."""
        cfg = StickCalibrationConfig(
            min_samples=50,
            deadzone_padding=0.1,
            stable_std_threshold=0.08,
        )
        assert cfg.min_samples == 50
        assert cfg.deadzone_padding == 0.1
        assert cfg.stable_std_threshold == 0.08

    def test_clamp_min_samples_lower(self):
        """min_samples clamped to minimum of 5."""
        cfg = StickCalibrationConfig(min_samples=1)
        assert cfg.min_samples == 5

    def test_clamp_min_samples_upper(self):
        """min_samples clamped to maximum of 1000."""
        cfg = StickCalibrationConfig(min_samples=2000)
        assert cfg.min_samples == 1000

    def test_clamp_deadzone_padding_lower(self):
        """deadzone_padding clamped to minimum of 0."""
        cfg = StickCalibrationConfig(deadzone_padding=-0.1)
        assert cfg.deadzone_padding == 0.0

    def test_clamp_deadzone_padding_upper(self):
        """deadzone_padding clamped to maximum of 0.5."""
        cfg = StickCalibrationConfig(deadzone_padding=0.8)
        assert cfg.deadzone_padding == 0.5

    def test_clamp_stable_std_threshold_lower(self):
        """stable_std_threshold clamped to minimum of 0."""
        cfg = StickCalibrationConfig(stable_std_threshold=-0.05)
        assert cfg.stable_std_threshold == 0.0

    def test_clamp_stable_std_threshold_upper(self):
        """stable_std_threshold clamped to maximum of 0.5."""
        cfg = StickCalibrationConfig(stable_std_threshold=0.7)
        assert cfg.stable_std_threshold == 0.5

    def test_to_dict(self):
        """to_dict serializes config to dictionary."""
        cfg = StickCalibrationConfig(
            min_samples=40,
            deadzone_padding=0.08,
            stable_std_threshold=0.06,
        )
        d = cfg.to_dict()
        assert d["min_samples"] == 40
        assert d["deadzone_padding"] == 0.08
        assert d["stable_std_threshold"] == 0.06

    def test_from_dict(self):
        """from_dict deserializes config from dictionary."""
        d = {
            "min_samples": 25,
            "deadzone_padding": 0.03,
            "stable_std_threshold": 0.04,
        }
        cfg = StickCalibrationConfig.from_dict(d)
        assert cfg.min_samples == 25
        assert cfg.deadzone_padding == 0.03
        assert cfg.stable_std_threshold == 0.04

    def test_from_dict_with_defaults(self):
        """from_dict uses defaults for missing keys."""
        d = {"min_samples": 50}
        cfg = StickCalibrationConfig.from_dict(d)
        assert cfg.min_samples == 50
        assert cfg.deadzone_padding == 0.05
        assert cfg.stable_std_threshold == 0.05


class TestStickCalibrationResult:
    """Tests for StickCalibrationResult dataclass."""

    def test_to_dict(self):
        """to_dict serializes result to dictionary."""
        result = StickCalibrationResult(
            center_x=0.025,
            center_y=-0.015,
            deadzone_radius=0.12,
            sample_count=50,
            stable=True,
        )
        d = result.to_dict()
        assert d["center_x"] == 0.025
        assert d["center_y"] == -0.015
        assert d["deadzone_radius"] == 0.12
        assert d["sample_count"] == 50
        assert d["stable"] is True

    def test_from_dict(self):
        """from_dict deserializes result from dictionary."""
        d = {
            "center_x": 0.03,
            "center_y": -0.02,
            "deadzone_radius": 0.15,
            "sample_count": 60,
            "stable": False,
        }
        result = StickCalibrationResult.from_dict(d)
        assert result.center_x == 0.03
        assert result.center_y == -0.02
        assert result.deadzone_radius == 0.15
        assert result.sample_count == 60
        assert result.stable is False

    def test_round_trip_serialization(self):
        """to_dict + from_dict preserves values."""
        original = StickCalibrationResult(
            center_x=0.042,
            center_y=-0.018,
            deadzone_radius=0.125,
            sample_count=75,
            stable=True,
        )
        result = StickCalibrationResult.from_dict(original.to_dict())
        assert result.center_x == original.center_x
        assert result.center_y == original.center_y
        assert result.deadzone_radius == original.deadzone_radius
        assert result.sample_count == original.sample_count
        assert result.stable == original.stable


class TestStickCalibrator:
    """Tests for StickCalibrator class."""

    def test_init(self):
        """Initializes with empty samples list."""
        cfg = StickCalibrationConfig(min_samples=10)
        calibrator = StickCalibrator(cfg)
        assert calibrator.cfg == cfg
        assert calibrator._samples == []

    def test_empty_calibrator_returns_none(self):
        """result() returns None when no samples."""
        calibrator = StickCalibrator(StickCalibrationConfig(min_samples=5))
        assert calibrator.result() is None

    def test_fewer_than_min_samples_returns_none(self):
        """result() returns None when fewer than min_samples."""
        cfg = StickCalibrationConfig(min_samples=10)
        calibrator = StickCalibrator(cfg)
        for i in range(5):
            calibrator.add_sample(0.01, -0.01)
        assert calibrator.result() is None

    def test_add_sample_clamps_x_lower(self):
        """add_sample clamps x to -1.0 minimum."""
        calibrator = StickCalibrator(StickCalibrationConfig(min_samples=1))
        calibrator.add_sample(-2.0, 0.0)
        assert calibrator._samples[0][0] == -1.0

    def test_add_sample_clamps_x_upper(self):
        """add_sample clamps x to 1.0 maximum."""
        calibrator = StickCalibrator(StickCalibrationConfig(min_samples=1))
        calibrator.add_sample(2.0, 0.0)
        assert calibrator._samples[0][0] == 1.0

    def test_add_sample_clamps_y_lower(self):
        """add_sample clamps y to -1.0 minimum."""
        calibrator = StickCalibrator(StickCalibrationConfig(min_samples=1))
        calibrator.add_sample(0.0, -2.0)
        assert calibrator._samples[0][1] == -1.0

    def test_add_sample_clamps_y_upper(self):
        """add_sample clamps y to 1.0 maximum."""
        calibrator = StickCalibrator(StickCalibrationConfig(min_samples=1))
        calibrator.add_sample(0.0, 2.0)
        assert calibrator._samples[0][1] == 1.0

    def test_constant_samples_compute_center(self):
        """Center computed correctly for constant samples."""
        cfg = StickCalibrationConfig(min_samples=5)
        calibrator = StickCalibrator(cfg)
        for _ in range(10):
            calibrator.add_sample(0.05, 0.03)
        result = calibrator.result()
        assert result is not None
        assert abs(result.center_x - 0.05) < 0.001
        assert abs(result.center_y - 0.03) < 0.001

    def test_varied_samples_compute_center(self):
        """Center computed correctly for varied samples."""
        cfg = StickCalibrationConfig(min_samples=5)
        calibrator = StickCalibrator(cfg)
        # Add samples at various offsets around (0.02, -0.01)
        # Repeat to hit min_samples
        calibrator.add_sample(0.01, -0.02)
        calibrator.add_sample(0.02, 0.00)
        calibrator.add_sample(0.03, -0.01)
        calibrator.add_sample(0.02, -0.01)
        calibrator.add_sample(0.02, -0.01)
        result = calibrator.result()
        assert result is not None
        assert abs(result.center_x - 0.02) < 0.001
        assert abs(result.center_y - (-0.01)) < 0.001

    def test_deadzone_radius_includes_max_distance_and_padding(self):
        """deadzone_radius = max_distance + padding."""
        cfg = StickCalibrationConfig(min_samples=5, deadzone_padding=0.02)
        calibrator = StickCalibrator(cfg)
        # Place samples very close together around (0.05, 0.05)
        for _ in range(5):
            calibrator.add_sample(0.05, 0.05)
        result = calibrator.result()
        assert result is not None
        assert abs(result.center_x - 0.05) < 0.001
        assert abs(result.center_y - 0.05) < 0.001
        # All samples at center, max distance = 0, deadzone = 0 + 0.02 = 0.02
        assert abs(result.deadzone_radius - 0.02) < 0.001

    def test_stable_true_when_low_variance(self):
        """stable=True when standard deviation is low."""
        cfg = StickCalibrationConfig(
            min_samples=10,
            stable_std_threshold=0.05,
        )
        calibrator = StickCalibrator(cfg)
        # Add very consistent samples
        for i in range(20):
            calibrator.add_sample(0.02 + i * 0.0001, -0.01)
        result = calibrator.result()
        assert result is not None
        assert result.stable is True

    def test_stable_false_when_high_variance(self):
        """stable=False when standard deviation is high."""
        cfg = StickCalibrationConfig(
            min_samples=5,
            stable_std_threshold=0.05,
        )
        calibrator = StickCalibrator(cfg)
        # Add very inconsistent samples
        calibrator.add_sample(-0.5, -0.5)
        calibrator.add_sample(0.5, 0.5)
        calibrator.add_sample(-0.5, 0.5)
        calibrator.add_sample(0.5, -0.5)
        calibrator.add_sample(0.0, 0.0)
        result = calibrator.result()
        assert result is not None
        assert result.stable is False

    def test_sample_count_correct(self):
        """sample_count matches number of samples."""
        cfg = StickCalibrationConfig(min_samples=5)
        calibrator = StickCalibrator(cfg)
        for i in range(15):
            calibrator.add_sample(0.01, -0.01)
        result = calibrator.result()
        assert result is not None
        assert result.sample_count == 15

    def test_clear_drops_samples(self):
        """clear() drops all samples."""
        cfg = StickCalibrationConfig(min_samples=5)
        calibrator = StickCalibrator(cfg)
        for _ in range(10):
            calibrator.add_sample(0.05, 0.03)
        assert len(calibrator._samples) == 10
        calibrator.clear()
        assert len(calibrator._samples) == 0
        assert calibrator.result() is None


class TestSticksCalibrator_Apply:
    """Tests for StickCalibrator.apply static method."""

    def test_apply_with_sample_within_deadzone(self):
        """apply returns (0, 0) for samples within deadzone."""
        result = StickCalibrationResult(
            center_x=0.05,
            center_y=-0.02,
            deadzone_radius=0.1,
            sample_count=30,
            stable=True,
        )
        # Sample at center + small offset
        out_x, out_y = StickCalibrator.apply(0.055, -0.015, result)
        assert out_x == 0.0
        assert out_y == 0.0

    def test_apply_with_sample_at_deadzone_boundary(self):
        """apply returns (0, 0) for samples at deadzone boundary."""
        result = StickCalibrationResult(
            center_x=0.0,
            center_y=0.0,
            deadzone_radius=0.1,
            sample_count=30,
            stable=True,
        )
        # Sample exactly at deadzone radius
        out_x, out_y = StickCalibrator.apply(0.1, 0.0, result)
        assert out_x == 0.0
        assert out_y == 0.0

    def test_apply_with_sample_outside_deadzone(self):
        """apply returns offset values for samples outside deadzone."""
        result = StickCalibrationResult(
            center_x=0.05,
            center_y=-0.02,
            deadzone_radius=0.05,
            sample_count=30,
            stable=True,
        )
        # Sample far from center (0.3, 0.3)
        out_x, out_y = StickCalibrator.apply(0.3, 0.3, result)
        # Expected: (0.3 - 0.05, 0.3 - (-0.02)) = (0.25, 0.32)
        assert abs(out_x - 0.25) < 0.001
        assert abs(out_y - 0.32) < 0.001

    def test_apply_clamps_output_lower(self):
        """apply clamps output to -1.0 minimum."""
        result = StickCalibrationResult(
            center_x=0.0,
            center_y=0.0,
            deadzone_radius=0.0,
            sample_count=30,
            stable=True,
        )
        # Large negative sample should clamp
        out_x, out_y = StickCalibrator.apply(-2.0, 0.0, result)
        assert out_x == -1.0

    def test_apply_clamps_output_upper(self):
        """apply clamps output to 1.0 maximum."""
        result = StickCalibrationResult(
            center_x=0.0,
            center_y=0.0,
            deadzone_radius=0.0,
            sample_count=30,
            stable=True,
        )
        # Large positive sample should clamp
        out_x, out_y = StickCalibrator.apply(2.0, 0.0, result)
        assert out_x == 1.0

    def test_apply_full_range_mapping(self):
        """apply correctly maps full range with center offset."""
        result = StickCalibrationResult(
            center_x=0.1,
            center_y=-0.1,
            deadzone_radius=0.05,
            sample_count=30,
            stable=True,
        )
        # Far right stick position
        out_x, out_y = StickCalibrator.apply(1.0, 0.0, result)
        expected_x = 1.0 - 0.1  # = 0.9
        assert abs(out_x - expected_x) < 0.001
        assert abs(out_y - 0.1) < 0.001


class TestStickCalibratorIntegration:
    """Integration tests for stick calibration workflow."""

    def test_observe_and_apply_drift(self):
        """Observe drift samples, then apply calibration to new samples."""
        # Simulate stick with -0.05, +0.03 resting drift
        cfg = StickCalibrationConfig(min_samples=20, deadzone_padding=0.02)
        calibrator = StickCalibrator(cfg)

        # Observe resting stick (with drift)
        for _ in range(30):
            calibrator.add_sample(-0.05, 0.03)

        result = calibrator.result()
        assert result is not None
        assert abs(result.center_x - (-0.05)) < 0.001
        assert abs(result.center_y - 0.03) < 0.001

        # Now apply calibration to an actual stick movement
        # User moves stick to (0.4, 0.5) from resting position
        corrected_x, corrected_y = StickCalibrator.apply(0.4, 0.5, result)
        # Expected: (0.4 - (-0.05), 0.5 - 0.03) = (0.45, 0.47)
        assert abs(corrected_x - 0.45) < 0.001
        assert abs(corrected_y - 0.47) < 0.001

    def test_round_trip_config_and_result(self):
        """Serialize and deserialize config and result together."""
        cfg = StickCalibrationConfig(
            min_samples=40,
            deadzone_padding=0.08,
            stable_std_threshold=0.06,
        )

        # Run calibration
        calibrator = StickCalibrator(cfg)
        for i in range(50):
            calibrator.add_sample(0.02 + i * 0.0001, -0.01)
        result = calibrator.result()

        # Serialize both
        cfg_dict = cfg.to_dict()
        result_dict = result.to_dict()

        # Deserialize
        cfg_restored = StickCalibrationConfig.from_dict(cfg_dict)
        result_restored = StickCalibrationResult.from_dict(result_dict)

        # Verify restoration
        assert cfg_restored.min_samples == 40
        assert cfg_restored.deadzone_padding == 0.08
        assert abs(result_restored.center_x - result.center_x) < 0.001
        assert result_restored.stable == result.stable

    def test_manual_calibration_example_from_spec(self):
        """Example from the spec: constant 0.05, 0.03 should yield that center."""
        cfg = StickCalibrationConfig(min_samples=5)
        calibrator = StickCalibrator(cfg)
        # Add samples: 0.02 + i*0.001 for i in range(10) + constant y=-0.01
        for i in range(10):
            calibrator.add_sample(0.02 + i * 0.001, -0.01)
        result = calibrator.result()
        assert result is not None
        # center_x should be mean of [0.02, 0.021, 0.022, ..., 0.029] ≈ 0.0245
        assert abs(result.center_x - 0.0245) < 0.0005
        assert abs(result.center_y - (-0.01)) < 0.001
        assert result.stable is True
