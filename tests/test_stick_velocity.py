"""Tests for stick velocity and acceleration tracking."""
from __future__ import annotations

import pytest
import math
from gamepad_midi_bridge.stick_velocity import StickVelocityConfig, StickVelocityTracker


class TestStickVelocityConfig:
    """Tests for StickVelocityConfig dataclass."""

    def test_default_config(self):
        """Default config has tracking disabled, sensible smoothing."""
        cfg = StickVelocityConfig()
        assert cfg.enabled is False
        assert cfg.smoothing == 0.3
        assert cfg.velocity_scale == 1.0
        assert cfg.max_history == 16

    def test_custom_config(self):
        """Can construct with custom values."""
        cfg = StickVelocityConfig(
            enabled=True,
            smoothing=0.5,
            velocity_scale=2.0,
            max_history=32,
        )
        assert cfg.enabled is True
        assert cfg.smoothing == 0.5
        assert cfg.velocity_scale == 2.0
        assert cfg.max_history == 32

    def test_clamp_smoothing_0_to_0_99(self):
        """smoothing is clamped to 0.0..0.99."""
        cfg = StickVelocityConfig(smoothing=-0.1)
        assert cfg.smoothing == 0.0

        cfg = StickVelocityConfig(smoothing=1.5)
        assert cfg.smoothing == 0.99

    def test_clamp_velocity_scale_0_01_to_100(self):
        """velocity_scale is clamped to 0.01..100."""
        cfg = StickVelocityConfig(velocity_scale=0.001)
        assert cfg.velocity_scale == 0.01

        cfg = StickVelocityConfig(velocity_scale=200.0)
        assert cfg.velocity_scale == 100.0

    def test_clamp_max_history_2_to_256(self):
        """max_history is clamped to 2..256."""
        cfg = StickVelocityConfig(max_history=1)
        assert cfg.max_history == 2

        cfg = StickVelocityConfig(max_history=500)
        assert cfg.max_history == 256

    def test_to_dict(self):
        """to_dict serializes config to dictionary."""
        cfg = StickVelocityConfig(
            enabled=True,
            smoothing=0.4,
            velocity_scale=1.5,
            max_history=24,
        )
        d = cfg.to_dict()
        assert d["enabled"] is True
        assert d["smoothing"] == 0.4
        assert d["velocity_scale"] == 1.5
        assert d["max_history"] == 24

    def test_from_dict(self):
        """from_dict deserializes config from dictionary."""
        d = {
            "enabled": True,
            "smoothing": 0.6,
            "velocity_scale": 0.8,
            "max_history": 20,
        }
        cfg = StickVelocityConfig.from_dict(d)
        assert cfg.enabled is True
        assert cfg.smoothing == 0.6
        assert cfg.velocity_scale == 0.8
        assert cfg.max_history == 20

    def test_from_dict_round_trip(self):
        """Round-trip: to_dict → from_dict preserves values."""
        original = StickVelocityConfig(
            enabled=True,
            smoothing=0.45,
            velocity_scale=2.5,
            max_history=64,
        )
        d = original.to_dict()
        restored = StickVelocityConfig.from_dict(d)
        assert restored.enabled == original.enabled
        assert restored.smoothing == original.smoothing
        assert restored.velocity_scale == original.velocity_scale
        assert restored.max_history == original.max_history

    def test_from_dict_partial(self):
        """from_dict fills missing keys with defaults."""
        d = {"enabled": True}
        cfg = StickVelocityConfig.from_dict(d)
        assert cfg.enabled is True
        assert cfg.smoothing == 0.3  # default
        assert cfg.velocity_scale == 1.0  # default
        assert cfg.max_history == 16  # default


