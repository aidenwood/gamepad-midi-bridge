"""Tests for MIDI velocity quantizer.

VelocityQuantizer enables chip-tune feel and dynamic range control via
quantization to N discrete levels with optional bias and naming.
Pure stdlib, no Qt.
"""
from __future__ import annotations

import pytest


class TestComputeLevels:
    """compute_levels() — compute actual velocity values at each level."""

    def test_compute_levels_two_levels(self):
        """2 levels: [min, max]."""
        from gamepad_midi_bridge.velocity_quantizer import compute_levels, VelocityQuantizerConfig
        cfg = VelocityQuantizerConfig(levels=2, min_value=1, max_value=127)
        levels = compute_levels(cfg)
        assert len(levels) == 2
        assert levels[0] == 1
        assert levels[1] == 127

    def test_compute_levels_four_levels_standard(self):
        """4 levels (pp/mp/mf/ff): approx [1, 43, 85, 127]."""
        from gamepad_midi_bridge.velocity_quantizer import compute_levels, VelocityQuantizerConfig
        cfg = VelocityQuantizerConfig(levels=4, min_value=1, max_value=127)
        levels = compute_levels(cfg)
        assert len(levels) == 4
        assert levels[0] == 1
        assert levels[1] == 43 or levels[1] == 42
        assert levels[2] == 85 or levels[2] == 84
        assert levels[3] == 127

    def test_compute_levels_eight_levels(self):
        """8 levels: evenly spaced from 1 to 127."""
        from gamepad_midi_bridge.velocity_quantizer import compute_levels, VelocityQuantizerConfig
        cfg = VelocityQuantizerConfig(levels=8, min_value=1, max_value=127)
        levels = compute_levels(cfg)
        assert len(levels) == 8
        assert levels[0] == 1
        assert levels[7] == 127

    def test_compute_levels_custom_min_max(self):
        """Custom min/max: e.g. [20..100] with 3 levels."""
        from gamepad_midi_bridge.velocity_quantizer import compute_levels, VelocityQuantizerConfig
        cfg = VelocityQuantizerConfig(levels=3, min_value=20, max_value=100)
        levels = compute_levels(cfg)
        assert len(levels) == 3
        assert levels[0] == 20
        assert levels[2] == 100

    def test_compute_levels_equal_min_max(self):
        """min_value == max_value: all levels equal."""
        from gamepad_midi_bridge.velocity_quantizer import compute_levels, VelocityQuantizerConfig
        cfg = VelocityQuantizerConfig(levels=4, min_value=64, max_value=64)
        levels = compute_levels(cfg)
        assert len(levels) == 4
        assert all(v == 64 for v in levels)

    def test_compute_levels_clamping(self):
        """levels clamped to 2..32; min/max clamped to valid ranges."""
        from gamepad_midi_bridge.velocity_quantizer import compute_levels, VelocityQuantizerConfig
        cfg = VelocityQuantizerConfig(levels=100, min_value=0, max_value=200)
        levels = compute_levels(cfg)
        assert len(levels) == 32
        assert levels[0] == 1
        assert levels[31] == 127


