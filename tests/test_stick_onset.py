"""Tests for stick onset detector module."""

import pytest
from gamepad_midi_bridge.stick_onset import StickOnsetConfig, StickOnsetDetector


class TestStickOnsetConfig:
    """Tests for StickOnsetConfig dataclass."""

    def test_default_config(self):
        """Default config has onset disabled with sensible thresholds."""
        cfg = StickOnsetConfig()
        assert cfg.enabled is False
        assert cfg.min_speed == 1.5
        assert cfg.min_acceleration == 5.0
        assert cfg.cooldown_ms == 80
        assert cfg.velocity_scale == 30.0
        assert cfg.velocity_min == 30
        assert cfg.velocity_max == 127

    def test_custom_config(self):
        """Can construct with custom values."""
        cfg = StickOnsetConfig(
            enabled=True,
            min_speed=2.0,
            min_acceleration=3.0,
            cooldown_ms=100,
            velocity_scale=50.0,
            velocity_min=40,
            velocity_max=120,
        )
        assert cfg.enabled is True
        assert cfg.min_speed == 2.0
        assert cfg.min_acceleration == 3.0
        assert cfg.cooldown_ms == 100
        assert cfg.velocity_scale == 50.0
        assert cfg.velocity_min == 40
        assert cfg.velocity_max == 120

    def test_clamp_min_speed(self):
        """min_speed is clamped to [0.1..20]."""
        cfg_low = StickOnsetConfig(min_speed=0.01)
        assert cfg_low.min_speed == 0.1

        cfg_high = StickOnsetConfig(min_speed=25.0)
        assert cfg_high.min_speed == 20.0

        cfg_valid = StickOnsetConfig(min_speed=5.0)
        assert cfg_valid.min_speed == 5.0

    def test_clamp_min_acceleration(self):
        """min_acceleration is clamped to [0.1..100]."""
        cfg_low = StickOnsetConfig(min_acceleration=0.01)
        assert cfg_low.min_acceleration == 0.1

        cfg_high = StickOnsetConfig(min_acceleration=150.0)
        assert cfg_high.min_acceleration == 100.0

        cfg_valid = StickOnsetConfig(min_acceleration=10.0)
        assert cfg_valid.min_acceleration == 10.0

    def test_clamp_cooldown_ms(self):
        """cooldown_ms is clamped to [10..1000]."""
        cfg_low = StickOnsetConfig(cooldown_ms=5)
        assert cfg_low.cooldown_ms == 10

        cfg_high = StickOnsetConfig(cooldown_ms=2000)
        assert cfg_high.cooldown_ms == 1000

        cfg_valid = StickOnsetConfig(cooldown_ms=100)
        assert cfg_valid.cooldown_ms == 100

    def test_clamp_velocity_scale(self):
        """velocity_scale is clamped to [1..200]."""
        cfg_low = StickOnsetConfig(velocity_scale=0.5)
        assert cfg_low.velocity_scale == 1.0

        cfg_high = StickOnsetConfig(velocity_scale=250.0)
        assert cfg_high.velocity_scale == 200.0

        cfg_valid = StickOnsetConfig(velocity_scale=50.0)
        assert cfg_valid.velocity_scale == 50.0

    def test_clamp_velocity_min_max(self):
        """velocity_min and velocity_max are clamped to [1..127]."""
        cfg_min_low = StickOnsetConfig(velocity_min=0)
        assert cfg_min_low.velocity_min == 1

        cfg_min_high = StickOnsetConfig(velocity_min=150)
        assert cfg_min_high.velocity_min == 127

        # Setting velocity_max=0 clamps to 1, but if velocity_min > 1, they swap
        cfg_max_low = StickOnsetConfig(velocity_max=0, velocity_min=1)
        assert cfg_max_low.velocity_max == 1

        cfg_max_high = StickOnsetConfig(velocity_max=150)
        assert cfg_max_high.velocity_max == 127

    def test_auto_swap_velocity_min_max(self):
        """If velocity_min > velocity_max, they are swapped."""
        cfg = StickOnsetConfig(velocity_min=100, velocity_max=50)
        assert cfg.velocity_min == 50
        assert cfg.velocity_max == 100

    def test_to_dict(self):
        """to_dict serializes config to dictionary."""
        cfg = StickOnsetConfig(
            enabled=True,
            min_speed=2.0,
            min_acceleration=4.0,
            cooldown_ms=90,
            velocity_scale=40.0,
            velocity_min=25,
            velocity_max=110,
        )
        d = cfg.to_dict()
        assert d["enabled"] is True
        assert d["min_speed"] == 2.0
        assert d["min_acceleration"] == 4.0
        assert d["cooldown_ms"] == 90
        assert d["velocity_scale"] == 40.0
        assert d["velocity_min"] == 25
        assert d["velocity_max"] == 110

    def test_from_dict(self):
        """from_dict deserializes config from dictionary."""
        d = {
            "enabled": True,
            "min_speed": 1.8,
            "min_acceleration": 6.0,
            "cooldown_ms": 75,
            "velocity_scale": 35.0,
            "velocity_min": 35,
            "velocity_max": 115,
        }
        cfg = StickOnsetConfig.from_dict(d)
        assert cfg.enabled is True
        assert cfg.min_speed == 1.8
        assert cfg.min_acceleration == 6.0
        assert cfg.cooldown_ms == 75
        assert cfg.velocity_scale == 35.0
        assert cfg.velocity_min == 35
        assert cfg.velocity_max == 115

    def test_from_dict_round_trip(self):
        """Round-trip: to_dict → from_dict preserves values."""
        original = StickOnsetConfig(
            enabled=True,
            min_speed=2.5,
            min_acceleration=7.0,
            cooldown_ms=120,
            velocity_scale=45.0,
            velocity_min=40,
            velocity_max=120,
        )
        d = original.to_dict()
        restored = StickOnsetConfig.from_dict(d)
        assert restored.enabled == original.enabled
        assert restored.min_speed == original.min_speed
        assert restored.min_acceleration == original.min_acceleration
        assert restored.cooldown_ms == original.cooldown_ms
        assert restored.velocity_scale == original.velocity_scale
        assert restored.velocity_min == original.velocity_min
        assert restored.velocity_max == original.velocity_max

    def test_from_dict_partial(self):
        """from_dict fills missing keys with defaults."""
        d = {"enabled": True, "min_speed": 2.0}
        cfg = StickOnsetConfig.from_dict(d)
        assert cfg.enabled is True
        assert cfg.min_speed == 2.0
        assert cfg.min_acceleration == 5.0  # default
        assert cfg.cooldown_ms == 80  # default


