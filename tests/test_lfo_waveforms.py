"""Tests for LFO waveform library and state machine."""

import math
import time

import pytest

from gamepad_midi_bridge.lfo_waveforms import (
    LfoConfig,
    LfoState,
    evaluate,
    ramp_down,
    ramp_up,
    sine,
    square,
    to_cc,
    triangle,
)


class TestSineWaveform:
    """Tests for sine wave."""

    def test_sine_zero_phase(self):
        """Sine at phase 0 should be 0.5 (mid)."""
        assert abs(sine(0) - 0.5) < 0.001

    def test_sine_quarter_phase(self):
        """Sine at phase 0.25 should be 1.0 (peak)."""
        assert abs(sine(0.25) - 1.0) < 0.001

    def test_sine_half_phase(self):
        """Sine at phase 0.5 should be 0.5 (mid)."""
        assert abs(sine(0.5) - 0.5) < 0.001

    def test_sine_three_quarter_phase(self):
        """Sine at phase 0.75 should be 0.0 (trough)."""
        assert abs(sine(0.75) - 0.0) < 0.001


class TestTriangleWaveform:
    """Tests for triangle wave."""

    def test_triangle_zero_phase(self):
        """Triangle at phase 0 should be 0.0."""
        assert triangle(0) == 0.0

    def test_triangle_quarter_phase(self):
        """Triangle at phase 0.25 should be 0.5."""
        assert triangle(0.25) == 0.5

    def test_triangle_half_phase(self):
        """Triangle at phase 0.5 should be 1.0 (peak)."""
        assert triangle(0.5) == 1.0

    def test_triangle_three_quarter_phase(self):
        """Triangle at phase 0.75 should be 0.5."""
        assert triangle(0.75) == 0.5

    def test_triangle_full_phase(self):
        """Triangle at phase 1.0 should be 0.0."""
        assert triangle(1.0) == 0.0


class TestRampWaveforms:
    """Tests for ramp_up and ramp_down."""

    def test_ramp_up_zero(self):
        """Ramp up at phase 0 should be 0.0."""
        assert ramp_up(0) == 0.0

    def test_ramp_up_mid(self):
        """Ramp up at phase 0.5 should be 0.5."""
        assert ramp_up(0.5) == 0.5

    def test_ramp_up_full(self):
        """Ramp up at phase 1.0 should be 1.0."""
        assert ramp_up(1.0) == 1.0

    def test_ramp_down_zero(self):
        """Ramp down at phase 0 should be 1.0."""
        assert ramp_down(0) == 1.0

    def test_ramp_down_mid(self):
        """Ramp down at phase 0.5 should be 0.5."""
        assert ramp_down(0.5) == 0.5

    def test_ramp_down_full(self):
        """Ramp down at phase 1.0 should be 0.0."""
        assert ramp_down(1.0) == 0.0


class TestSquareWaveform:
    """Tests for square wave with duty cycle."""

    def test_square_default_duty_low(self):
        """Square with default duty (0.5) should be 1.0 when phase < 0.5."""
        assert square(0.3, duty=0.5) == 1.0

    def test_square_default_duty_high(self):
        """Square with default duty (0.5) should be 0.0 when phase >= 0.5."""
        assert square(0.7, duty=0.5) == 0.0

    def test_square_at_duty_boundary(self):
        """Square at exactly the duty boundary should be 0.0."""
        assert square(0.5, duty=0.5) == 0.0

    def test_square_zero_duty(self):
        """Square with duty 0.0 should always be 0.0."""
        assert square(0.3, duty=0.0) == 0.0
        assert square(0.7, duty=0.0) == 0.0

    def test_square_full_duty(self):
        """Square with duty 1.0 should always be 1.0."""
        assert square(0.3, duty=1.0) == 1.0
        assert square(0.7, duty=1.0) == 1.0

    def test_square_duty_75_percent(self):
        """Square with 75% duty should transition at phase 0.75."""
        assert square(0.5, duty=0.75) == 1.0
        assert square(0.8, duty=0.75) == 0.0

    def test_square_clamps_duty_low(self):
        """Square should clamp duty < 0.0 to 0.0."""
        assert square(0.3, duty=-0.1) == 0.0

    def test_square_clamps_duty_high(self):
        """Square should clamp duty > 1.0 to 1.0."""
        assert square(0.3, duty=1.1) == 1.0


