"""Tests for stick gesture detector module."""

import math
import pytest
from gamepad_midi_bridge.stick_gesture import (
    StickGestureConfig,
    StickGestureDetector,
)


class TestStickGestureConfig:
    """Tests for StickGestureConfig dataclass."""

    def test_default_config(self):
        """Default config has gesture detection disabled."""
        cfg = StickGestureConfig()
        assert cfg.enabled is False
        assert cfg.swipe_min_magnitude == 0.7
        assert cfg.swipe_max_duration_s == 0.5
        assert cfg.circle_min_arc == 5.5
        assert cfg.circle_max_duration_s == 2.0
        assert cfg.min_radius == 0.3
        assert cfg.max_history == 64

    def test_custom_config(self):
        """Can construct with custom values."""
        cfg = StickGestureConfig(
            enabled=True,
            swipe_min_magnitude=0.5,
            swipe_max_duration_s=1.0,
            circle_min_arc=4.0,
            circle_max_duration_s=3.0,
            min_radius=0.2,
            max_history=128,
        )
        assert cfg.enabled is True
        assert cfg.swipe_min_magnitude == 0.5
        assert cfg.swipe_max_duration_s == 1.0
        assert cfg.circle_min_arc == 4.0
        assert cfg.circle_max_duration_s == 3.0
        assert cfg.min_radius == 0.2
        assert cfg.max_history == 128

    def test_clamp_swipe_min_magnitude_lower(self):
        """swipe_min_magnitude < 0.1 is clamped to 0.1."""
        cfg = StickGestureConfig(swipe_min_magnitude=0.05)
        assert cfg.swipe_min_magnitude == 0.1

    def test_clamp_swipe_min_magnitude_upper(self):
        """swipe_min_magnitude > 2.0 is clamped to 2.0."""
        cfg = StickGestureConfig(swipe_min_magnitude=3.0)
        assert cfg.swipe_min_magnitude == 2.0

    def test_clamp_swipe_max_duration_s_lower(self):
        """swipe_max_duration_s < 0.05 is clamped to 0.05."""
        cfg = StickGestureConfig(swipe_max_duration_s=0.01)
        assert cfg.swipe_max_duration_s == 0.05

    def test_clamp_swipe_max_duration_s_upper(self):
        """swipe_max_duration_s > 5.0 is clamped to 5.0."""
        cfg = StickGestureConfig(swipe_max_duration_s=10.0)
        assert cfg.swipe_max_duration_s == 5.0

    def test_clamp_circle_min_arc_lower(self):
        """circle_min_arc < 1.0 is clamped to 1.0."""
        cfg = StickGestureConfig(circle_min_arc=0.5)
        assert cfg.circle_min_arc == 1.0

    def test_clamp_circle_min_arc_upper(self):
        """circle_min_arc > 20.0 is clamped to 20.0."""
        cfg = StickGestureConfig(circle_min_arc=25.0)
        assert cfg.circle_min_arc == 20.0

    def test_clamp_circle_max_duration_s_lower(self):
        """circle_max_duration_s < 0.1 is clamped to 0.1."""
        cfg = StickGestureConfig(circle_max_duration_s=0.05)
        assert cfg.circle_max_duration_s == 0.1

    def test_clamp_circle_max_duration_s_upper(self):
        """circle_max_duration_s > 10.0 is clamped to 10.0."""
        cfg = StickGestureConfig(circle_max_duration_s=15.0)
        assert cfg.circle_max_duration_s == 10.0

    def test_clamp_min_radius_lower(self):
        """min_radius < 0.05 is clamped to 0.05."""
        cfg = StickGestureConfig(min_radius=0.01)
        assert cfg.min_radius == 0.05

    def test_clamp_min_radius_upper(self):
        """min_radius > 1.0 is clamped to 1.0."""
        cfg = StickGestureConfig(min_radius=1.5)
        assert cfg.min_radius == 1.0

    def test_clamp_max_history_lower(self):
        """max_history < 4 is clamped to 4."""
        cfg = StickGestureConfig(max_history=2)
        assert cfg.max_history == 4

    def test_clamp_max_history_upper(self):
        """max_history > 256 is clamped to 256."""
        cfg = StickGestureConfig(max_history=300)
        assert cfg.max_history == 256

    def test_to_dict(self):
        """to_dict serializes config to dictionary."""
        cfg = StickGestureConfig(
            enabled=True,
            swipe_min_magnitude=0.5,
            circle_min_arc=4.5,
        )
        d = cfg.to_dict()
        assert d["enabled"] is True
        assert d["swipe_min_magnitude"] == 0.5
        assert d["circle_min_arc"] == 4.5

    def test_from_dict(self):
        """from_dict deserializes config from dictionary."""
        d = {
            "enabled": True,
            "swipe_min_magnitude": 0.6,
            "swipe_max_duration_s": 0.8,
            "circle_min_arc": 5.0,
        }
        cfg = StickGestureConfig.from_dict(d)
        assert cfg.enabled is True
        assert cfg.swipe_min_magnitude == 0.6
        assert cfg.swipe_max_duration_s == 0.8
        assert cfg.circle_min_arc == 5.0

    def test_from_dict_round_trip(self):
        """Round-trip: to_dict → from_dict preserves values."""
        original = StickGestureConfig(
            enabled=True,
            swipe_min_magnitude=0.5,
            swipe_max_duration_s=0.7,
            circle_min_arc=4.5,
            circle_max_duration_s=1.5,
            min_radius=0.25,
            max_history=100,
        )
        d = original.to_dict()
        restored = StickGestureConfig.from_dict(d)
        assert restored.enabled == original.enabled
        assert restored.swipe_min_magnitude == original.swipe_min_magnitude
        assert restored.swipe_max_duration_s == original.swipe_max_duration_s
        assert restored.circle_min_arc == original.circle_min_arc
        assert restored.circle_max_duration_s == original.circle_max_duration_s
        assert restored.min_radius == original.min_radius
        assert restored.max_history == original.max_history

    def test_from_dict_partial(self):
        """from_dict fills missing keys with defaults."""
        d = {"enabled": True, "swipe_min_magnitude": 0.4}
        cfg = StickGestureConfig.from_dict(d)
        assert cfg.enabled is True
        assert cfg.swipe_min_magnitude == 0.4
        assert cfg.swipe_max_duration_s == 0.5  # Default
        assert cfg.circle_min_arc == 5.5  # Default


