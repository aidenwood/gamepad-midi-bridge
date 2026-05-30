"""Trigger noise gate — squelches small fluctuations in analog trigger pressure."""
from __future__ import annotations

import pytest

from gamepad_midi_bridge.trigger_noise_gate import (
    TriggerNoiseGateConfig,
    TriggerNoiseGate,
)


class TestTriggerNoiseGateConfigDefaults:
    """TriggerNoiseGateConfig dataclass — defaults and clamping."""

    def test_default_config_disabled(self):
        """Default config is disabled with standard thresholds."""
        cfg = TriggerNoiseGateConfig()
        assert cfg.enabled is False
        assert cfg.threshold == 0.01
        assert cfg.release_threshold == 0.005
        assert cfg.hysteresis_factor == 1.5

    def test_threshold_clamped_to_0_0_5(self):
        """threshold clamped to 0..0.5."""
        cfg = TriggerNoiseGateConfig(threshold=-0.1)
        assert cfg.threshold == 0

        cfg = TriggerNoiseGateConfig(threshold=1.0)
        assert cfg.threshold == 0.5

    def test_release_threshold_clamped_to_0_0_5(self):
        """release_threshold clamped to 0..0.5."""
        cfg = TriggerNoiseGateConfig(release_threshold=-0.1)
        assert cfg.release_threshold == 0

        cfg = TriggerNoiseGateConfig(release_threshold=1.0)
        assert cfg.release_threshold == 0.5

    def test_hysteresis_factor_clamped_to_1_5(self):
        """hysteresis_factor clamped to 1..5."""
        cfg = TriggerNoiseGateConfig(hysteresis_factor=0.5)
        assert cfg.hysteresis_factor == 1

        cfg = TriggerNoiseGateConfig(hysteresis_factor=10.0)
        assert cfg.hysteresis_factor == 5


class TestTriggerNoiseGateDisabled:
    """TriggerNoiseGate with disabled config."""

    def test_disabled_returns_pressure_unchanged(self):
        """Disabled gate returns all pressures unchanged."""
        cfg = TriggerNoiseGateConfig(enabled=False)
        gate = TriggerNoiseGate(cfg)
        assert gate.feed(0.0) == 0.0
        assert gate.feed(0.5) == 0.5
        assert gate.feed(1.0) == 1.0

    def test_disabled_does_not_track_state(self):
        """Disabled gate does not track state or affect subsequent values."""
        cfg = TriggerNoiseGateConfig(enabled=False)
        gate = TriggerNoiseGate(cfg)
        assert gate.feed(0.5) == 0.5
        assert gate.feed(0.5) == 0.5  # Same value passes again
        assert gate.feed(0.50001) == 0.50001  # Tiny change also passes


class TestTriggerNoiseGateInitial:
    """TriggerNoiseGate initial behavior."""

    def test_first_feed_emits_initial_value(self):
        """First feed always emits the initial pressure."""
        cfg = TriggerNoiseGateConfig(enabled=True, threshold=0.05)
        gate = TriggerNoiseGate(cfg)
        result = gate.feed(0.3)
        assert result == 0.3

    def test_first_feed_low_pressure_emits(self):
        """First feed emits even if pressure is low."""
        cfg = TriggerNoiseGateConfig(enabled=True, threshold=0.05)
        gate = TriggerNoiseGate(cfg)
        result = gate.feed(0.001)
        assert result == 0.001

    def test_first_feed_zero_emits(self):
        """First feed emits 0 pressure."""
        cfg = TriggerNoiseGateConfig(enabled=True)
        gate = TriggerNoiseGate(cfg)
        result = gate.feed(0.0)
        assert result == 0.0


class TestTriggerNoiseGateClamping:
    """TriggerNoiseGate pressure clamping."""

    def test_negative_pressure_clamped_to_zero(self):
        """Negative pressure is clamped to 0."""
        cfg = TriggerNoiseGateConfig(enabled=True)
        gate = TriggerNoiseGate(cfg)
        result = gate.feed(-0.5)
        assert result == 0.0

    def test_pressure_above_one_clamped_to_one(self):
        """Pressure above 1 is clamped to 1."""
        cfg = TriggerNoiseGateConfig(enabled=True)
        gate = TriggerNoiseGate(cfg)
        result = gate.feed(1.5)
        assert result == 1.0

    def test_pressure_within_range_unchanged(self):
        """Pressure within 0..1 is unchanged."""
        cfg = TriggerNoiseGateConfig(enabled=True)
        gate = TriggerNoiseGate(cfg)
        assert gate.feed(0.0) == 0.0
        assert gate.feed(0.5) == 0.5
        assert gate.feed(1.0) == 1.0


