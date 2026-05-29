"""Rate limiter tests — per-message-type quotas and coalescing."""
from __future__ import annotations

import pytest
from gamepad_midi_bridge.rate_limiter import RateLimitConfig, RateLimiter


class TestRateLimitConfig:
    """Configuration validation and serialization."""

    def test_defaults(self) -> None:
        """Default config is disabled."""
        cfg = RateLimitConfig()
        assert cfg.enabled is False
        assert cfg.max_total_per_sec == 1000
        assert cfg.max_cc_per_sec == 500
        assert cfg.max_note_per_sec == 100
        assert cfg.max_sysex_per_sec == 10
        assert cfg.coalesce_same_cc is True
        assert cfg.coalesce_window_ms == 8

    def test_clamp_max_total_per_sec(self) -> None:
        """max_total_per_sec clamped to 1..10000."""
        cfg1 = RateLimitConfig(max_total_per_sec=0)
        assert cfg1.max_total_per_sec == 1

        cfg2 = RateLimitConfig(max_total_per_sec=20000)
        assert cfg2.max_total_per_sec == 10000

    def test_clamp_max_cc_per_sec(self) -> None:
        """max_cc_per_sec clamped to 0..10000."""
        cfg1 = RateLimitConfig(max_cc_per_sec=-5)
        assert cfg1.max_cc_per_sec == 0

        cfg2 = RateLimitConfig(max_cc_per_sec=20000)
        assert cfg2.max_cc_per_sec == 10000

    def test_clamp_max_note_per_sec(self) -> None:
        """max_note_per_sec clamped to 0..10000."""
        cfg1 = RateLimitConfig(max_note_per_sec=-1)
        assert cfg1.max_note_per_sec == 0

        cfg2 = RateLimitConfig(max_note_per_sec=15000)
        assert cfg2.max_note_per_sec == 10000

    def test_clamp_max_sysex_per_sec(self) -> None:
        """max_sysex_per_sec clamped to 0..1000."""
        cfg1 = RateLimitConfig(max_sysex_per_sec=-1)
        assert cfg1.max_sysex_per_sec == 0

        cfg2 = RateLimitConfig(max_sysex_per_sec=5000)
        assert cfg2.max_sysex_per_sec == 1000

    def test_clamp_coalesce_window_ms(self) -> None:
        """coalesce_window_ms clamped to 1..1000."""
        cfg1 = RateLimitConfig(coalesce_window_ms=0)
        assert cfg1.coalesce_window_ms == 1

        cfg2 = RateLimitConfig(coalesce_window_ms=2000)
        assert cfg2.coalesce_window_ms == 1000

    def test_to_dict(self) -> None:
        """Serialize to dict."""
        cfg = RateLimitConfig(enabled=True, max_cc_per_sec=200)
        d = cfg.to_dict()
        assert d["enabled"] is True
        assert d["max_cc_per_sec"] == 200
        assert d["max_total_per_sec"] == 1000

    def test_from_dict(self) -> None:
        """Deserialize from dict."""
        d = {"enabled": True, "max_cc_per_sec": 300, "max_total_per_sec": 2000}
        cfg = RateLimitConfig.from_dict(d)
        assert cfg.enabled is True
        assert cfg.max_cc_per_sec == 300
        assert cfg.max_total_per_sec == 2000

    def test_from_dict_forward_compatible(self) -> None:
        """Ignore unknown fields in from_dict."""
        d = {"enabled": True, "unknown_field": "ignored", "max_cc_per_sec": 150}
        cfg = RateLimitConfig.from_dict(d)
        assert cfg.enabled is True
        assert cfg.max_cc_per_sec == 150

    def test_round_trip_serialization(self) -> None:
        """to_dict and from_dict round-trip."""
        cfg1 = RateLimitConfig(enabled=True, max_cc_per_sec=250, max_note_per_sec=75)
        d = cfg1.to_dict()
        cfg2 = RateLimitConfig.from_dict(d)
        assert cfg2.enabled == cfg1.enabled
        assert cfg2.max_cc_per_sec == cfg1.max_cc_per_sec
        assert cfg2.max_note_per_sec == cfg1.max_note_per_sec


class TestRateLimiterDisabled:
    """When disabled, all messages pass."""

    def test_disabled_always_allow(self) -> None:
        """Disabled limiter allows any message."""
        cfg = RateLimitConfig(enabled=False)
        limiter = RateLimiter(cfg)

        for i in range(1000):
            assert limiter.allow([0xB0, 1, 100], i * 0.001) is True