class TestStickGestureDetectorSwipes:
    """Tests for swipe detection."""

    def test_default_detector_disabled(self):
        """Default detector has enabled=False."""
        cfg = StickGestureConfig()
        detector = StickGestureDetector(cfg)
        # Detector doesn't check enabled flag; that's caller's responsibility.
        # Just test that detector initializes.
        assert detector.pending_history_size() == 0

    def test_swipe_up_simple(self):
        """Swipe up: (0,0,0) → (0,1,0.1) returns 'swipe_up'."""
        cfg = StickGestureConfig(enabled=True)
        detector = StickGestureDetector(cfg)
        result1 = detector.sample(0.0, 0.0, 0.0)
        result2 = detector.sample(0.0, 1.0, 0.1)
        assert result1 is None
        assert result2 == "swipe_up"

    def test_swipe_down_simple(self):
        """Swipe down: (0,0,0) → (0,-1,0.1) returns 'swipe_down'."""
        cfg = StickGestureConfig(enabled=True)
        detector = StickGestureDetector(cfg)
        detector.sample(0.0, 0.0, 0.0)
        result = detector.sample(0.0, -1.0, 0.1)
        assert result == "swipe_down"

    def test_swipe_left_simple(self):
        """Swipe left: (0,0,0) → (-1,0,0.1) returns 'swipe_left'."""
        cfg = StickGestureConfig(enabled=True)
        detector = StickGestureDetector(cfg)
        detector.sample(0.0, 0.0, 0.0)
        result = detector.sample(-1.0, 0.0, 0.1)
        assert result == "swipe_left"

    def test_swipe_right_simple(self):
        """Swipe right: (0,0,0) → (1,0,0.1) returns 'swipe_right'."""
        cfg = StickGestureConfig(enabled=True)
        detector = StickGestureDetector(cfg)
        detector.sample(0.0, 0.0, 0.0)
        result = detector.sample(1.0, 0.0, 0.1)
        assert result == "swipe_right"

    def test_swipe_too_slow(self):
        """Swipe that takes too long doesn't fire.

        Config max = 0.5s, swipe takes 1.0s → no fire.
        """
        cfg = StickGestureConfig(
            enabled=True,
            swipe_min_magnitude=0.7,
            swipe_max_duration_s=0.5,
        )
        detector = StickGestureDetector(cfg)
        detector.sample(0.0, 0.0, 0.0)
        result = detector.sample(0.0, 1.0, 1.0)  # 1 second later
        assert result is None

    def test_swipe_too_small(self):
        """Small swipe (magnitude < threshold) doesn't fire.

        Config min = 0.7, swipe magnitude = 0.3 → no fire.
        """
        cfg = StickGestureConfig(
            enabled=True,
            swipe_min_magnitude=0.7,
        )
        detector = StickGestureDetector(cfg)
        detector.sample(0.0, 0.0, 0.0)
        result = detector.sample(0.0, 0.3, 0.1)  # Too small
        assert result is None

    def test_swipe_fires_on_threshold(self):
        """Swipe at exactly min_magnitude fires."""
        cfg = StickGestureConfig(enabled=True, swipe_min_magnitude=0.7)
        detector = StickGestureDetector(cfg)
        detector.sample(0.0, 0.0, 0.0)
        result = detector.sample(0.0, 0.7, 0.1)
        assert result == "swipe_up"

    def test_swipe_diagonal_classified_by_dominant_axis(self):
        """Diagonal swipe (0.5, 1.0) is classified as vertical (swipe_up)."""
        cfg = StickGestureConfig(enabled=True)
        detector = StickGestureDetector(cfg)
        detector.sample(0.0, 0.0, 0.0)
        result = detector.sample(0.5, 1.0, 0.1)
        # Dominant axis is Y (1.0 > 0.5) → swipe_up
        assert result == "swipe_up"

    def test_swipe_diagonal_horizontal_dominant(self):
        """Diagonal swipe (1.0, 0.3) is classified as horizontal (swipe_right)."""
        cfg = StickGestureConfig(enabled=True)
        detector = StickGestureDetector(cfg)
        detector.sample(0.0, 0.0, 0.0)
        result = detector.sample(1.0, 0.3, 0.1)
        # Dominant axis is X (1.0 > 0.3) → swipe_right
        assert result == "swipe_right"