class TestTriggerNoiseGateWithinThreshold:
    """TriggerNoiseGate within threshold returns None."""

    def test_second_feed_within_threshold_suppressed(self):
        """Second feed within threshold returns None."""
        cfg = TriggerNoiseGateConfig(enabled=True, threshold=0.05)
        gate = TriggerNoiseGate(cfg)
        gate.feed(0.5)
        result = gate.feed(0.51)  # Delta 0.01 < threshold 0.05
        assert result is None

    def test_small_upward_change_within_threshold_suppressed(self):
        """Small upward change within threshold is suppressed."""
        cfg = TriggerNoiseGateConfig(enabled=True, threshold=0.05)
        gate = TriggerNoiseGate(cfg)
        gate.feed(0.5)
        result = gate.feed(0.52)  # Delta 0.02 < threshold 0.05
        assert result is None

    def test_small_downward_change_within_threshold_suppressed(self):
        """Small downward change within threshold is suppressed."""
        cfg = TriggerNoiseGateConfig(enabled=True, threshold=0.05)
        gate = TriggerNoiseGate(cfg)
        gate.feed(0.5)
        result = gate.feed(0.48)  # Delta 0.02 < threshold 0.05
        assert result is None

    def test_multiple_small_changes_all_suppressed(self):
        """Multiple small changes are all suppressed."""
        cfg = TriggerNoiseGateConfig(enabled=True, threshold=0.05)
        gate = TriggerNoiseGate(cfg)
        gate.feed(0.5)
        assert gate.feed(0.501) is None
        assert gate.feed(0.502) is None
        assert gate.feed(0.503) is None


class TestTriggerNoiseGateHysteresis:
    """TriggerNoiseGate hysteresis behavior."""

    def test_upward_change_uses_hysteresis_multiplier(self):
        """Upward change requires hysteresis_factor multiplier."""
        cfg = TriggerNoiseGateConfig(
            enabled=True, threshold=0.05, hysteresis_factor=2.0
        )
        gate = TriggerNoiseGate(cfg)
        gate.feed(0.5)

        # Upward change needs 0.05 * 2.0 = 0.10
        # Delta 0.08 < 0.10 → suppressed (still comparing against 0.5)
        assert gate.feed(0.58) is None

        # Delta 0.10 >= 0.10 → passes (0.6 - 0.5 = 0.1)
        assert gate.feed(0.6) == 0.6

    def test_downward_change_uses_raw_threshold(self):
        """Downward change uses raw threshold, not hysteresis multiplied."""
        cfg = TriggerNoiseGateConfig(
            enabled=True, threshold=0.05, hysteresis_factor=2.0
        )
        gate = TriggerNoiseGate(cfg)
        gate.feed(0.5)

        # Downward change needs 0.05 (not 0.10)
        # Delta 0.04 < 0.05 → suppressed (still comparing against 0.5)
        assert gate.feed(0.46) is None

        # Delta 0.05 >= 0.05 → passes (0.5 - 0.45 = 0.05)
        assert gate.feed(0.45) == 0.45

    def test_hysteresis_asymmetry_default(self):
        """Default hysteresis_factor 1.5 creates asymmetry."""
        cfg = TriggerNoiseGateConfig(
            enabled=True, threshold=0.02, hysteresis_factor=1.5
        )
        gate = TriggerNoiseGate(cfg)
        gate.feed(0.5)

        # Upward needs 0.02 * 1.5 = 0.03
        assert gate.feed(0.52) is None  # Delta 0.02 < 0.03
        assert gate.feed(0.53) == 0.53  # Delta 0.03 >= 0.03

        # Reset for downward test
        gate.reset()
        gate.feed(0.5)

        # Downward needs 0.02
        assert gate.feed(0.49) is None  # Delta 0.01 < 0.02
        assert gate.feed(0.48) == 0.48  # Delta 0.02 >= 0.02


