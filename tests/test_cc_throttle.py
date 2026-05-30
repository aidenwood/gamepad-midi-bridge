"""Tests for per-CC throttle.

CcThrottle rate-limits messages on a per-(channel, cc) basis.
Pure stdlib, no Qt.
"""
from __future__ import annotations

import pytest


class TestCcThrottleConfigDefaults:
    """CcThrottleConfig — initialization and defaults."""

    def test_config_default_values(self):
        """Default config has sensible values."""
        from gamepad_midi_bridge.cc_throttle import CcThrottleConfig

        cfg = CcThrottleConfig()
        assert cfg.enabled is False
        assert cfg.default_min_gap_ms == 8.0
        assert cfg.per_cc_overrides == {}

    def test_enabled_flag(self):
        """enabled flag can be set."""
        from gamepad_midi_bridge.cc_throttle import CcThrottleConfig

        cfg = CcThrottleConfig(enabled=True)
        assert cfg.enabled is True


class TestCcThrottleConfigClamping:
    """CcThrottleConfig — numeric clamping."""

    def test_clamp_default_min_gap_ms_below_range(self):
        """default_min_gap_ms < 0 clamped to 0."""
        from gamepad_midi_bridge.cc_throttle import CcThrottleConfig

        cfg = CcThrottleConfig(default_min_gap_ms=-10.0)
        assert cfg.default_min_gap_ms == 0.0

    def test_clamp_default_min_gap_ms_above_range(self):
        """default_min_gap_ms > 1000 clamped to 1000."""
        from gamepad_midi_bridge.cc_throttle import CcThrottleConfig

        cfg = CcThrottleConfig(default_min_gap_ms=5000.0)
        assert cfg.default_min_gap_ms == 1000.0

    def test_clamp_per_cc_overrides_below_range(self):
        """per_cc_overrides values < 0 clamped to 0."""
        from gamepad_midi_bridge.cc_throttle import CcThrottleConfig

        cfg = CcThrottleConfig(per_cc_overrides={7: -5.0})
        assert cfg.per_cc_overrides[7] == 0.0

    def test_clamp_per_cc_overrides_above_range(self):
        """per_cc_overrides values > 1000 clamped to 1000."""
        from gamepad_midi_bridge.cc_throttle import CcThrottleConfig

        cfg = CcThrottleConfig(per_cc_overrides={7: 5000.0})
        assert cfg.per_cc_overrides[7] == 1000.0

    def test_clamp_multiple_per_cc_overrides(self):
        """Multiple per_cc_overrides are all clamped."""
        from gamepad_midi_bridge.cc_throttle import CcThrottleConfig

        cfg = CcThrottleConfig(
            per_cc_overrides={1: -10.0, 7: 2000.0, 64: 50.0}
        )
        assert cfg.per_cc_overrides[1] == 0.0
        assert cfg.per_cc_overrides[7] == 1000.0
        assert cfg.per_cc_overrides[64] == 50.0