class TestQuantize:
    """quantize() — map velocity to discrete level."""

    def test_quantize_disabled_returns_raw(self):
        """If not enabled, return raw velocity unchanged."""
        from gamepad_midi_bridge.velocity_quantizer import quantize, VelocityQuantizerConfig
        cfg = VelocityQuantizerConfig(enabled=False, levels=4)
        assert quantize(0, cfg) == 0
        assert quantize(50, cfg) == 50
        assert quantize(127, cfg) == 127

    def test_quantize_clamping_below_zero(self):
        """Negative input clamped to 0."""
        from gamepad_midi_bridge.velocity_quantizer import quantize, VelocityQuantizerConfig
        cfg = VelocityQuantizerConfig(enabled=True, levels=4, min_value=1, max_value=127)
        assert quantize(-10, cfg) == 1
        assert quantize(-1, cfg) == 1

    def test_quantize_clamping_above_127(self):
        """Input > 127 clamped to 127."""
        from gamepad_midi_bridge.velocity_quantizer import quantize, VelocityQuantizerConfig
        cfg = VelocityQuantizerConfig(enabled=True, levels=4, min_value=1, max_value=127)
        assert quantize(200, cfg) == 127
        assert quantize(128, cfg) == 127

    def test_quantize_four_levels_low_velocity(self):
        """Low velocity maps to first level."""
        from gamepad_midi_bridge.velocity_quantizer import quantize, VelocityQuantizerConfig
        cfg = VelocityQuantizerConfig(enabled=True, levels=4, min_value=1, max_value=127)
        result = quantize(15, cfg)
        assert result == 1

    def test_quantize_four_levels_mid_velocity(self):
        """Mid velocity maps to middle level."""
        from gamepad_midi_bridge.velocity_quantizer import quantize, VelocityQuantizerConfig
        cfg = VelocityQuantizerConfig(enabled=True, levels=4, min_value=1, max_value=127)
        result = quantize(47, cfg)
        assert 42 <= result <= 44

    def test_quantize_four_levels_high_velocity(self):
        """High velocity maps to last level."""
        from gamepad_midi_bridge.velocity_quantizer import quantize, VelocityQuantizerConfig
        cfg = VelocityQuantizerConfig(enabled=True, levels=4, min_value=1, max_value=127)
        result = quantize(110, cfg)
        assert result == 127

    def test_quantize_bin_boundaries_no_bias(self):
        """Check boundaries with no bias (bias=0)."""
        from gamepad_midi_bridge.velocity_quantizer import quantize, VelocityQuantizerConfig
        cfg = VelocityQuantizerConfig(enabled=True, levels=2, min_value=1, max_value=127, bias=0.0)
        assert quantize(0, cfg) == 1
        assert quantize(63, cfg) == 1
        assert quantize(64, cfg) == 127
        assert quantize(127, cfg) == 127

    def test_quantize_custom_velocity_range(self):
        """Custom velocity range [20..100]."""
        from gamepad_midi_bridge.velocity_quantizer import quantize, VelocityQuantizerConfig
        cfg = VelocityQuantizerConfig(enabled=True, levels=3, min_value=20, max_value=100, bias=0.0)
        assert quantize(20, cfg) == 20
        assert quantize(100, cfg) == 100


class TestLevelIndex:
    """level_index() — return 0..levels-1 index for a velocity."""

    def test_level_index_disabled(self):
        """If disabled, return 0."""
        from gamepad_midi_bridge.velocity_quantizer import level_index, VelocityQuantizerConfig
        cfg = VelocityQuantizerConfig(enabled=False, levels=4)
        assert level_index(50, cfg) == 0

    def test_level_index_returns_zero_to_n_minus_1(self):
        """level_index always returns 0..levels-1."""
        from gamepad_midi_bridge.velocity_quantizer import level_index, VelocityQuantizerConfig
        cfg = VelocityQuantizerConfig(enabled=True, levels=4)
        for v in [0, 30, 60, 90, 127]:
            idx = level_index(v, cfg)
            assert 0 <= idx < 4


class TestLevelName:
    """level_name() — return name at level_index, if defined."""

    def test_level_name_disabled(self):
        """If disabled, return ''."""
        from gamepad_midi_bridge.velocity_quantizer import level_name, VelocityQuantizerConfig
        cfg = VelocityQuantizerConfig(enabled=False, level_names=["pp", "mp", "mf", "ff"])
        assert level_name(50, cfg) == ""

    def test_level_name_empty_list(self):
        """If level_names empty, return ''."""
        from gamepad_midi_bridge.velocity_quantizer import level_name, VelocityQuantizerConfig
        cfg = VelocityQuantizerConfig(enabled=True, levels=4, level_names=[])
        assert level_name(50, cfg) == ""

    def test_level_name_returns_name_at_index(self):
        """Return level_names[index] if in range."""
        from gamepad_midi_bridge.velocity_quantizer import level_name, VelocityQuantizerConfig
        cfg = VelocityQuantizerConfig(enabled=True, levels=4, level_names=["pp", "mp", "mf", "ff"], bias=0.0)
        assert level_name(10, cfg) == "pp"
        assert level_name(120, cfg) == "ff"