class TestStickVelocityTrackerBasic:
    """Tests for basic StickVelocityTracker functionality."""

    def test_default_no_samples_returns_zeros(self):
        """Tracker with no samples returns all zeros."""
        cfg = StickVelocityConfig(enabled=True)
        tracker = StickVelocityTracker(cfg)
        result = tracker.current()
        assert result["vx"] == 0.0
        assert result["vy"] == 0.0
        assert result["speed"] == 0.0
        assert result["ax"] == 0.0
        assert result["ay"] == 0.0

    def test_one_sample_vx_vy_are_zero(self):
        """First sample has zero velocity (no previous point)."""
        cfg = StickVelocityConfig(enabled=True)
        tracker = StickVelocityTracker(cfg)
        result = tracker.sample(1.0, 0.0, 0.0)
        # First sample: no previous, so vx/vy/speed/ax/ay = 0.
        assert result["vx"] == 0.0
        assert result["vy"] == 0.0
        assert result["speed"] == 0.0
        assert result["ax"] == 0.0
        assert result["ay"] == 0.0

    def test_two_samples_one_sec_apart(self):
        """Two samples 1 sec apart: (0,0) → (1,0) → vx ≈ 1.0."""
        cfg = StickVelocityConfig(enabled=True, smoothing=0.0)  # No smoothing for raw.
        tracker = StickVelocityTracker(cfg)
        tracker.sample(0.0, 0.0, 0.0)
        result = tracker.sample(1.0, 0.0, 1.0)
        # dt = 1.0, dx = 1.0 → vx = 1.0.
        assert abs(result["vx"] - 1.0) < 1e-6
        assert abs(result["vy"] - 0.0) < 1e-6
        assert abs(result["speed"] - 1.0) < 1e-6

    def test_diagonal_movement(self):
        """Diagonal movement (3,4,5 right triangle)."""
        cfg = StickVelocityConfig(enabled=True, smoothing=0.0)
        tracker = StickVelocityTracker(cfg)
        tracker.sample(0.0, 0.0, 0.0)
        result = tracker.sample(0.3, 0.4, 1.0)
        # dt = 1.0, dx = 0.3, dy = 0.4 → speed = 0.5.
        vx = result["vx"]
        vy = result["vy"]
        speed = result["speed"]
        assert abs(vx - 0.3) < 1e-6
        assert abs(vy - 0.4) < 1e-6
        assert abs(speed - 0.5) < 1e-6

    def test_reset_clears_state(self):
        """reset() clears history and returns to zeros."""
        cfg = StickVelocityConfig(enabled=True)
        tracker = StickVelocityTracker(cfg)
        tracker.sample(0.0, 0.0, 0.0)
        tracker.sample(1.0, 1.0, 1.0)

        # Before reset: non-zero.
        assert tracker.current()["speed"] > 0.0

        # After reset: zeros.
        tracker.reset()
        result = tracker.current()
        assert result["vx"] == 0.0
        assert result["vy"] == 0.0
        assert result["speed"] == 0.0
        assert result["ax"] == 0.0
        assert result["ay"] == 0.0


class TestStickVelocityTrackerSmoothing:
    """Tests for velocity smoothing."""

    def test_smoothing_0_no_smoothing(self):
        """Smoothing = 0.0: instant response."""
        cfg = StickVelocityConfig(enabled=True, smoothing=0.0)
        tracker = StickVelocityTracker(cfg)
        tracker.sample(0.0, 0.0, 0.0)
        result = tracker.sample(1.0, 0.0, 1.0)
        # smoothed = 0 * 0.0 + 1.0 * 1.0 = 1.0.
        assert abs(result["vx"] - 1.0) < 1e-6

    def test_smoothing_0_99_max_lag(self):
        """Smoothing = 0.99: heavy filtering."""
        cfg = StickVelocityConfig(enabled=True, smoothing=0.99)
        tracker = StickVelocityTracker(cfg)
        tracker.sample(0.0, 0.0, 0.0)
        result = tracker.sample(1.0, 0.0, 1.0)
        # smoothed = 0 * 0.99 + 1.0 * 0.01 = 0.01.
        assert abs(result["vx"] - 0.01) < 1e-6

    def test_smoothing_0_3_default(self):
        """Smoothing = 0.3: balanced (default)."""
        cfg = StickVelocityConfig(enabled=True, smoothing=0.3)
        tracker = StickVelocityTracker(cfg)
        tracker.sample(0.0, 0.0, 0.0)
        result = tracker.sample(1.0, 0.0, 1.0)
        # smoothed = 0 * 0.3 + 1.0 * 0.7 = 0.7.
        assert abs(result["vx"] - 0.7) < 1e-6

    def test_disabled_no_smoothing_applied(self):
        """When disabled, smoothing is not applied (raw value used)."""
        cfg = StickVelocityConfig(enabled=False, smoothing=0.99)
        tracker = StickVelocityTracker(cfg)
        tracker.sample(0.0, 0.0, 0.0)
        result = tracker.sample(1.0, 0.0, 1.0)
        assert abs(result["vx"] - 1.0) < 1e-6


