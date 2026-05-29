"""Tests for DualSense IMU (gyro / accelerometer) → CC mapper.

ImuAxisProcessor and ImuMapping transform raw motion samples into MIDI CC values
with smoothing, gain, deadzone, and bipolar/unipolar modes. Pure stdlib, no Qt.
"""
from __future__ import annotations

import pytest


class TestImuAxisConfig:
    """ImuAxisConfig — clamp values on construction."""

    def test_config_defaults(self):
        from gamepad_midi_bridge.imu_helper import ImuAxisConfig
        cfg = ImuAxisConfig()
        assert cfg.enabled is False
        assert cfg.cc == 1
        assert cfg.channel == 1
        assert cfg.gain == 1.0
        assert cfg.invert is False
        assert cfg.smoothing == 0.3
        assert cfg.deadzone == 0.05
        assert cfg.bipolar is True

    def test_config_clamp_cc_below_zero(self):
        from gamepad_midi_bridge.imu_helper import ImuAxisConfig
        cfg = ImuAxisConfig(cc=-10)
        assert cfg.cc == 0
        cfg = ImuAxisConfig(cc=-1)
        assert cfg.cc == 0

    def test_config_clamp_cc_above_127(self):
        from gamepad_midi_bridge.imu_helper import ImuAxisConfig
        cfg = ImuAxisConfig(cc=200)
        assert cfg.cc == 127
        cfg = ImuAxisConfig(cc=128)
        assert cfg.cc == 127

    def test_config_clamp_channel_below_one(self):
        from gamepad_midi_bridge.imu_helper import ImuAxisConfig
        cfg = ImuAxisConfig(channel=0)
        assert cfg.channel == 1
        cfg = ImuAxisConfig(channel=-5)
        assert cfg.channel == 1

    def test_config_clamp_channel_above_16(self):
        from gamepad_midi_bridge.imu_helper import ImuAxisConfig
        cfg = ImuAxisConfig(channel=20)
        assert cfg.channel == 16
        cfg = ImuAxisConfig(channel=100)
        assert cfg.channel == 16

    def test_config_clamp_gain_below_0_01(self):
        from gamepad_midi_bridge.imu_helper import ImuAxisConfig
        cfg = ImuAxisConfig(gain=0.0)
        assert cfg.gain == 0.01
        cfg = ImuAxisConfig(gain=-1.0)
        assert cfg.gain == 0.01

    def test_config_clamp_gain_above_100(self):
        from gamepad_midi_bridge.imu_helper import ImuAxisConfig
        cfg = ImuAxisConfig(gain=200.0)
        assert cfg.gain == 100.0
        cfg = ImuAxisConfig(gain=1000.0)
        assert cfg.gain == 100.0

    def test_config_clamp_smoothing_below_zero(self):
        from gamepad_midi_bridge.imu_helper import ImuAxisConfig
        cfg = ImuAxisConfig(smoothing=-0.5)
        assert cfg.smoothing == 0.0

    def test_config_clamp_smoothing_above_0_99(self):
        from gamepad_midi_bridge.imu_helper import ImuAxisConfig
        cfg = ImuAxisConfig(smoothing=1.0)
        assert cfg.smoothing == 0.99
        cfg = ImuAxisConfig(smoothing=2.0)
        assert cfg.smoothing == 0.99

    def test_config_clamp_deadzone_below_zero(self):
        from gamepad_midi_bridge.imu_helper import ImuAxisConfig
        cfg = ImuAxisConfig(deadzone=-0.1)
        assert cfg.deadzone == 0.0

    def test_config_clamp_deadzone_above_one(self):
        from gamepad_midi_bridge.imu_helper import ImuAxisConfig
        cfg = ImuAxisConfig(deadzone=1.5)
        assert cfg.deadzone == 1.0

    def test_config_to_dict(self):
        from gamepad_midi_bridge.imu_helper import ImuAxisConfig
        cfg = ImuAxisConfig(
            enabled=True,
            cc=100,
            channel=5,
            gain=2.0,
            invert=True,
            smoothing=0.5,
            deadzone=0.1,
            bipolar=False,
        )
        d = cfg.to_dict()
        assert d["enabled"] is True
        assert d["cc"] == 100
        assert d["channel"] == 5
        assert d["gain"] == 2.0
        assert d["invert"] is True
        assert d["smoothing"] == 0.5
        assert d["deadzone"] == 0.1
        assert d["bipolar"] is False

    def test_config_from_dict(self):
        from gamepad_midi_bridge.imu_helper import ImuAxisConfig
        d = {
            "enabled": True,
            "cc": 50,
            "channel": 10,
            "gain": 1.5,
            "invert": False,
            "smoothing": 0.7,
            "deadzone": 0.02,
            "bipolar": True,
        }
        cfg = ImuAxisConfig.from_dict(d)
        assert cfg.enabled is True
        assert cfg.cc == 50
        assert cfg.channel == 10
        assert cfg.gain == 1.5
        assert cfg.invert is False
        assert cfg.smoothing == 0.7
        assert cfg.deadzone == 0.02
        assert cfg.bipolar is True

    def test_config_from_dict_missing_keys_use_defaults(self):
        from gamepad_midi_bridge.imu_helper import ImuAxisConfig
        d = {"enabled": True, "cc": 42}
        cfg = ImuAxisConfig.from_dict(d)
        assert cfg.enabled is True
        assert cfg.cc == 42
        assert cfg.channel == 1
        assert cfg.gain == 1.0
        assert cfg.smoothing == 0.3
        assert cfg.deadzone == 0.05

    def test_config_from_dict_applies_clamping(self):
        from gamepad_midi_bridge.imu_helper import ImuAxisConfig
        d = {
            "cc": 200,
            "channel": 100,
            "gain": 500.0,
            "smoothing": 2.0,
            "deadzone": 2.0,
        }
        cfg = ImuAxisConfig.from_dict(d)
        assert cfg.cc == 127
        assert cfg.channel == 16
        assert cfg.gain == 100.0
        assert cfg.smoothing == 0.99
        assert cfg.deadzone == 1.0

    def test_config_round_trip(self):
        from gamepad_midi_bridge.imu_helper import ImuAxisConfig
        original = ImuAxisConfig(
            enabled=True,
            cc=80,
            channel=8,
            gain=3.5,
            invert=True,
            smoothing=0.6,
            deadzone=0.08,
            bipolar=False,
        )
        d = original.to_dict()
        restored = ImuAxisConfig.from_dict(d)
        assert restored.enabled == original.enabled
        assert restored.cc == original.cc
        assert restored.channel == original.channel
        assert restored.gain == original.gain
        assert restored.invert == original.invert
        assert restored.smoothing == original.smoothing
        assert restored.deadzone == original.deadzone
        assert restored.bipolar == original.bipolar