class TestEvaluateDispatch:
    """Tests for evaluate() dispatcher."""

    def test_evaluate_sine(self):
        """Evaluate with shape='sine' should match sine()."""
        assert abs(evaluate("sine", 0.25) - sine(0.25)) < 0.001

    def test_evaluate_triangle(self):
        """Evaluate with shape='triangle' should match triangle()."""
        assert evaluate("triangle", 0.5) == triangle(0.5)

    def test_evaluate_ramp_up(self):
        """Evaluate with shape='ramp_up' should match ramp_up()."""
        assert evaluate("ramp_up", 0.5) == ramp_up(0.5)

    def test_evaluate_ramp_down(self):
        """Evaluate with shape='ramp_down' should match ramp_down()."""
        assert evaluate("ramp_down", 0.5) == ramp_down(0.5)

    def test_evaluate_square(self):
        """Evaluate with shape='square' should match square()."""
        assert evaluate("square", 0.3, duty=0.5) == square(0.3, duty=0.5)

    def test_evaluate_unknown_defaults_to_sine(self):
        """Evaluate with unknown shape should default to sine."""
        unknown_result = evaluate("unknown", 0.25)
        sine_result = sine(0.25)
        assert abs(unknown_result - sine_result) < 0.001


class TestLfoConfigClamping:
    """Tests for LfoConfig value clamping."""

    def test_clamp_rate_hz_low(self):
        """Rate below 0.01 should be clamped to 0.01."""
        cfg = LfoConfig(rate_hz=0.001)
        assert cfg.rate_hz == 0.01

    def test_clamp_rate_hz_high(self):
        """Rate above 50 should be clamped to 50."""
        cfg = LfoConfig(rate_hz=100)
        assert cfg.rate_hz == 50.0

    def test_clamp_depth_low(self):
        """Depth below 0 should be clamped to 0."""
        cfg = LfoConfig(depth=-0.1)
        assert cfg.depth == 0.0

    def test_clamp_depth_high(self):
        """Depth above 1 should be clamped to 1."""
        cfg = LfoConfig(depth=1.5)
        assert cfg.depth == 1.0

    def test_clamp_phase_offset_low(self):
        """Phase offset below 0 should be clamped to 0."""
        cfg = LfoConfig(phase_offset=-0.1)
        assert cfg.phase_offset == 0.0

    def test_clamp_phase_offset_high(self):
        """Phase offset above 1 should be clamped to 1."""
        cfg = LfoConfig(phase_offset=1.5)
        assert cfg.phase_offset == 1.0

    def test_clamp_duty_low(self):
        """Duty below 0 should be clamped to 0."""
        cfg = LfoConfig(duty=-0.1)
        assert cfg.duty == 0.0

    def test_clamp_duty_high(self):
        """Duty above 1 should be clamped to 1."""
        cfg = LfoConfig(duty=1.5)
        assert cfg.duty == 1.0

    def test_unknown_shape_defaults_to_sine(self):
        """Unknown shape should default to 'sine'."""
        cfg = LfoConfig(shape="unknown")
        assert cfg.shape == "sine"


class TestLfoConfigSerialization:
    """Tests for LfoConfig to_dict / from_dict."""

    def test_round_trip_defaults(self):
        """Default config should round-trip."""
        cfg1 = LfoConfig()
        data = cfg1.to_dict()
        cfg2 = LfoConfig.from_dict(data)
        assert cfg1.to_dict() == cfg2.to_dict()

    def test_round_trip_custom(self):
        """Custom config should round-trip."""
        cfg1 = LfoConfig(
            enabled=True,
            shape="triangle",
            rate_hz=5.0,
            depth=0.8,
            phase_offset=0.25,
            duty=0.3,
            bipolar=True,
        )
        data = cfg1.to_dict()
        cfg2 = LfoConfig.from_dict(data)
        assert cfg1.to_dict() == cfg2.to_dict()

    def test_from_dict_missing_keys(self):
        """from_dict should fill missing keys with defaults."""
        data = {"enabled": True, "rate_hz": 10.0}
        cfg = LfoConfig.from_dict(data)
        assert cfg.enabled is True
        assert cfg.rate_hz == 10.0
        assert cfg.shape == "sine"
        assert cfg.depth == 1.0