class TestRateLimiterCC:
    """CC message rate limiting."""

    def test_cc_within_quota(self) -> None:
        """CC messages within quota pass."""
        cfg = RateLimitConfig(enabled=True, max_cc_per_sec=3)
        limiter = RateLimiter(cfg)

        assert limiter.allow([0xB0, 1, 10], 0.0) is True
        assert limiter.allow([0xB0, 1, 20], 0.01) is True
        assert limiter.allow([0xB0, 1, 30], 0.02) is True

    def test_cc_over_quota(self) -> None:
        """4th CC within same second blocked."""
        cfg = RateLimitConfig(enabled=True, max_cc_per_sec=3)
        limiter = RateLimiter(cfg)

        assert limiter.allow([0xB0, 1, 10], 0.0) is True
        assert limiter.allow([0xB0, 1, 20], 0.01) is True
        assert limiter.allow([0xB0, 1, 30], 0.02) is True
        assert limiter.allow([0xB0, 1, 40], 0.03) is False

    def test_cc_quota_zero_unlimited(self) -> None:
        """max_cc_per_sec=0 means unlimited CC."""
        cfg = RateLimitConfig(enabled=True, max_cc_per_sec=0, max_total_per_sec=1000)
        limiter = RateLimiter(cfg)

        for i in range(100):
            assert limiter.allow([0xB0, 1, i % 128], 0.1) is True

    def test_cc_different_channels(self) -> None:
        """CCs on different channels count toward same quota."""
        cfg = RateLimitConfig(enabled=True, max_cc_per_sec=2)
        limiter = RateLimiter(cfg)

        assert limiter.allow([0xB0, 1, 10], 0.0) is True  # Channel 0
        assert limiter.allow([0xB1, 1, 10], 0.01) is True  # Channel 1
        assert limiter.allow([0xB2, 1, 10], 0.02) is False  # Over quota


class TestRateLimiterNote:
    """Note-on/off message rate limiting."""

    def test_note_within_quota(self) -> None:
        """Note messages within quota pass."""
        cfg = RateLimitConfig(enabled=True, max_note_per_sec=2)
        limiter = RateLimiter(cfg)

        assert limiter.allow([0x90, 60, 100], 0.0) is True  # Note on
        assert limiter.allow([0x80, 60, 0], 0.01) is True  # Note off

    def test_note_over_quota(self) -> None:
        """3rd note blocked when quota=2."""
        cfg = RateLimitConfig(enabled=True, max_note_per_sec=2)
        limiter = RateLimiter(cfg)

        assert limiter.allow([0x90, 60, 100], 0.0) is True
        assert limiter.allow([0x80, 60, 0], 0.01) is True
        assert limiter.allow([0x90, 64, 100], 0.02) is False

    def test_note_quota_zero_unlimited(self) -> None:
        """max_note_per_sec=0 means unlimited notes."""
        cfg = RateLimitConfig(enabled=True, max_note_per_sec=0, max_total_per_sec=1000)
        limiter = RateLimiter(cfg)

        for i in range(100):
            assert limiter.allow([0x90, i % 128, 100], 0.1) is True

    def test_note_on_and_off_separate(self) -> None:
        """Both note-on and note-off consume quota."""
        cfg = RateLimitConfig(enabled=True, max_note_per_sec=2)
        limiter = RateLimiter(cfg)

        assert limiter.allow([0x90, 60, 100], 0.0) is True  # Note on
        assert limiter.allow([0x80, 60, 0], 0.01) is True  # Note off
        assert limiter.allow([0x90, 64, 100], 0.02) is False  # Over quota


class TestRateLimiterSysex:
    """Sysex message rate limiting."""

    def test_sysex_within_quota(self) -> None:
        """Sysex messages within quota pass."""
        cfg = RateLimitConfig(enabled=True, max_sysex_per_sec=2)
        limiter = RateLimiter(cfg)

        assert limiter.allow([0xF0, 0x43, 0x12, 0x00, 0xF7], 0.0) is True
        assert limiter.allow([0xF0, 0x41, 0x10, 0x42, 0xF7], 0.01) is True

    def test_sysex_over_quota(self) -> None:
        """3rd sysex blocked when quota=2."""
        cfg = RateLimitConfig(enabled=True, max_sysex_per_sec=2)
        limiter = RateLimiter(cfg)

        assert limiter.allow([0xF0, 0x43, 0x12, 0xF7], 0.0) is True
        assert limiter.allow([0xF0, 0x41, 0x10, 0xF7], 0.01) is True
        assert limiter.allow([0xF0, 0x7E, 0x00, 0xF7], 0.02) is False

    def test_sysex_quota_zero_unlimited(self) -> None:
        """max_sysex_per_sec=0 means unlimited sysex."""
        cfg = RateLimitConfig(enabled=True, max_sysex_per_sec=0, max_total_per_sec=1000)
        limiter = RateLimiter(cfg)

        for i in range(20):
            assert limiter.allow([0xF0, i, 0xF7], 0.1) is True


