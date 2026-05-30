"""Tests for LFO phase-scope sampler.

PhaseScopePoint and PhaseScopeConfig classes, plus pure functions for sampling
LFO waveforms over phase ranges for UI scope-style display.
"""

import pytest

from gamepad_midi_bridge.lfo_phase_scope import (
    PhaseScopeConfig,
    PhaseScopePoint,
    as_cc_curve,
    min_max,
    sample_cycle,
    sample_multi_cycles,
)


class TestPhaseScopePoint:
    """Tests for PhaseScopePoint dataclass."""

    def test_phase_scope_point_creation(self):
        """PhaseScopePoint stores phase, value, and time_ms."""
        pt = PhaseScopePoint(phase=0.5, value=0.75, time_ms=250.0)
        assert pt.phase == 0.5
        assert pt.value == 0.75
        assert pt.time_ms == 250.0

    def test_phase_scope_point_to_dict(self):
        """to_dict() serializes to a dict."""
        pt = PhaseScopePoint(phase=0.25, value=0.5, time_ms=125.0)
        d = pt.to_dict()
        assert d == {"phase": 0.25, "value": 0.5, "time_ms": 125.0}

    def test_phase_scope_point_from_dict(self):
        """from_dict() deserializes from a dict."""
        d = {"phase": 0.75, "value": 0.9, "time_ms": 375.0}
        pt = PhaseScopePoint.from_dict(d)
        assert pt.phase == 0.75
        assert pt.value == 0.9
        assert pt.time_ms == 375.0

    def test_phase_scope_point_roundtrip(self):
        """to_dict() → from_dict() roundtrip preserves values."""
        pt_orig = PhaseScopePoint(phase=0.33, value=0.66, time_ms=330.0)
        pt_restored = PhaseScopePoint.from_dict(pt_orig.to_dict())
        assert pt_restored.phase == pt_orig.phase
        assert pt_restored.value == pt_orig.value
        assert pt_restored.time_ms == pt_orig.time_ms

    def test_phase_scope_point_from_dict_defaults(self):
        """from_dict() with missing keys uses defaults."""
        pt = PhaseScopePoint.from_dict({})
        assert pt.phase == 0.0
        assert pt.value == 0.0
        assert pt.time_ms == 0.0


class TestPhaseScopeConfig:
    """Tests for PhaseScopeConfig dataclass."""

    def test_phase_scope_config_defaults(self):
        """PhaseScopeConfig has sensible defaults."""
        cfg = PhaseScopeConfig()
        assert cfg.enabled is False
        assert cfg.samples == 64
        assert cfg.cycles == 1
        assert cfg.apply_depth is True
        assert cfg.apply_bipolar is True

    def test_phase_scope_config_clamp_samples_low(self):
        """samples clamped to minimum 8."""
        cfg = PhaseScopeConfig(samples=2)
        assert cfg.samples == 8

    def test_phase_scope_config_clamp_samples_high(self):
        """samples clamped to maximum 1024."""
        cfg = PhaseScopeConfig(samples=2000)
        assert cfg.samples == 1024

    def test_phase_scope_config_clamp_cycles_low(self):
        """cycles clamped to minimum 1."""
        cfg = PhaseScopeConfig(cycles=0)
        assert cfg.cycles == 1

    def test_phase_scope_config_clamp_cycles_high(self):
        """cycles clamped to maximum 16."""
        cfg = PhaseScopeConfig(cycles=100)
        assert cfg.cycles == 16

    def test_phase_scope_config_to_dict(self):
        """to_dict() serializes all fields."""
        cfg = PhaseScopeConfig(
            enabled=True,
            samples=128,
            cycles=4,
            apply_depth=False,
            apply_bipolar=False,
        )
        d = cfg.to_dict()
        assert d == {
            "enabled": True,
            "samples": 128,
            "cycles": 4,
            "apply_depth": False,
            "apply_bipolar": False,
        }

    def test_phase_scope_config_from_dict(self):
        """from_dict() deserializes and clamps."""
        d = {
            "enabled": True,
            "samples": 256,
            "cycles": 8,
            "apply_depth": True,
            "apply_bipolar": False,
        }
        cfg = PhaseScopeConfig.from_dict(d)
        assert cfg.enabled is True
        assert cfg.samples == 256
        assert cfg.cycles == 8
        assert cfg.apply_depth is True
        assert cfg.apply_bipolar is False

    def test_phase_scope_config_roundtrip(self):
        """to_dict() → from_dict() roundtrip preserves values."""
        cfg_orig = PhaseScopeConfig(samples=100, cycles=5, apply_depth=False)
        cfg_restored = PhaseScopeConfig.from_dict(cfg_orig.to_dict())
        assert cfg_restored.enabled == cfg_orig.enabled
        assert cfg_restored.samples == cfg_orig.samples
        assert cfg_restored.cycles == cfg_orig.cycles
        assert cfg_restored.apply_depth == cfg_orig.apply_depth
        assert cfg_restored.apply_bipolar == cfg_orig.apply_bipolar


