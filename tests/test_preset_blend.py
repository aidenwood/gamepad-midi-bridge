"""Tests for preset blending: morphing between two configs via interpolation.

Pure stdlib + dataclasses, no Qt.
"""
from __future__ import annotations

import pytest


class TestLerp:
    """Linear interpolation functions."""

    def test_lerp_basic(self):
        from gamepad_midi_bridge.preset_blend import lerp

        assert lerp(0, 100, 0.5) == 50.0
        assert lerp(0, 100, 0.0) == 0.0
        assert lerp(0, 100, 1.0) == 100.0
        assert lerp(10, 20, 0.5) == 15.0

    def test_lerp_clamps_below_zero(self):
        from gamepad_midi_bridge.preset_blend import lerp

        assert lerp(0, 100, -0.5) == 0.0

    def test_lerp_clamps_above_one(self):
        from gamepad_midi_bridge.preset_blend import lerp

        assert lerp(0, 100, 1.5) == 100.0

    def test_lerp_negative_range(self):
        from gamepad_midi_bridge.preset_blend import lerp

        assert lerp(-50, 50, 0.5) == 0.0

    def test_lerp_float_precision(self):
        from gamepad_midi_bridge.preset_blend import lerp

        result = lerp(0.0, 1.0, 0.333)
        assert abs(result - 0.333) < 0.001


class TestLerpInt:
    """Integer interpolation with rounding."""

    def test_lerp_int_basic(self):
        from gamepad_midi_bridge.preset_blend import lerp_int

        assert lerp_int(0, 100, 0.5) == 50
        assert lerp_int(0, 127, 0.5) == 64  # 63.5 rounds to 64

    def test_lerp_int_rounds_correctly(self):
        from gamepad_midi_bridge.preset_blend import lerp_int

        # 0 + (100-0)*0.3 = 30.0 → 30
        assert lerp_int(0, 100, 0.3) == 30
        # 0 + (100-0)*0.7 = 70.0 → 70
        assert lerp_int(0, 100, 0.7) == 70

    def test_lerp_int_clamps_t(self):
        from gamepad_midi_bridge.preset_blend import lerp_int

        assert lerp_int(0, 100, -0.1) == 0
        assert lerp_int(0, 100, 1.1) == 100

    def test_lerp_int_midi_range(self):
        from gamepad_midi_bridge.preset_blend import lerp_int

        # Common MIDI: 0..127
        assert lerp_int(0, 127, 0.0) == 0
        assert lerp_int(0, 127, 0.5) == 64  # 63.5 rounds to 64
        assert lerp_int(0, 127, 1.0) == 127


class TestLerpBool:
    """Boolean crossfade at midpoint."""

    def test_lerp_bool_below_midpoint(self):
        from gamepad_midi_bridge.preset_blend import lerp_bool

        assert lerp_bool(True, False, 0.0) is True
        assert lerp_bool(True, False, 0.3) is True
        assert lerp_bool(True, False, 0.49999) is True

    def test_lerp_bool_above_midpoint(self):
        from gamepad_midi_bridge.preset_blend import lerp_bool

        assert lerp_bool(True, False, 0.5) is False
        assert lerp_bool(True, False, 0.7) is False
        assert lerp_bool(True, False, 1.0) is False

    def test_lerp_bool_reverse(self):
        from gamepad_midi_bridge.preset_blend import lerp_bool

        assert lerp_bool(False, True, 0.3) is False
        assert lerp_bool(False, True, 0.7) is True

    def test_lerp_bool_exact_midpoint(self):
        from gamepad_midi_bridge.preset_blend import lerp_bool

        # t=0.5 should return b (since condition is t < 0.5, not <=)
        assert lerp_bool(True, False, 0.5) is False


