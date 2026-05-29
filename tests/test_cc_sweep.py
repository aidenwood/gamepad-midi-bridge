"""Tests for CC sweep / envelope automator module.

Tests the CcSweepConfig dataclass (defaults, validation, clamping, round-trip
serialization) and the CcSweep stateful generator (shape functions, looping,
completion state, envelope interpolation).
"""
from __future__ import annotations

import math

import pytest

from gamepad_midi_bridge.cc_sweep import CcSweep, CcSweepConfig


# ─────────────────────────────────────────────────────────────────────────
# CcSweepConfig — defaults and construction
# ─────────────────────────────────────────────────────────────────────────

class TestCcSweepConfigDefaults:
    """Test default values and field initialisation."""

    def test_enabled_default_false(self):
        cfg = CcSweepConfig()
        assert cfg.enabled is False

    def test_cc_default(self):
        assert CcSweepConfig().cc == 1

    def test_channel_default(self):
        assert CcSweepConfig().channel == 1

    def test_start_value_default(self):
        assert CcSweepConfig().start_value == 0

    def test_end_value_default(self):
        assert CcSweepConfig().end_value == 127

    def test_duration_s_default(self):
        assert CcSweepConfig().duration_s == 1.0

    def test_shape_default_linear(self):
        assert CcSweepConfig().shape == "linear"

    def test_loop_default_false(self):
        assert CcSweepConfig().loop is False


# ─────────────────────────────────────────────────────────────────────────
# CcSweepConfig — clamping and validation
# ─────────────────────────────────────────────────────────────────────────

class TestCcSweepConfigClamping:
    """Test value clamping and range validation."""

    def test_cc_clamped_below_zero(self):
        cfg = CcSweepConfig(cc=-5)
        assert cfg.cc == 0

    def test_cc_clamped_above_127(self):
        cfg = CcSweepConfig(cc=200)
        assert cfg.cc == 127

    def test_channel_clamped_below_one(self):
        cfg = CcSweepConfig(channel=-1)
        assert cfg.channel == 1

    def test_channel_clamped_above_16(self):
        cfg = CcSweepConfig(channel=99)
        assert cfg.channel == 16

    def test_start_value_clamped_above_127(self):
        cfg = CcSweepConfig(start_value=200)
        assert cfg.start_value == 127

    def test_start_value_clamped_below_zero(self):
        cfg = CcSweepConfig(start_value=-50)
        assert cfg.start_value == 0

    def test_end_value_clamped_above_127(self):
        cfg = CcSweepConfig(end_value=500)
        assert cfg.end_value == 127

    def test_end_value_clamped_below_zero(self):
        cfg = CcSweepConfig(end_value=-10)
        assert cfg.end_value == 0

    def test_duration_clamped_below_minimum(self):
        cfg = CcSweepConfig(duration_s=0.001)
        assert cfg.duration_s == 0.01

    def test_duration_clamped_above_maximum(self):
        cfg = CcSweepConfig(duration_s=100.0)
        assert cfg.duration_s == 60.0

    def test_unknown_shape_falls_back_to_linear(self):
        cfg = CcSweepConfig(shape="unknown_waveform")
        assert cfg.shape == "linear"

    def test_valid_shapes_preserved(self):
        for shape in ["linear", "exponential", "logarithmic", "sine", "triangle", "sawtooth"]:
            cfg = CcSweepConfig(shape=shape)
            assert cfg.shape == shape


# ─────────────────────────────────────────────────────────────────────────
# CcSweepConfig — serialization
# ─────────────────────────────────────────────────────────────────────────

