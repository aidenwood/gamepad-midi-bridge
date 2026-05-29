"""Velocity gate filter — drops or remaps note_on messages by velocity threshold."""
from __future__ import annotations

import pytest

from gamepad_midi_bridge.velocity_gate import (
    VelocityGateConfig,
    VelocityGate,
    apply,
)


class TestVelocityGateConfigDefaults:
    """VelocityGateConfig dataclass — defaults and clamping."""

    def test_default_config_disabled(self):
        """Default config is disabled with full range."""
        cfg = VelocityGateConfig()
        assert cfg.enabled is False
        assert cfg.low_threshold == 1
        assert cfg.high_threshold == 127
        assert cfg.mode == "drop"
        assert cfg.floor_value == 1
        assert cfg.ceiling_value == 127

    def test_thresholds_clamped_to_0_127(self):
        """low/high thresholds clamped to 0..127."""
        cfg = VelocityGateConfig(low_threshold=-10, high_threshold=150)
        assert cfg.low_threshold == 0
        assert cfg.high_threshold == 127

    def test_floor_ceiling_clamped_to_1_127(self):
        """floor_value and ceiling_value clamped to 1..127."""
        cfg = VelocityGateConfig(floor_value=0, ceiling_value=200)
        assert cfg.floor_value == 1
        assert cfg.ceiling_value == 127

    def test_low_threshold_greater_than_high_swaps(self):
        """If low > high, thresholds are swapped."""
        cfg = VelocityGateConfig(low_threshold=100, high_threshold=30)
        assert cfg.low_threshold == 30
        assert cfg.high_threshold == 100

    def test_invalid_mode_defaults_to_drop(self):
        """Unknown mode defaults to 'drop'."""
        cfg = VelocityGateConfig(mode="unknown")
        assert cfg.mode == "drop"

    def test_valid_modes_preserved(self):
        """Valid modes are preserved."""
        for mode in ("drop", "clamp", "scale"):
            cfg = VelocityGateConfig(mode=mode)
            assert cfg.mode == mode


class TestApplyDisabled:
    """apply function — disabled config passes through unchanged."""

    def test_apply_disabled_returns_unchanged(self):
        """Disabled config returns velocity unchanged."""
        cfg = VelocityGateConfig(enabled=False)
        assert apply(5, cfg) == 5
        assert apply(64, cfg) == 64
        assert apply(127, cfg) == 127
        assert apply(0, cfg) == 0


class TestApplyDropMode:
    """apply function — drop mode."""

    def test_drop_mode_below_threshold_returns_none(self):
        """Velocity below low_threshold returns None."""
        cfg = VelocityGateConfig(enabled=True, mode="drop", low_threshold=30)
        assert apply(5, cfg) is None
        assert apply(29, cfg) is None

    def test_drop_mode_at_threshold_passes(self):
        """Velocity at low_threshold passes through."""
        cfg = VelocityGateConfig(enabled=True, mode="drop", low_threshold=30)
        assert apply(30, cfg) == 30

    def test_drop_mode_within_range_passes(self):
        """Velocity within range [low, high] passes through."""
        cfg = VelocityGateConfig(
            enabled=True, mode="drop", low_threshold=30, high_threshold=100
        )
        assert apply(50, cfg) == 50
        assert apply(75, cfg) == 75
        assert apply(100, cfg) == 100

    def test_drop_mode_above_high_threshold_returns_none(self):
        """Velocity above high_threshold returns None."""
        cfg = VelocityGateConfig(
            enabled=True, mode="drop", low_threshold=30, high_threshold=100
        )
        assert apply(101, cfg) is None
        assert apply(127, cfg) is None

    def test_drop_mode_at_high_threshold_passes(self):
        """Velocity at high_threshold passes."""
        cfg = VelocityGateConfig(
            enabled=True, mode="drop", low_threshold=30, high_threshold=100
        )
        assert apply(100, cfg) == 100


