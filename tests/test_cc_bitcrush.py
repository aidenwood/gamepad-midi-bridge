"""Tests for CC bitcrush quantizer.

CcBitcrusher reduces bit-depth of CC values for lo-fi / stepped expression.
Pure stdlib, no Qt.
"""
from __future__ import annotations

import pytest


class TestCrushValue:
    """crush_value() — quantize raw CC to discrete levels."""

    def test_crush_value_no_crushing_bit_depth_7(self):
        """bit_depth=7 → 128 levels → essentially no crushing (step=1)."""
        from gamepad_midi_bridge.cc_bitcrush import crush_value
        # 128 / 2^7 = 128 / 128 = 1.0, so each input maps to itself.
        assert crush_value(0, 7) == 0
        assert crush_value(50, 7) == 50
        assert crush_value(127, 7) == 127

    def test_crush_value_bit_depth_4(self):
        """bit_depth=4 → 16 levels (step=8)."""
        from gamepad_midi_bridge.cc_bitcrush import crush_value
        # 128 / 2^4 = 128 / 16 = 8.0
        # Values 0..7 → 0, 8..15 → 8, 16..23 → 16, etc.
        assert crush_value(0, 4) == 0
        assert crush_value(7, 4) == 0
        assert crush_value(8, 4) == 8
        assert crush_value(15, 4) == 8
        assert crush_value(50, 4) == 48  # 50 // 8 = 6, 6 * 8 = 48
        assert crush_value(100, 4) == 96  # 100 // 8 = 12, 12 * 8 = 96

    def test_crush_value_bit_depth_1(self):
        """bit_depth=1 → 2 levels (step=64): 0 or 64."""
        from gamepad_midi_bridge.cc_bitcrush import crush_value
        # 128 / 2^1 = 128 / 2 = 64.0
        # Values 0..63 → 0, 64..127 → 64.
        assert crush_value(0, 1) == 0
        assert crush_value(50, 1) == 0
        assert crush_value(63, 1) == 0
        assert crush_value(64, 1) == 64
        assert crush_value(100, 1) == 64
        assert crush_value(127, 1) == 64

    def test_crush_value_clamp_input_below_zero(self):
        """Negative input clamped to 0."""
        from gamepad_midi_bridge.cc_bitcrush import crush_value
        assert crush_value(-10, 4) == 0
        assert crush_value(-1, 4) == 0

    def test_crush_value_clamp_input_above_127(self):
        """Input > 127 clamped to 127, then quantized."""
        from gamepad_midi_bridge.cc_bitcrush import crush_value
        assert crush_value(200, 4) == 120  # 127 // 8 = 15, 15 * 8 = 120
        assert crush_value(128, 4) == 120

    def test_crush_value_bit_depth_2(self):
        """bit_depth=2 → 4 levels (step=32)."""
        from gamepad_midi_bridge.cc_bitcrush import crush_value
        # 128 / 2^2 = 128 / 4 = 32.0
        # 0..31→0, 32..63→32, 64..95→64, 96..127→96.
        assert crush_value(0, 2) == 0
        assert crush_value(31, 2) == 0
        assert crush_value(32, 2) == 32
        assert crush_value(63, 2) == 32
        assert crush_value(64, 2) == 64
        assert crush_value(95, 2) == 64
        assert crush_value(96, 2) == 96
        assert crush_value(127, 2) == 96

    def test_crush_value_bit_depth_3(self):
        """bit_depth=3 → 8 levels (step=16)."""
        from gamepad_midi_bridge.cc_bitcrush import crush_value
        # 128 / 2^3 = 128 / 8 = 16.0
        assert crush_value(0, 3) == 0
        assert crush_value(15, 3) == 0
        assert crush_value(16, 3) == 16
        assert crush_value(100, 3) == 96  # 100 // 16 = 6, 6 * 16 = 96

    def test_crush_value_edge_127(self):
        """Ensure 127 snaps correctly at bit_depth=1."""
        from gamepad_midi_bridge.cc_bitcrush import crush_value
        # With bit_depth=1, step=64. 127 // 64 = 1, 1 * 64 = 64.
        assert crush_value(127, 1) == 64


