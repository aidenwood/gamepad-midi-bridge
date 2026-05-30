"""Per-CC throttle: rate-limits messages on a per-(channel, cc) basis with configurable minimum gap.

Different from rate_limiter (which gates whole categories) — this throttles individual CC streams.
Pure stdlib, self-contained.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Optional


@dataclass
class CcThrottleConfig:
    """Configuration for per-CC throttle."""

    enabled: bool = False
    default_min_gap_ms: float = 8.0
    per_cc_overrides: dict[int, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate and clamp all numeric ranges."""
        # Clamp default_min_gap_ms to [0, 1000]
        self.default_min_gap_ms = max(0.0, min(1000.0, self.default_min_gap_ms))

        # Clamp all per_cc_overrides to [0, 1000]
        for cc_num in self.per_cc_overrides:
            self.per_cc_overrides[cc_num] = max(
                0.0, min(1000.0, self.per_cc_overrides[cc_num])
            )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for storage."""
        return {
            "enabled": self.enabled,
            "default_min_gap_ms": self.default_min_gap_ms,
            "per_cc_overrides": {str(cc): ms for cc, ms in self.per_cc_overrides.items()},
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CcThrottleConfig:
        """Deserialize from dict."""
        enabled = data.get("enabled", False)
        default_min_gap_ms = data.get("default_min_gap_ms", 8.0)

        # Parse per_cc_overrides: keys may be strings or ints
        per_cc_overrides = {}
        overrides_raw = data.get("per_cc_overrides", {})
        for key, value in overrides_raw.items():
            cc_num = int(key)
            per_cc_overrides[cc_num] = float(value)

        return cls(
            enabled=enabled,
            default_min_gap_ms=default_min_gap_ms,
            per_cc_overrides=per_cc_overrides,
        )


class CcThrottle:
    """Throttle individual CC streams on a per-(channel, cc) basis."""

    def __init__(self, cfg: CcThrottleConfig) -> None:
        """Initialize with config."""
        self.cfg = cfg
        # (channel, cc) -> last_send_at_s
        self._last_sent: dict[tuple[int, int], float] = {}

    def allow(self, channel: int, cc: int, now_s: float) -> bool:
        """
        Check if a CC message should be sent.

        Clamps channel to [1, 16], cc to [0, 127].
        Returns False if within throttle gap, True if allowed.
        On allow, updates _last_sent.
        """
        if not self.cfg.enabled:
            return True

        # Clamp inputs
        channel = max(1, min(16, channel))
        cc = max(0, min(127, cc))

        key = (channel, cc)

        # Get effective gap for this CC
        gap_ms = self.cfg.per_cc_overrides.get(cc, self.cfg.default_min_gap_ms)

        # Check if we've sent this (channel, cc) before
        if key in self._last_sent:
            last_time = self._last_sent[key]
            time_delta_ms = (now_s - last_time) * 1000.0
            if time_delta_ms < gap_ms:
                return False

        # Allowed: record the send
        self._last_sent[key] = now_s
        return True

    def record_sent(self, channel: int, cc: int, now_s: float) -> None:
        """Explicitly mark a (channel, cc) as sent without gating."""
        channel = max(1, min(16, channel))
        cc = max(0, min(127, cc))
        self._last_sent[(channel, cc)] = now_s

    def last_sent_at(self, channel: int, cc: int) -> Optional[float]:
        """Return the last time this (channel, cc) was sent, or None."""
        channel = max(1, min(16, channel))
        cc = max(0, min(127, cc))
        return self._last_sent.get((channel, cc))

    def reset(self) -> None:
        """Clear all sent history."""
        self._last_sent.clear()

    def set_per_cc(self, cc: int, min_gap_ms: float) -> None:
        """Set a per-CC override, clamped to [0, 1000]."""
        cc = max(0, min(127, cc))
        min_gap_ms = max(0.0, min(1000.0, min_gap_ms))
        self.cfg.per_cc_overrides[cc] = min_gap_ms

    def clear_per_cc(self, cc: int) -> bool:
        """Remove a per-CC override. Returns True if it existed, False otherwise."""
        cc = max(0, min(127, cc))
        if cc in self.cfg.per_cc_overrides:
            del self.cfg.per_cc_overrides[cc]
            return True
        return False

    def effective_gap_ms(self, cc: int) -> float:
        """Return the effective gap for this CC (override or default)."""
        cc = max(0, min(127, cc))
        return self.cfg.per_cc_overrides.get(cc, self.cfg.default_min_gap_ms)