class TestLerpDictValues:
    """Dict value interpolation with type-aware lerping."""

    def test_lerp_dict_numeric_keys(self):
        from gamepad_midi_bridge.preset_blend import lerp_dict_values

        a = {"x": 0.0, "y": 100.0}
        b = {"x": 100.0, "y": 0.0}
        result = lerp_dict_values(a, b, 0.5, numeric_keys=["x", "y"])
        assert result["x"] == 50.0
        assert result["y"] == 50.0

    def test_lerp_dict_int_keys(self):
        from gamepad_midi_bridge.preset_blend import lerp_dict_values

        a = {"cc": 0}
        b = {"cc": 127}
        result = lerp_dict_values(a, b, 0.5, int_keys=["cc"])
        assert result["cc"] == 64  # 63.5 rounded

    def test_lerp_dict_bool_keys(self):
        from gamepad_midi_bridge.preset_blend import lerp_dict_values

        a = {"enabled": True}
        b = {"enabled": False}
        result = lerp_dict_values(a, b, 0.3, bool_keys=["enabled"])
        assert result["enabled"] is True
        result = lerp_dict_values(a, b, 0.7, bool_keys=["enabled"])
        assert result["enabled"] is False

    def test_lerp_dict_categorical_fallback(self):
        from gamepad_midi_bridge.preset_blend import lerp_dict_values

        a = {"mode": "linear"}
        b = {"mode": "exponential"}
        # No category specified, so defaults to categorical (crossfade at 0.5)
        result = lerp_dict_values(a, b, 0.3)
        assert result["mode"] == "linear"
        result = lerp_dict_values(a, b, 0.7)
        assert result["mode"] == "exponential"

    def test_lerp_dict_mixed_types(self):
        from gamepad_midi_bridge.preset_blend import lerp_dict_values

        a = {"threshold": 0.5, "cc": 0, "enabled": True, "mode": "linear"}
        b = {"threshold": 0.9, "cc": 127, "enabled": False, "mode": "latch"}

        result = lerp_dict_values(
            a, b, 0.5,
            numeric_keys=["threshold"],
            int_keys=["cc"],
            bool_keys=["enabled"]
            # mode is categorical (not listed)
        )
        assert abs(result["threshold"] - 0.7) < 0.01
        assert result["cc"] == 64  # 63.5 rounded
        assert result["enabled"] is False  # t=0.5 → b
        assert result["mode"] == "latch"  # t=0.5 → b (categorical)

    def test_lerp_dict_skips_missing_keys(self):
        from gamepad_midi_bridge.preset_blend import lerp_dict_values

        a = {"x": 0.0, "y": 100.0}
        b = {"x": 100.0, "z": 50.0}  # 'y' only in a, 'z' only in b

        result = lerp_dict_values(a, b, 0.5, numeric_keys=["x", "y", "z"])
        # Only 'x' exists in both → only 'x' in result
        assert "x" in result
        assert "y" not in result
        assert "z" not in result

    def test_lerp_dict_at_t_zero(self):
        from gamepad_midi_bridge.preset_blend import lerp_dict_values

        a = {"val": 10.0}
        b = {"val": 20.0}
        result = lerp_dict_values(a, b, 0.0, numeric_keys=["val"])
        assert result["val"] == 10.0

    def test_lerp_dict_at_t_one(self):
        from gamepad_midi_bridge.preset_blend import lerp_dict_values

        a = {"val": 10.0}
        b = {"val": 20.0}
        result = lerp_dict_values(a, b, 1.0, numeric_keys=["val"])
        assert result["val"] == 20.0


class TestBlendConfigs:
    """Blend structured configs via schema."""

    def test_blend_configs_float_schema(self):
        from gamepad_midi_bridge.preset_blend import blend_configs

        a = {"threshold": 0.5, "curve": 1.0}
        b = {"threshold": 0.9, "curve": 2.0}
        schema = {"threshold": "float", "curve": "float"}

        result = blend_configs(a, b, 0.5, schema)
        assert abs(result["threshold"] - 0.7) < 0.01
        assert abs(result["curve"] - 1.5) < 0.01

    def test_blend_configs_int_schema(self):
        from gamepad_midi_bridge.preset_blend import blend_configs

        a = {"cc_a": 0, "cc_b": 64}
        b = {"cc_a": 127, "cc_b": 32}
        schema = {"cc_a": "int", "cc_b": "int"}

        result = blend_configs(a, b, 0.5, schema)
        assert result["cc_a"] == 64  # 63.5 rounded
        assert result["cc_b"] == 48  # 48.0

    def test_blend_configs_bool_schema(self):
        from gamepad_midi_bridge.preset_blend import blend_configs

        a = {"enabled": True, "active": False}
        b = {"enabled": False, "active": True}
        schema = {"enabled": "bool", "active": "bool"}

        result = blend_configs(a, b, 0.3, schema)
        assert result["enabled"] is True
        assert result["active"] is False

        result = blend_configs(a, b, 0.7, schema)
        assert result["enabled"] is False
        assert result["active"] is True

    def test_blend_configs_categorical_schema(self):
        from gamepad_midi_bridge.preset_blend import blend_configs

        a = {"mode": "linear"}
        b = {"mode": "exponential"}
        schema = {"mode": "categorical"}

        result = blend_configs(a, b, 0.3, schema)
        assert result["mode"] == "linear"

        result = blend_configs(a, b, 0.7, schema)
        assert result["mode"] == "exponential"

    def test_blend_configs_mixed_schema(self):
        from gamepad_midi_bridge.preset_blend import blend_configs

        a = {"ceiling": 100, "curve": 0.5, "enabled": True, "mode": "linear"}
        b = {"ceiling": 127, "curve": 2.0, "enabled": False, "mode": "latch"}
        schema = {
            "ceiling": "int",
            "curve": "float",
            "enabled": "bool",
            "mode": "categorical"
        }

        result = blend_configs(a, b, 0.5, schema)
        assert result["ceiling"] == 114  # 113.5 rounded
        assert abs(result["curve"] - 1.25) < 0.01
        assert result["enabled"] is False  # t=0.5 → b
        assert result["mode"] == "latch"  # t=0.5 → b (categorical)

    def test_blend_configs_unknown_type_defaults_categorical(self):
        from gamepad_midi_bridge.preset_blend import blend_configs

        a = {"val": "foo"}
        b = {"val": "bar"}
        schema = {"val": "unknown_type"}  # Not float, int, bool, or categorical

        result = blend_configs(a, b, 0.3, schema)
        assert result["val"] == "foo"  # Defaults to categorical

        result = blend_configs(a, b, 0.7, schema)
        assert result["val"] == "bar"