class TestCcThrottleConfigSerialization:
    """CcThrottleConfig.to_dict() / from_dict() round-trip."""

    def test_to_dict_basic(self):
        """to_dict returns correct dict."""
        from gamepad_midi_bridge.cc_throttle import CcThrottleConfig

        cfg = CcThrottleConfig(enabled=True, default_min_gap_ms=10.0)
        d = cfg.to_dict()
        assert d["enabled"] is True
        assert d["default_min_gap_ms"] == 10.0
        assert d["per_cc_overrides"] == {}

    def test_to_dict_with_overrides(self):
        """to_dict includes per_cc_overrides as str keys."""
        from gamepad_midi_bridge.cc_throttle import CcThrottleConfig

        cfg = CcThrottleConfig(
            enabled=True,
            default_min_gap_ms=10.0,
            per_cc_overrides={7: 20.0, 64: 5.0},
        )
        d = cfg.to_dict()
        assert d["enabled"] is True
        assert d["default_min_gap_ms"] == 10.0
        assert d["per_cc_overrides"]["7"] == 20.0
        assert d["per_cc_overrides"]["64"] == 5.0

    def test_from_dict_basic(self):
        """from_dict reconstructs config."""
        from gamepad_midi_bridge.cc_throttle import CcThrottleConfig

        d = {"enabled": True, "default_min_gap_ms": 10.0, "per_cc_overrides": {}}
        cfg = CcThrottleConfig.from_dict(d)
        assert cfg.enabled is True
        assert cfg.default_min_gap_ms == 10.0
        assert cfg.per_cc_overrides == {}

    def test_from_dict_with_overrides(self):
        """from_dict reconstructs config with overrides (str keys)."""
        from gamepad_midi_bridge.cc_throttle import CcThrottleConfig

        d = {
            "enabled": True,
            "default_min_gap_ms": 10.0,
            "per_cc_overrides": {"7": 20.0, "64": 5.0},
        }
        cfg = CcThrottleConfig.from_dict(d)
        assert cfg.enabled is True
        assert cfg.default_min_gap_ms == 10.0
        assert cfg.per_cc_overrides[7] == 20.0
        assert cfg.per_cc_overrides[64] == 5.0

    def test_round_trip_serialization(self):
        """to_dict → from_dict produces same config."""
        from gamepad_midi_bridge.cc_throttle import CcThrottleConfig

        cfg1 = CcThrottleConfig(
            enabled=True,
            default_min_gap_ms=15.0,
            per_cc_overrides={1: 10.0, 7: 20.0, 64: 5.0},
        )
        d = cfg1.to_dict()
        cfg2 = CcThrottleConfig.from_dict(d)

        assert cfg2.enabled == cfg1.enabled
        assert cfg2.default_min_gap_ms == cfg1.default_min_gap_ms
        assert cfg2.per_cc_overrides == cfg1.per_cc_overrides

    def test_from_dict_with_missing_keys_uses_defaults(self):
        """from_dict with partial dict uses defaults for missing keys."""
        from gamepad_midi_bridge.cc_throttle import CcThrottleConfig

        d = {"enabled": True}
        cfg = CcThrottleConfig.from_dict(d)
        assert cfg.enabled is True
        assert cfg.default_min_gap_ms == 8.0  # default
        assert cfg.per_cc_overrides == {}


class TestCcThrottleDisabled:
    """Disabled throttle always allows."""

    def test_disabled_always_returns_true(self):
        """When disabled=False, allow() always returns True."""
        from gamepad_midi_bridge.cc_throttle import CcThrottleConfig, CcThrottle

        cfg = CcThrottleConfig(enabled=False, default_min_gap_ms=100.0)
        throttle = CcThrottle(cfg)

        # Multiple calls at same time should all return True
        assert throttle.allow(1, 7, 0.0) is True
        assert throttle.allow(1, 7, 0.0) is True
        assert throttle.allow(1, 7, 0.0) is True


class TestCcThrottleFirstAllow:
    """First call to allow() always returns True."""

    def test_first_allow_returns_true(self):
        """First allow() returns True."""
        from gamepad_midi_bridge.cc_throttle import CcThrottleConfig, CcThrottle

        cfg = CcThrottleConfig(enabled=True, default_min_gap_ms=10.0)
        throttle = CcThrottle(cfg)

        assert throttle.allow(1, 7, 0.0) is True


class TestCcThrottleWithinGap:
    """Second allow() within gap returns False."""

    def test_second_allow_within_gap_returns_false(self):
        """Second allow() within default_min_gap_ms returns False."""
        from gamepad_midi_bridge.cc_throttle import CcThrottleConfig, CcThrottle

        cfg = CcThrottleConfig(enabled=True, default_min_gap_ms=10.0)
        throttle = CcThrottle(cfg)

        assert throttle.allow(1, 7, 0.0) is True
        # At t=0.005s (5ms), within 10ms gap
        assert throttle.allow(1, 7, 0.005) is False

    def test_second_allow_at_same_time_returns_false(self):
        """Second allow() at same time returns False."""
        from gamepad_midi_bridge.cc_throttle import CcThrottleConfig, CcThrottle

        cfg = CcThrottleConfig(enabled=True, default_min_gap_ms=10.0)
        throttle = CcThrottle(cfg)

        assert throttle.allow(1, 7, 0.0) is True
        assert throttle.allow(1, 7, 0.0) is False