class TestPreviewCurve:
    """preview_curve() — generate input → output samples for UI."""

    def test_preview_curve_default_samples(self):
        """Default 128 samples (one per MIDI velocity)."""
        from gamepad_midi_bridge.velocity_quantizer import preview_curve, VelocityQuantizerConfig
        cfg = VelocityQuantizerConfig(enabled=True, levels=4)
        curve = preview_curve(cfg)
        assert len(curve) == 128

    def test_preview_curve_custom_samples(self):
        """Custom sample count."""
        from gamepad_midi_bridge.velocity_quantizer import preview_curve, VelocityQuantizerConfig
        cfg = VelocityQuantizerConfig(enabled=True, levels=4)
        curve = preview_curve(cfg, samples=64)
        assert len(curve) == 64

    def test_preview_curve_output_in_range(self):
        """All output values are valid velocities (0..127)."""
        from gamepad_midi_bridge.velocity_quantizer import preview_curve, VelocityQuantizerConfig
        cfg = VelocityQuantizerConfig(enabled=True, levels=4, min_value=1, max_value=127)
        curve = preview_curve(cfg, samples=128)
        for v in curve:
            assert 0 <= v <= 127

    def test_preview_curve_matches_quantize(self):
        """preview_curve[i] == quantize(i, cfg)."""
        from gamepad_midi_bridge.velocity_quantizer import preview_curve, quantize, VelocityQuantizerConfig
        cfg = VelocityQuantizerConfig(enabled=True, levels=4)
        curve = preview_curve(cfg, samples=128)
        for i in range(128):
            assert curve[i] == quantize(i, cfg)


class TestVelocityQuantizerConfig:
    """VelocityQuantizerConfig — clamp and serialize/deserialize."""

    def test_config_defaults(self):
        from gamepad_midi_bridge.velocity_quantizer import VelocityQuantizerConfig
        cfg = VelocityQuantizerConfig()
        assert cfg.enabled is False
        assert cfg.levels == 4
        assert cfg.min_value == 1
        assert cfg.max_value == 127
        assert cfg.bias == 0.0
        assert cfg.level_names == []

    def test_config_clamp_levels_below_two(self):
        from gamepad_midi_bridge.velocity_quantizer import VelocityQuantizerConfig
        cfg = VelocityQuantizerConfig(levels=1)
        assert cfg.levels == 2

    def test_config_clamp_levels_above_32(self):
        from gamepad_midi_bridge.velocity_quantizer import VelocityQuantizerConfig
        cfg = VelocityQuantizerConfig(levels=33)
        assert cfg.levels == 32

    def test_config_clamp_min_value_below_one(self):
        from gamepad_midi_bridge.velocity_quantizer import VelocityQuantizerConfig
        cfg = VelocityQuantizerConfig(min_value=0)
        assert cfg.min_value == 1

    def test_config_clamp_max_value_above_127(self):
        from gamepad_midi_bridge.velocity_quantizer import VelocityQuantizerConfig
        cfg = VelocityQuantizerConfig(max_value=200)
        assert cfg.max_value == 127

    def test_config_ensure_max_geq_min(self):
        from gamepad_midi_bridge.velocity_quantizer import VelocityQuantizerConfig
        cfg = VelocityQuantizerConfig(min_value=100, max_value=50)
        assert cfg.max_value >= cfg.min_value

    def test_config_clamp_bias(self):
        from gamepad_midi_bridge.velocity_quantizer import VelocityQuantizerConfig
        cfg = VelocityQuantizerConfig(bias=-1.5)
        assert cfg.bias == -1.0
        cfg = VelocityQuantizerConfig(bias=2.0)
        assert cfg.bias == 1.0

    def test_config_to_dict(self):
        from gamepad_midi_bridge.velocity_quantizer import VelocityQuantizerConfig
        cfg = VelocityQuantizerConfig(
            enabled=True,
            levels=4,
            min_value=10,
            max_value=100,
            bias=0.5,
            level_names=["pp", "mp", "mf", "ff"]
        )
        d = cfg.to_dict()
        assert d["enabled"] is True
        assert d["levels"] == 4
        assert d["min_value"] == 10
        assert d["max_value"] == 100
        assert d["bias"] == 0.5
        assert d["level_names"] == ["pp", "mp", "mf", "ff"]

    def test_config_from_dict(self):
        from gamepad_midi_bridge.velocity_quantizer import VelocityQuantizerConfig
        d = {
            "enabled": True,
            "levels": 8,
            "min_value": 20,
            "max_value": 110,
            "bias": -0.3,
            "level_names": ["1", "2", "3", "4", "5", "6", "7", "8"]
        }
        cfg = VelocityQuantizerConfig.from_dict(d)
        assert cfg.enabled is True
        assert cfg.levels == 8

    def test_config_from_dict_missing_keys_use_defaults(self):
        from gamepad_midi_bridge.velocity_quantizer import VelocityQuantizerConfig
        d = {"enabled": True}
        cfg = VelocityQuantizerConfig.from_dict(d)
        assert cfg.enabled is True
        assert cfg.levels == 4

    def test_config_from_dict_applies_clamping(self):
        from gamepad_midi_bridge.velocity_quantizer import VelocityQuantizerConfig
        d = {
            "levels": 100,
            "min_value": -50,
            "max_value": 200,
            "bias": 2.5
        }
        cfg = VelocityQuantizerConfig.from_dict(d)
        assert cfg.levels == 32
        assert cfg.min_value == 1
        assert cfg.max_value == 127
        assert cfg.bias == 1.0

    def test_config_round_trip(self):
        from gamepad_midi_bridge.velocity_quantizer import VelocityQuantizerConfig
        original = VelocityQuantizerConfig(
            enabled=True,
            levels=6,
            min_value=30,
            max_value=110,
            bias=-0.2,
            level_names=["a", "b", "c", "d", "e", "f"]
        )
        d = original.to_dict()
        restored = VelocityQuantizerConfig.from_dict(d)
        assert restored.enabled == original.enabled
        assert restored.levels == original.levels


