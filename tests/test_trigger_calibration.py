"""Tests for trigger_calibration module."""
from __future__ import annotations

import pytest

from gamepad_midi_bridge.trigger_calibration import (
    TriggerCalibrationConfig,
    TriggerCalibrationResult,
    TriggerCalibrator,
)


def make_calibrator(
    peak_window: int = 50, min_samples: int = 10, padding_above: float = 0.02
) -> TriggerCalibrator:
    """Create a fresh TriggerCalibrator for each test.
    
    Note: Default min_samples is 10 for testing.
    Individual tests can override this.
    """
    cfg = TriggerCalibrationConfig(
        peak_window=peak_window, min_samples=min_samples, padding_above=padding_above
    )
    return TriggerCalibrator(cfg)


# ---------------------------------------------------------------------------
# config: validation and serialization
# ---------------------------------------------------------------------------


def test_config_defaults():
    """Default config has peak_window=50, min_samples=100, padding_above=0.02."""
    cfg = TriggerCalibrationConfig()
    assert cfg.peak_window == 50
    assert cfg.min_samples == 100
    assert cfg.padding_above == 0.02


def test_config_peak_window_clamped_low():
    """peak_window < 3 is clamped to 3."""
    cfg = TriggerCalibrationConfig(peak_window=1)
    assert cfg.peak_window == 3


def test_config_peak_window_clamped_high():
    """peak_window > 1000 is clamped to 1000."""
    cfg = TriggerCalibrationConfig(peak_window=2000)
    assert cfg.peak_window == 1000


def test_config_min_samples_clamped_low():
    """min_samples < 10 is clamped to 10."""
    cfg = TriggerCalibrationConfig(min_samples=5)
    assert cfg.min_samples == 10


def test_config_min_samples_clamped_high():
    """min_samples > 10000 is clamped to 10000."""
    cfg = TriggerCalibrationConfig(min_samples=20000)
    assert cfg.min_samples == 10000


def test_config_padding_above_clamped_low():
    """padding_above < 0.0 is clamped to 0.0."""
    cfg = TriggerCalibrationConfig(padding_above=-0.1)
    assert cfg.padding_above == 0.0


def test_config_padding_above_clamped_high():
    """padding_above > 0.5 is clamped to 0.5."""
    cfg = TriggerCalibrationConfig(padding_above=0.75)
    assert cfg.padding_above == 0.5


def test_config_to_dict():
    """Config round-trip serialization: to_dict() -> from_dict()."""
    cfg1 = TriggerCalibrationConfig(
        peak_window=30, min_samples=50, padding_above=0.05
    )
    d = cfg1.to_dict()
    cfg2 = TriggerCalibrationConfig.from_dict(d)
    assert cfg2.peak_window == 30
    assert cfg2.min_samples == 50
    assert cfg2.padding_above == 0.05


def test_result_to_dict():
    """Result round-trip serialization: to_dict() -> from_dict()."""
    result1 = TriggerCalibrationResult(
        trigger="L2",
        observed_peak=0.95,
        mean_peak=0.70,
        sample_count=150,
        recommended_max=0.72,
        recommended_min=0.05,
    )
    d = result1.to_dict()
    result2 = TriggerCalibrationResult.from_dict(d)
    assert result2.trigger == "L2"
    assert result2.observed_peak == 0.95
    assert result2.mean_peak == 0.70
    assert result2.sample_count == 150
    assert result2.recommended_max == 0.72
    assert result2.recommended_min == 0.05


# ---------------------------------------------------------------------------
# empty state
# ---------------------------------------------------------------------------


def test_analyze_empty_returns_none():
    """analyze() returns None when no samples."""
    c = make_calibrator()
    assert c.analyze("L2") is None
    assert c.analyze("R2") is None


def test_analyze_fewer_than_min_samples_returns_none():
    """analyze() returns None if fewer than min_samples have been recorded."""
    c = make_calibrator(min_samples=20)
    for i in range(15):
        c.add_sample("L2", 0.1 * i)
    assert c.analyze("L2") is None


def test_sample_count_empty():
    """sample_count() returns 0 when empty."""
    c = make_calibrator()
    assert c.sample_count("L2") == 0
    assert c.sample_count("R2") == 0


def test_peak_so_far_empty():
    """peak_so_far() returns None when no samples."""
    c = make_calibrator()
    assert c.peak_so_far("L2") is None
    assert c.peak_so_far("R2") is None


# ---------------------------------------------------------------------------
# basic operations: add_sample, sample_count, peak_so_far
# ---------------------------------------------------------------------------