class TestBlendConfig:
    """BlendConfig dataclass."""

    def test_blend_config_defaults(self):
        from gamepad_midi_bridge.preset_blend import BlendConfig

        cfg = BlendConfig()
        assert cfg.enabled is False
        assert cfg.blend_factor == 0.0
        assert cfg.auto_animate is False
        assert cfg.animation_duration_s == 1.0

    def test_blend_config_clamps_blend_factor(self):
        from gamepad_midi_bridge.preset_blend import BlendConfig

        cfg = BlendConfig(blend_factor=-0.5)
        assert cfg.blend_factor == 0.0

        cfg = BlendConfig(blend_factor=1.5)
        assert cfg.blend_factor == 1.0

    def test_blend_config_clamps_animation_duration(self):
        from gamepad_midi_bridge.preset_blend import BlendConfig

        cfg = BlendConfig(animation_duration_s=0.001)
        assert cfg.animation_duration_s == 0.01

        cfg = BlendConfig(animation_duration_s=120.0)
        assert cfg.animation_duration_s == 60.0

    def test_blend_config_to_dict(self):
        from gamepad_midi_bridge.preset_blend import BlendConfig

        cfg = BlendConfig(enabled=True, blend_factor=0.75, animation_duration_s=2.5)
        d = cfg.to_dict()
        assert d["enabled"] is True
        assert d["blend_factor"] == 0.75
        assert d["auto_animate"] is False
        assert d["animation_duration_s"] == 2.5

    def test_blend_config_from_dict(self):
        from gamepad_midi_bridge.preset_blend import BlendConfig

        d = {
            "enabled": True,
            "blend_factor": 0.5,
            "auto_animate": True,
            "animation_duration_s": 3.0
        }
        cfg = BlendConfig.from_dict(d)
        assert cfg.enabled is True
        assert cfg.blend_factor == 0.5
        assert cfg.auto_animate is True
        assert cfg.animation_duration_s == 3.0

    def test_blend_config_roundtrip(self):
        from gamepad_midi_bridge.preset_blend import BlendConfig

        orig = BlendConfig(enabled=True, blend_factor=0.33, animation_duration_s=1.5)
        d = orig.to_dict()
        restored = BlendConfig.from_dict(d)
        assert restored.enabled == orig.enabled
        assert restored.blend_factor == orig.blend_factor
        assert restored.auto_animate == orig.auto_animate
        assert restored.animation_duration_s == orig.animation_duration_s

    def test_blend_config_from_dict_partial(self):
        from gamepad_midi_bridge.preset_blend import BlendConfig

        # Missing keys default to BlendConfig defaults
        d = {"enabled": True}
        cfg = BlendConfig.from_dict(d)
        assert cfg.enabled is True
        assert cfg.blend_factor == 0.0
        assert cfg.animation_duration_s == 1.0