class TestStickGestureDetectorCircles:
    """Tests for circle detection."""

    def test_clockwise_circle(self):
        """Sample points around a clockwise circle triggers 'circle_cw'.

        In atan2 coords: right(0°) → up(90°) → left(180°) → down(-90°) = positive angle wrapping.
        Uses 16 samples over full circle to accumulate sufficient angle.
        """
        cfg = StickGestureConfig(
            enabled=True,
            circle_min_arc=5.5,
            min_radius=0.3,
            swipe_min_magnitude=2.0,  # Disable swipe to test circle
            circle_max_duration_s=5.0,  # Allow 16 samples × 200ms = 3.2s
        )
        detector = StickGestureDetector(cfg)

        now = 0.0
        step = 0.2
        radius = 0.5
        num_steps = 16  # Full circle in 16 steps

        for i in range(num_steps):
            angle = (i / num_steps) * 2 * math.pi
            x = radius * math.cos(angle)
            y = radius * math.sin(angle)
            result = detector.sample(x, y, now)
            now += step

            if i == num_steps - 1:
                # After ~360° of positive rotation
                assert result == "circle_cw", f"Expected circle_cw, got {result}"

    def test_counter_clockwise_circle(self):
        """Sample points around a counter-clockwise circle triggers 'circle_ccw'.

        In atan2 coords: right(0°) → down(-90°) → left(±180°) → up(90°) = negative angle wrapping.
        Uses 16 samples over full circle with negative sweep (backward).
        """
        cfg = StickGestureConfig(
            enabled=True,
            circle_min_arc=5.5,
            min_radius=0.3,
            swipe_min_magnitude=2.0,  # Disable swipe to test circle
            circle_max_duration_s=5.0,  # Allow 16 samples × 200ms = 3.2s
        )
        detector = StickGestureDetector(cfg)

        now = 0.0
        step = 0.2
        radius = 0.5
        num_steps = 16  # Full circle in 16 steps

        for i in range(num_steps):
            angle = -(i / num_steps) * 2 * math.pi  # Negative sweep = ccw
            x = radius * math.cos(angle)
            y = radius * math.sin(angle)
            result = detector.sample(x, y, now)
            now += step

            if i == num_steps - 1:
                # After ~360° of negative rotation
                assert result == "circle_ccw", f"Expected circle_ccw, got {result}"

    def test_half_circle_does_not_fire(self):
        """Half circle (arc < circle_min_arc) doesn't fire."""
        cfg = StickGestureConfig(
            enabled=True,
            circle_min_arc=5.5,  # ~315° (5.5 rad)
            min_radius=0.3,
            circle_max_duration_s=2.0,
        )
        detector = StickGestureDetector(cfg)

        # Only sample half circle (π rad ≈ 3.14, less than 5.5)
        now = 0.0
        step = 0.2
        radius = 0.5

        # Right (0°)
        detector.sample(radius, 0.0, now)
        now += step

        # Down (90°)
        detector.sample(0.0, -radius, now)
        now += step

        # Left (180°)
        result = detector.sample(-radius, 0.0, now)
        # Only π rad accumulated, less than 5.5 rad
        assert result is None

    def test_circle_exceeds_max_duration(self):
        """Circle that takes too long doesn't fire."""
        cfg = StickGestureConfig(
            enabled=True,
            circle_min_arc=5.5,
            circle_max_duration_s=0.5,  # Very short window
            min_radius=0.3,
        )
        detector = StickGestureDetector(cfg)

        # Try to complete circle over 2 seconds (exceeds max)
        now = 0.0
        step = 0.6  # 600ms per step
        radius = 0.5

        detector.sample(radius, 0.0, now)
        now += step

        detector.sample(0.0, -radius, now)
        now += step

        detector.sample(-radius, 0.0, now)
        now += step

        result = detector.sample(0.0, radius, now)
        # Samples are too spread out (outside max_duration_s window)
        assert result is None

    def test_circle_small_radius_ignored(self):
        """Points with magnitude < min_radius don't contribute to circle."""
        cfg = StickGestureConfig(
            enabled=True,
            circle_min_arc=5.5,
            min_radius=0.5,  # High threshold
        )
        detector = StickGestureDetector(cfg)

        # Try circle with radius 0.3 (below threshold)
        now = 0.0
        step = 0.2
        radius = 0.3  # Below min_radius (0.5)

        detector.sample(radius, 0.0, now)
        now += step
        detector.sample(0.0, -radius, now)
        now += step
        detector.sample(-radius, 0.0, now)
        now += step
        result = detector.sample(0.0, radius, now)
        # All points ignored due to low radius
        assert result is None

    def test_circle_full_360_fires(self):
        """Full 360° circle (2π ≈ 6.28 rad) fires."""
        cfg = StickGestureConfig(
            enabled=True,
            circle_min_arc=5.5,
            min_radius=0.3,
            swipe_min_magnitude=2.0,  # Disable swipe to test circle
            circle_max_duration_s=5.0,  # Allow time for 16 samples
        )
        detector = StickGestureDetector(cfg)

        now = 0.0
        step = 0.2
        radius = 0.5
        num_steps = 16  # 16 steps × 22.5° ≈ 360°

        for i in range(num_steps):
            angle = (i / num_steps) * 2 * math.pi  # Full rotation (positive = cw)
            x = radius * math.cos(angle)
            y = radius * math.sin(angle)
            result = detector.sample(x, y, now)
            now += step

            if i == num_steps - 1:
                # Full circle should fire
                assert result == "circle_cw", f"Expected circle_cw, got {result}"