def test_add_sample_single():
    """add_sample() records a single pressure."""
    c = make_calibrator(min_samples=10, peak_window=1)
    c.add_sample("L2", 0.5)
    assert c.sample_count("L2") == 1
    assert c.peak_so_far("L2") == 0.5


def test_add_sample_multiple():
    """add_sample() appends multiple pressures."""
    c = make_calibrator(min_samples=10, peak_window=3)
    for i in range(10):
        c.add_sample("L2", 0.1 * i)
    assert c.sample_count("L2") == 10


def test_peak_so_far_max():
    """peak_so_far() returns the maximum pressure recorded."""
    c = make_calibrator(min_samples=10, peak_window=5)
    pressures = [0.1, 0.5, 0.9, 0.3, 0.7, 0.2, 0.4, 0.6, 0.8, 0.45]
    for p in pressures:
        c.add_sample("L2", p)
    assert c.peak_so_far("L2") == 0.9


def test_add_sample_multiple_triggers():
    """add_sample() records pressures for both L2 and R2 independently."""
    c = make_calibrator(min_samples=10, peak_window=3)
    for p in [0.1, 0.5, 0.9, 0.2, 0.6, 0.8, 0.3, 0.7, 0.4, 0.5]:
        c.add_sample("L2", p)
    for p in [0.2, 0.4, 0.8, 0.1, 0.6, 0.9, 0.3, 0.5, 0.7, 0.2]:
        c.add_sample("R2", p)

    assert c.sample_count("L2") == 10
    assert c.sample_count("R2") == 10
    assert c.peak_so_far("L2") == 0.9
    assert c.peak_so_far("R2") == 0.9


# ---------------------------------------------------------------------------
# pressure clamping
# ---------------------------------------------------------------------------


def test_add_sample_clamps_negative_to_zero():
    """Negative pressure is clamped to 0."""
    c = make_calibrator(min_samples=10, peak_window=1)
    c.add_sample("L2", -0.5)
    assert c.peak_so_far("L2") == 0.0


def test_add_sample_clamps_over_one_to_one():
    """Pressure > 1.0 is clamped to 1.0."""
    c = make_calibrator(min_samples=10, peak_window=1)
    c.add_sample("L2", 1.5)
    assert c.peak_so_far("L2") == 1.0


def test_add_sample_boundary_zero():
    """Pressure = 0.0 is valid."""
    c = make_calibrator(min_samples=10, peak_window=1)
    c.add_sample("L2", 0.0)
    assert c.peak_so_far("L2") == 0.0


def test_add_sample_boundary_one():
    """Pressure = 1.0 is valid."""
    c = make_calibrator(min_samples=10, peak_window=1)
    c.add_sample("L2", 1.0)
    assert c.peak_so_far("L2") == 1.0


# ---------------------------------------------------------------------------
# unknown trigger names
# ---------------------------------------------------------------------------


def test_add_sample_unknown_trigger_ignored():
    """add_sample() to unknown trigger name is silently ignored."""
    c = make_calibrator()
    c.add_sample("X9", 0.5)
    assert c.sample_count("L2") == 0
    assert c.sample_count("R2") == 0
    assert c.sample_count("X9") == 0


def test_analyze_unknown_trigger_returns_none():
    """analyze() on unknown trigger returns None."""
    c = make_calibrator()
    assert c.analyze("X9") is None


def test_peak_so_far_unknown_trigger_returns_none():
    """peak_so_far() on unknown trigger returns None."""
    c = make_calibrator()
    assert c.peak_so_far("X9") is None


def test_sample_count_unknown_trigger_returns_zero():
    """sample_count() on unknown trigger returns 0."""
    c = make_calibrator()
    assert c.sample_count("X9") == 0


# ---------------------------------------------------------------------------
# analyze: observed_peak
# ---------------------------------------------------------------------------


def test_analyze_observed_peak_single():
    """analyze() observed_peak matches single sample."""
    c = make_calibrator(min_samples=10, peak_window=1)
    c.add_sample("L2", 0.75)
    for _ in range(9):
        c.add_sample("L2", 0.5)
    result = c.analyze("L2")
    assert result is not None
    assert result.observed_peak == 0.75


def test_analyze_observed_peak_multiple():
    """analyze() observed_peak is max of all samples."""
    c = make_calibrator(min_samples=10, peak_window=3)
    samples = [0.1, 0.5, 0.9, 0.3, 0.7, 0.2, 0.4, 0.6, 0.8, 0.45]
    for p in samples:
        c.add_sample("L2", p)
    result = c.analyze("L2")
    assert result is not None
    assert result.observed_peak == 0.9