class TestStickOnsetDetectorDisabled:
    """Tests when onset detection is disabled."""

    def test_disabled_returns_none(self):
        """When disabled, feed always returns None."""
        cfg = StickOnsetConfig(enabled=False)
        d = StickOnsetDetector(cfg)
        result = d.feed(speed=5.0, acceleration=10.0, now_s=0.0)
        assert result is None

    def test_disabled_high_speed_high_accel_still_returns_none(self):
        """Even with high speed and accel, disabled mode returns None."""
        cfg = StickOnsetConfig(enabled=False, min_speed=0.1, min_acceleration=0.1)
        d = StickOnsetDetector(cfg)
        result = d.feed(speed=10.0, acceleration=20.0, now_s=0.0)
        assert result is None


class TestStickOnsetDetectorThresholds:
    """Tests for speed and acceleration thresholds."""

    def test_speed_below_threshold_returns_none(self):
        """Speed below min_speed returns None."""
        cfg = StickOnsetConfig(enabled=True, min_speed=2.0, min_acceleration=1.0)
        d = StickOnsetDetector(cfg)
        result = d.feed(speed=1.5, acceleration=5.0, now_s=0.0)
        assert result is None

    def test_acceleration_below_threshold_returns_none(self):
        """Acceleration below min_acceleration returns None."""
        cfg = StickOnsetConfig(enabled=True, min_speed=1.0, min_acceleration=10.0)
        d = StickOnsetDetector(cfg)
        result = d.feed(speed=5.0, acceleration=5.0, now_s=0.0)
        assert result is None

    def test_both_thresholds_met_returns_velocity(self):
        """When both thresholds are met, returns velocity int."""
        cfg = StickOnsetConfig(
            enabled=True, min_speed=1.0, min_acceleration=5.0, velocity_scale=50.0
        )
        d = StickOnsetDetector(cfg)
        result = d.feed(speed=2.0, acceleration=10.0, now_s=0.0)
        assert result is not None
        assert isinstance(result, int)
        assert 1 <= result <= 127

    def test_exactly_at_speed_threshold(self):
        """Speed exactly at threshold should fire."""
        cfg = StickOnsetConfig(enabled=True, min_speed=2.0, min_acceleration=1.0)
        d = StickOnsetDetector(cfg)
        result = d.feed(speed=2.0, acceleration=10.0, now_s=0.0)
        assert result is not None

    def test_exactly_at_acceleration_threshold(self):
        """Acceleration exactly at threshold should fire."""
        cfg = StickOnsetConfig(enabled=True, min_speed=1.0, min_acceleration=5.0)
        d = StickOnsetDetector(cfg)
        result = d.feed(speed=5.0, acceleration=5.0, now_s=0.0)
        assert result is not None