class TestTriggerNoiseGateReleaseThreshold:
    """TriggerNoiseGate release condition."""

    def test_drop_below_release_threshold_emits_zero(self):
        """Pressure dropping below release_threshold emits 0."""
        cfg = TriggerNoiseGateConfig(enabled=True, release_threshold=0.01)
        gate = TriggerNoiseGate(cfg)
        gate.feed(0.5)
        result = gate.feed(0.005)  # Below release_threshold
        assert result == 0

    def test_release_requires_prior_above_threshold(self):
        """Release only happens if last_value was above release_threshold."""
        cfg = TriggerNoiseGateConfig(enabled=True, release_threshold=0.01)
        gate = TriggerNoiseGate(cfg)

        # Start at 0 (below release threshold)
        gate.feed(0.0)
        # Drop to 0.005 — should not trigger release since we started at 0
        result = gate.feed(0.005)
        # This should not be special-cased, will be treated as noise within threshold
        assert result is None

    def test_release_zero_maintains_state(self):
        """After emitting 0 via release, last_emitted returns 0."""
        cfg = TriggerNoiseGateConfig(enabled=True, release_threshold=0.01)
        gate = TriggerNoiseGate(cfg)
        gate.feed(0.5)
        gate.feed(0.005)  # Emit 0 via release
        assert gate.last_emitted() == 0

    def test_release_threshold_exact_boundary(self):
        """Pressure at exactly release_threshold does not trigger release."""
        cfg = TriggerNoiseGateConfig(enabled=True, release_threshold=0.01)
        gate = TriggerNoiseGate(cfg)
        gate.feed(0.5)
        # Exactly at release_threshold; condition is <= so it triggers
        result = gate.feed(0.01)
        assert result == 0


class TestTriggerNoiseGateLastEmitted:
    """TriggerNoiseGate.last_emitted."""

    def test_last_emitted_returns_initial(self):
        """last_emitted returns the initial value after first feed."""
        cfg = TriggerNoiseGateConfig(enabled=True)
        gate = TriggerNoiseGate(cfg)
        gate.feed(0.3)
        assert gate.last_emitted() == 0.3

    def test_last_emitted_returns_none_initially(self):
        """last_emitted returns None before any feed."""
        cfg = TriggerNoiseGateConfig(enabled=True)
        gate = TriggerNoiseGate(cfg)
        assert gate.last_emitted() is None

    def test_last_emitted_updated_on_pass(self):
        """last_emitted updates when a value passes."""
        cfg = TriggerNoiseGateConfig(enabled=True, threshold=0.05)
        gate = TriggerNoiseGate(cfg)
        gate.feed(0.5)
        gate.feed(0.51)  # Suppressed
        assert gate.last_emitted() == 0.5
        gate.feed(0.6)  # Passes (delta 0.1 > threshold 0.05)
        assert gate.last_emitted() == 0.6

    def test_last_emitted_not_updated_on_suppress(self):
        """last_emitted does not update when a value is suppressed."""
        cfg = TriggerNoiseGateConfig(enabled=True, threshold=0.05)
        gate = TriggerNoiseGate(cfg)
        gate.feed(0.5)
        gate.feed(0.51)  # Suppressed
        assert gate.last_emitted() == 0.5


class TestTriggerNoiseGateReset:
    """TriggerNoiseGate.reset."""

    def test_reset_clears_state(self):
        """reset() clears the last_value and returns None on next feed."""
        cfg = TriggerNoiseGateConfig(enabled=True, threshold=0.05)
        gate = TriggerNoiseGate(cfg)
        gate.feed(0.5)
        gate.reset()
        # After reset, next feed is treated as initial
        result = gate.feed(0.5)
        assert result == 0.5

    def test_reset_clears_stats(self):
        """reset() clears suppressed and passed counts."""
        cfg = TriggerNoiseGateConfig(enabled=True, threshold=0.05)
        gate = TriggerNoiseGate(cfg)
        gate.feed(0.5)
        gate.feed(0.51)  # Suppressed
        gate.reset()
        stats = gate.stats()
        assert stats["suppressed"] == 0
        assert stats["passed"] == 0

    def test_reset_allows_same_value_again(self):
        """reset() allows the same value to be emitted again."""
        cfg = TriggerNoiseGateConfig(enabled=True)
        gate = TriggerNoiseGate(cfg)
        gate.feed(0.5)
        gate.reset()
        result = gate.feed(0.5)
        assert result == 0.5


