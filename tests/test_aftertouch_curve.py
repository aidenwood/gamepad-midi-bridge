"""Tests for the aftertouch_curve module — pure-function pressure transforms.

This module covers curve shapes, threshold, ceiling, min/max output clamping,
and serialization. All logic is stateless and deterministic.
"""
from __future__ import annotations

import math

import pytest

from gamepad_midi_bridge import aftertouch_curve


# ─────────────────────────────────────────────────────────────────────
# Linear curve — baseline 1:1 response
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("input_val,expected", [
    (0.0, 0),
    (0.5, 64),
    (1.0, 127),
])
def test_linear_basic(input_val, expected):
    """Linear curve: input directly maps to output range."""
    cfg = aftertouch_curve.AftertouchCurveConfig(curve="linear")
    assert aftertouch_curve.compute_pressure(input_val, cfg) == expected


# ─────────────────────────────────────────────────────────────────────
# Soft curve — x^0.5 boosts low input
# ─────────────────────────────────────────────────────────────────────

def test_soft_midpoint_higher_than_linear():
    """Soft curve at midpoint should be > linear midpoint (boosts low input)."""
    cfg = aftertouch_curve.AftertouchCurveConfig(curve="soft")
    linear_cfg = aftertouch_curve.AftertouchCurveConfig(curve="linear")

    soft_mid = aftertouch_curve.compute_pressure(0.5, cfg)
    linear_mid = aftertouch_curve.compute_pressure(0.5, linear_cfg)

    # sqrt(0.5) ≈ 0.707 > 0.5
    assert soft_mid > linear_mid


def test_soft_endpoints_match_linear():
    """Soft curve at 0 and 1 should match linear."""
    cfg = aftertouch_curve.AftertouchCurveConfig(curve="soft")
    assert aftertouch_curve.compute_pressure(0.0, cfg) == 0
    assert aftertouch_curve.compute_pressure(1.0, cfg) == 127


# ─────────────────────────────────────────────────────────────────────
# Hard curve — x^2 penalises low input
# ─────────────────────────────────────────────────────────────────────

def test_hard_midpoint_lower_than_linear():
    """Hard curve at midpoint should be < linear midpoint (penalises low input)."""
    cfg = aftertouch_curve.AftertouchCurveConfig(curve="hard")
    linear_cfg = aftertouch_curve.AftertouchCurveConfig(curve="linear")

    hard_mid = aftertouch_curve.compute_pressure(0.5, cfg)
    linear_mid = aftertouch_curve.compute_pressure(0.5, linear_cfg)

    # 0.5^2 = 0.25 < 0.5
    assert hard_mid < linear_mid


def test_hard_endpoints_match_linear():
    """Hard curve at 0 and 1 should match linear."""
    cfg = aftertouch_curve.AftertouchCurveConfig(curve="hard")
    assert aftertouch_curve.compute_pressure(0.0, cfg) == 0
    assert aftertouch_curve.compute_pressure(1.0, cfg) == 127


# ─────────────────────────────────────────────────────────────────────
# Threshold — dead-zone below which output is min_output
# ─────────────────────────────────────────────────────────────────────

def test_threshold_below_returns_min_output():
    """Input below threshold should return min_output."""
    cfg = aftertouch_curve.AftertouchCurveConfig(
        curve="linear",
        threshold=0.2,
        min_output=0,
        max_output=127,
    )
    # Input 0.1 < threshold 0.2 → min_output
    assert aftertouch_curve.compute_pressure(0.1, cfg) == 0


def test_threshold_at_boundary_returns_min_output():
    """Input exactly at threshold should return min_output."""
    cfg = aftertouch_curve.AftertouchCurveConfig(
        curve="linear",
        threshold=0.2,
        min_output=0,
        max_output=127,
    )
    # Input 0.2 == threshold 0.2 → min_output (not < threshold)
    # Actually at threshold, the remapped value is 0, so output is min_output
    assert aftertouch_curve.compute_pressure(0.2, cfg) == 0


def test_threshold_above_starts_responding():
    """Input just above threshold should produce output > min_output."""
    cfg = aftertouch_curve.AftertouchCurveConfig(
        curve="linear",
        threshold=0.2,
        min_output=0,
        max_output=127,
    )
    # Input 0.21 > threshold 0.2 → should have some output
    output = aftertouch_curve.compute_pressure(0.21, cfg)
    assert output > 0


# ─────────────────────────────────────────────────────────────────────
# Ceiling — clip point above which output is max_output
# ─────────────────────────────────────────────────────────────────────

def test_ceiling_clips_at_max():
    """Input at or above ceiling should return max_output."""
    cfg = aftertouch_curve.AftertouchCurveConfig(
        curve="linear",
        threshold=0.0,
        ceiling=0.8,
        min_output=0,
        max_output=127,
    )
    # Input 0.8 == ceiling → max_output
    assert aftertouch_curve.compute_pressure(0.8, cfg) == 127
    # Input 1.0 > ceiling → clamped, returns max_output
    assert aftertouch_curve.compute_pressure(1.0, cfg) == 127