class TestApplyClampMode:
    """apply function — clamp mode."""

    def test_clamp_mode_below_threshold_uses_floor(self):
        """Velocity below low_threshold uses floor_value."""
        cfg = VelocityGateConfig(
            enabled=True, mode="clamp", low_threshold=30, floor_value=10
        )
        assert apply(5, cfg) == 10
        assert apply(20, cfg) == 10

    def test_clamp_mode_within_range_unchanged(self):
        """Velocity within range passes through unchanged."""
        cfg = VelocityGateConfig(
            enabled=True,
            mode="clamp",
            low_threshold=30,
            high_threshold=100,
            floor_value=10,
            ceiling_value=120,
        )
        assert apply(30, cfg) == 30
        assert apply(50, cfg) == 50
        assert apply(100, cfg) == 100

    def test_clamp_mode_above_threshold_uses_ceiling(self):
        """Velocity above high_threshold uses ceiling_value."""
        cfg = VelocityGateConfig(
            enabled=True,
            mode="clamp",
            low_threshold=30,
            high_threshold=100,
            ceiling_value=120,
        )
        assert apply(101, cfg) == 120
        assert apply(127, cfg) == 120

    def test_clamp_mode_floor_ceiling_result_clamped_to_1_127(self):
        """Floor/ceiling values are clamped to 1..127 in result."""
        cfg = VelocityGateConfig(
            enabled=True, mode="clamp", floor_value=1, ceiling_value=127
        )
        # floor and ceiling already within range, no adjustment needed
        assert apply(0, cfg) == 1
        assert apply(127, cfg) == 127


class TestApplyScaleMode:
    """apply function — scale mode."""

    def test_scale_mode_at_low_threshold_becomes_floor(self):
        """Velocity at low_threshold becomes floor_value."""
        cfg = VelocityGateConfig(
            enabled=True,
            mode="scale",
            low_threshold=20,
            high_threshold=100,
            floor_value=10,
            ceiling_value=120,
        )
        assert apply(20, cfg) == 10

    def test_scale_mode_at_high_threshold_becomes_ceiling(self):
        """Velocity at high_threshold becomes ceiling_value."""
        cfg = VelocityGateConfig(
            enabled=True,
            mode="scale",
            low_threshold=20,
            high_threshold=100,
            floor_value=10,
            ceiling_value=120,
        )
        assert apply(100, cfg) == 120

    def test_scale_mode_below_threshold_clipped_then_scaled(self):
        """Velocity below low_threshold is clipped then scaled."""
        cfg = VelocityGateConfig(
            enabled=True,
            mode="scale",
            low_threshold=20,
            high_threshold=100,
            floor_value=10,
            ceiling_value=120,
        )
        # 5 clipped to 20, then scaled to 10
        assert apply(5, cfg) == 10

    def test_scale_mode_above_threshold_clipped_then_scaled(self):
        """Velocity above high_threshold is clipped then scaled."""
        cfg = VelocityGateConfig(
            enabled=True,
            mode="scale",
            low_threshold=20,
            high_threshold=100,
            floor_value=10,
            ceiling_value=120,
        )
        # 127 clipped to 100, then scaled to 120
        assert apply(127, cfg) == 120

    def test_scale_mode_midpoint_linear(self):
        """Velocity at midpoint of range scales to midpoint of floor/ceiling."""
        cfg = VelocityGateConfig(
            enabled=True,
            mode="scale",
            low_threshold=20,
            high_threshold=100,  # midpoint = 60
            floor_value=10,
            ceiling_value=120,  # midpoint = 65
        )
        # 60 should map to approximately 65
        result = apply(60, cfg)
        assert 64 <= result <= 66  # Allow rounding tolerance

    def test_scale_mode_full_range_linear(self):
        """Scaling across full velocity range works linearly."""
        cfg = VelocityGateConfig(
            enabled=True,
            mode="scale",
            low_threshold=0,
            high_threshold=127,
            floor_value=1,
            ceiling_value=127,
        )
        # 0 -> 1, 127 -> 127, 64 -> ~64
        assert apply(0, cfg) == 1
        assert apply(127, cfg) == 127
        result_mid = apply(64, cfg)
        assert 63 <= result_mid <= 65

    def test_scale_mode_degenerate_equal_thresholds(self):
        """When low == high, uses floor_value."""
        cfg = VelocityGateConfig(
            enabled=True,
            mode="scale",
            low_threshold=50,
            high_threshold=50,
            floor_value=20,
            ceiling_value=120,
        )
        # Any velocity maps to floor_value
        assert apply(30, cfg) == 20
        assert apply(50, cfg) == 20
        assert apply(70, cfg) == 20