class TestImuAxisProcessor:
    """ImuAxisProcessor — stateful axis processing with smoothing, gain, etc."""

    def test_feed_disabled_returns_none(self):
        from gamepad_midi_bridge.imu_helper import ImuAxisConfig, ImuAxisProcessor
        cfg = ImuAxisConfig(enabled=False)
        proc = ImuAxisProcessor(cfg)
        assert proc.feed(0.0) is None
        assert proc.feed(1.0) is None
        assert proc.feed(-1.0) is None

    def test_feed_enabled_returns_int(self):
        from gamepad_midi_bridge.imu_helper import ImuAxisConfig, ImuAxisProcessor
        cfg = ImuAxisConfig(enabled=True, smoothing=0.0)
        proc = ImuAxisProcessor(cfg)
        result = proc.feed(0.0)
        assert isinstance(result, int)
        assert 0 <= result <= 127

    def test_feed_bipolar_raw_zero_returns_midpoint(self):
        """Bipolar at raw=0 should return ~64 (midpoint of 0..127)."""
        from gamepad_midi_bridge.imu_helper import ImuAxisConfig, ImuAxisProcessor
        cfg = ImuAxisConfig(enabled=True, bipolar=True, smoothing=0.0)
        proc = ImuAxisProcessor(cfg)
        result = proc.feed(0.0)
        # At raw=0 with no smoothing: (0 + 1) * 63.5 = 63.5 → rounds to 64.
        assert result == 64

    def test_feed_bipolar_raw_positive_one(self):
        """Bipolar at raw=1 (after smoothing) should approach 127."""
        from gamepad_midi_bridge.imu_helper import ImuAxisConfig, ImuAxisProcessor
        cfg = ImuAxisConfig(enabled=True, bipolar=True, smoothing=0.0)
        proc = ImuAxisProcessor(cfg)
        # With smoothing=0.0, _smoothed = 0 * 0 + 1.0 * 1.0 = 1.0
        # Map: (1.0 + 1) * 63.5 = 127
        result = proc.feed(1.0)
        assert result == 127

    def test_feed_bipolar_raw_negative_one(self):
        """Bipolar at raw=-1 should approach 0."""
        from gamepad_midi_bridge.imu_helper import ImuAxisConfig, ImuAxisProcessor
        cfg = ImuAxisConfig(enabled=True, bipolar=True, smoothing=0.0)
        proc = ImuAxisProcessor(cfg)
        # With smoothing=0.0, _smoothed = 0 * 0 + (-1.0) * 1.0 = -1.0
        # Map: (-1.0 + 1) * 63.5 = 0
        result = proc.feed(-1.0)
        assert result == 0

    def test_feed_unipolar_raw_zero(self):
        """Unipolar at raw=0 should return 0."""
        from gamepad_midi_bridge.imu_helper import ImuAxisConfig, ImuAxisProcessor
        cfg = ImuAxisConfig(enabled=True, bipolar=False, smoothing=0.0)
        proc = ImuAxisProcessor(cfg)
        result = proc.feed(0.0)
        assert result == 0

    def test_feed_unipolar_raw_one(self):
        """Unipolar at raw=1 should return 127."""
        from gamepad_midi_bridge.imu_helper import ImuAxisConfig, ImuAxisProcessor
        cfg = ImuAxisConfig(enabled=True, bipolar=False, smoothing=0.0)
        proc = ImuAxisProcessor(cfg)
        result = proc.feed(1.0)
        assert result == 127

    def test_feed_deadzone_suppresses_small_raw(self):
        """Deadzone: small values treated as zero."""
        from gamepad_midi_bridge.imu_helper import ImuAxisConfig, ImuAxisProcessor
        cfg = ImuAxisConfig(
            enabled=True,
            deadzone=0.1,
            bipolar=True,
            smoothing=0.0,
        )
        proc = ImuAxisProcessor(cfg)
        # Raw within deadzone (0.05 < 0.1) → treated as 0 → maps to 64.
        result = proc.feed(0.05)
        assert result == 64

    def test_feed_deadzone_passes_large_raw(self):
        """Deadzone: large values pass through."""
        from gamepad_midi_bridge.imu_helper import ImuAxisConfig, ImuAxisProcessor
        cfg = ImuAxisConfig(
            enabled=True,
            deadzone=0.1,
            bipolar=True,
            smoothing=0.0,
        )
        proc = ImuAxisProcessor(cfg)
        # Raw outside deadzone (0.5 > 0.1) → passes → maps to positive.
        result = proc.feed(0.5)
        assert result > 64

    def test_feed_invert_flips_sign(self):
        """Invert: negates raw before output."""
        from gamepad_midi_bridge.imu_helper import ImuAxisConfig, ImuAxisProcessor
        cfg_normal = ImuAxisConfig(
            enabled=True,
            invert=False,
            bipolar=True,
            smoothing=0.0,
        )
        proc_normal = ImuAxisProcessor(cfg_normal)
        result_normal = proc_normal.feed(0.5)

        cfg_inverted = ImuAxisConfig(
            enabled=True,
            invert=True,
            bipolar=True,
            smoothing=0.0,
        )
        proc_inverted = ImuAxisProcessor(cfg_inverted)
        result_inverted = proc_inverted.feed(0.5)

        # Normal 0.5 → maps to > 64; inverted -0.5 → maps to < 64.
        assert result_normal > 64
        assert result_inverted < 64

    def test_feed_gain_amplifies(self):
        """Gain: multiplies raw before smoothing."""
        from gamepad_midi_bridge.imu_helper import ImuAxisConfig, ImuAxisProcessor
        cfg_no_gain = ImuAxisConfig(
            enabled=True,
            gain=1.0,
            bipolar=True,
            smoothing=0.0,
        )
        proc_no_gain = ImuAxisProcessor(cfg_no_gain)
        result_no_gain = proc_no_gain.feed(0.5)

        cfg_gain_2x = ImuAxisConfig(
            enabled=True,
            gain=2.0,
            bipolar=True,
            smoothing=0.0,
        )
        proc_gain_2x = ImuAxisProcessor(cfg_gain_2x)
        result_gain_2x = proc_gain_2x.feed(0.5)

        # 0.5 * 2.0 = 1.0 (clamped) → 127. 0.5 * 1.0 = 0.5 → mid-high.
        assert result_gain_2x > result_no_gain

    def test_feed_smoothing_blends(self):
        """Smoothing: exponential moving average with blend factor."""
        from gamepad_midi_bridge.imu_helper import ImuAxisConfig, ImuAxisProcessor
        cfg = ImuAxisConfig(
            enabled=True,
            smoothing=0.5,
            bipolar=True,
        )
        proc = ImuAxisProcessor(cfg)
        # First feed: raw=1.0 → _smoothed = 0 * 0.5 + 1.0 * 0.5 = 0.5
        result1 = proc.feed(1.0)
        # After first feed, _smoothed ≈ 0.5; second feed: raw=0 →
        # _smoothed = 0.5 * 0.5 + 0 * 0.5 = 0.25
        result2 = proc.feed(0.0)
        # result1 should be higher than result2 (smoother decay).
        assert result1 > result2

    def test_feed_smoothing_zero_no_smoothing(self):
        """Smoothing=0: no EMA, direct passthrough."""
        from gamepad_midi_bridge.imu_helper import ImuAxisConfig, ImuAxisProcessor
        cfg = ImuAxisConfig(
            enabled=True,
            smoothing=0.0,
            bipolar=True,
        )
        proc = ImuAxisProcessor(cfg)
        result1 = proc.feed(1.0)
        result2 = proc.feed(-1.0)
        # With smoothing=0, output is immediate: 1.0 → 127, -1.0 → 0.
        assert result1 == 127
        assert result2 == 0

    def test_feed_clamping_bipolar(self):
        """Bipolar clamping: _smoothed clamped to -1..+1 before mapping."""
        from gamepad_midi_bridge.imu_helper import ImuAxisConfig, ImuAxisProcessor
        cfg = ImuAxisConfig(
            enabled=True,
            gain=10.0,  # Amplify beyond -1..+1.
            bipolar=True,
            smoothing=0.0,
        )
        proc = ImuAxisProcessor(cfg)
        # Raw=0.2 * gain=10 = 2.0 → clamped to 1.0 → 127.
        result = proc.feed(0.2)
        assert result == 127

    def test_feed_clamping_unipolar(self):
        """Unipolar clamping: _smoothed clamped to 0..1 before mapping."""
        from gamepad_midi_bridge.imu_helper import ImuAxisConfig, ImuAxisProcessor
        cfg = ImuAxisConfig(
            enabled=True,
            gain=10.0,
            bipolar=False,
            smoothing=0.0,
        )
        proc = ImuAxisProcessor(cfg)
        # Raw=0.2 * gain=10 = 2.0 → clamped to 1.0 → 127.
        result = proc.feed(0.2)
        assert result == 127

    def test_reset_clears_smoothed_state(self):
        """reset(): clears _smoothed to 0."""
        from gamepad_midi_bridge.imu_helper import ImuAxisConfig, ImuAxisProcessor
        cfg = ImuAxisConfig(enabled=True, smoothing=0.9)
        proc = ImuAxisProcessor(cfg)
        proc.feed(1.0)
        assert proc._smoothed != 0.0
        proc.reset()
        assert proc._smoothed == 0.0

    def test_reset_then_first_feed_fresh(self):
        """After reset(), first feed() starts from _smoothed=0."""
        from gamepad_midi_bridge.imu_helper import ImuAxisConfig, ImuAxisProcessor
        cfg = ImuAxisConfig(
            enabled=True,
            smoothing=0.5,
            bipolar=True,
        )
        proc = ImuAxisProcessor(cfg)
        proc.feed(1.0)
        proc.reset()
        result = proc.feed(1.0)
        # After reset, _smoothed=0; feed(1.0) → _smoothed = 0 * 0.5 + 1.0 * 0.5 = 0.5
        # Mapped: (0.5 + 1) * 63.5 ≈ 95.25 → 95.
        assert result == 95


