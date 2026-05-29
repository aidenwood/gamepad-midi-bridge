"""Tests for the velocity_curve module — pure-function velocity mapping.

Proves the curve shapes (linear, soft, hard, exponential, logarithmic, s_curve)
and config handling work correctly in isolation, without bridge.py or Qt.
"""
from __future__ import annotations

import math

import pytest

from gamepad_midi_bridge import velocity_curve as vc


# ─────────────────────────────────────────────────────────────────────
# Config dataclass: defaults, clamping, serialisation
# ─────────────────────────────────────────────────────────────────────


def test_velocity_curve_config_defaults():
    """Check default values match spec."""
    cfg = vc.VelocityCurveConfig()
    assert cfg.enabled is False
    assert cfg.curve == "linear"
    assert cfg.fixed_velocity == 100
    assert cfg.min_velocity == 1
    assert cfg.max_velocity == 127


def test_velocity_curve_config_clamps_fixed_velocity():
    """fixed_velocity outside 1..127 is clamped."""
    cfg = vc.VelocityCurveConfig(fixed_velocity=200)
    assert cfg.fixed_velocity == 127

    cfg = vc.VelocityCurveConfig(fixed_velocity=-10)
    assert cfg.fixed_velocity == 1


def test_velocity_curve_config_clamps_min_velocity():
    """min_velocity outside 1..127 is clamped."""
    cfg = vc.VelocityCurveConfig(min_velocity=200)
    assert cfg.min_velocity == 127

    cfg = vc.VelocityCurveConfig(min_velocity=-10)
    assert cfg.min_velocity == 1


def test_velocity_curve_config_clamps_max_velocity():
    """max_velocity outside 1..127 is clamped."""
    cfg = vc.VelocityCurveConfig(max_velocity=200)
    assert cfg.max_velocity == 127

    cfg = vc.VelocityCurveConfig(max_velocity=-10)
    assert cfg.max_velocity == 1


def test_velocity_curve_config_swaps_reversed_min_max():
    """If max < min after clamping, they are swapped."""
    cfg = vc.VelocityCurveConfig(min_velocity=100, max_velocity=50)
    assert cfg.min_velocity == 50
    assert cfg.max_velocity == 100


def test_velocity_curve_config_normalises_unknown_curve():
    """Unknown curve mode falls back to 'linear'."""
    cfg = vc.VelocityCurveConfig(curve="unknown_curve")
    assert cfg.curve == "linear"


def test_velocity_curve_config_to_dict():
    """Serialise to dict."""
    cfg = vc.VelocityCurveConfig(
        enabled=True,
        curve="soft",
        fixed_velocity=80,
        min_velocity=10,
        max_velocity=110,
    )
    d = cfg.to_dict()
    assert d == {
        "enabled": True,
        "curve": "soft",
        "fixed_velocity": 80,
        "min_velocity": 10,
        "max_velocity": 110,
    }


def test_velocity_curve_config_from_dict():
    """Deserialise from dict."""
    d = {
        "enabled": True,
        "curve": "hard",
        "fixed_velocity": 60,
        "min_velocity": 5,
        "max_velocity": 120,
    }
    cfg = vc.VelocityCurveConfig.from_dict(d)
    assert cfg.enabled is True
    assert cfg.curve == "hard"
    assert cfg.fixed_velocity == 60
    assert cfg.min_velocity == 5
    assert cfg.max_velocity == 120


def test_velocity_curve_config_from_dict_missing_keys_fallback():
    """Missing keys in dict fall back to defaults."""
    d = {"enabled": True}
    cfg = vc.VelocityCurveConfig.from_dict(d)
    assert cfg.enabled is True
    assert cfg.curve == "linear"
    assert cfg.fixed_velocity == 100
    assert cfg.min_velocity == 1
    assert cfg.max_velocity == 127


