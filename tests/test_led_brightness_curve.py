"""Tests for led_brightness_curve.py — LED brightness fade helpers."""
from __future__ import annotations

import pytest
import math

from gamepad_midi_bridge.led_brightness_curve import (
    linear,
    ease_in,
    ease_out,
    ease_in_out_cubic,
    exponential,
    breathing,
    apply_curve,
    to_brightness_byte,
    BrightnessFadeConfig,
    BrightnessFade,
    BRIGHTNESS_CURVE_MODES,
)


# ============================================================================
# Tests for pure curve functions
# ============================================================================


class TestLinear:
    """Tests for linear(progress: float) -> float."""

    def test_linear_at_0(self):
        """Linear at progress=0 returns 0."""
        assert linear(0.0) == 0.0

    def test_linear_at_1(self):
        """Linear at progress=1 returns 1."""
        assert linear(1.0) == 1.0

    def test_linear_midpoint(self):
        """Linear at progress=0.5 returns 0.5."""
        assert linear(0.5) == 0.5

    def test_linear_clamps_below_0(self):
        """Linear clamps negative values to 0."""
        assert linear(-0.5) == 0.0
        assert linear(-100.0) == 0.0

    def test_linear_clamps_above_1(self):
        """Linear clamps values > 1 to 1."""
        assert linear(1.5) == 1.0
        assert linear(100.0) == 1.0


class TestEaseIn:
    """Tests for ease_in(progress: float) -> float."""

    def test_ease_in_at_0(self):
        """Ease-in at progress=0 returns 0."""
        assert ease_in(0.0) == 0.0

    def test_ease_in_at_1(self):
        """Ease-in at progress=1 returns 1."""
        assert ease_in(1.0) == 1.0

    def test_ease_in_midpoint(self):
        """Ease-in at progress=0.5 returns 0.25 (0.5^2)."""
        assert ease_in(0.5) == 0.25

    def test_ease_in_slower_than_linear(self):
        """Ease-in curves below linear at midpoint."""
        assert ease_in(0.5) < linear(0.5)
        assert ease_in(0.25) < linear(0.25)


class TestEaseOut:
    """Tests for ease_out(progress: float) -> float."""

    def test_ease_out_at_0(self):
        """Ease-out at progress=0 returns 0."""
        assert ease_out(0.0) == 0.0

    def test_ease_out_at_1(self):
        """Ease-out at progress=1 returns 1."""
        assert ease_out(1.0) == 1.0

    def test_ease_out_midpoint(self):
        """Ease-out at progress=0.5 returns 0.75 (1 - 0.5^2)."""
        assert ease_out(0.5) == 0.75

    def test_ease_out_faster_than_linear(self):
        """Ease-out curves above linear at midpoint."""
        assert ease_out(0.5) > linear(0.5)
        assert ease_out(0.25) > linear(0.25)


class TestEaseInOutCubic:
    """Tests for ease_in_out_cubic(progress: float) -> float."""

    def test_ease_in_out_cubic_at_0(self):
        """Ease-in-out-cubic at progress=0 returns 0."""
        assert ease_in_out_cubic(0.0) == 0.0

    def test_ease_in_out_cubic_at_1(self):
        """Ease-in-out-cubic at progress=1 returns 1."""
        assert ease_in_out_cubic(1.0) == 1.0

    def test_ease_in_out_cubic_at_0_5(self):
        """Ease-in-out-cubic at progress=0.5 returns 0.5 (symmetric)."""
        assert ease_in_out_cubic(0.5) == 0.5

    def test_ease_in_out_cubic_monotonic(self):
        """Ease-in-out-cubic is monotonically increasing."""
        prev = 0.0
        for i in range(1, 11):
            p = i / 10.0
            val = ease_in_out_cubic(p)
            assert val >= prev
            prev = val