class TestSampleCycle:
    """Tests for sample_cycle() function."""

    def test_sample_cycle_returns_correct_count(self):
        """sample_cycle returns exactly N points for N samples."""
        cfg = PhaseScopeConfig(samples=64)
        pts = sample_cycle({"shape": "sine", "rate_hz": 2.0, "depth": 1.0}, cfg)
        assert len(pts) == 64

    def test_sample_cycle_sine_shape(self):
        """sample_cycle with sine shape returns 0..1 range values."""
        cfg = PhaseScopeConfig(samples=64)
        pts = sample_cycle({"shape": "sine", "rate_hz": 1.0, "depth": 1.0}, cfg)
        # Sample a few key points: phase 0, 0.25, 0.5, 0.75 should give sine values
        # Sine at phase 0.0 → 0.5, 0.25 → 1.0, 0.5 → 0.5, 0.75 → 0.0.
        # With 64 samples: sample indices [0, 16, 32, 48] are closest.
        assert abs(pts[0].value - 0.5) < 0.01  # phase 0
        assert abs(pts[16].value - 1.0) < 0.01  # phase ≈0.25
        assert abs(pts[32].value - 0.5) < 0.01  # phase ≈0.5
        assert abs(pts[48].value - 0.0) < 0.01  # phase ≈0.75

    def test_sample_cycle_first_point_phase_zero(self):
        """First point has phase ≈ 0."""
        cfg = PhaseScopeConfig(samples=64)
        pts = sample_cycle({"shape": "sine"}, cfg)
        assert pts[0].phase == 0.0

    def test_sample_cycle_last_point_phase_near_one(self):
        """Last point has phase ≈ (N-1)/N."""
        cfg = PhaseScopeConfig(samples=64)
        pts = sample_cycle({"shape": "sine"}, cfg)
        expected_last_phase = 63 / 64
        assert abs(pts[-1].phase - expected_last_phase) < 0.001

    def test_sample_cycle_phase_monotonic(self):
        """Phase values increase monotonically."""
        cfg = PhaseScopeConfig(samples=16)
        pts = sample_cycle({"shape": "sine"}, cfg)
        for i in range(len(pts) - 1):
            assert pts[i].phase <= pts[i + 1].phase

    def test_sample_cycle_time_ms_monotonic(self):
        """time_ms values increase monotonically."""
        cfg = PhaseScopeConfig(samples=16)
        pts = sample_cycle({"shape": "sine", "rate_hz": 2.0}, cfg)
        for i in range(len(pts) - 1):
            assert pts[i].time_ms <= pts[i + 1].time_ms

    def test_sample_cycle_depth_multiplier(self):
        """apply_depth=True multiplies values by depth."""
        cfg = PhaseScopeConfig(samples=8, apply_depth=True)
        pts = sample_cycle({"shape": "ramp_up", "depth": 0.5}, cfg)
        # ramp_up at phase i/8 is [0, 0.125, 0.25, 0.375, 0.5, 0.625, 0.75, 0.875].
        # With depth=0.5: [0, 0.0625, 0.125, 0.1875, 0.25, 0.3125, 0.375, 0.4375].
        assert abs(pts[0].value - 0.0) < 0.001
        assert abs(pts[1].value - 0.0625) < 0.001
        assert abs(pts[2].value - 0.125) < 0.001
        assert abs(pts[4].value - 0.25) < 0.001

    def test_sample_cycle_no_depth_multiplier(self):
        """apply_depth=False returns raw waveform (clamped 0..1)."""
        cfg = PhaseScopeConfig(samples=8, apply_depth=False)
        pts = sample_cycle({"shape": "ramp_up", "depth": 0.5}, cfg)
        # ramp_up at phase i/8 is [0, 0.125, 0.25, 0.375, 0.5, 0.625, 0.75, 0.875].
        # apply_depth=False means we return the raw waveform, no depth multiplier.
        assert abs(pts[0].value - 0.0) < 0.001
        assert abs(pts[1].value - 0.125) < 0.001
        assert abs(pts[4].value - 0.5) < 0.001
        assert abs(pts[6].value - 0.75) < 0.001

    def test_sample_cycle_unipolar_no_bipolar_config(self):
        """Unipolar waveform with apply_bipolar=False stays 0..1."""
        cfg = PhaseScopeConfig(samples=4, apply_depth=False, apply_bipolar=False)
        pts = sample_cycle(
            {"shape": "sine", "bipolar": False, "depth": 1.0}, cfg
        )
        for pt in pts:
            assert 0.0 <= pt.value <= 1.0

    def test_sample_cycle_bipolar_transform(self):
        """Bipolar transform scales 0..1 to -1..1 (or -depth..+depth)."""
        cfg = PhaseScopeConfig(samples=8, apply_depth=True, apply_bipolar=True)
        pts = sample_cycle(
            {"shape": "ramp_up", "depth": 1.0, "bipolar": True}, cfg
        )
        # ramp_up at phase i/8 is [0, 0.125, 0.25, 0.375, 0.5, 0.625, 0.75, 0.875].
        # With depth=1.0 and bipolar: scale = val*2 - depth = val*2 - 1.0
        # [0, 0.125, 0.25, 0.375, 0.5, ...] → [-1, -0.75, -0.5, -0.25, 0, ...].
        assert abs(pts[0].value - (-1.0)) < 0.001
        assert abs(pts[2].value - (-0.5)) < 0.001
        assert abs(pts[4].value - 0.0) < 0.001
        assert abs(pts[6].value - 0.5) < 0.001

    def test_sample_cycle_default_rate_hz(self):
        """Missing rate_hz defaults to 2.0."""
        cfg = PhaseScopeConfig(samples=64)
        pts = sample_cycle({"shape": "sine"}, cfg)
        # time_ms should be based on rate_hz=2.0 (default).
        # Last sample at phase (63/64), time = (phase / rate_hz) * 1000.
        expected_last_time = ((63 / 64) / 2.0) * 1000.0
        assert abs(pts[-1].time_ms - expected_last_time) < 1.0

    def test_sample_cycle_low_rate_hz(self):
        """rate_hz clamped to minimum 0.01."""
        cfg = PhaseScopeConfig(samples=2)
        pts = sample_cycle({"shape": "sine", "rate_hz": 0.001}, cfg)
        # Should clamp to 0.01, so cycle duration = 100 seconds.
        assert pts[-1].time_ms > 10000.0