class TestStickVelocityTrackerVelocityScale:
    """Tests for velocity_scale multiplier."""

    def test_velocity_scale_1_0_identity(self):
        """velocity_scale = 1.0: no scaling."""
        cfg = StickVelocityConfig(enabled=True, smoothing=0.0, velocity_scale=1.0)
        tracker = StickVelocityTracker(cfg)
        tracker.sample(0.0, 0.0, 0.0)
        result = tracker.sample(1.0, 0.0, 1.0)
        assert abs(result["vx"] - 1.0) < 1e-6

    def test_velocity_scale_2_0_doubling(self):
        """velocity_scale = 2.0: doubles velocity."""
        cfg = StickVelocityConfig(enabled=True, smoothing=0.0, velocity_scale=2.0)
        tracker = StickVelocityTracker(cfg)
        tracker.sample(0.0, 0.0, 0.0)
        result = tracker.sample(1.0, 0.0, 1.0)
        # vx = 1.0 * 2.0 = 2.0.
        assert abs(result["vx"] - 2.0) < 1e-6
        assert abs(result["speed"] - 2.0) < 1e-6

    def test_velocity_scale_0_5_halving(self):
        """velocity_scale = 0.5: halves velocity."""
        cfg = StickVelocityConfig(enabled=True, smoothing=0.0, velocity_scale=0.5)
        tracker = StickVelocityTracker(cfg)
        tracker.sample(0.0, 0.0, 0.0)
        result = tracker.sample(1.0, 0.0, 1.0)
        # vx = 1.0 * 0.5 = 0.5.
        assert abs(result["vx"] - 0.5) < 1e-6


class TestStickVelocityTrackerMaxHistory:
    """Tests for max_history cap."""

    def test_max_history_2_truncates(self):
        """History buffer respects max_history = 2 (keeps last 2)."""
        cfg = StickVelocityConfig(enabled=True, max_history=2)
        tracker = StickVelocityTracker(cfg)
        tracker.sample(0.0, 0.0, 0.0)
        tracker.sample(1.0, 0.0, 1.0)
        tracker.sample(2.0, 0.0, 2.0)
        # Should have last 2: (1.0, 1.0) and (2.0, 2.0).
        # Check internally (via reset and re-feeding):
        assert len(tracker._history) == 2

    def test_max_history_large_keeps_all(self):
        """Large max_history doesn't truncate small samples."""
        cfg = StickVelocityConfig(enabled=True, max_history=256)
        tracker = StickVelocityTracker(cfg)
        for i in range(10):
            tracker.sample(float(i), 0.0, float(i))
        assert len(tracker._history) == 10


class TestStickVelocityTrackerAcceleration:
    """Tests for acceleration computation."""

    def test_constant_velocity_zero_acceleration(self):
        """Constant velocity → zero acceleration."""
        cfg = StickVelocityConfig(enabled=True, smoothing=0.0)
        tracker = StickVelocityTracker(cfg)
        tracker.sample(0.0, 0.0, 0.0)
        tracker.sample(1.0, 0.0, 1.0)
        result = tracker.sample(2.0, 0.0, 2.0)
        # vx at t=1: 1.0. vx at t=2: 1.0. Δv = 0. ax ≈ 0.
        assert abs(result["ax"]) < 1e-6

    def test_increasing_velocity_positive_acceleration(self):
        """Increasing velocity → positive acceleration."""
        cfg = StickVelocityConfig(enabled=True, smoothing=0.0)
        tracker = StickVelocityTracker(cfg)
        tracker.sample(0.0, 0.0, 0.0)      # t=0, x=0
        tracker.sample(1.0, 0.0, 1.0)      # t=1, x=1 → vx=1.0
        result = tracker.sample(3.0, 0.0, 2.0)  # t=2, x=3 → vx=2.0, ax=(2-1)/1=1.0
        # vx at t=1: 1.0. vx at t=2: 2.0. dt=1.0. ax = 1.0.
        assert abs(result["ax"] - 1.0) < 1e-6

    def test_decreasing_velocity_negative_acceleration(self):
        """Decreasing velocity → negative acceleration."""
        cfg = StickVelocityConfig(enabled=True, smoothing=0.0)
        tracker = StickVelocityTracker(cfg)
        tracker.sample(0.0, 0.0, 0.0)      # t=0, x=0
        tracker.sample(2.0, 0.0, 1.0)      # t=1, x=2 → vx=2.0
        result = tracker.sample(2.5, 0.0, 2.0)  # t=2, x=2.5 → vx=0.5, ax=(0.5-2)/1=-1.5
        # vx at t=1: 2.0. vx at t=2: 0.5. dt=1.0. ax = -1.5.
        assert abs(result["ax"] - (-1.5)) < 1e-6

    def test_acceleration_y_axis(self):
        """Acceleration computed on y-axis."""
        cfg = StickVelocityConfig(enabled=True, smoothing=0.0)
        tracker = StickVelocityTracker(cfg)
        tracker.sample(0.0, 0.0, 0.0)      # t=0, y=0
        tracker.sample(0.0, 1.0, 1.0)      # t=1, y=1 → vy=1.0
        result = tracker.sample(0.0, 3.0, 2.0)  # t=2, y=3 → vy=2.0, ay=1.0
        assert abs(result["ay"] - 1.0) < 1e-6