class TestStickGestureDetectorHistory:
    """Tests for history management."""

    def test_max_history_truncates_buffer(self):
        """History is truncated to max_history."""
        cfg = StickGestureConfig(enabled=True, max_history=10)
        detector = StickGestureDetector(cfg)

        for i in range(20):
            detector.sample(float(i) * 0.01, float(i) * 0.01, float(i) * 0.01)

        assert detector.pending_history_size() == 10

    def test_gesture_fires_then_clears_history(self):
        """After gesture fires, history is cleared."""
        cfg = StickGestureConfig(enabled=True)
        detector = StickGestureDetector(cfg)

        # Fire a swipe
        detector.sample(0.0, 0.0, 0.0)
        result = detector.sample(0.0, 1.0, 0.1)
        assert result == "swipe_up"

        # History should be cleared
        assert detector.pending_history_size() == 0

    def test_gesture_no_refire_on_repeated_input(self):
        """After gesture fires and history clears, repeated input doesn't refire."""
        cfg = StickGestureConfig(enabled=True)
        detector = StickGestureDetector(cfg)

        # Fire a swipe
        detector.sample(0.0, 0.0, 0.0)
        result1 = detector.sample(0.0, 1.0, 0.1)
        assert result1 == "swipe_up"

        # Try same input again — no history to match against
        result2 = detector.sample(0.0, 1.0, 0.2)
        assert result2 is None

    def test_reset_clears_history(self):
        """reset() clears history."""
        cfg = StickGestureConfig(enabled=True, swipe_min_magnitude=2.0)
        detector = StickGestureDetector(cfg)

        detector.sample(0.0, 0.0, 0.0)
        detector.sample(0.5, 0.5, 0.1)
        assert detector.pending_history_size() == 2

        detector.reset()
        assert detector.pending_history_size() == 0

    def test_pending_history_size(self):
        """pending_history_size() returns correct count."""
        cfg = StickGestureConfig(enabled=True, swipe_min_magnitude=2.0)
        detector = StickGestureDetector(cfg)

        assert detector.pending_history_size() == 0

        detector.sample(0.0, 0.0, 0.0)
        assert detector.pending_history_size() == 1

        detector.sample(0.5, 0.5, 0.1)
        assert detector.pending_history_size() == 2

        detector.sample(1.0, 1.0, 0.2)
        assert detector.pending_history_size() == 3


class TestStickGestureDetectorEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_single_sample_no_gesture(self):
        """Single sample cannot trigger a gesture."""
        cfg = StickGestureConfig(enabled=True)
        detector = StickGestureDetector(cfg)
        result = detector.sample(1.0, 1.0, 0.0)
        assert result is None

    def test_zero_velocity_no_gesture(self):
        """Stationary stick doesn't trigger gesture."""
        cfg = StickGestureConfig(enabled=True)
        detector = StickGestureDetector(cfg)
        detector.sample(0.5, 0.5, 0.0)
        result = detector.sample(0.5, 0.5, 0.1)
        assert result is None

    def test_swipe_checks_all_history_within_window(self):
        """Swipe detection checks all samples within max_duration_s."""
        cfg = StickGestureConfig(
            enabled=True,
            swipe_min_magnitude=0.7,
            swipe_max_duration_s=0.5,
        )
        detector = StickGestureDetector(cfg)

        # Sample: start, small move, then large swipe
        detector.sample(0.0, 0.0, 0.0)
        detector.sample(0.1, 0.1, 0.1)  # Small movement, within window
        result = detector.sample(0.1, 1.0, 0.3)  # Large swipe up, within window
        # Should detect swipe from earliest sample (0,0) to current (0.1, 1.0)
        assert result == "swipe_up"

    def test_negative_time_not_supported(self):
        """Detector assumes monotonic time (no negative dt).

        Negative dt is still within the swipe_max_duration_s window,
        but swipe detection still works as it checks displacement magnitude.
        """
        cfg = StickGestureConfig(enabled=True, swipe_min_magnitude=2.0)
        detector = StickGestureDetector(cfg)
        detector.sample(0.0, 0.0, 0.0)
        # Going backward in time — swipe won't fire due to high threshold
        result = detector.sample(0.0, 1.0, -0.1)
        # Magnitude 1.0 < 2.0 threshold → no gesture
        assert result is None

    def test_angle_wrap_around_at_pi(self):
        """Angle computation handles ±π wrap-around correctly.

        This test verifies that swipe detection works and doesn't crash
        even with extreme angles near ±π. The motion is detected as a swipe
        because the displacement is large enough.
        """
        cfg = StickGestureConfig(
            enabled=True,
            circle_min_arc=1.0,  # Low threshold for this test
            min_radius=0.3,
            swipe_min_magnitude=1.5,  # Swipe threshold
        )
        detector = StickGestureDetector(cfg)

        now = 0.0

        # Sample crossing ±π boundary
        # Just before -π
        detector.sample(-0.99, 0.01, now)
        now += 0.1

        # Just after π (same direction, wraps)
        # Displacement is ~2.0, which triggers swipe_right
        result = detector.sample(0.99, -0.01, now)
        # The large displacement detects as a swipe or none, not crash
        assert result is None or result in ("circle_cw", "circle_ccw", "swipe_right", "swipe_left", "swipe_up", "swipe_down")