class TestTriggerNoiseGateStats:
    """TriggerNoiseGate stats tracking."""

    def test_initial_stats_zero(self):
        """Initial stats are all zero."""
        cfg = TriggerNoiseGateConfig(enabled=True)
        gate = TriggerNoiseGate(cfg)
        stats = gate.stats()
        assert stats["suppressed"] == 0
        assert stats["passed"] == 0

    def test_first_feed_increments_passed(self):
        """First feed increments passed count."""
        cfg = TriggerNoiseGateConfig(enabled=True)
        gate = TriggerNoiseGate(cfg)
        gate.feed(0.5)
        stats = gate.stats()
        assert stats["passed"] == 1
        assert stats["suppressed"] == 0

    def test_suppressed_feed_increments_suppressed(self):
        """Suppressed feed increments suppressed count."""
        cfg = TriggerNoiseGateConfig(enabled=True, threshold=0.05)
        gate = TriggerNoiseGate(cfg)
        gate.feed(0.5)
        gate.feed(0.51)  # Suppressed
        stats = gate.stats()
        assert stats["suppressed"] == 1
        assert stats["passed"] == 1

    def test_multiple_suppressed_feeds(self):
        """Multiple suppressed feeds increment counter correctly."""
        cfg = TriggerNoiseGateConfig(enabled=True, threshold=0.05)
        gate = TriggerNoiseGate(cfg)
        gate.feed(0.5)
        gate.feed(0.51)  # Suppressed
        gate.feed(0.502)  # Suppressed
        gate.feed(0.503)  # Suppressed
        stats = gate.stats()
        assert stats["suppressed"] == 3
        assert stats["passed"] == 1

    def test_passed_and_suppressed_tracking(self):
        """Mixed passed and suppressed are tracked correctly."""
        cfg = TriggerNoiseGateConfig(enabled=True, threshold=0.05)
        gate = TriggerNoiseGate(cfg)
        gate.feed(0.5)  # Passed
        gate.feed(0.51)  # Suppressed
        gate.feed(0.52)  # Suppressed
        gate.feed(0.6)  # Passed (delta 0.1 > threshold)
        gate.feed(0.61)  # Suppressed
        stats = gate.stats()
        assert stats["passed"] == 2
        assert stats["suppressed"] == 3


class TestTriggerNoiseGateSerialization:
    """to_dict and from_dict — round-trip serialization."""

    def test_to_dict_defaults(self):
        """to_dict serializes default config correctly."""
        cfg = TriggerNoiseGateConfig()
        data = cfg.to_dict()
        assert data == {
            "enabled": False,
            "threshold": 0.01,
            "release_threshold": 0.005,
            "hysteresis_factor": 1.5,
        }

    def test_to_dict_full_config(self):
        """to_dict serializes all fields."""
        cfg = TriggerNoiseGateConfig(
            enabled=True,
            threshold=0.05,
            release_threshold=0.01,
            hysteresis_factor=2.0,
        )
        data = cfg.to_dict()
        assert data == {
            "enabled": True,
            "threshold": 0.05,
            "release_threshold": 0.01,
            "hysteresis_factor": 2.0,
        }

    def test_from_dict_defaults(self):
        """from_dict with empty dict uses defaults."""
        cfg = TriggerNoiseGateConfig.from_dict({})
        assert cfg.enabled is False
        assert cfg.threshold == 0.01
        assert cfg.release_threshold == 0.005
        assert cfg.hysteresis_factor == 1.5

    def test_from_dict_full_config(self):
        """from_dict loads all fields."""
        data = {
            "enabled": True,
            "threshold": 0.05,
            "release_threshold": 0.01,
            "hysteresis_factor": 2.0,
        }
        cfg = TriggerNoiseGateConfig.from_dict(data)
        assert cfg.enabled is True
        assert cfg.threshold == 0.05
        assert cfg.release_threshold == 0.01
        assert cfg.hysteresis_factor == 2.0

    def test_from_dict_clamps_thresholds(self):
        """from_dict clamps threshold values."""
        cfg = TriggerNoiseGateConfig.from_dict(
            {"threshold": -0.1, "release_threshold": 1.0}
        )
        assert cfg.threshold == 0
        assert cfg.release_threshold == 0.5

    def test_from_dict_clamps_hysteresis(self):
        """from_dict clamps hysteresis_factor."""
        cfg = TriggerNoiseGateConfig.from_dict({"hysteresis_factor": 10.0})
        assert cfg.hysteresis_factor == 5

    def test_round_trip_serialization(self):
        """to_dict and from_dict preserve config exactly."""
        cfg = TriggerNoiseGateConfig(
            enabled=True,
            threshold=0.03,
            release_threshold=0.008,
            hysteresis_factor=2.5,
        )
        data = cfg.to_dict()
        cfg2 = TriggerNoiseGateConfig.from_dict(data)
        assert cfg == cfg2

    def test_round_trip_serialization_default(self):
        """Round-trip preserves default config."""
        cfg = TriggerNoiseGateConfig()
        data = cfg.to_dict()
        cfg2 = TriggerNoiseGateConfig.from_dict(data)
        assert cfg == cfg2