class TestApplyUnknownMode:
    """apply function — unknown mode handling."""

    def test_unknown_mode_normalized_to_drop(self):
        """Unknown mode is normalized to drop during __post_init__."""
        cfg = VelocityGateConfig(enabled=True, mode="bogus")
        assert cfg.mode == "drop"


class TestVelocityGateStats:
    """VelocityGate.process and stats — tracking counts."""

    def test_process_increments_passed_count(self):
        """process() increments passed_count for non-dropped velocities."""
        cfg = VelocityGateConfig(enabled=True, mode="drop", low_threshold=30)
        gate = VelocityGate(cfg)
        gate.process(50)
        gate.process(75)
        stats = gate.stats()
        assert stats["passed"] == 2
        assert stats["dropped"] == 0

    def test_process_increments_dropped_count(self):
        """process() increments dropped_count for dropped velocities."""
        cfg = VelocityGateConfig(enabled=True, mode="drop", low_threshold=30)
        gate = VelocityGate(cfg)
        gate.process(10)
        gate.process(20)
        stats = gate.stats()
        assert stats["dropped"] == 2
        assert stats["passed"] == 0

    def test_process_mixed_dropped_and_passed(self):
        """process() tracks both dropped and passed correctly."""
        cfg = VelocityGateConfig(enabled=True, mode="drop", low_threshold=50)
        gate = VelocityGate(cfg)
        gate.process(30)  # dropped
        gate.process(60)  # passed
        gate.process(40)  # dropped
        gate.process(80)  # passed
        stats = gate.stats()
        assert stats["dropped"] == 2
        assert stats["passed"] == 2

    def test_reset_stats_zeros_counts(self):
        """reset_stats() resets both counts to 0."""
        cfg = VelocityGateConfig(enabled=True, mode="drop", low_threshold=50)
        gate = VelocityGate(cfg)
        gate.process(30)
        gate.process(60)
        gate.reset_stats()
        stats = gate.stats()
        assert stats["dropped"] == 0
        assert stats["passed"] == 0

    def test_stats_initial_state(self):
        """Initial stats are zero."""
        cfg = VelocityGateConfig()
        gate = VelocityGate(cfg)
        stats = gate.stats()
        assert stats["dropped"] == 0
        assert stats["passed"] == 0


class TestSerialization:
    """to_dict and from_dict — round-trip serialization."""

    def test_to_dict_defaults(self):
        """to_dict serializes default config correctly."""
        cfg = VelocityGateConfig()
        data = cfg.to_dict()
        assert data == {
            "enabled": False,
            "low_threshold": 1,
            "high_threshold": 127,
            "mode": "drop",
            "floor_value": 1,
            "ceiling_value": 127,
        }

    def test_to_dict_full_config(self):
        """to_dict serializes all fields."""
        cfg = VelocityGateConfig(
            enabled=True,
            low_threshold=30,
            high_threshold=100,
            mode="clamp",
            floor_value=10,
            ceiling_value=120,
        )
        data = cfg.to_dict()
        assert data == {
            "enabled": True,
            "low_threshold": 30,
            "high_threshold": 100,
            "mode": "clamp",
            "floor_value": 10,
            "ceiling_value": 120,
        }

    def test_from_dict_defaults(self):
        """from_dict with empty dict uses defaults."""
        cfg = VelocityGateConfig.from_dict({})
        assert cfg.enabled is False
        assert cfg.low_threshold == 1
        assert cfg.high_threshold == 127
        assert cfg.mode == "drop"
        assert cfg.floor_value == 1
        assert cfg.ceiling_value == 127

    def test_from_dict_full_config(self):
        """from_dict loads all fields."""
        data = {
            "enabled": True,
            "low_threshold": 30,
            "high_threshold": 100,
            "mode": "clamp",
            "floor_value": 10,
            "ceiling_value": 120,
        }
        cfg = VelocityGateConfig.from_dict(data)
        assert cfg.enabled is True
        assert cfg.low_threshold == 30
        assert cfg.high_threshold == 100
        assert cfg.mode == "clamp"
        assert cfg.floor_value == 10
        assert cfg.ceiling_value == 120

    def test_from_dict_clamps_thresholds(self):
        """from_dict clamps thresholds to 0..127."""
        cfg = VelocityGateConfig.from_dict({"low_threshold": -10, "high_threshold": 150})
        assert cfg.low_threshold == 0
        assert cfg.high_threshold == 127

    def test_from_dict_clamps_floor_ceiling(self):
        """from_dict clamps floor/ceiling to 1..127."""
        cfg = VelocityGateConfig.from_dict({"floor_value": 0, "ceiling_value": 200})
        assert cfg.floor_value == 1
        assert cfg.ceiling_value == 127

    def test_from_dict_swaps_if_low_greater_than_high(self):
        """from_dict swaps if low > high."""
        cfg = VelocityGateConfig.from_dict({"low_threshold": 100, "high_threshold": 30})
        assert cfg.low_threshold == 30
        assert cfg.high_threshold == 100

    def test_round_trip_serialization(self):
        """to_dict and from_dict preserve config exactly."""
        cfg = VelocityGateConfig(
            enabled=True,
            low_threshold=30,
            high_threshold=100,
            mode="scale",
            floor_value=10,
            ceiling_value=120,
        )
        data = cfg.to_dict()
        cfg2 = VelocityGateConfig.from_dict(data)
        assert cfg == cfg2

    def test_round_trip_serialization_default(self):
        """Round-trip preserves default config."""
        cfg = VelocityGateConfig()
        data = cfg.to_dict()
        cfg2 = VelocityGateConfig.from_dict(data)
        assert cfg == cfg2