class TestCcThrottleAfterGap:
    """Second allow() after gap returns True."""

    def test_second_allow_after_gap_returns_true(self):
        """Second allow() after default_min_gap_ms returns True."""
        from gamepad_midi_bridge.cc_throttle import CcThrottleConfig, CcThrottle

        cfg = CcThrottleConfig(enabled=True, default_min_gap_ms=10.0)
        throttle = CcThrottle(cfg)

        assert throttle.allow(1, 7, 0.0) is True
        # At t=0.020s (20ms), beyond 10ms gap
        assert throttle.allow(1, 7, 0.020) is True

    def test_allow_just_at_gap_boundary_returns_true(self):
        """allow() exactly at gap boundary returns True."""
        from gamepad_midi_bridge.cc_throttle import CcThrottleConfig, CcThrottle

        cfg = CcThrottleConfig(enabled=True, default_min_gap_ms=10.0)
        throttle = CcThrottle(cfg)

        assert throttle.allow(1, 7, 0.0) is True
        # At t=0.010s (10ms), exactly at gap
        assert throttle.allow(1, 7, 0.010) is True

    def test_allow_just_before_gap_boundary_returns_false(self):
        """allow() just before gap boundary returns False."""
        from gamepad_midi_bridge.cc_throttle import CcThrottleConfig, CcThrottle

        cfg = CcThrottleConfig(enabled=True, default_min_gap_ms=10.0)
        throttle = CcThrottle(cfg)

        assert throttle.allow(1, 7, 0.0) is True
        # At t=0.0099s (9.9ms), just before 10ms gap
        assert throttle.allow(1, 7, 0.0099) is False


class TestCcThrottlePerCcOverrides:
    """per_cc_overrides: different CCs can have different gaps."""

    def test_per_cc_override_different_from_default(self):
        """CC with override uses override, not default."""
        from gamepad_midi_bridge.cc_throttle import CcThrottleConfig, CcThrottle

        cfg = CcThrottleConfig(
            enabled=True,
            default_min_gap_ms=10.0,
            per_cc_overrides={7: 20.0},
        )
        throttle = CcThrottle(cfg)

        # CC 7 with 20ms override
        assert throttle.allow(1, 7, 0.0) is True
        assert throttle.allow(1, 7, 0.015) is False  # 15ms < 20ms
        assert throttle.allow(1, 7, 0.020) is True   # 20ms >= 20ms

    def test_cc_without_override_uses_default(self):
        """CC without override uses default."""
        from gamepad_midi_bridge.cc_throttle import CcThrottleConfig, CcThrottle

        cfg = CcThrottleConfig(
            enabled=True,
            default_min_gap_ms=10.0,
            per_cc_overrides={7: 20.0},
        )
        throttle = CcThrottle(cfg)

        # CC 64 without override, uses 10ms default
        assert throttle.allow(1, 64, 0.0) is True
        assert throttle.allow(1, 64, 0.015) is True  # 15ms > 10ms

    def test_multiple_ccs_throttled_independently(self):
        """Different CCs throttled independently."""
        from gamepad_midi_bridge.cc_throttle import CcThrottleConfig, CcThrottle

        cfg = CcThrottleConfig(
            enabled=True,
            default_min_gap_ms=10.0,
            per_cc_overrides={1: 20.0, 7: 5.0},
        )
        throttle = CcThrottle(cfg)

        # CC 1 at t=0
        assert throttle.allow(1, 1, 0.0) is True

        # CC 7 at t=0 (different CC, allowed)
        assert throttle.allow(1, 7, 0.0) is True

        # CC 1 at t=0.015s (within 20ms, blocked)
        assert throttle.allow(1, 1, 0.015) is False

        # CC 7 at t=0.015s (beyond 5ms, allowed)
        assert throttle.allow(1, 7, 0.015) is True

    def test_per_cc_override_zero_gap_always_allowed(self):
        """Per-CC override of 0ms allows all sends."""
        from gamepad_midi_bridge.cc_throttle import CcThrottleConfig, CcThrottle

        cfg = CcThrottleConfig(
            enabled=True,
            default_min_gap_ms=100.0,
            per_cc_overrides={7: 0.0},
        )
        throttle = CcThrottle(cfg)

        # CC 7 with 0ms gap
        assert throttle.allow(1, 7, 0.0) is True
        assert throttle.allow(1, 7, 0.0) is True  # Same time, still allowed
        assert throttle.allow(1, 7, 0.001) is True


class TestCcThrottleChannels:
    """Throttle is per-(channel, cc), not just per-cc."""

    def test_same_cc_different_channels_throttled_independently(self):
        """Same CC on different channels throttled independently."""
        from gamepad_midi_bridge.cc_throttle import CcThrottleConfig, CcThrottle

        cfg = CcThrottleConfig(enabled=True, default_min_gap_ms=10.0)
        throttle = CcThrottle(cfg)

        # CC 7 on channel 1 at t=0
        assert throttle.allow(1, 7, 0.0) is True

        # CC 7 on channel 2 at t=0 (different channel, allowed)
        assert throttle.allow(2, 7, 0.0) is True

        # CC 7 on channel 1 at t=0.005s (within 10ms, blocked)
        assert throttle.allow(1, 7, 0.005) is False

        # CC 7 on channel 2 at t=0.005s (within 10ms for channel 2, blocked)
        assert throttle.allow(2, 7, 0.005) is False