class TestExponential:
    """Tests for exponential(progress: float) -> float."""

    def test_exponential_at_0(self):
        """Exponential at progress=0 returns 0."""
        assert exponential(0.0) == 0.0

    def test_exponential_at_1(self):
        """Exponential at progress=1 returns 1."""
        assert exponential(1.0) == 1.0

    def test_exponential_biases_low(self):
        """Exponential at progress=0.5 is < 0.5 (biases low)."""
        val = exponential(0.5)
        assert val < 0.5

    def test_exponential_accelerates(self):
        """Exponential accelerates sharply towards end."""
        val_75 = exponential(0.75)
        val_25 = exponential(0.25)
        # Exponential biases low, so val_25 is much lower than 0.5
        assert val_75 > val_25
        assert val_75 > 0.5
        assert val_25 < 0.5


class TestBreathing:
    """Tests for breathing(progress: float, periods: float = 2.0) -> float."""

    def test_breathing_at_0(self):
        """Breathing at progress=0 returns 0."""
        assert breathing(0.0) == 0.0

    def test_breathing_at_1(self):
        """Breathing at progress=1 returns 0 (full period)."""
        val = breathing(1.0)
        assert abs(val - 0.0) < 1e-10

    def test_breathing_at_half_period(self):
        """Breathing at progress=0.5 (half period) with periods=2 returns 0."""
        # With periods=2, at progress=0.5 we've completed one full period,
        # so we're back to the trough (0), not the peak
        val = breathing(0.5, periods=2.0)
        assert abs(val - 0.0) < 1e-10

    def test_breathing_oscillates(self):
        """Breathing oscillates smoothly between 0 and 1."""
        samples = [breathing(i / 10.0) for i in range(11)]
        # Should have a peak somewhere in the middle
        # With periods=2 (default), peak is around 0.9 (not 1.0)
        assert max(samples) > 0.85
        assert min(samples) < 0.1

    def test_breathing_single_period(self):
        """With periods=1, one complete oscillation in [0, 1]."""
        val_25 = breathing(0.25, periods=1.0)
        val_50 = breathing(0.50, periods=1.0)
        val_75 = breathing(0.75, periods=1.0)
        # Should reach peak around 0.5
        assert val_50 > val_25
        assert val_50 > val_75


# ============================================================================
# Tests for apply_curve dispatcher
# ============================================================================


class TestApplyCurve:
    """Tests for apply_curve(curve_name: str, progress: float, **kwargs)."""

    @pytest.mark.parametrize("name,func", [
        ("linear", linear),
        ("ease_in", ease_in),
        ("ease_out", ease_out),
        ("ease_in_out_cubic", ease_in_out_cubic),
        ("exponential", exponential),
    ])
    def test_apply_curve_dispatches_correctly(self, name, func):
        """apply_curve dispatches to correct curve function."""
        for p in [0.0, 0.25, 0.5, 0.75, 1.0]:
            assert apply_curve(name, p) == func(p)

    def test_apply_curve_breathing_default_periods(self):
        """apply_curve dispatches breathing with default periods=2."""
        assert apply_curve("breathing", 0.0) == breathing(0.0, periods=2.0)
        assert apply_curve("breathing", 0.5) == breathing(0.5, periods=2.0)

    def test_apply_curve_breathing_custom_periods(self):
        """apply_curve can pass custom periods to breathing."""
        val = apply_curve("breathing", 0.5, periods=1.0)
        assert val == breathing(0.5, periods=1.0)

    def test_apply_curve_unknown_falls_back_to_linear(self):
        """Unknown curve name falls back to linear."""
        assert apply_curve("unknown_curve", 0.5) == linear(0.5)
        assert apply_curve("foobar", 0.25) == linear(0.25)


# ============================================================================
# Tests for to_brightness_byte
# ============================================================================