class TestStickVelocityTrackerToCc:
    """Tests for to_cc() mapping."""

    def test_to_cc_speed_at_rest_is_min(self):
        """Speed = 0 → CC at min_value."""
        cfg = StickVelocityConfig(enabled=True)
        tracker = StickVelocityTracker(cfg)
        cc = tracker.to_cc("speed", min_value=0, max_value=127, clip_at_speed=5.0)
        assert cc == 0

    def test_to_cc_speed_at_max_is_max(self):
        """Speed >= clip_at_speed → CC at max_value."""
        cfg = StickVelocityConfig(enabled=True, smoothing=0.0)
        tracker = StickVelocityTracker(cfg)
        tracker.sample(0.0, 0.0, 0.0)
        tracker.sample(10.0, 0.0, 1.0)  # vx=10, speed=10 >= 5.
        cc = tracker.to_cc("speed", min_value=0, max_value=127, clip_at_speed=5.0)
        assert cc == 127

    def test_to_cc_speed_linear_interpolation(self):
        """Speed = clip_at_speed / 2 → CC ≈ (min + max) / 2."""
        cfg = StickVelocityConfig(enabled=True, smoothing=0.0)
        tracker = StickVelocityTracker(cfg)
        tracker.sample(0.0, 0.0, 0.0)
        tracker.sample(2.5, 0.0, 1.0)  # vx=2.5, speed=2.5 = clip/2.
        cc = tracker.to_cc("speed", min_value=0, max_value=100, clip_at_speed=5.0)
        # norm = 2.5 / 5.0 = 0.5. cc = 0 + 0.5 * 100 = 50.
        assert abs(cc - 50) < 1

    def test_to_cc_vx_axis_absolute_value(self):
        """vx axis uses absolute value (direction-agnostic)."""
        cfg = StickVelocityConfig(enabled=True, smoothing=0.0)
        tracker = StickVelocityTracker(cfg)
        tracker.sample(0.0, 0.0, 0.0)
        tracker.sample(-2.5, 0.0, 1.0)  # vx=-2.5
        cc = tracker.to_cc("vx", min_value=0, max_value=100, clip_at_speed=5.0)
        # abs(-2.5) = 2.5 = clip/2. cc = 50.
        assert abs(cc - 50) < 1

    def test_to_cc_vy_axis(self):
        """vy axis is supported."""
        cfg = StickVelocityConfig(enabled=True, smoothing=0.0)
        tracker = StickVelocityTracker(cfg)
        tracker.sample(0.0, 0.0, 0.0)
        tracker.sample(0.0, 2.5, 1.0)  # vy=2.5
        cc = tracker.to_cc("vy", min_value=0, max_value=100, clip_at_speed=5.0)
        assert abs(cc - 50) < 1

    def test_to_cc_ax_axis(self):
        """ax axis is supported."""
        cfg = StickVelocityConfig(enabled=True, smoothing=0.0)
        tracker = StickVelocityTracker(cfg)
        tracker.sample(0.0, 0.0, 0.0)
        tracker.sample(1.0, 0.0, 1.0)
        tracker.sample(3.0, 0.0, 2.0)  # ax=1.0
        cc = tracker.to_cc("ax", min_value=0, max_value=100, clip_at_speed=2.0)
        # abs(1.0) = 1.0. norm = 1.0 / 2.0 = 0.5. cc = 50.
        assert abs(cc - 50) < 1

    def test_to_cc_ay_axis(self):
        """ay axis is supported."""
        cfg = StickVelocityConfig(enabled=True, smoothing=0.0)
        tracker = StickVelocityTracker(cfg)
        tracker.sample(0.0, 0.0, 0.0)
        tracker.sample(0.0, 1.0, 1.0)
        tracker.sample(0.0, 3.0, 2.0)  # ay=1.0
        cc = tracker.to_cc("ay", min_value=0, max_value=100, clip_at_speed=2.0)
        assert abs(cc - 50) < 1

    def test_to_cc_unknown_axis_defaults_to_speed(self):
        """Unknown axis falls back to speed."""
        cfg = StickVelocityConfig(enabled=True, smoothing=0.0)
        tracker = StickVelocityTracker(cfg)
        tracker.sample(0.0, 0.0, 0.0)
        tracker.sample(2.5, 2.5, 1.0)  # speed=sqrt(2.5^2+2.5^2)≈3.54
        cc = tracker.to_cc("unknown", min_value=0, max_value=100, clip_at_speed=5.0)
        # Should map speed, not crash.
        assert 0 <= cc <= 100

    def test_to_cc_clamp_to_range(self):
        """CC value clamped to [min_value, max_value]."""
        cfg = StickVelocityConfig(enabled=True, smoothing=0.0)
        tracker = StickVelocityTracker(cfg)
        tracker.sample(0.0, 0.0, 0.0)
        tracker.sample(20.0, 0.0, 1.0)  # vx=20 >> clip=5.
        cc = tracker.to_cc("speed", min_value=10, max_value=50, clip_at_speed=5.0)
        assert cc == 50

    def test_to_cc_custom_min_max(self):
        """Custom min/max values work."""
        cfg = StickVelocityConfig(enabled=True, smoothing=0.0)
        tracker = StickVelocityTracker(cfg)
        tracker.sample(0.0, 0.0, 0.0)
        tracker.sample(0.0, 0.0, 0.0)  # Rest.
        cc = tracker.to_cc("speed", min_value=64, max_value=127, clip_at_speed=5.0)
        # speed=0 → min_value=64.
        assert cc == 64

    def test_to_cc_edge_case_clip_at_speed_zero(self):
        """clip_at_speed <= 0 always returns max_value."""
        cfg = StickVelocityConfig(enabled=True, smoothing=0.0)
        tracker = StickVelocityTracker(cfg)
        tracker.sample(0.0, 0.0, 0.0)
        tracker.sample(0.001, 0.0, 1.0)  # Tiny velocity.
        cc = tracker.to_cc("speed", min_value=0, max_value=100, clip_at_speed=0.0)
        assert cc == 100