class TestCcThrottleInputClamping:
    """allow() clamps channel [1,16] and cc [0,127]."""

    def test_clamp_channel_below_range(self):
        """Channel < 1 clamped to 1."""
        from gamepad_midi_bridge.cc_throttle import CcThrottleConfig, CcThrottle

        cfg = CcThrottleConfig(enabled=True, default_min_gap_ms=10.0)
        throttle = CcThrottle(cfg)

        # Channel 0 (invalid) clamped to 1
        assert throttle.allow(0, 7, 0.0) is True
        # Same (1, 7) queried again
        assert throttle.allow(1, 7, 0.0) is False

    def test_clamp_channel_above_range(self):
        """Channel > 16 clamped to 16."""
        from gamepad_midi_bridge.cc_throttle import CcThrottleConfig, CcThrottle

        cfg = CcThrottleConfig(enabled=True, default_min_gap_ms=10.0)
        throttle = CcThrottle(cfg)

        # Channel 20 clamped to 16
        assert throttle.allow(20, 7, 0.0) is True
        # Same (16, 7) queried again
        assert throttle.allow(16, 7, 0.0) is False

    def test_clamp_cc_below_range(self):
        """CC < 0 clamped to 0."""
        from gamepad_midi_bridge.cc_throttle import CcThrottleConfig, CcThrottle

        cfg = CcThrottleConfig(enabled=True, default_min_gap_ms=10.0)
        throttle = CcThrottle(cfg)

        # CC -1 clamped to 0
        assert throttle.allow(1, -1, 0.0) is True
        # Same (1, 0) queried again
        assert throttle.allow(1, 0, 0.0) is False

    def test_clamp_cc_above_range(self):
        """CC > 127 clamped to 127."""
        from gamepad_midi_bridge.cc_throttle import CcThrottleConfig, CcThrottle

        cfg = CcThrottleConfig(enabled=True, default_min_gap_ms=10.0)
        throttle = CcThrottle(cfg)

        # CC 128 clamped to 127
        assert throttle.allow(1, 128, 0.0) is True
        # Same (1, 127) queried again
        assert throttle.allow(1, 127, 0.0) is False


class TestCcThrottleRecordSent:
    """record_sent() marks as sent without gating."""

    def test_record_sent_updates_state(self):
        """record_sent() updates _last_sent without returning True."""
        from gamepad_midi_bridge.cc_throttle import CcThrottleConfig, CcThrottle

        cfg = CcThrottleConfig(enabled=True, default_min_gap_ms=10.0)
        throttle = CcThrottle(cfg)

        # Manually record a send
        throttle.record_sent(1, 7, 0.0)

        # Next allow at t=0.005s should be blocked
        assert throttle.allow(1, 7, 0.005) is False

        # At t=0.010s should be allowed
        assert throttle.allow(1, 7, 0.010) is True


class TestCcThrottleLastSentAt:
    """last_sent_at() returns last send time or None."""

    def test_last_sent_at_no_history(self):
        """last_sent_at() returns None if never sent."""
        from gamepad_midi_bridge.cc_throttle import CcThrottleConfig, CcThrottle

        cfg = CcThrottleConfig(enabled=True, default_min_gap_ms=10.0)
        throttle = CcThrottle(cfg)

        assert throttle.last_sent_at(1, 7) is None

    def test_last_sent_at_after_allow(self):
        """last_sent_at() returns time after allow()."""
        from gamepad_midi_bridge.cc_throttle import CcThrottleConfig, CcThrottle

        cfg = CcThrottleConfig(enabled=True, default_min_gap_ms=10.0)
        throttle = CcThrottle(cfg)

        assert throttle.allow(1, 7, 0.5) is True
        assert throttle.last_sent_at(1, 7) == 0.5

    def test_last_sent_at_after_record_sent(self):
        """last_sent_at() returns time after record_sent()."""
        from gamepad_midi_bridge.cc_throttle import CcThrottleConfig, CcThrottle

        cfg = CcThrottleConfig(enabled=True, default_min_gap_ms=10.0)
        throttle = CcThrottle(cfg)

        throttle.record_sent(1, 7, 0.3)
        assert throttle.last_sent_at(1, 7) == 0.3

    def test_last_sent_at_clamped_inputs(self):
        """last_sent_at() clamps channel/cc."""
        from gamepad_midi_bridge.cc_throttle import CcThrottleConfig, CcThrottle

        cfg = CcThrottleConfig(enabled=True, default_min_gap_ms=10.0)
        throttle = CcThrottle(cfg)

        # Record (1, 7)
        throttle.record_sent(1, 7, 0.0)

        # Query with clamped inputs
        assert throttle.last_sent_at(0, 7) == 0.0  # Channel 0 → 1
        assert throttle.last_sent_at(1, -1) is None  # CC -1 → 0 (different CC)