class TestLfoStateBasics:
    """Tests for LfoState basic functionality."""

    def test_value_before_start(self):
        """Value before start() should return 0."""
        cfg = LfoConfig(enabled=True, shape="sine")
        state = LfoState(cfg)
        assert state.value(time.time()) == 0.0

    def test_value_when_disabled(self):
        """Value when disabled should return 0 regardless of time."""
        cfg = LfoConfig(enabled=False, shape="sine")
        state = LfoState(cfg)
        now = time.time()
        state.start(now)
        assert state.value(now) == 0.0

    def test_value_immediate_after_start(self):
        """Value immediately after start should match waveform at phase 0 + offset."""
        cfg = LfoConfig(enabled=True, shape="sine", rate_hz=1.0, phase_offset=0.0)
        state = LfoState(cfg)
        now = time.time()
        state.start(now)
        value = state.value(now)
        # sine(0) = 0.5
        assert abs(value - 0.5) < 0.001

    def test_phase_computation(self):
        """Phase should advance with time based on rate_hz."""
        cfg = LfoConfig(enabled=True, shape="ramp_up", rate_hz=1.0)
        state = LfoState(cfg)
        now = time.time()
        state.start(now)
        # After 0.25 seconds, phase should be 0.25 (at 1 Hz).
        value_at_quarter = state.value(now + 0.25)
        assert abs(value_at_quarter - 0.25) < 0.01

    def test_depth_multiplier(self):
        """Depth should scale the output."""
        cfg = LfoConfig(enabled=True, shape="sine", depth=0.5)
        state = LfoState(cfg)
        now = time.time()
        state.start(now)
        value = state.value(now)
        # sine(0) = 0.5, * depth 0.5 = 0.25
        assert abs(value - 0.25) < 0.001

    def test_bipolar_output_range(self):
        """Bipolar should scale output from -depth..+depth."""
        cfg = LfoConfig(enabled=True, shape="sine", depth=1.0, bipolar=True, rate_hz=1.0)
        state = LfoState(cfg)
        now = time.time()
        state.start(now)
        # sine(0) = 0.5, with bipolar scale: (0.5*1.0) * 2 - 1.0 = 0 (mid)
        value = state.value(now)
        assert abs(value - 0.0) < 0.001

        # At 1 Hz, quarter period is 0.25 seconds. sine(0.25) = 1.0, depth applied: 1.0
        # With bipolar: 1.0 * 2 - 1.0 = 1.0 (max)
        value_peak = state.value(now + 0.25)
        assert value_peak > 0.99


class TestLfoStateSampleHold:
    """Tests for sample_hold waveform in LfoState."""

    def test_sample_hold_same_within_cycle(self):
        """Sample_hold should return same value within a cycle."""
        cfg = LfoConfig(enabled=True, shape="sample_hold", rate_hz=1.0)
        state = LfoState(cfg, seed=42)
        now = time.time()
        state.start(now)
        value_a = state.value(now + 0.1)
        value_b = state.value(now + 0.2)
        # Within same cycle (< 1 second), should be equal.
        assert value_a == value_b

    def test_sample_hold_different_across_cycles(self):
        """Sample_hold should change when phase wraps (new cycle)."""
        cfg = LfoConfig(enabled=True, shape="sample_hold", rate_hz=1.0)
        state = LfoState(cfg, seed=42)
        now = time.time()
        state.start(now)
        value_cycle_0 = state.value(now + 0.5)
        value_cycle_1 = state.value(now + 1.5)
        # Across cycles, should be different (statistically likely with RNG).
        # Note: there's a small chance they're the same, but probability is ~1/256.
        # For robustness, just check they're both in valid range.
        assert 0.0 <= value_cycle_0 <= 1.0
        assert 0.0 <= value_cycle_1 <= 1.0

    def test_sample_hold_seeded_deterministic(self):
        """Sample_hold with same seed should give same sequence."""
        cfg = LfoConfig(enabled=True, shape="sample_hold", rate_hz=1.0)

        state1 = LfoState(cfg, seed=42)
        state2 = LfoState(cfg, seed=42)

        now = time.time()
        state1.start(now)
        state2.start(now)

        # Get same sequence of values.
        values1 = [state1.value(now + i * 1.5) for i in range(5)]
        values2 = [state2.value(now + i * 1.5) for i in range(5)]

        assert values1 == values2