class TestRateLimiterTotal:
    """Total message cap across all categories."""

    def test_total_cap_enforced(self) -> None:
        """Total cap blocks even when category not full."""
        cfg = RateLimitConfig(
            enabled=True,
            max_total_per_sec=3,
            max_cc_per_sec=10,
            max_note_per_sec=10,
        )
        limiter = RateLimiter(cfg)

        assert limiter.allow([0xB0, 1, 10], 0.0) is True  # Total=1
        assert limiter.allow([0x90, 60, 100], 0.01) is True  # Total=2
        assert limiter.allow([0xB0, 2, 20], 0.02) is True  # Total=3
        assert limiter.allow([0x90, 61, 100], 0.03) is False  # Total would be 4

    def test_total_quota_zero_invalid(self) -> None:
        """max_total_per_sec=0 is clamped to 1."""
        cfg = RateLimitConfig(enabled=True, max_total_per_sec=0)
        assert cfg.max_total_per_sec == 1


class TestRateLimiterCoalesce:
    """CC coalescing — drop same values arriving quickly."""

    def test_coalesce_same_value_within_window(self) -> None:
        """Same CC value within window is dropped."""
        cfg = RateLimitConfig(
            enabled=True,
            max_cc_per_sec=10,
            coalesce_same_cc=True,
            coalesce_window_ms=10,
        )
        limiter = RateLimiter(cfg)

        # 0.0 s: CC 1 = 100 (allowed)
        assert limiter.allow([0xB0, 1, 100], 0.0) is True
        # 0.005 s: same CC 1 = 100 (dropped, within window)
        assert limiter.allow([0xB0, 1, 100], 0.005) is False

    def test_coalesce_different_value_within_window(self) -> None:
        """Different CC value within window is allowed."""
        cfg = RateLimitConfig(
            enabled=True,
            max_cc_per_sec=10,
            coalesce_same_cc=True,
            coalesce_window_ms=10,
        )
        limiter = RateLimiter(cfg)

        assert limiter.allow([0xB0, 1, 100], 0.0) is True
        assert limiter.allow([0xB0, 1, 101], 0.005) is True

    def test_coalesce_same_value_after_window(self) -> None:
        """Same CC value AFTER window is allowed."""
        cfg = RateLimitConfig(
            enabled=True,
            max_cc_per_sec=10,
            coalesce_same_cc=True,
            coalesce_window_ms=10,
        )
        limiter = RateLimiter(cfg)

        assert limiter.allow([0xB0, 1, 100], 0.0) is True
        assert limiter.allow([0xB0, 1, 100], 0.015) is True

    def test_coalesce_disabled(self) -> None:
        """With coalesce_same_cc=False, duplicates pass."""
        cfg = RateLimitConfig(
            enabled=True,
            max_cc_per_sec=10,
            coalesce_same_cc=False,
            coalesce_window_ms=10,
        )
        limiter = RateLimiter(cfg)

        assert limiter.allow([0xB0, 1, 100], 0.0) is True
        assert limiter.allow([0xB0, 1, 100], 0.005) is True

    def test_coalesce_per_channel(self) -> None:
        """Coalescing is per (channel, cc) pair."""
        cfg = RateLimitConfig(
            enabled=True,
            max_cc_per_sec=10,
            coalesce_same_cc=True,
            coalesce_window_ms=10,
        )
        limiter = RateLimiter(cfg)

        # Channel 0, CC 1, value 100
        assert limiter.allow([0xB0, 1, 100], 0.0) is True
        # Channel 1, CC 1, value 100 (different channel — allowed)
        assert limiter.allow([0xB1, 1, 100], 0.005) is True
        # Channel 0, CC 1, value 100 again (same channel/cc — dropped)
        assert limiter.allow([0xB0, 1, 100], 0.006) is False


class TestRateLimiterOther:
    """Non-CC, non-note, non-sysex messages classified as "other"."""

    def test_other_messages_count_toward_total(self) -> None:
        """Other messages consume total quota but not a category quota."""
        cfg = RateLimitConfig(
            enabled=True,
            max_total_per_sec=2,
            max_cc_per_sec=10,
        )
        limiter = RateLimiter(cfg)

        # Program change (0xC0)
        assert limiter.allow([0xC0, 5], 0.0) is True  # Total=1
        assert limiter.allow([0xC0, 10], 0.01) is True  # Total=2
        assert limiter.allow([0xC0, 15], 0.02) is False  # Total capped


