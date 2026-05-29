"""Tests for RandomWalkConfig dataclass and RandomWalk class."""
from __future__ import annotations

import pytest

from gamepad_midi_bridge.random_walk import RandomWalk, RandomWalkConfig


# ---------------------------------------------------------------------------
# RandomWalkConfig: defaults and post_init validation
# ---------------------------------------------------------------------------

class TestRandomWalkConfigDefaults:
    """Test that RandomWalkConfig has sensible defaults."""

    def test_enabled_default_false(self):
        cfg = RandomWalkConfig()
        assert cfg.enabled is False

    def test_cc_default(self):
        assert RandomWalkConfig().cc == 1

    def test_channel_default(self):
        assert RandomWalkConfig().channel == 1

    def test_min_value_default(self):
        assert RandomWalkConfig().min_value == 0

    def test_max_value_default(self):
        assert RandomWalkConfig().max_value == 127

    def test_step_size_default(self):
        assert RandomWalkConfig().step_size == 5

    def test_step_rate_hz_default(self):
        assert RandomWalkConfig().step_rate_hz == 4.0

    def test_seed_default_none(self):
        assert RandomWalkConfig().seed is None


class TestRandomWalkConfigClamping:
    """Test that __post_init__ clamps values to legal ranges."""

    def test_cc_clamped_to_0_127(self):
        cfg = RandomWalkConfig(cc=-5)
        assert cfg.cc == 0
        cfg = RandomWalkConfig(cc=200)
        assert cfg.cc == 127

    def test_channel_clamped_to_1_16(self):
        cfg = RandomWalkConfig(channel=0)
        assert cfg.channel == 1
        cfg = RandomWalkConfig(channel=20)
        assert cfg.channel == 16

    def test_min_value_clamped_to_0_127(self):
        cfg = RandomWalkConfig(min_value=-10)
        assert cfg.min_value == 0
        cfg = RandomWalkConfig(min_value=200)
        assert cfg.min_value == 127

    def test_max_value_clamped_to_0_127(self):
        cfg = RandomWalkConfig(max_value=-10)
        assert cfg.max_value == 0
        cfg = RandomWalkConfig(max_value=200)
        assert cfg.max_value == 127

    def test_step_size_clamped_to_1_64(self):
        cfg = RandomWalkConfig(step_size=0)
        assert cfg.step_size == 1
        cfg = RandomWalkConfig(step_size=100)
        assert cfg.step_size == 64

    def test_step_rate_hz_clamped_to_0_1_50(self):
        cfg = RandomWalkConfig(step_rate_hz=0.01)
        assert cfg.step_rate_hz == 0.1
        cfg = RandomWalkConfig(step_rate_hz=100.0)
        assert cfg.step_rate_hz == 50.0

    def test_swap_min_max_if_inverted(self):
        """If max < min, they should be swapped."""
        cfg = RandomWalkConfig(min_value=100, max_value=50)
        assert cfg.min_value == 50
        assert cfg.max_value == 100

    def test_seed_converted_to_int_when_provided(self):
        cfg = RandomWalkConfig(seed=42.7)
        assert cfg.seed == 42


class TestRandomWalkConfigSerialization:
    """Test to_dict / from_dict round-trip."""

    def test_to_dict_returns_all_fields(self):
        cfg = RandomWalkConfig(
            enabled=True, cc=74, channel=2, min_value=20, max_value=100,
            step_size=10, step_rate_hz=2.0, seed=42,
        )
        d = cfg.to_dict()
        assert d["enabled"] is True
        assert d["cc"] == 74
        assert d["channel"] == 2
        assert d["min_value"] == 20
        assert d["max_value"] == 100
        assert d["step_size"] == 10
        assert d["step_rate_hz"] == 2.0
        assert d["seed"] == 42

    def test_from_dict_none_returns_defaults(self):
        cfg = RandomWalkConfig.from_dict(None)
        assert cfg.enabled is False
        assert cfg.cc == 1

    def test_from_dict_empty_dict_returns_defaults(self):
        cfg = RandomWalkConfig.from_dict({})
        assert cfg.enabled is False

    def test_round_trip_full_config(self):
        """Serialize and deserialize a full config."""
        original = RandomWalkConfig(
            enabled=True, cc=74, channel=3, min_value=10, max_value=110,
            step_size=8, step_rate_hz=1.5, seed=99,
        )
        d = original.to_dict()
        restored = RandomWalkConfig.from_dict(d)
        assert restored.enabled == original.enabled
        assert restored.cc == original.cc
        assert restored.channel == original.channel
        assert restored.min_value == original.min_value
        assert restored.max_value == original.max_value
        assert restored.step_size == original.step_size
        assert restored.step_rate_hz == original.step_rate_hz
        assert restored.seed == original.seed