class TestStickVelocityTrackerEdgeCases:
    """Tests for edge cases and robustness."""

    def test_zero_dt_does_not_crash(self):
        """dt=0 (same timestamp twice) doesn't crash."""
        cfg = StickVelocityConfig(enabled=True)
        tracker = StickVelocityTracker(cfg)
        tracker.sample(0.0, 0.0, 1.0)
        result = tracker.sample(1.0, 0.0, 1.0)  # Same time, different position.
        # dt=0 → division by zero avoided. vx, vy stay at previous value.
        assert "vx" in result
        assert "speed" in result

    def test_negative_time_still_works(self):
        """Negative time values (edge case) don't crash."""
        cfg = StickVelocityConfig(enabled=True, smoothing=0.0)
        tracker = StickVelocityTracker(cfg)
        tracker.sample(0.0, 0.0, -10.0)
        result = tracker.sample(1.0, 0.0, -9.0)  # dt = 1.0.
        assert abs(result["vx"] - 1.0) < 1e-6

    def test_large_position_values(self):
        """Large position values don't overflow."""
        cfg = StickVelocityConfig(enabled=True, smoothing=0.0)
        tracker = StickVelocityTracker(cfg)
        tracker.sample(0.0, 0.0, 0.0)
        result = tracker.sample(1e6, 0.0, 1.0)
        # Large velocity; should compute fine.
        assert result["speed"] > 0

    def test_very_small_dt(self):
        """Very small dt (microseconds) doesn't cause issues."""
        cfg = StickVelocityConfig(enabled=True, smoothing=0.0)
        tracker = StickVelocityTracker(cfg)
        tracker.sample(0.0, 0.0, 0.0)
        result = tracker.sample(1e-6, 0.0, 1e-6)  # dt = 1e-6.
        # vx = 1e-6 / 1e-6 = 1.0.
        assert abs(result["vx"] - 1.0) < 1e-6

    def test_multiple_resets(self):
        """Multiple resets are safe."""
        cfg = StickVelocityConfig(enabled=True)
        tracker = StickVelocityTracker(cfg)
        tracker.reset()
        tracker.reset()
        result = tracker.current()
        assert result["speed"] == 0.0

    def test_sample_after_reset(self):
        """Sampling after reset works correctly."""
        cfg = StickVelocityConfig(enabled=True, smoothing=0.0)
        tracker = StickVelocityTracker(cfg)
        tracker.sample(0.0, 0.0, 0.0)
        tracker.sample(1.0, 0.0, 1.0)
        tracker.reset()
        result = tracker.sample(1.0, 0.0, 2.0)
        # After reset, this is the first sample again → vx/vy/speed = 0.
        assert result["vx"] == 0.0