class TestStickOnsetVelocityComputation:
    """Tests for velocity computation from speed."""

    def test_velocity_scales_with_speed(self):
        """Higher speed produces higher velocity."""
        cfg = StickOnsetConfig(
            enabled=True,
            min_speed=1.0,
            min_acceleration=1.0,
            velocity_scale=50.0,
            velocity_min=10,
            velocity_max=127,
        )
        d = StickOnsetDetector(cfg)
        vel_slow = d.feed(speed=2.0, acceleration=5.0, now_s=0.0)
        d.reset()
        vel_fast = d.feed(speed=4.0, acceleration=5.0, now_s=0.0)
        assert vel_fast > vel_slow

    def test_velocity_clamped_to_max(self):
        """Very high speed is clamped to velocity_max."""
        cfg = StickOnsetConfig(
            enabled=True,
            min_speed=1.0,
            min_acceleration=1.0,
            velocity_scale=50.0,
            velocity_min=10,
            velocity_max=100,
        )
        d = StickOnsetDetector(cfg)
        # speed=10 * scale=50 = 500, clamped to 100
        result = d.feed(speed=10.0, acceleration=5.0, now_s=0.0)
        assert result == 100

    def test_velocity_clamped_to_min(self):
        """Low speed (but above threshold) is clamped to velocity_min."""
        cfg = StickOnsetConfig(
            enabled=True,
            min_speed=1.0,
            min_acceleration=1.0,
            velocity_scale=10.0,
            velocity_min=30,
            velocity_max=127,
        )
        d = StickOnsetDetector(cfg)
        # speed=1.5 * scale=10 = 15, clamped to velocity_min=30
        result = d.feed(speed=1.5, acceleration=5.0, now_s=0.0)
        assert result == 30

    def test_velocity_just_above_min_speed_returns_velocity_min(self):
        """Speed just above threshold returns approximately velocity_min."""
        cfg = StickOnsetConfig(
            enabled=True,
            min_speed=1.0,
            min_acceleration=1.0,
            velocity_scale=10.0,
            velocity_min=30,
            velocity_max=127,
        )
        d = StickOnsetDetector(cfg)
        # speed=1.1 * scale=10 = 11, clamped to velocity_min=30
        result = d.feed(speed=1.1, acceleration=5.0, now_s=0.0)
        assert result == 30


class TestStickOnsetCooldown:
    """Tests for cooldown (refire suppression)."""

    def test_second_onset_within_cooldown_suppressed(self):
        """Second onset within cooldown window returns None."""
        cfg = StickOnsetConfig(
            enabled=True,
            min_speed=1.0,
            min_acceleration=1.0,
            cooldown_ms=100,
            velocity_scale=50.0,
        )
        d = StickOnsetDetector(cfg)
        vel1 = d.feed(speed=2.0, acceleration=5.0, now_s=0.0)
        assert vel1 is not None

        # 0.05 seconds = 50 ms, within 100 ms cooldown
        vel2 = d.feed(speed=2.0, acceleration=5.0, now_s=0.05)
        assert vel2 is None

    def test_second_onset_after_cooldown_fires(self):
        """Second onset after cooldown window fires normally."""
        cfg = StickOnsetConfig(
            enabled=True,
            min_speed=1.0,
            min_acceleration=1.0,
            cooldown_ms=80,
            velocity_scale=50.0,
        )
        d = StickOnsetDetector(cfg)
        vel1 = d.feed(speed=2.0, acceleration=5.0, now_s=0.0)
        assert vel1 is not None

        # 0.1 seconds = 100 ms, after 80 ms cooldown
        vel2 = d.feed(speed=2.0, acceleration=5.0, now_s=0.1)
        assert vel2 is not None

    def test_exactly_at_cooldown_boundary_fires(self):
        """Onset exactly at cooldown boundary (>= after) should fire."""
        cfg = StickOnsetConfig(
            enabled=True,
            min_speed=1.0,
            min_acceleration=1.0,
            cooldown_ms=100,
            velocity_scale=50.0,
        )
        d = StickOnsetDetector(cfg)
        vel1 = d.feed(speed=2.0, acceleration=5.0, now_s=0.0)
        assert vel1 is not None

        # Exactly 0.1 seconds = 100 ms
        vel2 = d.feed(speed=2.0, acceleration=5.0, now_s=0.1)
        assert vel2 is not None