class TestImuMappingConfig:
    """ImuMappingConfig — 6-axis config with serialization."""

    def test_config_defaults(self):
        from gamepad_midi_bridge.imu_helper import ImuMappingConfig
        cfg = ImuMappingConfig()
        assert cfg.enabled is False
        assert cfg.gyro_x.enabled is False
        assert cfg.accel_z.enabled is False

    def test_config_to_dict(self):
        from gamepad_midi_bridge.imu_helper import ImuMappingConfig, ImuAxisConfig
        cfg = ImuMappingConfig(
            enabled=True,
            gyro_x=ImuAxisConfig(enabled=True, cc=10),
        )
        d = cfg.to_dict()
        assert d["enabled"] is True
        assert d["gyro_x"]["enabled"] is True
        assert d["gyro_x"]["cc"] == 10
        assert isinstance(d["gyro_y"], dict)

    def test_config_from_dict(self):
        from gamepad_midi_bridge.imu_helper import ImuMappingConfig
        d = {
            "enabled": True,
            "gyro_x": {"enabled": True, "cc": 20, "channel": 2},
            "accel_y": {"enabled": True, "cc": 30},
        }
        cfg = ImuMappingConfig.from_dict(d)
        assert cfg.enabled is True
        assert cfg.gyro_x.enabled is True
        assert cfg.gyro_x.cc == 20
        assert cfg.gyro_x.channel == 2
        assert cfg.accel_y.enabled is True
        assert cfg.accel_y.cc == 30
        assert cfg.gyro_y.enabled is False  # Missing, defaults to False.

    def test_config_round_trip(self):
        from gamepad_midi_bridge.imu_helper import ImuMappingConfig, ImuAxisConfig
        original = ImuMappingConfig(
            enabled=True,
            gyro_x=ImuAxisConfig(enabled=True, cc=11, gain=2.0),
            accel_z=ImuAxisConfig(enabled=True, cc=50, invert=True),
        )
        d = original.to_dict()
        restored = ImuMappingConfig.from_dict(d)
        assert restored.enabled == original.enabled
        assert restored.gyro_x.enabled == original.gyro_x.enabled
        assert restored.gyro_x.cc == original.gyro_x.cc
        assert restored.gyro_x.gain == original.gyro_x.gain
        assert restored.accel_z.enabled == original.accel_z.enabled
        assert restored.accel_z.cc == original.accel_z.cc
        assert restored.accel_z.invert == original.accel_z.invert