class TestSampleMultiCycles:
    """Tests for sample_multi_cycles() function."""

    def test_sample_multi_cycles_one_cycle(self):
        """sample_multi_cycles with cycles=1 matches sample_cycle."""
        cfg = PhaseScopeConfig(samples=64, cycles=1)
        pts_single = sample_cycle({"shape": "sine", "rate_hz": 2.0}, cfg)
        pts_multi = sample_multi_cycles({"shape": "sine", "rate_hz": 2.0}, cfg)
        assert len(pts_single) == len(pts_multi)
        for p1, p2 in zip(pts_single, pts_multi):
            assert abs(p1.value - p2.value) < 0.001
            assert abs(p1.time_ms - p2.time_ms) < 0.1

    def test_sample_multi_cycles_two_cycles(self):
        """sample_multi_cycles with cycles=2 returns 2*samples points."""
        cfg = PhaseScopeConfig(samples=64, cycles=2)
        pts = sample_multi_cycles({"shape": "sine"}, cfg)
        assert len(pts) == 128

    def test_sample_multi_cycles_phase_unwrapped(self):
        """Phase continues across cycles (unwrapped)."""
        cfg = PhaseScopeConfig(samples=8, cycles=2)
        pts = sample_multi_cycles({"shape": "sine"}, cfg)
        # First cycle: phase 0..7/8.
        # Second cycle: phase 8/8..15/8 (1..1.875).
        assert pts[0].phase == 0.0
        assert abs(pts[7].phase - 7 / 8) < 0.001
        assert abs(pts[8].phase - 1.0) < 0.001
        assert abs(pts[15].phase - 15 / 8) < 0.001

    def test_sample_multi_cycles_time_continuous(self):
        """time_ms continuous across cycles."""
        cfg = PhaseScopeConfig(samples=8, cycles=2)
        pts = sample_multi_cycles({"shape": "sine", "rate_hz": 1.0}, cfg)
        # rate_hz=1.0, so time per sample (one cycle) = 1000 / 8 = 125 ms per sample.
        expected_times = [i * 125.0 for i in range(16)]
        for i, pt in enumerate(pts):
            assert abs(pt.time_ms - expected_times[i]) < 1.0