class TestIntegration:
    """Integration tests spanning multiple modes and behaviors."""

    def test_drop_mode_typical_use_case(self):
        """Example: Drop low-velocity notes, keep mid-high."""
        cfg = VelocityGateConfig(
            enabled=True, mode="drop", low_threshold=40, high_threshold=127
        )
        # Soft touch → dropped
        assert apply(20, cfg) is None
        # Normal play → passed
        assert apply(60, cfg) == 60
        # Hard play → passed
        assert apply(100, cfg) == 100

    def test_clamp_mode_typical_use_case(self):
        """Example: Clamp weak hits to a minimum velocity."""
        cfg = VelocityGateConfig(
            enabled=True,
            mode="clamp",
            low_threshold=40,
            high_threshold=127,
            floor_value=40,
            ceiling_value=127,
        )
        # Below 40 → 40
        assert apply(20, cfg) == 40
        # Within range → unchanged
        assert apply(60, cfg) == 60

    def test_scale_mode_typical_use_case(self):
        """Example: Compress dynamic range (60-100) into (30-120)."""
        cfg = VelocityGateConfig(
            enabled=True,
            mode="scale",
            low_threshold=60,
            high_threshold=100,
            floor_value=30,
            ceiling_value=120,
        )
        # 60 → 30, 100 → 120, 80 → ~75
        assert apply(60, cfg) == 30
        assert apply(100, cfg) == 120
        result_80 = apply(80, cfg)
        assert 74 <= result_80 <= 76

    def test_all_modes_disabled_pass_through(self):
        """Disabled gate passes all velocities unchanged."""
        for mode in ("drop", "clamp", "scale"):
            cfg = VelocityGateConfig(enabled=False, mode=mode)
            for vel in [0, 30, 64, 100, 127]:
                assert apply(vel, cfg) == vel

    def test_velocity_gate_multiple_processes(self):
        """VelocityGate.process works correctly across multiple calls."""
        cfg = VelocityGateConfig(enabled=True, mode="drop", low_threshold=50)
        gate = VelocityGate(cfg)

        # First batch
        gate.process(30)  # dropped
        gate.process(60)  # passed
        gate.process(40)  # dropped

        stats = gate.stats()
        assert stats["dropped"] == 2
        assert stats["passed"] == 1

        # Reset and continue
        gate.reset_stats()
        gate.process(50)  # passed
        gate.process(80)  # passed

        stats = gate.stats()
        assert stats["dropped"] == 0
        assert stats["passed"] == 2