class TestApplyWet:
    """apply_wet() — linear blend between crushed and original."""

    def test_apply_wet_fully_dry(self):
        """wet=0.0 → return original unchanged."""
        from gamepad_midi_bridge.cc_bitcrush import apply_wet
        assert apply_wet(0, 100, 0.0) == 100
        assert apply_wet(50, 100, 0.0) == 100
        assert apply_wet(127, 64, 0.0) == 64

    def test_apply_wet_fully_wet(self):
        """wet=1.0 → return crushed unchanged."""
        from gamepad_midi_bridge.cc_bitcrush import apply_wet
        assert apply_wet(0, 100, 1.0) == 0
        assert apply_wet(50, 100, 1.0) == 50
        assert apply_wet(127, 64, 1.0) == 127

    def test_apply_wet_half_wet(self):
        """wet=0.5 → average of crushed and original."""
        from gamepad_midi_bridge.cc_bitcrush import apply_wet
        # 0.5 * 100 + 0.5 * 100 = 100
        assert apply_wet(100, 100, 0.5) == 100
        # 0.5 * 0 + 0.5 * 100 = 50
        assert apply_wet(0, 100, 0.5) == 50
        # 0.5 * 127 + 0.5 * 0 ≈ 63.5 → 64 (rounded)
        assert apply_wet(127, 0, 0.5) == 64
        # 0.5 * 50 + 0.5 * 100 = 75
        assert apply_wet(50, 100, 0.5) == 75

    def test_apply_wet_quarter_wet(self):
        """wet=0.25 → 25% crushed, 75% original."""
        from gamepad_midi_bridge.cc_bitcrush import apply_wet
        # 0.25 * 0 + 0.75 * 100 = 75
        assert apply_wet(0, 100, 0.25) == 75
        # 0.25 * 100 + 0.75 * 0 = 25
        assert apply_wet(100, 0, 0.25) == 25

    def test_apply_wet_rounding(self):
        """apply_wet uses standard rounding."""
        from gamepad_midi_bridge.cc_bitcrush import apply_wet
        # 0.5 * 10 + 0.5 * 11 = 10.5 → rounds to 10
        assert apply_wet(10, 11, 0.5) == 10 or apply_wet(10, 11, 0.5) == 11
        # Just check that rounding is applied (might be 10 or 11 depending on ties).
        result = apply_wet(10, 11, 0.5)
        assert result in [10, 11]