class TestCcSweepConfigSerialization:
    """Test round-trip serialization via to_dict() and from_dict()."""

    def test_to_dict_includes_all_fields(self):
        cfg = CcSweepConfig(
            enabled=True,
            cc=74,
            channel=2,
            start_value=30,
            end_value=100,
            duration_s=2.5,
            shape="sine",
            loop=True,
        )
        d = cfg.to_dict()
        assert d["enabled"] is True
        assert d["cc"] == 74
        assert d["channel"] == 2
        assert d["start_value"] == 30
        assert d["end_value"] == 100
        assert d["duration_s"] == 2.5
        assert d["shape"] == "sine"
        assert d["loop"] is True

    def test_round_trip_from_dict_defaults(self):
        cfg = CcSweepConfig.from_dict({})
        assert cfg.enabled is False
        assert cfg.cc == 1
        assert cfg.channel == 1
        assert cfg.start_value == 0
        assert cfg.end_value == 127
        assert cfg.duration_s == 1.0
        assert cfg.shape == "linear"
        assert cfg.loop is False

    def test_round_trip_from_dict_none(self):
        cfg = CcSweepConfig.from_dict(None)
        assert cfg.enabled is False
        assert cfg.cc == 1

    def test_round_trip_full_dict(self):
        original = CcSweepConfig(
            enabled=True,
            cc=100,
            channel=5,
            start_value=10,
            end_value=120,
            duration_s=3.0,
            shape="triangle",
            loop=True,
        )
        d = original.to_dict()
        restored = CcSweepConfig.from_dict(d)
        assert restored.enabled == original.enabled
        assert restored.cc == original.cc
        assert restored.channel == original.channel
        assert restored.start_value == original.start_value
        assert restored.end_value == original.end_value
        assert restored.duration_s == original.duration_s
        assert restored.shape == original.shape
        assert restored.loop == original.loop

    def test_from_dict_partial_dict(self):
        """from_dict with missing keys should fill in defaults."""
        d = {"cc": 50, "duration_s": 2.0}
        cfg = CcSweepConfig.from_dict(d)
        assert cfg.cc == 50
        assert cfg.duration_s == 2.0
        assert cfg.enabled is False
        assert cfg.start_value == 0


# ─────────────────────────────────────────────────────────────────────────
# CcSweep — state and lifecycle
# ─────────────────────────────────────────────────────────────────────────

class TestCcSweepLifecycle:
    """Test start(), reset(), value_at() state transitions."""

    def test_value_at_before_start_returns_none(self):
        cfg = CcSweepConfig()
        sweep = CcSweep(cfg)
        assert sweep.value_at(0.0) is None

    def test_value_at_after_start_returns_value(self):
        cfg = CcSweepConfig(start_value=0, end_value=127, duration_s=1.0)
        sweep = CcSweep(cfg)
        sweep.start(0.0)
        val = sweep.value_at(0.0)
        assert val is not None
        assert isinstance(val, int)

    def test_is_done_false_before_completion(self):
        cfg = CcSweepConfig(duration_s=1.0)
        sweep = CcSweep(cfg)
        sweep.start(0.0)
        sweep.value_at(0.5)  # Halfway through
        assert sweep.is_done() is False

    def test_is_done_true_after_completion(self):
        cfg = CcSweepConfig(duration_s=1.0, loop=False)
        sweep = CcSweep(cfg)
        sweep.start(0.0)
        sweep.value_at(1.5)  # Past the end
        assert sweep.is_done() is True

    def test_reset_clears_state(self):
        cfg = CcSweepConfig(duration_s=1.0, loop=False)
        sweep = CcSweep(cfg)
        sweep.start(0.0)
        sweep.value_at(1.5)
        assert sweep.is_done() is True
        sweep.reset()
        assert sweep.is_done() is False
        assert sweep.start_time is None


# ─────────────────────────────────────────────────────────────────────────
# CcSweep — linear shape
# ─────────────────────────────────────────────────────────────────────────

class TestCcSweepLinear:
    """Test linear interpolation shape."""

    def test_linear_at_start(self):
        cfg = CcSweepConfig(start_value=0, end_value=127, duration_s=1.0, shape="linear")
        sweep = CcSweep(cfg)
        sweep.start(0.0)
        val = sweep.value_at(0.0)
        assert val == 0

    def test_linear_at_end(self):
        cfg = CcSweepConfig(start_value=0, end_value=127, duration_s=1.0, shape="linear")
        sweep = CcSweep(cfg)
        sweep.start(0.0)
        val = sweep.value_at(1.0)
        assert val == 127

    def test_linear_at_midpoint(self):
        cfg = CcSweepConfig(start_value=0, end_value=127, duration_s=1.0, shape="linear")
        sweep = CcSweep(cfg)
        sweep.start(0.0)
        val = sweep.value_at(0.5)
        # Expect ~63 or 64 (127 * 0.5 = 63.5)
        assert val in (63, 64)

    def test_linear_quarter_point(self):
        cfg = CcSweepConfig(start_value=0, end_value=100, duration_s=1.0, shape="linear")
        sweep = CcSweep(cfg)
        sweep.start(0.0)
        val = sweep.value_at(0.25)
        # Expect ~25
        assert val in (24, 25, 26)

    def test_linear_descending(self):
        """Start value > end value should sweep downward."""
        cfg = CcSweepConfig(start_value=127, end_value=0, duration_s=1.0, shape="linear")
        sweep = CcSweep(cfg)
        sweep.start(0.0)
        start_val = sweep.value_at(0.0)
        mid_val = sweep.value_at(0.5)
        end_val = sweep.value_at(1.0)
        assert start_val == 127
        assert mid_val < start_val
        assert end_val == 0