def test_velocity_curve_config_roundtrip():
    """Serialise and deserialise to confirm round-trip."""
    orig = vc.VelocityCurveConfig(
        enabled=True,
        curve="exponential",
        fixed_velocity=75,
        min_velocity=20,
        max_velocity=110,
    )
    d = orig.to_dict()
    restored = vc.VelocityCurveConfig.from_dict(d)

    assert restored.enabled == orig.enabled
    assert restored.curve == orig.curve
    assert restored.fixed_velocity == orig.fixed_velocity
    assert restored.min_velocity == orig.min_velocity
    assert restored.max_velocity == orig.max_velocity


# ─────────────────────────────────────────────────────────────────────
# Linear curve: y = x (default, 1:1 response)
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("input_,expected", [
    (0.0, 1),      # 0 input → min_velocity (default 1)
    (0.5, 64),     # 0.5 input → midpoint (approx 64)
    (1.0, 127),    # 1 input → max_velocity (default 127)
])
def test_linear_curve_default_range(input_, expected):
    """Linear mode with default min/max."""
    cfg = vc.VelocityCurveConfig(curve="linear")
    result = vc.compute_velocity(input_, cfg)
    assert result == expected


def test_linear_curve_custom_range():
    """Linear mode respects custom min/max."""
    cfg = vc.VelocityCurveConfig(curve="linear", min_velocity=20, max_velocity=100)
    assert vc.compute_velocity(0.0, cfg) == 20
    assert vc.compute_velocity(0.5, cfg) == pytest.approx(60, abs=1)
    assert vc.compute_velocity(1.0, cfg) == 100


# ─────────────────────────────────────────────────────────────────────
# Soft curve: y = x^0.5 (boosts low input)
# ─────────────────────────────────────────────────────────────────────


def test_soft_curve_boosts_low_input():
    """Soft curve (sqrt) produces value > linear at 0.5."""
    cfg = vc.VelocityCurveConfig(curve="soft")
    soft_val = vc.compute_velocity(0.5, cfg)
    linear_val = vc.compute_velocity(0.5, vc.VelocityCurveConfig(curve="linear"))
    assert soft_val > linear_val


def test_soft_curve_boundaries():
    """Soft curve passes through 0 and 1."""
    cfg = vc.VelocityCurveConfig(curve="soft")
    assert vc.compute_velocity(0.0, cfg) == 1
    assert vc.compute_velocity(1.0, cfg) == 127


# ─────────────────────────────────────────────────────────────────────
# Hard curve: y = x^2 (penalises low input)
# ─────────────────────────────────────────────────────────────────────


def test_hard_curve_penalises_low_input():
    """Hard curve (x^2) produces value < linear at 0.5."""
    cfg = vc.VelocityCurveConfig(curve="hard")
    hard_val = vc.compute_velocity(0.5, cfg)
    linear_val = vc.compute_velocity(0.5, vc.VelocityCurveConfig(curve="linear"))
    assert hard_val < linear_val


def test_hard_curve_boundaries():
    """Hard curve passes through 0 and 1."""
    cfg = vc.VelocityCurveConfig(curve="hard")
    assert vc.compute_velocity(0.0, cfg) == 1
    assert vc.compute_velocity(1.0, cfg) == 127


# ─────────────────────────────────────────────────────────────────────
# Fixed curve: returns fixed_velocity regardless of input
# ─────────────────────────────────────────────────────────────────────


def test_fixed_curve_ignores_input():
    """Fixed mode always returns fixed_velocity."""
    cfg = vc.VelocityCurveConfig(curve="fixed", fixed_velocity=64)
    assert vc.compute_velocity(0.0, cfg) == 64
    assert vc.compute_velocity(0.25, cfg) == 64
    assert vc.compute_velocity(0.5, cfg) == 64
    assert vc.compute_velocity(0.75, cfg) == 64
    assert vc.compute_velocity(1.0, cfg) == 64