def test_ceiling_partway_maps_linearly():
    """Input between threshold and ceiling maps to the remapped range."""
    cfg = aftertouch_curve.AftertouchCurveConfig(
        curve="linear",
        threshold=0.0,
        ceiling=0.8,
        min_output=0,
        max_output=127,
    )
    # Input 0.4 is halfway between threshold (0) and ceiling (0.8)
    # Remapped: (0.4 - 0) / (0.8 - 0) = 0.5
    # Linear at 0.5 of output range: 0 + 0.5 * 127 ≈ 64
    output = aftertouch_curve.compute_pressure(0.4, cfg)
    assert output == pytest.approx(64, abs=1)


def test_ceiling_and_threshold_combined():
    """Threshold and ceiling together define the active input range."""
    cfg = aftertouch_curve.AftertouchCurveConfig(
        curve="linear",
        threshold=0.2,
        ceiling=0.8,
        min_output=0,
        max_output=127,
    )
    # Input 0.1 < threshold → min_output
    assert aftertouch_curve.compute_pressure(0.1, cfg) == 0
    # Input 0.5 is halfway in [0.2, 0.8]
    # Remapped: (0.5 - 0.2) / (0.8 - 0.2) = 0.3 / 0.6 = 0.5
    # Linear at 0.5: 0 + 0.5 * 127 ≈ 64
    output = aftertouch_curve.compute_pressure(0.5, cfg)
    assert output == pytest.approx(64, abs=1)
    # Input 0.9 > ceiling → max_output
    assert aftertouch_curve.compute_pressure(0.9, cfg) == 127


# ─────────────────────────────────────────────────────────────────────
# Stepped curve — quantised levels
# ─────────────────────────────────────────────────────────────────────

def test_stepped_produces_discrete_values():
    """Stepped curve with step_count=4 should produce at most 4 distinct values."""
    cfg = aftertouch_curve.AftertouchCurveConfig(
        curve="stepped",
        step_count=4,
        min_output=0,
        max_output=127,
    )

    # Sample across the full range and collect unique outputs.
    values = set()
    for i in range(101):
        t = i / 100.0
        output = aftertouch_curve.compute_pressure(t, cfg)
        values.add(output)

    # With step_count=4, we should have at most 4 distinct output values.
    assert len(values) <= 4


def test_stepped_endpoints():
    """Stepped curve at 0 and 1 should match linear endpoints."""
    cfg = aftertouch_curve.AftertouchCurveConfig(
        curve="stepped",
        step_count=4,
    )
    assert aftertouch_curve.compute_pressure(0.0, cfg) == 0
    assert aftertouch_curve.compute_pressure(1.0, cfg) == 127


# ─────────────────────────────────────────────────────────────────────
# Exponential curve — biases low
# ─────────────────────────────────────────────────────────────────────

def test_exponential_midpoint_lower_than_linear():
    """Exponential curve at midpoint should be < linear midpoint (biases low)."""
    cfg = aftertouch_curve.AftertouchCurveConfig(curve="exponential")
    linear_cfg = aftertouch_curve.AftertouchCurveConfig(curve="linear")

    exp_mid = aftertouch_curve.compute_pressure(0.5, cfg)
    linear_mid = aftertouch_curve.compute_pressure(0.5, linear_cfg)

    assert exp_mid < linear_mid


def test_exponential_endpoints():
    """Exponential curve at 0 and 1 should match linear."""
    cfg = aftertouch_curve.AftertouchCurveConfig(curve="exponential")
    assert aftertouch_curve.compute_pressure(0.0, cfg) == 0
    assert aftertouch_curve.compute_pressure(1.0, cfg) == 127


# ─────────────────────────────────────────────────────────────────────
# Logarithmic curve — biases high
# ─────────────────────────────────────────────────────────────────────

def test_logarithmic_midpoint_higher_than_linear():
    """Logarithmic curve at midpoint should be > linear midpoint (biases high)."""
    cfg = aftertouch_curve.AftertouchCurveConfig(curve="logarithmic")
    linear_cfg = aftertouch_curve.AftertouchCurveConfig(curve="linear")

    log_mid = aftertouch_curve.compute_pressure(0.5, cfg)
    linear_mid = aftertouch_curve.compute_pressure(0.5, linear_cfg)

    assert log_mid > linear_mid


def test_logarithmic_endpoints():
    """Logarithmic curve at 0 and 1 should match linear."""
    cfg = aftertouch_curve.AftertouchCurveConfig(curve="logarithmic")
    assert aftertouch_curve.compute_pressure(0.0, cfg) == 0
    assert aftertouch_curve.compute_pressure(1.0, cfg) == 127


# ─────────────────────────────────────────────────────────────────────
# Unknown curve — defaults to linear
# ─────────────────────────────────────────────────────────────────────