class TestCcThrottleReset:
    """reset() clears all sent history."""

    def test_reset_clears_history(self):
        """reset() clears _last_sent."""
        from gamepad_midi_bridge.cc_throttle import CcThrottleConfig, CcThrottle

        cfg = CcThrottleConfig(enabled=True, default_min_gap_ms=10.0)
        throttle = CcThrottle(cfg)

        # Add some history
        throttle.allow(1, 7, 0.0)
        throttle.allow(2, 64, 0.0)

        assert throttle.last_sent_at(1, 7) is not None
        assert throttle.last_sent_at(2, 64) is not None

        # Reset
        throttle.reset()

        # History should be clear
        assert throttle.last_sent_at(1, 7) is None
        assert throttle.last_sent_at(2, 64) is None

    def test_reset_allows_next_event_immediately(self):
        """After reset(), first allow() at same time returns True."""
        from gamepad_midi_bridge.cc_throttle import CcThrottleConfig, CcThrottle

        cfg = CcThrottleConfig(enabled=True, default_min_gap_ms=10.0)
        throttle = CcThrottle(cfg)

        throttle.allow(1, 7, 0.0)
        # Next at same time would fail
        assert throttle.allow(1, 7, 0.0) is False

        # After reset
        throttle.reset()
        assert throttle.allow(1, 7, 0.0) is True


class TestCcThrottleSetPerCc:
    """set_per_cc() adds/updates per-CC override."""

    def test_set_per_cc_adds_override(self):
        """set_per_cc() adds a per-CC override."""
        from gamepad_midi_bridge.cc_throttle import CcThrottleConfig, CcThrottle

        cfg = CcThrottleConfig(enabled=True, default_min_gap_ms=10.0)
        throttle = CcThrottle(cfg)

        throttle.set_per_cc(7, 50.0)
        assert throttle.effective_gap_ms(7) == 50.0

    def test_set_per_cc_clamps_value(self):
        """set_per_cc() clamps value to [0, 1000]."""
        from gamepad_midi_bridge.cc_throttle import CcThrottleConfig, CcThrottle

        cfg = CcThrottleConfig(enabled=True, default_min_gap_ms=10.0)
        throttle = CcThrottle(cfg)

        throttle.set_per_cc(7, -5.0)
        assert throttle.effective_gap_ms(7) == 0.0

        throttle.set_per_cc(7, 5000.0)
        assert throttle.effective_gap_ms(7) == 1000.0

    def test_set_per_cc_clamps_cc(self):
        """set_per_cc() clamps CC to [0, 127]."""
        from gamepad_midi_bridge.cc_throttle import CcThrottleConfig, CcThrottle

        cfg = CcThrottleConfig(enabled=True, default_min_gap_ms=10.0)
        throttle = CcThrottle(cfg)

        throttle.set_per_cc(-1, 50.0)
        assert throttle.effective_gap_ms(0) == 50.0

        throttle.set_per_cc(200, 50.0)
        assert throttle.effective_gap_ms(127) == 50.0