def test_fixed_curve_clamped_within_min_max():
    """Fixed value is clamped to min..max range."""
    # fixed_velocity=10, but min=20 → should return 20
    cfg = vc.VelocityCurveConfig(
        curve="fixed",
        fixed_velocity=10,
        min_velocity=20,
        max_velocity=100,
    )
    assert vc.compute_velocity(0.5, cfg) == 20

    # fixed_velocity=150, but max=100 → should return 100
    cfg = vc.VelocityCurveConfig(
        curve="fixed",
        fixed_velocity=150,
        min_velocity=20,
        max_velocity=100,
    )
    assert vc.compute_velocity(0.5, cfg) == 100


# ─────────────────────────────────────────────────────────────────────
# Exponential curve: curved growth biasing high
# ─────────────────────────────────────────────────────────────────────


def test_exponential_curve_exists():
    """Exponential mode produces reasonable outputs."""
    cfg = vc.VelocityCurveConfig(curve="exponential")
    val = vc.compute_velocity(0.5, cfg)
    # Should be a valid MIDI velocity
    assert 1 <= val <= 127


def test_exponential_boundaries():
    """Exponential curve passes through 0 and 1."""
    cfg = vc.VelocityCurveConfig(curve="exponential")
    assert vc.compute_velocity(0.0, cfg) == 1
    assert vc.compute_velocity(1.0, cfg) == 127


# ─────────────────────────────────────────────────────────────────────
# Logarithmic curve: curved growth biasing low
# ─────────────────────────────────────────────────────────────────────


def test_logarithmic_curve_exists():
    """Logarithmic mode produces reasonable outputs."""
    cfg = vc.VelocityCurveConfig(curve="logarithmic")
    val = vc.compute_velocity(0.5, cfg)
    assert 1 <= val <= 127


def test_logarithmic_boundaries():
    """Logarithmic curve passes through 0 and 1."""
    cfg = vc.VelocityCurveConfig(curve="logarithmic")
    assert vc.compute_velocity(0.0, cfg) == 1
    assert vc.compute_velocity(1.0, cfg) == 127


# ─────────────────────────────────────────────────────────────────────
# S-curve: smooth ease-in-out
# ─────────────────────────────────────────────────────────────────────


def test_s_curve_ease_in_out():
    """S-curve is smooth and symmetric."""
    cfg = vc.VelocityCurveConfig(curve="s_curve")

    # Boundaries
    assert vc.compute_velocity(0.0, cfg) == 1
    assert vc.compute_velocity(1.0, cfg) == 127

    # Midpoint should be near 64
    mid = vc.compute_velocity(0.5, cfg)
    assert 60 <= mid <= 68  # Allow small rounding variance


def test_s_curve_symmetry():
    """S-curve should be roughly symmetric around 0.5."""
    cfg = vc.VelocityCurveConfig(curve="s_curve", min_velocity=1, max_velocity=127)
    val_low = vc.compute_velocity(0.25, cfg)
    val_high = vc.compute_velocity(0.75, cfg)
    # They should be roughly symmetric around midpoint (64)
    mid = 64
    dist_low = abs(val_low - mid)
    dist_high = abs(val_high - mid)
    assert abs(dist_low - dist_high) <= 2  # Allow small rounding variance


# ─────────────────────────────────────────────────────────────────────
# Input clamping
# ─────────────────────────────────────────────────────────────────────


def test_input_below_zero_clamped():
    """Input < 0 should clamp to min_velocity."""
    cfg = vc.VelocityCurveConfig(curve="linear", min_velocity=20, max_velocity=100)
    assert vc.compute_velocity(-0.5, cfg) == 20
    assert vc.compute_velocity(-999.0, cfg) == 20


def test_input_above_one_clamped():
    """Input > 1 should clamp to max_velocity."""
    cfg = vc.VelocityCurveConfig(curve="linear", min_velocity=20, max_velocity=100)
    assert vc.compute_velocity(1.5, cfg) == 100
    assert vc.compute_velocity(999.0, cfg) == 100


# ─────────────────────────────────────────────────────────────────────
# Output clamping
# ─────────────────────────────────────────────────────────────────────