class TestRateLimiterCurrentRate:
    """current_rate() reports message counts within 1-second window."""

    def test_current_rate_empty(self) -> None:
        """Empty limiter has zero counts."""
        cfg = RateLimitConfig(enabled=True)
        limiter = RateLimiter(cfg)

        rates = limiter.current_rate(1.0)
        assert rates == {"total": 0, "cc": 0, "note": 0, "sysex": 0}

    def test_current_rate_mixed(self) -> None:
        """current_rate counts by category."""
        cfg = RateLimitConfig(enabled=True, max_total_per_sec=1000)
        limiter = RateLimiter(cfg)

        limiter.allow([0xB0, 1, 100], 0.0)  # CC
        limiter.allow([0xB0, 2, 100], 0.01)  # CC
        limiter.allow([0x90, 60, 100], 0.02)  # Note
        limiter.allow([0xF0, 0x43, 0xF7], 0.03)  # Sysex

        rates = limiter.current_rate(0.5)
        assert rates["total"] == 4
        assert rates["cc"] == 2
        assert rates["note"] == 1
        assert rates["sysex"] == 1

    def test_current_rate_prunes_old(self) -> None:
        """current_rate only counts within 1-second window."""
        cfg = RateLimitConfig(enabled=True, max_total_per_sec=1000)
        limiter = RateLimiter(cfg)

        limiter.allow([0xB0, 1, 100], 0.0)
        limiter.allow([0xB0, 2, 100], 0.8)

        # At 1.5s, only the 0.8s message (0.8 > 1.5-1.0=0.5) is within the 1-second window
        rates = limiter.current_rate(1.5)
        assert rates["total"] == 1
        assert rates["cc"] == 1


class TestRateLimiterReset:
    """reset() clears all queues and coalesce state."""

    def test_reset_clears_queues(self) -> None:
        """Reset clears all message queues."""
        cfg = RateLimitConfig(enabled=True, max_cc_per_sec=1)
        limiter = RateLimiter(cfg)

        limiter.allow([0xB0, 1, 100], 0.0)

        # Now quota is full
        assert limiter.allow([0xB0, 2, 100], 0.01) is False

        # Reset and try again
        limiter.reset()
        assert limiter.allow([0xB0, 2, 100], 0.01) is True

    def test_reset_clears_coalesce(self) -> None:
        """Reset clears coalesce memory."""
        cfg = RateLimitConfig(
            enabled=True,
            max_cc_per_sec=10,
            coalesce_same_cc=True,
            coalesce_window_ms=10,
        )
        limiter = RateLimiter(cfg)

        # First message
        assert limiter.allow([0xB0, 1, 100], 0.0) is True
        # Same value within window (dropped)
        assert limiter.allow([0xB0, 1, 100], 0.005) is False

        # After reset, same value is allowed again
        limiter.reset()
        assert limiter.allow([0xB0, 1, 100], 0.005) is True


class TestRateLimiterEdgeCases:
    """Edge cases and defensive behavior."""

    def test_empty_message_bytes(self) -> None:
        """Empty message bytes return True (no-op)."""
        cfg = RateLimitConfig(enabled=True)
        limiter = RateLimiter(cfg)

        assert limiter.allow([], 0.0) is True

    def test_one_byte_message(self) -> None:
        """Single-byte message (just status) is classified and counted."""
        cfg = RateLimitConfig(enabled=True, max_total_per_sec=2)
        limiter = RateLimiter(cfg)

        assert limiter.allow([0xF8], 0.0) is True  # Timing clock (other)
        assert limiter.allow([0xF8], 0.01) is True  # Other
        assert limiter.allow([0xF8], 0.02) is False  # Over total quota

    def test_large_cc_value(self) -> None:
        """CC value 127 is valid."""
        cfg = RateLimitConfig(enabled=True, max_cc_per_sec=1)
        limiter = RateLimiter(cfg)

        assert limiter.allow([0xB0, 127, 127], 0.0) is True

    def test_window_boundary_precision(self) -> None:
        """Messages exactly at the 1-second boundary are excluded."""
        cfg = RateLimitConfig(enabled=True, max_total_per_sec=1000)
        limiter = RateLimiter(cfg)

        limiter.allow([0xB0, 1, 100], 0.0)

        # At exactly 1.0 seconds, the old entry is pruned (> 1.0 - 1.0 = 0.0)
        rates = limiter.current_rate(1.0)
        assert rates["total"] == 0

    def test_negative_time_handled(self) -> None:
        """Negative times don't crash (defensive)."""
        cfg = RateLimitConfig(enabled=True, max_total_per_sec=1000)
        limiter = RateLimiter(cfg)

        # Should not crash
        assert limiter.allow([0xB0, 1, 100], -1.0) is True