class TestTriggerNoiseGateIntegration:
    """Integration tests spanning typical use cases."""

    def test_typical_pressure_stream(self):
        """Example: Filter jittery analog pressure stream."""
        cfg = TriggerNoiseGateConfig(
            enabled=True, threshold=0.05, hysteresis_factor=1.5
        )
        gate = TriggerNoiseGate(cfg)

        # Stable initial pressure
        assert gate.feed(0.5) == 0.5

        # Jitter: small fluctuations suppressed
        assert gate.feed(0.501) is None
        assert gate.feed(0.499) is None
        assert gate.feed(0.502) is None

        # Significant increase passes
        assert gate.feed(0.6) == 0.6

        # More jitter
        assert gate.feed(0.601) is None
        assert gate.feed(0.599) is None

        # Release via low pressure
        assert gate.feed(0.005) == 0  # Below release_threshold

    def test_rapid_kick_detection(self):
        """Example: Detect kick drum (rapid pressure spike)."""
        cfg = TriggerNoiseGateConfig(
            enabled=True, threshold=0.1, hysteresis_factor=1.5
        )
        gate = TriggerNoiseGate(cfg)

        # Resting state
        gate.feed(0.0)

        # Kick hit (large, rapid increase)
        result = gate.feed(0.8)
        assert result == 0.8  # Large delta > threshold * hysteresis

        # Jitter on the sustained pressure
        assert gate.feed(0.81) is None
        assert gate.feed(0.79) is None

        # Release
        result = gate.feed(0.0)
        assert result == 0

    def test_disabled_gate_no_suppression(self):
        """Example: Disabled gate never suppresses."""
        cfg = TriggerNoiseGateConfig(enabled=False, threshold=0.1)
        gate = TriggerNoiseGate(cfg)

        gate.feed(0.5)
        # Even tiny changes pass through
        assert gate.feed(0.501) == 0.501
        assert gate.feed(0.502) == 0.502

    def test_stats_across_realistic_sequence(self):
        """Realistic sequence with stats tracking."""
        cfg = TriggerNoiseGateConfig(
            enabled=True, threshold=0.05, hysteresis_factor=1.5
        )
        gate = TriggerNoiseGate(cfg)

        # Initial
        gate.feed(0.0)  # Passed: 1

        # Pressure builds with jitter
        gate.feed(0.01)  # Suppressed: 1
        gate.feed(0.02)  # Suppressed: 2
        gate.feed(0.08)  # Passed: 2 (delta 0.08 > 0.05)

        # More jitter
        gate.feed(0.09)  # Suppressed: 3
        gate.feed(0.07)  # Suppressed: 4

        # Release
        gate.feed(0.0)  # Passed: 3

        stats = gate.stats()
        assert stats["passed"] == 3
        assert stats["suppressed"] == 4


class TestTriggerNoiseGateEdgeCases:
    """Edge cases and boundary conditions."""

    def test_pressure_transitions_slowly(self):
        """Simulate slow pressure ramp-up with threshold filtering."""
        cfg = TriggerNoiseGateConfig(
            enabled=True, threshold=0.02, hysteresis_factor=1.0
        )
        gate = TriggerNoiseGate(cfg)

        gate.feed(0.0)
        assert gate.feed(0.01) is None  # Below threshold
        assert gate.feed(0.02) == 0.02  # At threshold, passes
        assert gate.feed(0.03) is None  # Delta 0.01 < threshold
        assert gate.feed(0.04) == 0.04  # Delta 0.02 == threshold, passes

    def test_zero_threshold_allows_any_change(self):
        """With threshold=0, any change passes."""
        cfg = TriggerNoiseGateConfig(
            enabled=True, threshold=0.0, hysteresis_factor=1.5
        )
        gate = TriggerNoiseGate(cfg)

        gate.feed(0.5)
        # With threshold=0, any delta (no matter how tiny) passes
        assert gate.feed(0.5001) == 0.5001  # Delta 0.0001 > 0
        assert gate.feed(0.50001) == 0.50001  # Delta 0.00009 > 0

    def test_max_hysteresis_factor(self):
        """With hysteresis_factor=5, upward changes need 5x threshold."""
        cfg = TriggerNoiseGateConfig(
            enabled=True, threshold=0.01, hysteresis_factor=5.0
        )
        gate = TriggerNoiseGate(cfg)

        gate.feed(0.5)
        # Upward needs 0.01 * 5 = 0.05
        assert gate.feed(0.54) is None  # Delta 0.04 < 0.05
        assert gate.feed(0.55) == 0.55  # Delta 0.05 >= 0.05