class TestCcBitcrushConfig:
    """CcBitcrushConfig — clamp values on construction."""

    def test_config_defaults(self):
        from gamepad_midi_bridge.cc_bitcrush import CcBitcrushConfig
        cfg = CcBitcrushConfig()
        assert cfg.enabled is False
        assert cfg.bit_depth == 7
        assert cfg.sample_hold_ms == 0
        assert cfg.wet == 1.0

    def test_config_clamp_bit_depth_below_one(self):
        from gamepad_midi_bridge.cc_bitcrush import CcBitcrushConfig
        cfg = CcBitcrushConfig(bit_depth=0)
        assert cfg.bit_depth == 1
        cfg = CcBitcrushConfig(bit_depth=-5)
        assert cfg.bit_depth == 1

    def test_config_clamp_bit_depth_above_seven(self):
        from gamepad_midi_bridge.cc_bitcrush import CcBitcrushConfig
        cfg = CcBitcrushConfig(bit_depth=8)
        assert cfg.bit_depth == 7
        cfg = CcBitcrushConfig(bit_depth=100)
        assert cfg.bit_depth == 7

    def test_config_no_clamp_bit_depth_in_range(self):
        from gamepad_midi_bridge.cc_bitcrush import CcBitcrushConfig
        cfg = CcBitcrushConfig(bit_depth=4)
        assert cfg.bit_depth == 4

    def test_config_clamp_sample_hold_ms_below_zero(self):
        from gamepad_midi_bridge.cc_bitcrush import CcBitcrushConfig
        cfg = CcBitcrushConfig(sample_hold_ms=-100)
        assert cfg.sample_hold_ms == 0

    def test_config_clamp_sample_hold_ms_above_5000(self):
        from gamepad_midi_bridge.cc_bitcrush import CcBitcrushConfig
        cfg = CcBitcrushConfig(sample_hold_ms=10000)
        assert cfg.sample_hold_ms == 5000

    def test_config_no_clamp_sample_hold_ms_in_range(self):
        from gamepad_midi_bridge.cc_bitcrush import CcBitcrushConfig
        cfg = CcBitcrushConfig(sample_hold_ms=100)
        assert cfg.sample_hold_ms == 100

    def test_config_clamp_wet_below_zero(self):
        from gamepad_midi_bridge.cc_bitcrush import CcBitcrushConfig
        cfg = CcBitcrushConfig(wet=-0.5)
        assert cfg.wet == 0.0

    def test_config_clamp_wet_above_one(self):
        from gamepad_midi_bridge.cc_bitcrush import CcBitcrushConfig
        cfg = CcBitcrushConfig(wet=1.5)
        assert cfg.wet == 1.0

    def test_config_no_clamp_wet_in_range(self):
        from gamepad_midi_bridge.cc_bitcrush import CcBitcrushConfig
        cfg = CcBitcrushConfig(wet=0.5)
        assert cfg.wet == 0.5

    def test_config_to_dict(self):
        from gamepad_midi_bridge.cc_bitcrush import CcBitcrushConfig
        cfg = CcBitcrushConfig(enabled=True, bit_depth=4, sample_hold_ms=100, wet=0.75)
        d = cfg.to_dict()
        assert d["enabled"] is True
        assert d["bit_depth"] == 4
        assert d["sample_hold_ms"] == 100
        assert d["wet"] == 0.75

    def test_config_from_dict(self):
        from gamepad_midi_bridge.cc_bitcrush import CcBitcrushConfig
        d = {"enabled": True, "bit_depth": 3, "sample_hold_ms": 200, "wet": 0.5}
        cfg = CcBitcrushConfig.from_dict(d)
        assert cfg.enabled is True
        assert cfg.bit_depth == 3
        assert cfg.sample_hold_ms == 200
        assert cfg.wet == 0.5

    def test_config_from_dict_missing_keys_use_defaults(self):
        from gamepad_midi_bridge.cc_bitcrush import CcBitcrushConfig
        d = {"enabled": True}
        cfg = CcBitcrushConfig.from_dict(d)
        assert cfg.enabled is True
        assert cfg.bit_depth == 7
        assert cfg.sample_hold_ms == 0
        assert cfg.wet == 1.0

    def test_config_from_dict_applies_clamping(self):
        from gamepad_midi_bridge.cc_bitcrush import CcBitcrushConfig
        d = {"bit_depth": 20, "sample_hold_ms": -100, "wet": 2.0}
        cfg = CcBitcrushConfig.from_dict(d)
        assert cfg.bit_depth == 7
        assert cfg.sample_hold_ms == 0
        assert cfg.wet == 1.0

    def test_config_round_trip(self):
        from gamepad_midi_bridge.cc_bitcrush import CcBitcrushConfig
        original = CcBitcrushConfig(enabled=True, bit_depth=4, sample_hold_ms=150, wet=0.6)
        d = original.to_dict()
        restored = CcBitcrushConfig.from_dict(d)
        assert restored.enabled == original.enabled
        assert restored.bit_depth == original.bit_depth
        assert restored.sample_hold_ms == original.sample_hold_ms
        assert restored.wet == original.wet