class TestToBrightnessByte:
    """Tests for to_brightness_byte(value_0_1: float, max_byte: int = 255)."""

    def test_to_brightness_byte_at_0(self):
        """at_value=0.0 returns 0."""
        assert to_brightness_byte(0.0) == 0

    def test_to_brightness_byte_at_1(self):
        """at_value=1.0 returns 255."""
        assert to_brightness_byte(1.0) == 255

    def test_to_brightness_byte_at_midpoint(self):
        """at_value=0.5 returns 128 (rounded)."""
        assert to_brightness_byte(0.5) == 128

    def test_to_brightness_byte_clamps_below_0(self):
        """Negative values clamp to 0."""
        assert to_brightness_byte(-0.5) == 0
        assert to_brightness_byte(-1.0) == 0

    def test_to_brightness_byte_clamps_above_1(self):
        """Values > 1 clamp to 255."""
        assert to_brightness_byte(1.5) == 255
        assert to_brightness_byte(2.0) == 255

    def test_to_brightness_byte_custom_max(self):
        """Custom max_byte argument is respected."""
        assert to_brightness_byte(0.0, max_byte=100) == 0
        assert to_brightness_byte(1.0, max_byte=100) == 100
        assert to_brightness_byte(0.5, max_byte=100) == 50


# ============================================================================
# Tests for BrightnessFadeConfig
# ============================================================================


class TestBrightnessFadeConfigDefaults:
    """Tests for BrightnessFadeConfig defaults."""

    def test_enabled_default_false(self):
        cfg = BrightnessFadeConfig()
        assert cfg.enabled is False

    def test_start_value_default(self):
        assert BrightnessFadeConfig().start_value == 0

    def test_end_value_default(self):
        assert BrightnessFadeConfig().end_value == 255

    def test_duration_s_default(self):
        assert BrightnessFadeConfig().duration_s == 1.0

    def test_curve_default(self):
        assert BrightnessFadeConfig().curve == "ease_in_out_cubic"

    def test_loop_default_false(self):
        assert BrightnessFadeConfig().loop is False


class TestBrightnessFadeConfigClamping:
    """Tests for BrightnessFadeConfig clamping and normalisation."""

    def test_clamp_start_value_below_0(self):
        cfg = BrightnessFadeConfig(start_value=-100)
        assert cfg.start_value == 0

    def test_clamp_start_value_above_255(self):
        cfg = BrightnessFadeConfig(start_value=300)
        assert cfg.start_value == 255

    def test_clamp_end_value_below_0(self):
        cfg = BrightnessFadeConfig(end_value=-50)
        assert cfg.end_value == 0

    def test_clamp_end_value_above_255(self):
        cfg = BrightnessFadeConfig(end_value=500)
        assert cfg.end_value == 255

    def test_clamp_duration_below_0_01(self):
        cfg = BrightnessFadeConfig(duration_s=0.001)
        assert cfg.duration_s == 0.01

    def test_clamp_duration_above_60(self):
        cfg = BrightnessFadeConfig(duration_s=100.0)
        assert cfg.duration_s == 60.0

    def test_normalize_curve_unknown_to_linear(self):
        cfg = BrightnessFadeConfig(curve="unknown_mode")
        assert cfg.curve == "linear"

    def test_normalize_curve_valid_mode(self):
        cfg = BrightnessFadeConfig(curve="ease_in")
        assert cfg.curve == "ease_in"


class TestBrightnessFadeConfigSerialization:
    """Tests for BrightnessFadeConfig to_dict and from_dict."""

    def test_to_dict_roundtrip(self):
        cfg = BrightnessFadeConfig(
            enabled=True,
            start_value=50,
            end_value=200,
            duration_s=2.5,
            curve="ease_in",
            loop=True,
        )
        data = cfg.to_dict()
        cfg2 = BrightnessFadeConfig.from_dict(data)
        assert cfg2.enabled is True
        assert cfg2.start_value == 50
        assert cfg2.end_value == 200
        assert cfg2.duration_s == 2.5
        assert cfg2.curve == "ease_in"
        assert cfg2.loop is True

    def test_from_dict_with_missing_keys(self):
        data = {"start_value": 100}
        cfg = BrightnessFadeConfig.from_dict(data)
        assert cfg.start_value == 100
        assert cfg.end_value == 255  # default
        assert cfg.enabled is False  # default
        assert cfg.curve == "ease_in_out_cubic"  # default

    def test_from_dict_clamping_still_applies(self):
        data = {
            "start_value": 500,
            "duration_s": 0.001,
            "curve": "invalid",
        }
        cfg = BrightnessFadeConfig.from_dict(data)
        assert cfg.start_value == 255  # clamped
        assert cfg.duration_s == 0.01  # clamped
        assert cfg.curve == "linear"  # normalized