class TestMinMax:
    """Tests for min_max() function."""

    def test_min_max_empty_list(self):
        """min_max on empty list returns (0.0, 1.0)."""
        result = min_max([])
        assert result == (0.0, 1.0)

    def test_min_max_single_point(self):
        """min_max on single point returns (value, value)."""
        pts = [PhaseScopePoint(phase=0.5, value=0.6, time_ms=500.0)]
        min_val, max_val = min_max(pts)
        assert min_val == 0.6
        assert max_val == 0.6

    def test_min_max_multiple_points(self):
        """min_max returns correct bounds."""
        pts = [
            PhaseScopePoint(phase=0.0, value=0.2, time_ms=0.0),
            PhaseScopePoint(phase=0.5, value=0.9, time_ms=500.0),
            PhaseScopePoint(phase=1.0, value=0.1, time_ms=1000.0),
        ]
        min_val, max_val = min_max(pts)
        assert min_val == 0.1
        assert max_val == 0.9

    def test_min_max_bipolar_range(self):
        """min_max works with bipolar (-1..1) values."""
        pts = [
            PhaseScopePoint(phase=0.0, value=-0.5, time_ms=0.0),
            PhaseScopePoint(phase=0.5, value=0.0, time_ms=500.0),
            PhaseScopePoint(phase=1.0, value=0.8, time_ms=1000.0),
        ]
        min_val, max_val = min_max(pts)
        assert min_val == -0.5
        assert max_val == 0.8