def test_unknown_curve_defaults_to_linear():
    """Unknown curve mode should be normalized to linear."""
    cfg = aftertouch_curve.AftertouchCurveConfig(curve="bogus_curve_name")
    assert cfg.curve == "linear"

    # Output should match linear.
    assert aftertouch_curve.compute_pressure(0.5, cfg) == 64


# ─────────────────────────────────────────────────────────────────────
# Threshold clamping
# ─────────────────────────────────────────────────────────────────────

def test_threshold_clamped_to_0_0_95():
    """Threshold is clamped to [0.0, 0.95]."""
    cfg_low = aftertouch_curve.AftertouchCurveConfig(threshold=-0.5)
    assert cfg_low.threshold == 0.0

    cfg_high = aftertouch_curve.AftertouchCurveConfig(threshold=1.5)
    assert cfg_high.threshold == 0.95


# ─────────────────────────────────────────────────────────────────────
# Ceiling clamping and swap
# ─────────────────────────────────────────────────────────────────────

def test_ceiling_clamped_to_0_05_1_0():
    """Ceiling is clamped to [0.05, 1.0]."""
    cfg_low = aftertouch_curve.AftertouchCurveConfig(ceiling=-0.5)
    assert cfg_low.ceiling == 0.05

    cfg_high = aftertouch_curve.AftertouchCurveConfig(ceiling=2.0)
    assert cfg_high.ceiling == 1.0


def test_ceiling_less_than_threshold_swaps():
    """If ceiling < threshold, they are swapped."""
    cfg = aftertouch_curve.AftertouchCurveConfig(
        threshold=0.8,
        ceiling=0.2,
    )
    # After swap, threshold should be 0.2 and ceiling should be 0.8.
    assert cfg.threshold == 0.2
    assert cfg.ceiling == 0.8


# ─────────────────────────────────────────────────────────────────────
# Min/max output clamping and swap
# ─────────────────────────────────────────────────────────────────────

def test_min_output_greater_than_max_output_swaps():
    """If min_output > max_output, they are swapped."""
    cfg = aftertouch_curve.AftertouchCurveConfig(
        min_output=100,
        max_output=50,
    )
    # After swap, min_output should be 50 and max_output should be 100.
    assert cfg.min_output == 50
    assert cfg.max_output == 100


def test_min_output_max_output_clamped_to_0_127():
    """Min and max output are clamped to [0, 127]."""
    cfg = aftertouch_curve.AftertouchCurveConfig(
        min_output=-10,
        max_output=200,
    )
    assert cfg.min_output == 0
    assert cfg.max_output == 127


# ─────────────────────────────────────────────────────────────────────
# Serialization (to_dict / from_dict)
# ─────────────────────────────────────────────────────────────────────

def test_round_trip_serialization():
    """Config should round-trip through to_dict and from_dict."""
    original = aftertouch_curve.AftertouchCurveConfig(
        enabled=True,
        curve="soft",
        threshold=0.1,
        ceiling=0.9,
        step_count=8,
        min_output=10,
        max_output=120,
    )

    data = original.to_dict()
    restored = aftertouch_curve.AftertouchCurveConfig.from_dict(data)

    assert restored.enabled == original.enabled
    assert restored.curve == original.curve
    assert restored.threshold == original.threshold
    assert restored.ceiling == original.ceiling
    assert restored.step_count == original.step_count
    assert restored.min_output == original.min_output
    assert restored.max_output == original.max_output


def test_from_dict_with_missing_keys():
    """from_dict should use defaults for missing keys."""
    data = {"enabled": True}
    cfg = aftertouch_curve.AftertouchCurveConfig.from_dict(data)

    assert cfg.enabled is True
    assert cfg.curve == "linear"
    assert cfg.threshold == 0.0
    assert cfg.ceiling == 1.0
    assert cfg.step_count == 4
    assert cfg.min_output == 0
    assert cfg.max_output == 127


# ─────────────────────────────────────────────────────────────────────
# Preview curve
# ─────────────────────────────────────────────────────────────────────

def test_preview_curve_returns_expected_count():
    """preview_curve should return the requested number of samples."""
    cfg = aftertouch_curve.AftertouchCurveConfig(curve="linear")

    for sample_count in [2, 8, 16, 32]:
        result = aftertouch_curve.preview_curve(cfg, samples=sample_count)
        assert len(result) == sample_count


def test_preview_curve_starts_at_zero_ends_at_max():
    """Preview curve for linear should start at min_output and end at max_output."""
    cfg = aftertouch_curve.AftertouchCurveConfig(
        curve="linear",
        min_output=0,
        max_output=127,
    )
    result = aftertouch_curve.preview_curve(cfg, samples=16)

    # First sample at t=0 should be min_output.
    assert result[0] == 0
    # Last sample at t=1 should be max_output.
    assert result[-1] == 127


def test_preview_curve_min_samples_is_2():
    """If samples < 2, should be clamped to 2."""
    cfg = aftertouch_curve.AftertouchCurveConfig(curve="linear")
    result = aftertouch_curve.preview_curve(cfg, samples=1)
    assert len(result) == 2