def test_output_clamped_to_1_to_127():
    """All curves output velocity in [1, 127] (MIDI range)."""
    for curve in vc.VELOCITY_CURVE_MODES:
        cfg = vc.VelocityCurveConfig(curve=curve, min_velocity=1, max_velocity=127)
        for input_ in (0.0, 0.25, 0.5, 0.75, 1.0):
            result = vc.compute_velocity(input_, cfg)
            assert 1 <= result <= 127, f"curve={curve}, input={input_}, result={result}"


# ─────────────────────────────────────────────────────────────────────
# Preview curve function
# ─────────────────────────────────────────────────────────────────────


def test_preview_curve_returns_list():
    """preview_curve returns a list of integers."""
    cfg = vc.VelocityCurveConfig(curve="linear")
    result = vc.preview_curve(cfg, samples=16)
    assert isinstance(result, list)
    assert len(result) == 16
    assert all(isinstance(v, int) for v in result)


def test_preview_curve_ascending_for_linear():
    """Linear curve preview should be monotonically ascending."""
    cfg = vc.VelocityCurveConfig(curve="linear")
    result = vc.preview_curve(cfg, samples=10)
    for i in range(len(result) - 1):
        assert result[i] <= result[i + 1]


def test_preview_curve_ascending_for_soft():
    """Soft curve preview should be monotonically ascending."""
    cfg = vc.VelocityCurveConfig(curve="soft")
    result = vc.preview_curve(cfg, samples=10)
    for i in range(len(result) - 1):
        assert result[i] <= result[i + 1]


def test_preview_curve_ascending_for_hard():
    """Hard curve preview should be monotonically ascending."""
    cfg = vc.VelocityCurveConfig(curve="hard")
    result = vc.preview_curve(cfg, samples=10)
    for i in range(len(result) - 1):
        assert result[i] <= result[i + 1]


def test_preview_curve_ascending_for_exponential():
    """Exponential curve preview should be monotonically ascending."""
    cfg = vc.VelocityCurveConfig(curve="exponential")
    result = vc.preview_curve(cfg, samples=10)
    for i in range(len(result) - 1):
        assert result[i] <= result[i + 1]


def test_preview_curve_ascending_for_logarithmic():
    """Logarithmic curve preview should be monotonically ascending."""
    cfg = vc.VelocityCurveConfig(curve="logarithmic")
    result = vc.preview_curve(cfg, samples=10)
    for i in range(len(result) - 1):
        assert result[i] <= result[i + 1]


def test_preview_curve_ascending_for_s_curve():
    """S-curve preview should be monotonically ascending."""
    cfg = vc.VelocityCurveConfig(curve="s_curve")
    result = vc.preview_curve(cfg, samples=10)
    for i in range(len(result) - 1):
        assert result[i] <= result[i + 1]


def test_preview_curve_fixed_returns_copies():
    """Fixed curve preview returns N copies of fixed_velocity (clamped)."""
    cfg = vc.VelocityCurveConfig(curve="fixed", fixed_velocity=64)
    result = vc.preview_curve(cfg, samples=8)
    assert len(result) == 8
    assert all(v == 64 for v in result)


def test_preview_curve_min_samples():
    """If samples < 2, default to 2."""
    cfg = vc.VelocityCurveConfig(curve="linear")
    result = vc.preview_curve(cfg, samples=1)
    assert len(result) == 2


def test_preview_curve_custom_sample_count():
    """preview_curve respects custom sample count."""
    cfg = vc.VelocityCurveConfig(curve="linear")
    for n in (2, 5, 32, 100):
        result = vc.preview_curve(cfg, samples=n)
        assert len(result) == n


# ─────────────────────────────────────────────────────────────────────
# Unknown/fallback modes
# ─────────────────────────────────────────────────────────────────────


def test_unknown_curve_falls_back_to_linear():
    """Unknown curve mode is treated as linear."""
    cfg = vc.VelocityCurveConfig(curve="unknown_mode")
    assert cfg.curve == "linear"
    result = vc.compute_velocity(0.5, cfg)
    linear_result = vc.compute_velocity(0.5, vc.VelocityCurveConfig(curve="linear"))
    assert result == linear_result