# ============================================================================
# Tests for BrightnessFade runtime
# ============================================================================


class TestBrightnessFadeBeforeStart:
    """Tests for BrightnessFade.value before start() called."""

    def test_value_before_start_returns_start_value(self):
        cfg = BrightnessFadeConfig(start_value=50, end_value=200)
        fade = BrightnessFade(cfg)
        assert fade.value(0.0) == 50

    def test_is_done_before_start_returns_false(self):
        cfg = BrightnessFadeConfig()
        fade = BrightnessFade(cfg)
        assert fade.is_done(0.0) is False


class TestBrightnessFadeSimpleFade:
    """Tests for a simple forward fade without looping."""

    def test_fade_at_start(self):
        cfg = BrightnessFadeConfig(start_value=0, end_value=255, duration_s=1.0)
        fade = BrightnessFade(cfg)
        fade.start(0.0)
        val = fade.value(0.0)
        assert val == 0

    def test_fade_at_end(self):
        cfg = BrightnessFadeConfig(start_value=0, end_value=255, duration_s=1.0)
        fade = BrightnessFade(cfg)
        fade.start(0.0)
        val = fade.value(1.0)
        assert val == 255

    def test_fade_at_midpoint(self):
        cfg = BrightnessFadeConfig(
            start_value=0,
            end_value=255,
            duration_s=1.0,
            curve="linear",
        )
        fade = BrightnessFade(cfg)
        fade.start(0.0)
        val = fade.value(0.5)
        # Linear at 0.5 = 0.5, lerp 0->255 = 127.5 -> round to 128
        assert 127 <= val <= 128

    def test_is_done_at_end(self):
        cfg = BrightnessFadeConfig(duration_s=1.0, loop=False)
        fade = BrightnessFade(cfg)
        fade.start(0.0)
        assert fade.is_done(0.5) is False
        assert fade.is_done(1.0) is True
        assert fade.is_done(1.5) is True


class TestBrightnessFadeLooping:
    """Tests for looping fades (direction reversal)."""

    def test_loop_reverses_direction(self):
        cfg = BrightnessFadeConfig(
            start_value=0,
            end_value=255,
            duration_s=1.0,
            curve="linear",
            loop=True,
        )
        fade = BrightnessFade(cfg)
        fade.start(0.0)
        # At t=1.0, should be at end; direction should flip
        val_at_1_0 = fade.value(1.0)
        assert val_at_1_0 == 255
        # Immediately after, progress resets and direction is reversed
        # At t=1.01 (0.01s into the reverse), should be slightly below 255
        val_at_1_01 = fade.value(1.01)
        assert val_at_1_01 < 255

    def test_loop_continues_indefinitely(self):
        cfg = BrightnessFadeConfig(
            start_value=0,
            end_value=255,
            duration_s=1.0,
            curve="linear",
            loop=True,
        )
        fade = BrightnessFade(cfg)
        fade.start(0.0)
        # Forward phase
        assert fade.value(0.5) > 0
        assert fade.value(1.0) == 255
        # Reverse phase
        assert fade.value(1.5) < 255
        assert fade.value(2.0) == 0
        # Forward again
        assert fade.value(2.5) > 0

    def test_loop_false_stops_at_end(self):
        cfg = BrightnessFadeConfig(
            start_value=0,
            end_value=255,
            duration_s=1.0,
            curve="linear",
            loop=False,
        )
        fade = BrightnessFade(cfg)
        fade.start(0.0)
        assert fade.value(1.0) == 255
        assert fade.value(1.5) == 255  # Stays at end
        assert fade.value(2.0) == 255