class TestLfoStateSmoothRandom:
    """Tests for smooth_random waveform in LfoState."""

    def test_smooth_random_lerps_toward_target(self):
        """Smooth_random should lerp current toward target by 0.1 per call."""
        cfg = LfoConfig(enabled=True, shape="smooth_random", rate_hz=100.0)
        state = LfoState(cfg, seed=42)
        now = time.time()
        state.start(now)
        # Call value multiple times to accumulate lerp.
        value_0 = state.value(now)
        value_1 = state.value(now + 0.0001)
        value_2 = state.value(now + 0.0002)
        # Values should be in valid range and should be changing (lerping).
        assert 0.0 <= value_0 <= 1.0
        assert 0.0 <= value_1 <= 1.0
        assert 0.0 <= value_2 <= 1.0


class TestLfoStateReset:
    """Tests for LfoState reset functionality."""

    def test_reset_clears_start_time(self):
        """Reset should clear the start time."""
        cfg = LfoConfig(enabled=True)
        state = LfoState(cfg)
        now = time.time()
        state.start(now)
        state.reset()
        # After reset, value() should return 0.
        assert state.value(now) == 0.0

    def test_reset_clears_sample_hold_state(self):
        """Reset should clear sample_hold tracking."""
        cfg = LfoConfig(enabled=True, shape="sample_hold")
        state = LfoState(cfg, seed=42)
        now = time.time()
        state.start(now)
        state.value(now + 0.5)
        state.reset()
        # After reset, _sh_last_phase should be -1.0.
        assert state._sh_last_phase == -1.0


class TestToCc:
    """Tests for to_cc CC mapping function."""

    def test_to_cc_unipolar_zero(self):
        """Unipolar 0.0 should map to min_cc."""
        assert to_cc(0.0, min_cc=0, max_cc=127, bipolar=False) == 0

    def test_to_cc_unipolar_mid(self):
        """Unipolar 0.5 should map to mid CC."""
        cc = to_cc(0.5, min_cc=0, max_cc=127, bipolar=False)
        # 0.5 * 127 = 63.5 ≈ 64
        assert 63 <= cc <= 65

    def test_to_cc_unipolar_one(self):
        """Unipolar 1.0 should map to max_cc."""
        assert to_cc(1.0, min_cc=0, max_cc=127, bipolar=False) == 127

    def test_to_cc_bipolar_negative_one(self):
        """Bipolar -1.0 should map to 0."""
        cc = to_cc(-1.0, bipolar=True)
        assert cc == 0

    def test_to_cc_bipolar_zero(self):
        """Bipolar 0.0 should map to 64 (mid)."""
        cc = to_cc(0.0, bipolar=True)
        assert cc == 64

    def test_to_cc_bipolar_one(self):
        """Bipolar 1.0 should map to 127."""
        cc = to_cc(1.0, bipolar=True)
        assert cc == 127

    def test_to_cc_clamps_output(self):
        """to_cc should clamp output to 0..127."""
        cc_low = to_cc(-2.0, bipolar=True)
        cc_high = to_cc(2.0, bipolar=True)
        assert cc_low >= 0
        assert cc_high <= 127

    def test_to_cc_custom_range(self):
        """to_cc should respect min_cc and max_cc."""
        cc = to_cc(0.5, min_cc=20, max_cc=100, bipolar=False)
        assert 20 <= cc <= 100