class TestAsCcCurve:
    """Tests for as_cc_curve() function."""

    def test_as_cc_curve_empty_list(self):
        """as_cc_curve on empty list returns empty list."""
        result = as_cc_curve([])
        assert result == []

    def test_as_cc_curve_unipolar_single_point(self):
        """as_cc_curve unipolar 0.5 → 64."""
        pts = [PhaseScopePoint(phase=0.5, value=0.5, time_ms=500.0)]
        ccs = as_cc_curve(pts)
        assert len(ccs) == 1
        assert ccs[0] == 64

    def test_as_cc_curve_unipolar_bounds(self):
        """as_cc_curve unipolar: 0→0, 1→127."""
        pts = [
            PhaseScopePoint(phase=0.0, value=0.0, time_ms=0.0),
            PhaseScopePoint(phase=1.0, value=1.0, time_ms=1000.0),
        ]
        ccs = as_cc_curve(pts)
        assert ccs[0] == 0
        assert ccs[1] == 127

    def test_as_cc_curve_unipolar_quarter_points(self):
        """as_cc_curve unipolar: 0.25→32, 0.75→95-96."""
        pts = [
            PhaseScopePoint(phase=0.0, value=0.25, time_ms=0.0),
            PhaseScopePoint(phase=1.0, value=0.75, time_ms=1000.0),
        ]
        ccs = as_cc_curve(pts)
        assert ccs[0] == 32
        assert ccs[1] == 95  # 0.75 * 127 ≈ 95.25 → rounds to 95

    def test_as_cc_curve_bipolar_zero_mid(self):
        """as_cc_curve bipolar: 0→64 (only if list has negative values for bipolar detection)."""
        # Bipolar is only detected if there's at least one value < 0.
        # A single value 0.0 with no negative values is treated as unipolar.
        pts = [
            PhaseScopePoint(phase=0.0, value=-0.5, time_ms=0.0),
            PhaseScopePoint(phase=0.5, value=0.0, time_ms=500.0),
        ]
        ccs = as_cc_curve(pts)
        assert ccs[1] == 64  # 0.0 bipolar maps to 64

    def test_as_cc_curve_bipolar_bounds(self):
        """as_cc_curve bipolar: -1→0, 1→127."""
        pts = [
            PhaseScopePoint(phase=0.0, value=-1.0, time_ms=0.0),
            PhaseScopePoint(phase=1.0, value=1.0, time_ms=1000.0),
        ]
        ccs = as_cc_curve(pts)
        assert ccs[0] == 0
        assert ccs[1] == 127

    def test_as_cc_curve_bipolar_negative_half(self):
        """as_cc_curve bipolar: -0.5→32."""
        pts = [PhaseScopePoint(phase=0.0, value=-0.5, time_ms=0.0)]
        ccs = as_cc_curve(pts)
        assert ccs[0] == 32

    def test_as_cc_curve_bipolar_positive_half(self):
        """as_cc_curve bipolar: 0.5→96 (only if list has negative values)."""
        # Bipolar detection requires at least one negative value.
        pts = [
            PhaseScopePoint(phase=0.0, value=-1.0, time_ms=0.0),
            PhaseScopePoint(phase=1.0, value=0.5, time_ms=1000.0),
        ]
        ccs = as_cc_curve(pts)
        assert ccs[1] == 96  # 0.5 bipolar: 64 + 0.5*63.5 ≈ 95.75 → 96

    def test_as_cc_curve_returns_integers(self):
        """as_cc_curve always returns integers."""
        pts = [
            PhaseScopePoint(phase=0.0, value=0.33, time_ms=0.0),
            PhaseScopePoint(phase=0.5, value=0.67, time_ms=500.0),
            PhaseScopePoint(phase=1.0, value=0.99, time_ms=1000.0),
        ]
        ccs = as_cc_curve(pts)
        for cc in ccs:
            assert isinstance(cc, int)

    def test_as_cc_curve_custom_range(self):
        """as_cc_curve with custom min_cc..max_cc range."""
        pts = [
            PhaseScopePoint(phase=0.0, value=0.0, time_ms=0.0),
            PhaseScopePoint(phase=0.5, value=0.5, time_ms=500.0),
            PhaseScopePoint(phase=1.0, value=1.0, time_ms=1000.0),
        ]
        ccs = as_cc_curve(pts, min_cc=50, max_cc=100)
        assert ccs[0] == 50
        assert ccs[1] == 75
        assert ccs[2] == 100

    def test_as_cc_curve_clamps_to_0_127(self):
        """as_cc_curve always returns values in 0..127."""
        pts = [
            PhaseScopePoint(phase=0.0, value=-2.0, time_ms=0.0),
            PhaseScopePoint(phase=1.0, value=2.0, time_ms=1000.0),
        ]
        ccs = as_cc_curve(pts)
        for cc in ccs:
            assert 0 <= cc <= 127