# ─────────────────────────────────────────────────────────────────────────
# CcSweep — exponential shape
# ─────────────────────────────────────────────────────────────────────────

class TestCcSweepExponential:
    """Test exponential (quadratic) curve: progress^2."""

    def test_exponential_at_start(self):
        cfg = CcSweepConfig(start_value=0, end_value=127, duration_s=1.0, shape="exponential")
        sweep = CcSweep(cfg)
        sweep.start(0.0)
        val = sweep.value_at(0.0)
        assert val == 0

    def test_exponential_at_end(self):
        cfg = CcSweepConfig(start_value=0, end_value=127, duration_s=1.0, shape="exponential")
        sweep = CcSweep(cfg)
        sweep.start(0.0)
        val = sweep.value_at(1.0)
        assert val == 127

    def test_exponential_biases_low_at_midpoint(self):
        """At progress=0.5, exponential (0.25) should be lower than linear (0.5)."""
        cfg = CcSweepConfig(start_value=0, end_value=127, duration_s=1.0, shape="exponential")
        sweep = CcSweep(cfg)
        sweep.start(0.0)
        exp_val = sweep.value_at(0.5)

        cfg_lin = CcSweepConfig(start_value=0, end_value=127, duration_s=1.0, shape="linear")
        sweep_lin = CcSweep(cfg_lin)
        sweep_lin.start(0.0)
        lin_val = sweep_lin.value_at(0.5)

        assert exp_val < lin_val


# ─────────────────────────────────────────────────────────────────────────
# CcSweep — logarithmic shape
# ─────────────────────────────────────────────────────────────────────────

class TestCcSweepLogarithmic:
    """Test logarithmic (square root) curve: sqrt(progress)."""

    def test_logarithmic_at_start(self):
        cfg = CcSweepConfig(start_value=0, end_value=127, duration_s=1.0, shape="logarithmic")
        sweep = CcSweep(cfg)
        sweep.start(0.0)
        val = sweep.value_at(0.0)
        assert val == 0

    def test_logarithmic_at_end(self):
        cfg = CcSweepConfig(start_value=0, end_value=127, duration_s=1.0, shape="logarithmic")
        sweep = CcSweep(cfg)
        sweep.start(0.0)
        val = sweep.value_at(1.0)
        assert val == 127

    def test_logarithmic_biases_high_at_midpoint(self):
        """At progress=0.5, logarithmic (sqrt(0.5)≈0.707) should be higher than linear (0.5)."""
        cfg = CcSweepConfig(start_value=0, end_value=127, duration_s=1.0, shape="logarithmic")
        sweep = CcSweep(cfg)
        sweep.start(0.0)
        log_val = sweep.value_at(0.5)

        cfg_lin = CcSweepConfig(start_value=0, end_value=127, duration_s=1.0, shape="linear")
        sweep_lin = CcSweep(cfg_lin)
        sweep_lin.start(0.0)
        lin_val = sweep_lin.value_at(0.5)

        assert log_val > lin_val


# ─────────────────────────────────────────────────────────────────────────
# CcSweep — sine (ease-in-out) shape
# ─────────────────────────────────────────────────────────────────────────

class TestCcSweepSine:
    """Test sine easing: smooth acceleration + deceleration."""

    def test_sine_at_start(self):
        cfg = CcSweepConfig(start_value=0, end_value=127, duration_s=1.0, shape="sine")
        sweep = CcSweep(cfg)
        sweep.start(0.0)
        val = sweep.value_at(0.0)
        assert val == 0

    def test_sine_at_end(self):
        cfg = CcSweepConfig(start_value=0, end_value=127, duration_s=1.0, shape="sine")
        sweep = CcSweep(cfg)
        sweep.start(0.0)
        val = sweep.value_at(1.0)
        assert val == 127

    def test_sine_smooth_at_midpoint(self):
        """Sine easing should give smooth interpolation near midpoint."""
        cfg = CcSweepConfig(start_value=0, end_value=127, duration_s=1.0, shape="sine")
        sweep = CcSweep(cfg)
        sweep.start(0.0)
        val = sweep.value_at(0.5)
        # At progress=0.5, sine easing is (1 - cos(π/2)) / 2 = 0.5 → expect ~63-64
        assert val in (63, 64)


# ─────────────────────────────────────────────────────────────────────────
# CcSweep — triangle shape
# ─────────────────────────────────────────────────────────────────────────