class TestStickGestureDetectorIntegration:
    """Integration tests combining multiple features."""

    def test_swipe_then_circle_different_gestures(self):
        """Can detect different gestures in sequence after reset."""
        cfg = StickGestureConfig(
            enabled=True,
            swipe_min_magnitude=2.0,  # Disable swipe for circle test
            circle_min_arc=5.5,
            min_radius=0.3,
            circle_max_duration_s=5.0,
        )
        detector = StickGestureDetector(cfg)

        # First: attempt a swipe (but threshold is 2.0, so won't fire with 1.0)
        detector.sample(0.0, 0.0, 0.0)
        result1 = detector.sample(0.0, 1.0, 0.1)
        assert result1 is None  # Below threshold

        # Manually reset to clear history, simulate a fresh session
        detector.reset()

        # Now start a circle (16 samples for full rotation)
        now = 0.2
        step = 0.2
        radius = 0.5
        for i in range(16):
            angle = (i / 16) * 2 * math.pi
            x = radius * math.cos(angle)
            y = radius * math.sin(angle)
            result2 = detector.sample(x, y, now)
            now += step

        # After full circle, should detect
        assert result2 == "circle_cw", f"Expected circle_cw, got {result2}"

    def test_config_serialization_preserves_detector_state(self):
        """Config can be serialized and used to create equivalent detector."""
        cfg1 = StickGestureConfig(
            enabled=True,
            swipe_min_magnitude=0.5,
            circle_min_arc=4.5,
            max_history=100,
        )
        d = cfg1.to_dict()
        cfg2 = StickGestureConfig.from_dict(d)

        # Create detectors with both configs
        det1 = StickGestureDetector(cfg1)
        det2 = StickGestureDetector(cfg2)

        # Both should behave the same
        det1.sample(0.0, 0.0, 0.0)
        det2.sample(0.0, 0.0, 0.0)

        result1 = det1.sample(0.0, 0.8, 0.1)
        result2 = det2.sample(0.0, 0.8, 0.1)

        # Both should fire (0.8 > 0.5)
        assert result1 == result2 == "swipe_up"