# ---------------------------------------------------------------------------
# RandomWalk: initialization and basic state
# ---------------------------------------------------------------------------

class TestRandomWalkInitialization:
    """Test RandomWalk initialization and state setup."""

    def test_init_with_default_range_uses_midpoint(self):
        cfg = RandomWalkConfig()
        walk = RandomWalk(cfg)
        assert walk.value() == 63

    def test_init_with_custom_range_uses_midpoint(self):
        cfg = RandomWalkConfig(min_value=20, max_value=80)
        walk = RandomWalk(cfg)
        assert walk.value() == 50

    def test_init_with_explicit_start_value(self):
        cfg = RandomWalkConfig(min_value=0, max_value=100)
        walk = RandomWalk(cfg, start_value=75)
        assert walk.value() == 75

    def test_init_start_value_clamped_to_range(self):
        cfg = RandomWalkConfig(min_value=30, max_value=80)
        walk = RandomWalk(cfg, start_value=10)
        assert walk.value() == 30
        walk = RandomWalk(cfg, start_value=100)
        assert walk.value() == 80

    def test_init_with_seed_creates_seeded_rng(self):
        cfg = RandomWalkConfig(seed=42)
        walk = RandomWalk(cfg)
        assert walk.current == 63


class TestRandomWalkValue:
    """Test the value() getter."""

    def test_value_returns_current_without_stepping(self):
        cfg = RandomWalkConfig()
        walk = RandomWalk(cfg, start_value=50)
        assert walk.value() == 50


# ---------------------------------------------------------------------------
# RandomWalk: stepping and rate control
# ---------------------------------------------------------------------------

class TestRandomWalkStepping:
    """Test the step() method: timing, values, bounds."""

    def test_step_too_soon_returns_none(self):
        cfg = RandomWalkConfig(step_rate_hz=1.0)
        walk = RandomWalk(cfg)
        result = walk.step(0.0)
        assert result is not None
        result = walk.step(0.4)
        assert result is None

    def test_step_after_rate_interval_returns_value(self):
        cfg = RandomWalkConfig(step_rate_hz=2.0)
        walk = RandomWalk(cfg)
        v1 = walk.step(0.0)
        assert isinstance(v1, int)
        assert cfg.min_value <= v1 <= cfg.max_value
        v2 = walk.step(0.6)
        assert isinstance(v2, int)
        assert cfg.min_value <= v2 <= cfg.max_value

    def test_step_returns_int_in_valid_range(self):
        cfg = RandomWalkConfig(min_value=20, max_value=100, step_rate_hz=10.0)
        walk = RandomWalk(cfg)
        for i in range(10):
            value = walk.step(i * 0.11)
            assert isinstance(value, int)
            assert 20 <= value <= 100

    def test_step_first_call_always_succeeds(self):
        cfg = RandomWalkConfig(step_rate_hz=0.1)
        walk = RandomWalk(cfg)
        result = walk.step(0.0)
        assert result is not None


class TestRandomWalkBounds:
    """Test that random walk respects min/max bounds via reflection."""

    def test_reflection_at_max_boundary(self):
        cfg = RandomWalkConfig(min_value=0, max_value=10, step_size=5, seed=42, step_rate_hz=10.0)
        walk = RandomWalk(cfg, start_value=10)
        for i in range(50):
            value = walk.step(i * 0.11)
            assert value is not None
            assert 0 <= value <= 10

    def test_reflection_at_min_boundary(self):
        cfg = RandomWalkConfig(min_value=0, max_value=10, step_size=5, seed=42, step_rate_hz=10.0)
        walk = RandomWalk(cfg, start_value=0)
        for i in range(50):
            value = walk.step(i * 0.11)
            assert value is not None
            assert 0 <= value <= 10

    def test_tight_range_stays_in_bounds(self):
        cfg = RandomWalkConfig(min_value=50, max_value=60, step_size=30, seed=42, step_rate_hz=10.0)
        walk = RandomWalk(cfg)
        for i in range(100):
            value = walk.step(i * 0.11)
            assert value is not None
            assert 50 <= value <= 60


# ---------------------------------------------------------------------------
# RandomWalk: reset and seed control
# ---------------------------------------------------------------------------

class TestRandomWalkReset:
    """Test the reset() method."""

    def test_reset_without_value_uses_midpoint(self):
        cfg = RandomWalkConfig(min_value=20, max_value=80)
        walk = RandomWalk(cfg, start_value=50)
        walk.step(0.0)
        walk.reset()
        assert walk.value() == 50

    def test_reset_with_value_sets_current(self):
        cfg = RandomWalkConfig()
        walk = RandomWalk(cfg, start_value=10)
        walk.reset(value=99)
        assert walk.value() == 99

    def test_reset_clears_last_step_at(self):
        cfg = RandomWalkConfig(step_rate_hz=1.0)
        walk = RandomWalk(cfg)
        walk.step(0.0)
        walk.reset()
        result = walk.step(0.1)
        assert result is not None

    def test_reset_value_clamped_to_range(self):
        cfg = RandomWalkConfig(min_value=30, max_value=80)
        walk = RandomWalk(cfg)
        walk.reset(value=10)
        assert walk.value() == 30
        walk.reset(value=100)
        assert walk.value() == 80