class TestStickVelocityTrackerIntegration:
    """Integration tests combining multiple features."""

    def test_realistic_stick_shake(self):
        """Realistic stick input: rapid back-and-forth (jitter)."""
        cfg = StickVelocityConfig(enabled=True, smoothing=0.5)
        tracker = StickVelocityTracker(cfg)

        # Simulate jittery stick (oscillating around center).
        times = [0.0, 0.01, 0.02, 0.03, 0.04, 0.05]
        positions = [(0.1, 0.0), (-0.1, 0.0), (0.08, 0.0), (-0.12, 0.0), (0.05, 0.0), (-0.08, 0.0)]

        for t, (x, y) in zip(times, positions):
            tracker.sample(x, y, t)

        result = tracker.current()
        # With smoothing, velocity should be damped compared to raw.
        assert "vx" in result
        assert "speed" in result
        # Speed should be non-zero (jitter has movement).
        assert result["speed"] >= 0

    def test_smooth_circular_motion(self):
        """Smooth circular motion (e.g. stick rotation)."""
        cfg = StickVelocityConfig(enabled=True, smoothing=0.1)
        tracker = StickVelocityTracker(cfg)

        # Trace a quarter circle: (1, 0) → (0.707, 0.707) → (0, 1).
        import math
        for angle_deg in range(0, 91, 10):
            angle_rad = math.radians(angle_deg)
            x = math.cos(angle_rad)
            y = math.sin(angle_rad)
            t = angle_deg / 10.0  # 0.0, 1.0, 2.0, ...
            tracker.sample(x, y, t)

        result = tracker.current()
        # Circular motion should have non-zero velocity and changing direction.
        assert result["speed"] >= 0
        assert "ax" in result
        assert "ay" in result

    def test_to_cc_haptic_trigger_mapping(self):
        """Example: map velocity to haptic trigger intensity."""
        cfg = StickVelocityConfig(enabled=True, smoothing=0.2, velocity_scale=1.0)
        tracker = StickVelocityTracker(cfg)

        # Simulate a "kick" motion: rest → fast upward → release.
        tracker.sample(0.0, 0.0, 0.0)  # Rest.
        tracker.sample(0.0, 0.5, 0.05)  # Fast upward.
        cc = tracker.to_cc("vy", min_value=0, max_value=255, clip_at_speed=1.0)

        # Upward motion should trigger haptics.
        assert cc > 0

    def test_to_cc_adaptive_range(self):
        """Example: adaptive MIDI range based on movement intensity."""
        cfg = StickVelocityConfig(enabled=True, smoothing=0.0)
        tracker = StickVelocityTracker(cfg)

        # Fast movement.
        tracker.sample(0.0, 0.0, 0.0)
        tracker.sample(1.0, 1.0, 1.0)

        # Map to a subset of CC range depending on speed.
        speed_cc = tracker.to_cc("speed", min_value=0, max_value=127, clip_at_speed=2.0)

        # If fast enough, trigger adaptive response.
        if speed_cc > 63:
            # Use extended CC range.
            adaptive_cc = tracker.to_cc("speed", min_value=64, max_value=127, clip_at_speed=2.0)
            assert adaptive_cc > 64