# ---------------------------------------------------------------------------
# analyze: mean_peak
# ---------------------------------------------------------------------------


def test_analyze_mean_peak_uniform_samples():
    """analyze() mean_peak with uniform samples ~= observed_peak."""
    c = make_calibrator(min_samples=10, peak_window=5)
    # Add 10 samples all at 0.7
    for _ in range(10):
        c.add_sample("L2", 0.7)
    result = c.analyze("L2")
    assert result is not None
    assert abs(result.mean_peak - 0.7) < 1e-9


def test_analyze_mean_peak_top_window():
    """analyze() mean_peak is average of top peak_window samples."""
    c = make_calibrator(min_samples=10, peak_window=3)
    # Add samples: [0.5, 0.5, 0.6, 0.6, 0.7, 0.7, 0.65, 0.68, 0.7, 0.62]
    samples = [0.5, 0.5, 0.6, 0.6, 0.7, 0.7, 0.65, 0.68, 0.7, 0.62]
    for p in samples:
        c.add_sample("L2", p)
    result = c.analyze("L2")
    assert result is not None
    # Top 3: [0.7, 0.7, 0.7], mean = 0.7
    assert abs(result.mean_peak - 0.7) < 1e-9


def test_analyze_mean_peak_fewer_than_window():
    """analyze() mean_peak when fewer samples than peak_window."""
    c = make_calibrator(min_samples=10, peak_window=20)
    # Add 10 samples
    for i in range(10):
        c.add_sample("L2", 0.1 * i)
    result = c.analyze("L2")
    assert result is not None
    # All 10 samples, mean = 0.45
    assert abs(result.mean_peak - 0.45) < 0.01


# ---------------------------------------------------------------------------
# analyze: recommended_max
# ---------------------------------------------------------------------------


def test_analyze_recommended_max_with_padding():
    """analyze() recommended_max = mean_peak + padding_above."""
    c = make_calibrator(min_samples=10, peak_window=3, padding_above=0.05)
    for p in [0.6, 0.65, 0.7, 0.5, 0.55, 0.4, 0.45, 0.3, 0.35, 0.2]:
        c.add_sample("L2", p)
    result = c.analyze("L2")
    assert result is not None
    # Top 3: [0.7, 0.65, 0.6], mean_peak = 0.65
    # recommended_max = 0.65 + 0.05 = 0.70
    assert abs(result.recommended_max - 0.70) < 0.01


def test_analyze_recommended_max_clamped_to_one():
    """analyze() recommended_max is clamped to 1.0."""
    c = make_calibrator(min_samples=10, peak_window=3, padding_above=0.5)
    for p in [0.9, 0.95, 1.0, 0.8, 0.85, 0.7, 0.75, 0.6, 0.65, 0.5]:
        c.add_sample("L2", p)
    result = c.analyze("L2")
    assert result is not None
    # mean_peak ~= 0.95, padding = 0.5 -> 1.45, clamped to 1.0
    assert result.recommended_max == 1.0


def test_analyze_recommended_max_no_padding():
    """analyze() recommended_max with padding_above=0 equals mean_peak."""
    c = make_calibrator(min_samples=10, peak_window=3, padding_above=0.0)
    for p in [0.6, 0.65, 0.7, 0.5, 0.55, 0.4, 0.45, 0.3, 0.35, 0.2]:
        c.add_sample("L2", p)
    result = c.analyze("L2")
    assert result is not None
    # recommended_max ~= mean_peak (no padding)
    assert abs(result.recommended_max - result.mean_peak) < 1e-9


# ---------------------------------------------------------------------------
# analyze: recommended_min
# ---------------------------------------------------------------------------


def test_analyze_recommended_min_is_minimum():
    """analyze() recommended_min is the minimum sample."""
    c = make_calibrator(min_samples=10, peak_window=5)
    samples = [0.1, 0.5, 0.9, 0.3, 0.7, 0.2, 0.4, 0.6, 0.8, 0.45]
    for p in samples:
        c.add_sample("L2", p)
    result = c.analyze("L2")
    assert result is not None
    assert result.recommended_min == 0.1


def test_analyze_recommended_min_all_zeros():
    """analyze() recommended_min is 0.0 when all samples are zero."""
    c = make_calibrator(min_samples=10, peak_window=3)
    for _ in range(10):
        c.add_sample("L2", 0.0)
    result = c.analyze("L2")
    assert result is not None
    assert result.recommended_min == 0.0