class TestCcSweepTriangle:
    """Test triangle wave: rises to 1.0 at progress=0.5, then falls."""

    def test_triangle_at_start(self):
        cfg = CcSweepConfig(start_value=0, end_value=100, duration_s=1.0, shape="triangle")
        sweep = CcSweep(cfg)
        sweep.start(0.0)
        val = sweep.value_at(0.0)
        assert val == 0

    def test_triangle_peaks_at_midpoint(self):
        """At progress=0.5, triangle should peak at 1.0."""
        cfg = CcSweepConfig(start_value=0, end_value=100, duration_s=1.0, shape="triangle")
        sweep = CcSweep(cfg)
        sweep.start(0.0)
        val = sweep.value_at(0.5)
        # Peak should be at end_value = 100
        assert val == 100

    def test_triangle_at_end(self):
        cfg = CcSweepConfig(start_value=0, end_value=100, duration_s=1.0, shape="triangle")
        sweep = CcSweep(cfg)
        sweep.start(0.0)
        val = sweep.value_at(1.0)
        assert val == 0


# ─────────────────────────────────────────────────────────────────────────
# CcSweep — sawtooth shape
# ─────────────────────────────────────────────────────────────────────────

class TestCcSweepSawtooth:
    """Test sawtooth: linear ramp (equivalent to linear for single cycle)."""

    def test_sawtooth_at_start(self):
        cfg = CcSweepConfig(start_value=0, end_value=127, duration_s=1.0, shape="sawtooth")
        sweep = CcSweep(cfg)
        sweep.start(0.0)
        val = sweep.value_at(0.0)
        assert val == 0

    def test_sawtooth_at_end(self):
        cfg = CcSweepConfig(start_value=0, end_value=127, duration_s=1.0, shape="sawtooth")
        sweep = CcSweep(cfg)
        sweep.start(0.0)
        val = sweep.value_at(1.0)
        assert val == 127

    def test_sawtooth_midpoint_linear(self):
        """Sawtooth without looping behaves like linear."""
        cfg = CcSweepConfig(start_value=0, end_value=100, duration_s=1.0, shape="sawtooth", loop=False)
        sweep = CcSweep(cfg)
        sweep.start(0.0)
        val = sweep.value_at(0.5)
        assert val in (49, 50, 51)


# ─────────────────────────────────────────────────────────────────────────
# CcSweep — looping behaviour
# ─────────────────────────────────────────────────────────────────────────

class TestCcSweepLooping:
    """Test loop=True cycles the envelope, loop=False completes once."""

    def test_no_loop_done_after_duration(self):
        cfg = CcSweepConfig(duration_s=1.0, loop=False)
        sweep = CcSweep(cfg)
        sweep.start(0.0)
        sweep.value_at(1.5)
        assert sweep.is_done() is True

    def test_loop_never_done(self):
        cfg = CcSweepConfig(duration_s=1.0, loop=True)
        sweep = CcSweep(cfg)
        sweep.start(0.0)
        sweep.value_at(2.5)  # 2.5 cycles
        assert sweep.is_done() is False

    def test_loop_cycles_linearly(self):
        """Looping should reset progress modulo duration."""
        cfg = CcSweepConfig(start_value=0, end_value=100, duration_s=1.0, shape="linear", loop=True)
        sweep = CcSweep(cfg)
        sweep.start(0.0)

        # First cycle: 0.5s → ~50
        val1 = sweep.value_at(0.5)
        assert val1 in (49, 50, 51)

        # Second cycle: 1.5s → wraps to 0.5s progress → ~50 again
        val2 = sweep.value_at(1.5)
        assert val2 in (49, 50, 51)

    def test_loop_resets_after_each_cycle(self):
        """Loop should return to start_value at each cycle boundary."""
        cfg = CcSweepConfig(start_value=10, end_value=100, duration_s=1.0, shape="linear", loop=True)
        sweep = CcSweep(cfg)
        sweep.start(0.0)

        # Start of first cycle
        val1 = sweep.value_at(0.0)
        assert val1 == 10

        # Start of second cycle (1.0s)
        val2 = sweep.value_at(1.0)
        assert val2 == 10


# ─────────────────────────────────────────────────────────────────────────
# CcSweep — edge cases and robustness
# ─────────────────────────────────────────────────────────────────────────