class TestBrightnessFadeReset:
    """Tests for BrightnessFade.reset()."""

    def test_reset_clears_state(self):
        cfg = BrightnessFadeConfig(start_value=0, end_value=255, duration_s=1.0)
        fade = BrightnessFade(cfg)
        fade.start(0.0)
        fade.value(0.5)
        fade.reset()
        # After reset, should return to start_value
        assert fade.value(999.0) == 0


class TestBrightnessFadeCurveApplication:
    """Tests for curve application in BrightnessFade."""

    def test_ease_in_fades_slower_at_start(self):
        cfg_ease_in = BrightnessFadeConfig(
            start_value=0,
            end_value=255,
            duration_s=1.0,
            curve="ease_in",
        )
        cfg_linear = BrightnessFadeConfig(
            start_value=0,
            end_value=255,
            duration_s=1.0,
            curve="linear",
        )
        fade_ease_in = BrightnessFade(cfg_ease_in)
        fade_linear = BrightnessFade(cfg_linear)
        fade_ease_in.start(0.0)
        fade_linear.start(0.0)
        # At quarter-way through, ease_in should be below linear
        val_ease_in = fade_ease_in.value(0.25)
        val_linear = fade_linear.value(0.25)
        assert val_ease_in < val_linear

    def test_ease_out_fades_faster_at_start(self):
        cfg_ease_out = BrightnessFadeConfig(
            start_value=0,
            end_value=255,
            duration_s=1.0,
            curve="ease_out",
        )
        cfg_linear = BrightnessFadeConfig(
            start_value=0,
            end_value=255,
            duration_s=1.0,
            curve="linear",
        )
        fade_ease_out = BrightnessFade(cfg_ease_out)
        fade_linear = BrightnessFade(cfg_linear)
        fade_ease_out.start(0.0)
        fade_linear.start(0.0)
        # At quarter-way through, ease_out should be above linear
        val_ease_out = fade_ease_out.value(0.25)
        val_linear = fade_linear.value(0.25)
        assert val_ease_out > val_linear


class TestBrightnessFadeEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_very_short_duration(self):
        cfg = BrightnessFadeConfig(
            start_value=0,
            end_value=255,
            duration_s=0.01,  # Minimum
        )
        fade = BrightnessFade(cfg)
        fade.start(0.0)
        val = fade.value(0.0)
        assert val == 0
        val = fade.value(0.01)
        assert val == 255

    def test_very_long_duration(self):
        cfg = BrightnessFadeConfig(
            start_value=0,
            end_value=255,
            duration_s=60.0,  # Maximum
        )
        fade = BrightnessFade(cfg)
        fade.start(0.0)
        val = fade.value(30.0)
        # At halfway, expect roughly 128
        assert 120 <= val <= 135

    def test_same_start_and_end(self):
        cfg = BrightnessFadeConfig(
            start_value=100,
            end_value=100,
            duration_s=1.0,
        )
        fade = BrightnessFade(cfg)
        fade.start(0.0)
        # Should always be 100 regardless of progress
        assert fade.value(0.0) == 100
        assert fade.value(0.5) == 100
        assert fade.value(1.0) == 100

    def test_inverted_start_end(self):
        cfg = BrightnessFadeConfig(
            start_value=255,
            end_value=0,
            duration_s=1.0,
            curve="linear",
        )
        fade = BrightnessFade(cfg)
        fade.start(0.0)
        # Should fade from 255 down to 0
        assert fade.value(0.0) == 255
        val_mid = fade.value(0.5)
        assert 120 <= val_mid <= 135
        assert fade.value(1.0) == 0