class TestStickOnsetReset:
    """Tests for reset functionality."""

    def test_reset_clears_last_onset_timestamp(self):
        """After reset, next onset fires immediately (no cooldown suppression)."""
        cfg = StickOnsetConfig(
            enabled=True,
            min_speed=1.0,
            min_acceleration=1.0,
            cooldown_ms=100,
            velocity_scale=50.0,
        )
        d = StickOnsetDetector(cfg)

        # Fire first onset
        vel1 = d.feed(speed=2.0, acceleration=5.0, now_s=0.0)
        assert vel1 is not None

        # Within cooldown (suppressed)
        vel2 = d.feed(speed=2.0, acceleration=5.0, now_s=0.05)
        assert vel2 is None

        # Reset
        d.reset()

        # Now fires immediately (cooldown cleared)
        vel3 = d.feed(speed=2.0, acceleration=5.0, now_s=0.05)
        assert vel3 is not None

    def test_reset_clears_last_speed(self):
        """After reset, _last_speed is cleared to 0."""
        cfg = StickOnsetConfig(enabled=True)
        d = StickOnsetDetector(cfg)
        d.feed(speed=5.0, acceleration=10.0, now_s=0.0)
        assert d._last_speed == 5.0
        d.reset()
        assert d._last_speed == 0.0


class TestStickOnsetIntegration:
    """Integration tests: multiple onsets with varied scenarios."""

    def test_full_cycle_speed_accel_cooldown_reset(self):
        """Full cycle: onset → cooldown → reset → onset."""
        cfg = StickOnsetConfig(
            enabled=True,
            min_speed=1.0,
            min_acceleration=1.0,
            cooldown_ms=50,
            velocity_scale=50.0,
        )
        d = StickOnsetDetector(cfg)

        # First onset fires
        vel1 = d.feed(speed=2.0, acceleration=5.0, now_s=0.0)
        assert vel1 == 100  # 2.0 * 50 = 100

        # Within cooldown (suppressed)
        vel2 = d.feed(speed=2.0, acceleration=5.0, now_s=0.02)
        assert vel2 is None

        # After cooldown (fires)
        vel3 = d.feed(speed=2.0, acceleration=5.0, now_s=0.1)
        assert vel3 == 100

        # Reset
        d.reset()

        # Fires immediately after reset (no cooldown)
        vel4 = d.feed(speed=2.0, acceleration=5.0, now_s=0.1)
        assert vel4 == 100

    def test_verify_command_example(self):
        """Test the example from the verify command."""
        cfg = StickOnsetConfig(
            enabled=True,
            min_speed=1,
            min_acceleration=1,
            cooldown_ms=50,
            velocity_scale=50,
        )
        d = StickOnsetDetector(cfg)

        # First call: expect 100 (2.0 * 50)
        vel1 = d.feed(speed=2, acceleration=5, now_s=0.0)
        assert vel1 == 100

        # Second call at 0.02s (20ms): within 50ms cooldown, expect None
        vel2 = d.feed(speed=2, acceleration=5, now_s=0.02)
        assert vel2 is None

        # Third call at 0.1s (100ms): after 50ms cooldown, expect 100
        vel3 = d.feed(speed=2, acceleration=5, now_s=0.1)
        assert vel3 == 100

    def test_multiple_fast_strikes_with_proper_spacing(self):
        """Multiple strikes properly spaced fire correctly."""
        cfg = StickOnsetConfig(
            enabled=True,
            min_speed=1.0,
            min_acceleration=1.0,
            cooldown_ms=100,
            velocity_scale=40.0,
        )
        d = StickOnsetDetector(cfg)

        times = [0.0, 0.15, 0.30, 0.45, 0.60]
        results = []

        for t in times:
            vel = d.feed(speed=3.0, acceleration=8.0, now_s=t)
            results.append(vel)

        # All should fire because each is 150ms apart (> 100ms cooldown)
        assert all(v is not None for v in results)
        assert all(v == 120 for v in results)  # 3.0 * 40 = 120