def test_analyze_recommended_min_positive_floor():
    """analyze() recommended_min > 0 when all samples > 0."""
    c = make_calibrator(min_samples=10, peak_window=3)
    for p in [0.1, 0.5, 0.9, 0.2, 0.6, 0.8, 0.3, 0.7, 0.4, 0.55]:
        c.add_sample("L2", p)
    result = c.analyze("L2")
    assert result is not None
    assert result.recommended_min == 0.1


# ---------------------------------------------------------------------------
# analyze: sample_count in result
# ---------------------------------------------------------------------------


def test_analyze_sample_count_in_result():
    """analyze() result includes total sample count."""
    c = make_calibrator(min_samples=10, peak_window=5)
    for i in range(10):
        c.add_sample("L2", 0.1 * i)
    result = c.analyze("L2")
    assert result is not None
    assert result.sample_count == 10


# ---------------------------------------------------------------------------
# analyze: trigger in result
# ---------------------------------------------------------------------------


def test_analyze_trigger_in_result():
    """analyze() result includes trigger name."""
    c = make_calibrator(min_samples=10, peak_window=1)
    c.add_sample("L2", 0.5)
    for _ in range(9):
        c.add_sample("L2", 0.5)
    result = c.analyze("L2")
    assert result is not None
    assert result.trigger == "L2"


def test_analyze_result_different_triggers():
    """analyze() returns result for L2 or R2 independently."""
    c = make_calibrator(min_samples=10, peak_window=1)
    c.add_sample("L2", 0.6)
    for _ in range(9):
        c.add_sample("L2", 0.5)
    c.add_sample("R2", 0.7)
    for _ in range(9):
        c.add_sample("R2", 0.6)

    l2_result = c.analyze("L2")
    r2_result = c.analyze("R2")

    assert l2_result is not None and l2_result.trigger == "L2"
    assert r2_result is not None and r2_result.trigger == "R2"
    assert l2_result.observed_peak == 0.6
    assert r2_result.observed_peak == 0.7


# ---------------------------------------------------------------------------
# clear
# ---------------------------------------------------------------------------


def test_clear_single_trigger():
    """clear(trigger) resets one trigger."""
    c = make_calibrator(min_samples=1)
    c.add_sample("L2", 0.5)
    c.add_sample("R2", 0.75)
    c.clear("L2")
    assert c.sample_count("L2") == 0
    assert c.sample_count("R2") == 1


def test_clear_both_triggers():
    """clear(None) resets both triggers."""
    c = make_calibrator(min_samples=1)
    c.add_sample("L2", 0.5)
    c.add_sample("R2", 0.75)
    c.clear(None)
    assert c.sample_count("L2") == 0
    assert c.sample_count("R2") == 0


def test_clear_no_argument_clears_both():
    """clear() with no argument clears both triggers."""
    c = make_calibrator(min_samples=1)
    c.add_sample("L2", 0.5)
    c.add_sample("R2", 0.75)
    c.clear()
    assert c.sample_count("L2") == 0
    assert c.sample_count("R2") == 0


# ---------------------------------------------------------------------------
# integration: manual verification case
# ---------------------------------------------------------------------------


def test_integration_manual_verification():
    """Integration test matching the manual verification command.

    From the spec:
    ```
    python -c "from gamepad_midi_bridge import trigger_calibration as tc; \
    cfg=tc.TriggerCalibrationConfig(min_samples=10, peak_window=3); \
    c=tc.TriggerCalibrator(cfg); \
    [c.add_sample('L2', p) for p in [0.1, 0.3, 0.5, 0.6, 0.7, 0.5, 0.4, 0.6, 0.65, 0.7, 0.62]]; \
    r=c.analyze('L2'); \
    print(round(r.observed_peak, 2), round(r.mean_peak, 2), round(r.recommended_max, 2))"
    ```
    Expected output: 0.7 0.68 0.7 approx
    """
    cfg = TriggerCalibrationConfig(min_samples=10, peak_window=3, padding_above=0.02)
    c = TriggerCalibrator(cfg)
    samples = [0.1, 0.3, 0.5, 0.6, 0.7, 0.5, 0.4, 0.6, 0.65, 0.7, 0.62]
    for p in samples:
        c.add_sample("L2", p)

    result = c.analyze("L2")
    assert result is not None

    # observed_peak should be 0.7 (max of samples)
    assert round(result.observed_peak, 2) == 0.70

    # Top 3 samples: [0.7, 0.7, 0.65]
    # mean_peak = (0.7 + 0.7 + 0.65) / 3 = 2.05 / 3 ~= 0.6833
    assert round(result.mean_peak, 2) == 0.68

    # recommended_max = 0.6833 + 0.02 ~= 0.7033, rounds to 0.70
    assert round(result.recommended_max, 2) == 0.70