class TestIntegration:
    """Integration tests: realistic use cases."""

    def test_chip_tune_feel_four_levels(self):
        """Classic chip-tune: 4 levels (pp/mp/mf/ff)."""
        from gamepad_midi_bridge.velocity_quantizer import (
            quantize, level_name, VelocityQuantizerConfig
        )
        cfg = VelocityQuantizerConfig(
            enabled=True,
            levels=4,
            min_value=1,
            max_value=127,
            level_names=["pp", "mp", "mf", "ff"]
        )
        assert level_name(20, cfg) == "pp"
        assert level_name(50, cfg) == "mp"
        assert level_name(80, cfg) == "mf"
        assert level_name(110, cfg) == "ff"

    def test_limited_dynamic_range_10_to_100(self):
        """Limited range: velocities compressed to 10..100."""
        from gamepad_midi_bridge.velocity_quantizer import quantize, VelocityQuantizerConfig
        cfg = VelocityQuantizerConfig(
            enabled=True,
            levels=4,
            min_value=10,
            max_value=100
        )
        for v in [0, 50, 127]:
            result = quantize(v, cfg)
            assert 10 <= result <= 100

    def test_biased_towards_soft(self):
        """Negative bias: favor lower velocity levels."""
        from gamepad_midi_bridge.velocity_quantizer import quantize, VelocityQuantizerConfig
        cfg_no_bias = VelocityQuantizerConfig(enabled=True, levels=4, bias=0.0)
        cfg_soft_bias = VelocityQuantizerConfig(enabled=True, levels=4, bias=-0.5)
        result_no_bias = quantize(64, cfg_no_bias)
        result_soft_bias = quantize(64, cfg_soft_bias)
        assert result_soft_bias <= result_no_bias

    def test_round_trip_with_custom_config(self):
        """Serialize, deserialize, and verify quantization is consistent."""
        from gamepad_midi_bridge.velocity_quantizer import (
            quantize, VelocityQuantizerConfig
        )
        original_cfg = VelocityQuantizerConfig(
            enabled=True,
            levels=6,
            min_value=20,
            max_value=100,
            bias=0.2,
            level_names=["verysoft", "soft", "med", "loud", "louder", "loudest"]
        )
        d = original_cfg.to_dict()
        restored_cfg = VelocityQuantizerConfig.from_dict(d)
        for v in [0, 30, 60, 90, 127]:
            orig_result = quantize(v, original_cfg)
            restored_result = quantize(v, restored_cfg)
            assert orig_result == restored_result