class TestBlendAnimator:
    """BlendAnimator — animation state machine."""

    def test_animator_no_animation_returns_cfg_value(self):
        from gamepad_midi_bridge.preset_blend import BlendAnimator, BlendConfig

        cfg = BlendConfig(blend_factor=0.3)
        anim = BlendAnimator(cfg=cfg)
        assert anim.current(0.0) == 0.3
        assert anim.current(10.0) == 0.3

    def test_animator_set_target_clamps(self):
        from gamepad_midi_bridge.preset_blend import BlendAnimator, BlendConfig

        cfg = BlendConfig()
        anim = BlendAnimator(cfg=cfg)
        anim.set_target(-0.5, 0.0)
        # Target is clamped to 0..1
        assert anim._target_factor == 0.0

        anim.set_target(1.5, 0.0)
        assert anim._target_factor == 1.0

    def test_animator_midpoint_interpolation(self):
        from gamepad_midi_bridge.preset_blend import BlendAnimator, BlendConfig

        cfg = BlendConfig(animation_duration_s=1.0)
        anim = BlendAnimator(cfg=cfg)
        anim.set_target(1.0, 0.0)
        # At t=0.5s (halfway), should be ~0.5
        current = anim.current(0.5)
        assert abs(current - 0.5) < 0.01

    def test_animator_settles_at_target(self):
        from gamepad_midi_bridge.preset_blend import BlendAnimator, BlendConfig

        cfg = BlendConfig(animation_duration_s=1.0)
        anim = BlendAnimator(cfg=cfg)
        anim.set_target(1.0, 0.0)
        # At t=1.0s (animation complete)
        current = anim.current(1.0)
        assert current == 1.0
        # cfg.blend_factor should be updated
        assert cfg.blend_factor == 1.0

    def test_animator_clears_state_after_completion(self):
        from gamepad_midi_bridge.preset_blend import BlendAnimator, BlendConfig

        cfg = BlendConfig(animation_duration_s=1.0)
        anim = BlendAnimator(cfg=cfg)
        anim.set_target(1.0, 0.0)
        anim.current(1.0)  # Complete animation
        # State should be cleared
        assert anim._start_time is None
        # Subsequent calls should return settled value
        assert anim.current(10.0) == 1.0

    def test_animator_preserves_start_factor(self):
        from gamepad_midi_bridge.preset_blend import BlendAnimator, BlendConfig

        cfg = BlendConfig(blend_factor=0.2, animation_duration_s=1.0)
        anim = BlendAnimator(cfg=cfg)
        anim.set_target(0.8, 0.0)
        # _start_factor should capture current value
        assert anim._start_factor == 0.2
        # Midpoint should interpolate from 0.2 to 0.8
        current = anim.current(0.5)
        assert abs(current - 0.5) < 0.01

    def test_animator_sequential_animations(self):
        from gamepad_midi_bridge.preset_blend import BlendAnimator, BlendConfig

        cfg = BlendConfig(animation_duration_s=1.0)
        anim = BlendAnimator(cfg=cfg)

        # First animation: 0 → 1 over [0, 1]
        anim.set_target(1.0, 0.0)
        anim.current(1.0)
        assert cfg.blend_factor == 1.0

        # Second animation: 1 → 0 over [2, 3]
        anim.set_target(0.0, 2.0)
        assert anim._start_factor == 1.0
        current = anim.current(2.5)  # Halfway
        assert abs(current - 0.5) < 0.01

    def test_animator_beyond_completion(self):
        from gamepad_midi_bridge.preset_blend import BlendAnimator, BlendConfig

        cfg = BlendConfig(animation_duration_s=1.0)
        anim = BlendAnimator(cfg=cfg)
        anim.set_target(1.0, 0.0)
        current = anim.current(2.0)  # Way past completion
        assert current == 1.0

    def test_animator_zero_duration_edge_case(self):
        from gamepad_midi_bridge.preset_blend import BlendAnimator, BlendConfig

        # Zero duration is clamped to 0.01 by BlendConfig
        cfg = BlendConfig(animation_duration_s=0.001)  # Will be clamped
        anim = BlendAnimator(cfg=cfg)
        anim.set_target(1.0, 0.0)
        # Should still complete (very fast)
        current = anim.current(0.02)
        assert current == 1.0

    def test_animator_interrupt_during_animation(self):
        from gamepad_midi_bridge.preset_blend import BlendAnimator, BlendConfig

        cfg = BlendConfig(animation_duration_s=2.0)
        anim = BlendAnimator(cfg=cfg)
        anim.set_target(1.0, 0.0)
        # At t=0.5s, progress is 0.5/2.0 = 0.25, so value should be ~0.25
        mid = anim.current(0.5)
        assert abs(mid - 0.25) < 0.01

        # Interrupt at 0.5s with new target at 0.0
        anim.set_target(0.0, 0.5)
        # _start_factor should be the current mid value
        assert abs(anim._start_factor - 0.25) < 0.01
        # Midway through new animation: elapsed=0.5, progress=0.5/2.0=0.25
        # lerp(0.25, 0.0, 0.25) = 0.1875
        current = anim.current(1.0)  # 0.5s later
        assert abs(current - 0.1875) < 0.01