class TestRandomWalkSeedControl:
    """Test set_seed() and determinism."""

    def test_same_seed_gives_same_sequence(self):
        cfg = RandomWalkConfig(min_value=0, max_value=100, step_size=5, seed=42)
        walk1 = RandomWalk(cfg)
        walk2 = RandomWalk(cfg)
        sequence1 = []
        sequence2 = []
        for i in range(10):
            v1 = walk1.step(i * 0.11)
            v2 = walk2.step(i * 0.11)
            sequence1.append(v1)
            sequence2.append(v2)
        assert sequence1 == sequence2

    def test_different_seeds_give_different_sequences(self):
        cfg1 = RandomWalkConfig(min_value=0, max_value=100, step_size=5, seed=42)
        cfg2 = RandomWalkConfig(min_value=0, max_value=100, step_size=5, seed=99)
        walk1 = RandomWalk(cfg1)
        walk2 = RandomWalk(cfg2)
        sequence1 = []
        sequence2 = []
        for i in range(10):
            v1 = walk1.step(i * 0.11)
            v2 = walk2.step(i * 0.11)
            sequence1.append(v1)
            sequence2.append(v2)
        assert sequence1 != sequence2

    def test_set_seed_resets_rng_state(self):
        cfg = RandomWalkConfig(min_value=0, max_value=100, step_size=5, seed=42)
        walk = RandomWalk(cfg)
        v1 = walk.step(0.0)
        v2 = walk.step(0.11)
        v3 = walk.step(0.22)
        walk.set_seed(42)
        walk.reset(value=None)
        walk.last_step_at = None
        v1_replay = walk.step(0.0)
        v2_replay = walk.step(0.11)
        v3_replay = walk.step(0.22)
        assert v1 == v1_replay
        assert v2 == v2_replay
        assert v3 == v3_replay


# ---------------------------------------------------------------------------
# RandomWalk: edge cases and property-based tests
# ---------------------------------------------------------------------------

class TestRandomWalkEdgeCases:
    """Test edge cases: single-value range, zero range, etc."""

    def test_min_equals_max_walk_stays_at_that_value(self):
        cfg = RandomWalkConfig(min_value=50, max_value=50, step_size=10, step_rate_hz=10.0)
        walk = RandomWalk(cfg)
        for i in range(20):
            value = walk.step(i * 0.11)
            assert value == 50

    def test_step_size_one_gradual_walk(self):
        cfg = RandomWalkConfig(min_value=0, max_value=127, step_size=1, seed=42, step_rate_hz=10.0)
        walk = RandomWalk(cfg, start_value=64)
        prev_value = walk.value()
        for i in range(20):
            value = walk.step(i * 0.11)
            assert value is not None
            assert abs(value - prev_value) <= 1
            prev_value = value

    def test_high_rate_hz_allows_frequent_steps(self):
        cfg = RandomWalkConfig(step_rate_hz=50.0)  # Max allowed; interval = 20ms
        walk = RandomWalk(cfg)
        result = walk.step(0.0)
        assert result is not None
        result = walk.step(0.025)  # 25ms later, more than 20ms interval
        assert result is not None

    def test_low_rate_hz_requires_long_waits(self):
        cfg = RandomWalkConfig(step_rate_hz=0.1)
        walk = RandomWalk(cfg)
        result = walk.step(0.0)
        assert result is not None
        result = walk.step(5.0)
        assert result is None
        result = walk.step(10.1)
        assert result is not None


class TestRandomWalkPropertyBased:
    """Property-based tests: invariants that hold over many runs."""

    def test_long_run_stays_in_bounds(self):
        cfg = RandomWalkConfig(
            min_value=10, max_value=110, step_size=20, step_rate_hz=10.0, seed=42,
        )
        walk = RandomWalk(cfg)
        for i in range(1000):
            value = walk.step(i * 0.101)
            if value is not None:
                assert 10 <= value <= 110

    def test_multiple_walks_are_independent(self):
        cfg = RandomWalkConfig(min_value=0, max_value=100, step_size=5)
        walk1 = RandomWalk(cfg)
        walk2 = RandomWalk(cfg)
        sequence1 = []
        sequence2 = []
        for i in range(20):
            v1 = walk1.step(i * 0.11)
            v2 = walk2.step(i * 0.11)
            sequence1.append(v1)
            sequence2.append(v2)
        assert sequence1 != sequence2 or len(set(sequence1)) > 1