class TestImuMapping:
    """ImuMapping — process gyro and accel, emit CC tuples."""

    def test_process_disabled_returns_empty(self):
        from gamepad_midi_bridge.imu_helper import ImuMappingConfig, ImuMapping
        cfg = ImuMappingConfig(enabled=False)
        mapping = ImuMapping(cfg)
        result = mapping.process((0.5, 0.5, 0.5), (0.5, 0.5, 0.5))
        assert result == []

    def test_process_all_axes_enabled_returns_six_tuples(self):
        from gamepad_midi_bridge.imu_helper import (
            ImuMappingConfig,
            ImuAxisConfig,
            ImuMapping,
        )
        cfg = ImuMappingConfig(
            enabled=True,
            gyro_x=ImuAxisConfig(enabled=True, cc=1, channel=1),
            gyro_y=ImuAxisConfig(enabled=True, cc=2, channel=1),
            gyro_z=ImuAxisConfig(enabled=True, cc=3, channel=1),
            accel_x=ImuAxisConfig(enabled=True, cc=4, channel=1),
            accel_y=ImuAxisConfig(enabled=True, cc=5, channel=1),
            accel_z=ImuAxisConfig(enabled=True, cc=6, channel=1),
        )
        mapping = ImuMapping(cfg)
        result = mapping.process((0.1, 0.2, 0.3), (0.4, 0.5, 0.6))
        assert len(result) == 6
        # Each tuple is (cc, channel, value).
        ccs = [t[0] for t in result]
        assert ccs == [1, 2, 3, 4, 5, 6]

    def test_process_only_gyro_x_enabled(self):
        from gamepad_midi_bridge.imu_helper import (
            ImuMappingConfig,
            ImuAxisConfig,
            ImuMapping,
        )
        cfg = ImuMappingConfig(
            enabled=True,
            gyro_x=ImuAxisConfig(enabled=True, cc=10, channel=5),
        )
        mapping = ImuMapping(cfg)
        result = mapping.process((0.5, 0.5, 0.5), (0.5, 0.5, 0.5))
        assert len(result) == 1
        assert result[0][0] == 10  # CC
        assert result[0][1] == 5  # Channel
        assert isinstance(result[0][2], int)
        assert 0 <= result[0][2] <= 127

    def test_process_mixed_enabled_disabled(self):
        from gamepad_midi_bridge.imu_helper import (
            ImuMappingConfig,
            ImuAxisConfig,
            ImuMapping,
        )
        cfg = ImuMappingConfig(
            enabled=True,
            gyro_x=ImuAxisConfig(enabled=True, cc=1, channel=1),
            gyro_y=ImuAxisConfig(enabled=False),
            accel_z=ImuAxisConfig(enabled=True, cc=6, channel=1),
        )
        mapping = ImuMapping(cfg)
        result = mapping.process((0.1, 0.2, 0.3), (0.4, 0.5, 0.6))
        assert len(result) == 2
        ccs = [t[0] for t in result]
        assert 1 in ccs
        assert 6 in ccs

    def test_process_returns_cc_channel_value_tuples(self):
        from gamepad_midi_bridge.imu_helper import (
            ImuMappingConfig,
            ImuAxisConfig,
            ImuMapping,
        )
        cfg = ImuMappingConfig(
            enabled=True,
            gyro_x=ImuAxisConfig(enabled=True, cc=20, channel=7),
        )
        mapping = ImuMapping(cfg)
        result = mapping.process((0.5, 0.0, 0.0), (0.0, 0.0, 0.0))
        assert len(result) == 1
        cc, channel, value = result[0]
        assert cc == 20
        assert channel == 7
        assert isinstance(value, int)
        assert 0 <= value <= 127

    def test_reset_clears_all_processors(self):
        from gamepad_midi_bridge.imu_helper import (
            ImuMappingConfig,
            ImuAxisConfig,
            ImuMapping,
        )
        cfg = ImuMappingConfig(
            enabled=True,
            gyro_x=ImuAxisConfig(enabled=True, cc=1, channel=1, smoothing=0.9),
        )
        mapping = ImuMapping(cfg)
        mapping.process((1.0, 0.0, 0.0), (0.0, 0.0, 0.0))
        # After process, _gyro_x._smoothed should be non-zero.
        assert mapping._gyro_x._smoothed != 0.0
        mapping.reset()
        # After reset, all processors cleared.
        assert mapping._gyro_x._smoothed == 0.0
        assert mapping._gyro_y._smoothed == 0.0
        assert mapping._accel_x._smoothed == 0.0

    def test_comprehensive_scenario(self):
        """End-to-end: multi-axis with different configs."""
        from gamepad_midi_bridge.imu_helper import (
            ImuMappingConfig,
            ImuAxisConfig,
            ImuMapping,
        )
        cfg = ImuMappingConfig(
            enabled=True,
            gyro_x=ImuAxisConfig(
                enabled=True,
                cc=10,
                channel=1,
                gain=2.0,
                smoothing=0.5,
            ),
            gyro_y=ImuAxisConfig(
                enabled=True,
                cc=11,
                channel=2,
                invert=True,
            ),
            accel_x=ImuAxisConfig(
                enabled=True,
                cc=20,
                channel=3,
                deadzone=0.1,
            ),
            accel_z=ImuAxisConfig(
                enabled=False,  # Disabled axis.
            ),
        )
        mapping = ImuMapping(cfg)
        # First call: gyro_x, gyro_y, accel_x enabled and active.
        result1 = mapping.process((0.5, 0.5, 0.0), (0.5, 0.0, 0.0))
        assert len(result1) == 3
        # gyro_x, gyro_y, accel_x should be present.
        ccs = [t[0] for t in result1]
        assert set(ccs) == {10, 11, 20}

        # Second call: accel_z remains disabled, so still 3 results.
        result2 = mapping.process((0.5, 0.5, 0.0), (0.5, 0.0, 0.5))
        assert len(result2) == 3
        ccs2 = [t[0] for t in result2]
        assert set(ccs2) == {10, 11, 20}  # accel_z is still disabled