class TestCcSweepEdgeCases:
    """Test boundary conditions and robustness."""

    def test_zero_duration_clamps_to_minimum(self):
        """CcSweepConfig should clamp duration to 0.01 minimum."""
        cfg = CcSweepConfig(duration_s=0.001)
        assert cfg.duration_s == 0.01

    def test_very_short_duration_sweeps_quickly(self):
        cfg = CcSweepConfig(start_value=0, end_value=127, duration_s=0.01)
        sweep = CcSweep(cfg)
        sweep.start(0.0)
        val = sweep.value_at(0.01)
        assert val == 127

    def test_very_long_duration_sweeps_slowly(self):
        cfg = CcSweepConfig(start_value=0, end_value=100, duration_s=60.0)
        sweep = CcSweep(cfg)
        sweep.start(0.0)
        val = sweep.value_at(30.0)  # Halfway
        assert val in (49, 50, 51)

    def test_value_clamped_to_0_to_127(self):
        """Output values should never exceed 0..127 range."""
        cfg = CcSweepConfig(start_value=0, end_value=150, duration_s=1.0)  # Will be clamped
        sweep = CcSweep(cfg)
        sweep.start(0.0)
        val = sweep.value_at(1.0)
        assert 0 <= val <= 127

    def test_negative_time_delta_clamped(self):
        """If now_s < start_time, progress should clamp to 0."""
        cfg = CcSweepConfig(start_value=0, end_value=127, duration_s=1.0)
        sweep = CcSweep(cfg)
        sweep.start(5.0)
        val = sweep.value_at(2.0)  # Before start
        # Progress will be negative; _apply_shape clamps to [0, 1]
        assert val == 0

    def test_same_start_and_end_values(self):
        """If start == end, output should be constant."""
        cfg = CcSweepConfig(start_value=50, end_value=50, duration_s=1.0)
        sweep = CcSweep(cfg)
        sweep.start(0.0)
        assert sweep.value_at(0.0) == 50
        assert sweep.value_at(0.5) == 50
        assert sweep.value_at(1.0) == 50

    def test_multiple_start_calls_reset_timing(self):
        """Calling start() again should reset the timer."""
        cfg = CcSweepConfig(start_value=0, end_value=127, duration_s=1.0)
        sweep = CcSweep(cfg)

        sweep.start(0.0)
        val1 = sweep.value_at(0.5)

        # Re-start at t=1.0; now progress should be (2.0 - 1.0) / 1.0 = 1.0
        sweep.start(1.0)
        val2 = sweep.value_at(2.0)

        assert val2 == 127  # Should be at end


# ─────────────────────────────────────────────────────────────────────────
# CcSweep — real-world scenarios
# ─────────────────────────────────────────────────────────────────────────

class TestCcSweepRealWorld:
    """Test realistic use cases: filter sweeps, filter envelope, etc."""

    def test_kick_filter_sweep(self):
        """Simulate a kick drum filter sweep: 0→127 over 100ms."""
        cfg = CcSweepConfig(
            cc=74,  # Cutoff
            channel=1,
            start_value=0,
            end_value=127,
            duration_s=0.1,
            shape="exponential",  # Snappy rise
            loop=False,
        )
        sweep = CcSweep(cfg)
        sweep.start(0.0)

        val_start = sweep.value_at(0.0)
        val_mid = sweep.value_at(0.05)
        val_end = sweep.value_at(0.1)

        assert val_start == 0
        assert 0 < val_mid < 127
        assert val_end == 127
        assert sweep.is_done()

    def test_automation_lane_sine_ramp(self):
        """Simulate smooth automation: 40→100 over 2 seconds with sine easing."""
        cfg = CcSweepConfig(
            cc=7,  # Volume
            start_value=40,
            end_value=100,
            duration_s=2.0,
            shape="sine",
        )
        sweep = CcSweep(cfg)
        sweep.start(0.0)

        # Collect samples
        samples = [sweep.value_at(t * 0.1) for t in range(21)]  # 0.0 to 2.0s

        # Start and end should match
        assert samples[0] == 40
        assert samples[-1] == 100

        # Middle values should increase monotonically (sine is monotonic in [0, 1])
        for i in range(1, len(samples)):
            assert samples[i] >= samples[i - 1]

    def test_lfo_like_triangle_wave(self):
        """Use triangle wave to modulate a parameter in a looping LFO style."""
        cfg = CcSweepConfig(
            cc=74,
            start_value=30,
            end_value=100,
            duration_s=0.5,
            shape="triangle",
            loop=True,
        )
        sweep = CcSweep(cfg)
        sweep.start(0.0)

        # Two complete cycles
        samples = [sweep.value_at(t * 0.05) for t in range(21)]  # 0.0 to 1.0s

        # Should peak twice (at 0.25s and 0.75s)
        # Just check that we never mark as done
        assert not sweep.is_done()
        assert len([v for v in samples if v is not None]) == 21