class TestCcThrottleClearPerCc:
    """clear_per_cc() removes per-CC override."""

    def test_clear_per_cc_removes_override(self):
        """clear_per_cc() removes an override."""
        from gamepad_midi_bridge.cc_throttle import CcThrottleConfig, CcThrottle

        cfg = CcThrottleConfig(
            enabled=True,
            default_min_gap_ms=10.0,
            per_cc_overrides={7: 50.0},
        )
        throttle = CcThrottle(cfg)

        assert throttle.clear_per_cc(7) is True
        assert throttle.effective_gap_ms(7) == 10.0  # back to default

    def test_clear_per_cc_nonexistent_returns_false(self):
        """clear_per_cc() on nonexistent override returns False."""
        from gamepad_midi_bridge.cc_throttle import CcThrottleConfig, CcThrottle

        cfg = CcThrottleConfig(enabled=True, default_min_gap_ms=10.0)
        throttle = CcThrottle(cfg)

        assert throttle.clear_per_cc(7) is False

    def test_clear_per_cc_clamps_cc(self):
        """clear_per_cc() clamps CC."""
        from gamepad_midi_bridge.cc_throttle import CcThrottleConfig, CcThrottle

        cfg = CcThrottleConfig(
            enabled=True,
            default_min_gap_ms=10.0,
            per_cc_overrides={127: 50.0},
        )
        throttle = CcThrottle(cfg)

        # Clear using clamped input
        assert throttle.clear_per_cc(200) is True
        assert throttle.effective_gap_ms(127) == 10.0


class TestCcThrottleEffectiveGap:
    """effective_gap_ms() returns override or default."""

    def test_effective_gap_with_override(self):
        """effective_gap_ms() returns override if present."""
        from gamepad_midi_bridge.cc_throttle import CcThrottleConfig, CcThrottle

        cfg = CcThrottleConfig(
            enabled=True,
            default_min_gap_ms=10.0,
            per_cc_overrides={7: 50.0},
        )
        throttle = CcThrottle(cfg)

        assert throttle.effective_gap_ms(7) == 50.0

    def test_effective_gap_without_override(self):
        """effective_gap_ms() returns default if no override."""
        from gamepad_midi_bridge.cc_throttle import CcThrottleConfig, CcThrottle

        cfg = CcThrottleConfig(
            enabled=True,
            default_min_gap_ms=10.0,
            per_cc_overrides={7: 50.0},
        )
        throttle = CcThrottle(cfg)

        assert throttle.effective_gap_ms(64) == 10.0

    def test_effective_gap_clamps_cc(self):
        """effective_gap_ms() clamps CC."""
        from gamepad_midi_bridge.cc_throttle import CcThrottleConfig, CcThrottle

        cfg = CcThrottleConfig(
            enabled=True,
            default_min_gap_ms=10.0,
            per_cc_overrides={127: 50.0},
        )
        throttle = CcThrottle(cfg)

        # Query with clamped CC
        assert throttle.effective_gap_ms(200) == 50.0


class TestCcThrottleIntegration:
    """Integration tests: realistic usage patterns."""

    def test_multiple_ccs_multiple_channels(self):
        """Throttle correctly handles multiple CCs and channels."""
        from gamepad_midi_bridge.cc_throttle import CcThrottleConfig, CcThrottle

        cfg = CcThrottleConfig(
            enabled=True,
            default_min_gap_ms=10.0,
            per_cc_overrides={7: 20.0, 64: 5.0},
        )
        throttle = CcThrottle(cfg)

        # Ch1, CC7 at t=0
        assert throttle.allow(1, 7, 0.0) is True
        # Ch1, CC64 at t=0 (different CC)
        assert throttle.allow(1, 64, 0.0) is True
        # Ch2, CC7 at t=0 (different channel)
        assert throttle.allow(2, 7, 0.0) is True

        # Ch1, CC7 at t=0.015s (within 20ms)
        assert throttle.allow(1, 7, 0.015) is False
        # Ch1, CC64 at t=0.015s (beyond 5ms)
        assert throttle.allow(1, 64, 0.015) is True
        # Ch2, CC7 at t=0.015s (within 20ms for ch2)
        assert throttle.allow(2, 7, 0.015) is False

    def test_real_world_cc_stream(self):
        """Simulate real CC stream with bursts and pauses."""
        from gamepad_midi_bridge.cc_throttle import CcThrottleConfig, CcThrottle

        cfg = CcThrottleConfig(
            enabled=True,
            default_min_gap_ms=8.0,
            per_cc_overrides={7: 16.0},
        )
        throttle = CcThrottle(cfg)

        # Burst of CC7 every 2ms for 20ms
        burst_count = 0
        for i in range(10):
            if throttle.allow(1, 7, i * 0.002):
                burst_count += 1

        # With 16ms gap, should get ~1-2 through
        assert burst_count >= 1
        assert burst_count <= 2

        # Reset and do slower stream
        throttle.reset()
        slow_count = 0
        for i in range(10):
            if throttle.allow(1, 7, i * 0.020):
                slow_count += 1

        # With 16ms gap and 20ms interval, all should go through
        assert slow_count == 10