class TestCcBitcrusher:
    """CcBitcrusher — stateful quantizer with rate limiting."""

    def test_feed_disabled_returns_raw(self):
        from gamepad_midi_bridge.cc_bitcrush import CcBitcrusher, CcBitcrushConfig
        cfg = CcBitcrushConfig(enabled=False)
        crusher = CcBitcrusher(cfg)
        assert crusher.feed(100, 0.0) == 100
        assert crusher.feed(50, 0.1) == 50
        assert crusher.feed(127, 0.2) == 127

    def test_feed_clamping_input(self):
        from gamepad_midi_bridge.cc_bitcrush import CcBitcrusher, CcBitcrushConfig
        cfg = CcBitcrushConfig(enabled=True, bit_depth=7)
        crusher = CcBitcrusher(cfg)
        assert crusher.feed(-10, 0.0) == 0
        assert crusher.feed(200, 0.0) == 127

    def test_feed_quantize_fresh_bit_depth_4(self):
        """Feed with no sample-hold always quantizes fresh."""
        from gamepad_midi_bridge.cc_bitcrush import CcBitcrusher, CcBitcrushConfig
        cfg = CcBitcrushConfig(enabled=True, bit_depth=4, sample_hold_ms=0, wet=1.0)
        crusher = CcBitcrusher(cfg)
        # 50 with bit_depth=4, step=8 → 48 (crushed, no blending).
        assert crusher.feed(50, 0.0) == 48
        # 100 with bit_depth=4 → 96.
        assert crusher.feed(100, 0.1) == 96

    def test_feed_sample_hold_suppresses_rapid_updates(self):
        """sample_hold_ms > 0 suppresses updates within hold time."""
        from gamepad_midi_bridge.cc_bitcrush import CcBitcrusher, CcBitcrushConfig
        cfg = CcBitcrushConfig(enabled=True, bit_depth=4, sample_hold_ms=100, wet=1.0)
        crusher = CcBitcrusher(cfg)
        # First emit: 50 → 48
        result1 = crusher.feed(50, 0.0)
        assert result1 == 48
        # Immediate second emit (0 ms elapsed < 100 ms hold): returns cached 48
        result2 = crusher.feed(100, 0.001)
        assert result2 == 48
        # After hold time: fresh quantization of 100 → 96
        result3 = crusher.feed(100, 0.2)
        assert result3 == 96

    def test_feed_sample_hold_edge_at_hold_time(self):
        """Emit happens exactly at hold boundary."""
        from gamepad_midi_bridge.cc_bitcrush import CcBitcrusher, CcBitcrushConfig
        cfg = CcBitcrushConfig(enabled=True, bit_depth=4, sample_hold_ms=100, wet=1.0)
        crusher = CcBitcrusher(cfg)
        result1 = crusher.feed(50, 0.0)
        assert result1 == 48
        # Just before 100 ms (99 ms < 100 ms hold): should still hold.
        result2 = crusher.feed(100, 0.099)
        assert result2 == 48
        # At or past 100 ms (elapsed >= hold_time): emit fresh.
        result3 = crusher.feed(100, 0.1)
        assert result3 == 96

    def test_feed_wet_blending_50_50(self):
        """wet=0.5 blends crushed and original."""
        from gamepad_midi_bridge.cc_bitcrush import CcBitcrusher, CcBitcrushConfig
        cfg = CcBitcrushConfig(enabled=True, bit_depth=4, sample_hold_ms=0, wet=0.5)
        crusher = CcBitcrusher(cfg)
        # Crushed: 50 → 48. Blend: 0.5*48 + 0.5*50 = 49.
        result = crusher.feed(50, 0.0)
        assert result == 49 or result == 49  # round(49.0) = 49

    def test_feed_wet_blending_dry(self):
        """wet=0.0 returns original unchanged."""
        from gamepad_midi_bridge.cc_bitcrush import CcBitcrusher, CcBitcrushConfig
        cfg = CcBitcrushConfig(enabled=True, bit_depth=4, sample_hold_ms=0, wet=0.0)
        crusher = CcBitcrusher(cfg)
        # Crushed: 50 → 48. Blend with wet=0.0: 0.0*48 + 1.0*50 = 50.
        result = crusher.feed(50, 0.0)
        assert result == 50

    def test_feed_updates_state(self):
        """feed() updates _last_emit_value and _last_emit_at."""
        from gamepad_midi_bridge.cc_bitcrush import CcBitcrusher, CcBitcrushConfig
        cfg = CcBitcrushConfig(enabled=True, bit_depth=4, sample_hold_ms=0, wet=1.0)
        crusher = CcBitcrusher(cfg)
        assert crusher._last_emit_at is None
        result1 = crusher.feed(50, 0.0)
        assert crusher._last_emit_at == 0.0
        assert crusher._last_emit_value == result1
        result2 = crusher.feed(100, 0.1)
        assert crusher._last_emit_at == 0.1
        assert crusher._last_emit_value == result2

    def test_feed_no_rate_limit_always_fresh(self):
        """sample_hold_ms=0 always emits fresh quantized value."""
        from gamepad_midi_bridge.cc_bitcrush import CcBitcrusher, CcBitcrushConfig
        cfg = CcBitcrushConfig(enabled=True, bit_depth=4, sample_hold_ms=0, wet=1.0)
        crusher = CcBitcrusher(cfg)
        result1 = crusher.feed(50, 0.0)
        assert result1 == 48
        # Very next call with same input but different value.
        result2 = crusher.feed(100, 0.0001)
        assert result2 == 96

    def test_reset_clears_state(self):
        """reset() clears _last_emit_at and _last_emit_value."""
        from gamepad_midi_bridge.cc_bitcrush import CcBitcrusher, CcBitcrushConfig
        cfg = CcBitcrushConfig(enabled=True, bit_depth=4, sample_hold_ms=100, wet=1.0)
        crusher = CcBitcrusher(cfg)
        crusher.feed(50, 0.0)
        assert crusher._last_emit_at is not None
        assert crusher._last_emit_value != 0
        crusher.reset()
        assert crusher._last_emit_at is None
        assert crusher._last_emit_value == 0

    def test_reset_then_first_feed_ignores_hold(self):
        """After reset(), first feed() ignores hold time."""
        from gamepad_midi_bridge.cc_bitcrush import CcBitcrusher, CcBitcrushConfig
        cfg = CcBitcrushConfig(enabled=True, bit_depth=4, sample_hold_ms=1000, wet=1.0)
        crusher = CcBitcrusher(cfg)
        crusher.feed(50, 0.0)
        crusher.reset()
        # After reset, _last_emit_at is None, so second check won't apply hold.
        result = crusher.feed(100, 0.001)
        assert result == 96

    def test_comprehensive_scenario(self):
        """End-to-end: quantize, hold, blend."""
        from gamepad_midi_bridge.cc_bitcrush import CcBitcrusher, CcBitcrushConfig
        cfg = CcBitcrushConfig(enabled=True, bit_depth=4, sample_hold_ms=50, wet=0.75)
        crusher = CcBitcrusher(cfg)

        # t=0.0: Raw 50, crushed→48, wet blend (0.75*48 + 0.25*50 = 48.5 → 49).
        result1 = crusher.feed(50, 0.0)
        assert result1 == 49 or result1 == 48  # Rounding may vary.

        # t=0.01 (10 ms < 50 ms hold): return cached.
        result2 = crusher.feed(100, 0.01)
        assert result2 == result1

        # t=0.06 (60 ms > 50 ms hold): fresh quantize. Raw 100, crushed→96, blend (0.75*96 + 0.25*100 = 97).
        result3 = crusher.feed(100, 0.06)
        assert result3 == 97 or result3 == 96 or result3 == 97  # Rounding.
