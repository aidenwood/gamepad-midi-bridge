"""Adaptive cooldown calculator that adjusts thresholds based on event rates.

This module tracks recent event rates and auto-adjusts a cooldown threshold to
balance responsiveness vs. spam protection. Pure stdlib, no Qt.

Features:
  - Configurable min/max cooldown bounds (ms).
  - Target event rate (Hz) — the cooldown adjusts to hit this rate.
  - Learning rate controls how aggressively cooldown adjusts.
  - Trailing window: only recent events within window_seconds count towards rate.
  - Pure stdlib: math + time only, deterministic and testable.
  - Serialization: to_dict() / from_dict() for config persistence.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class AdaptiveCooldownConfig:
    """Configuration for adaptive cooldown calculator.

    Attributes:
        min_cooldown_ms: Minimum cooldown in milliseconds (1..1000).
                        Clamped on construction.
        max_cooldown_ms: Maximum cooldown in milliseconds (10..10000).
                        Clamped on construction.
                        MUST be >= min_cooldown_ms.
        target_rate_hz: Target event rate in Hz (0.1..200).
                       Cooldown adjusts to hit this rate.
                       Clamped on construction.
        learn_rate: Learning rate for cooldown adjustment (0.01..1.0).
                   Higher = more aggressive adjustment.
                   Clamped on construction.
        window_seconds: Trailing window for event history (0.1..30).
                       Only events within this window count towards observed rate.
                       Clamped on construction.
    """
    min_cooldown_ms: int = 10
    max_cooldown_ms: int = 500
    target_rate_hz: float = 20.0
    learn_rate: float = 0.2
    window_seconds: float = 2.0

    def __post_init__(self) -> None:
        """Normalize and clamp all values after construction."""
        # Clamp min_cooldown_ms to 1..1000.
        self.min_cooldown_ms = max(1, min(1000, self.min_cooldown_ms))

        # Clamp max_cooldown_ms to 10..10000, ensure >= min.
        self.max_cooldown_ms = max(10, min(10000, self.max_cooldown_ms))
        if self.max_cooldown_ms < self.min_cooldown_ms:
            self.max_cooldown_ms = self.min_cooldown_ms

        # Clamp target_rate_hz to 0.1..200.
        self.target_rate_hz = max(0.1, min(200.0, self.target_rate_hz))

        # Clamp learn_rate to 0.01..1.0.
        self.learn_rate = max(0.01, min(1.0, self.learn_rate))

        # Clamp window_seconds to 0.1..30.
        self.window_seconds = max(0.1, min(30.0, self.window_seconds))

    def to_dict(self) -> Dict[str, Any]:
        """Serialize config to dict."""
        return {
            "min_cooldown_ms": self.min_cooldown_ms,
            "max_cooldown_ms": self.max_cooldown_ms,
            "target_rate_hz": self.target_rate_hz,
            "learn_rate": self.learn_rate,
            "window_seconds": self.window_seconds,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> AdaptiveCooldownConfig:
        """Deserialize config from dict."""
        return AdaptiveCooldownConfig(
            min_cooldown_ms=int(data.get("min_cooldown_ms", 10)),
            max_cooldown_ms=int(data.get("max_cooldown_ms", 500)),
            target_rate_hz=float(data.get("target_rate_hz", 20.0)),
            learn_rate=float(data.get("learn_rate", 0.2)),
            window_seconds=float(data.get("window_seconds", 2.0)),
        )


class AdaptiveCooldown:
    """Adaptive cooldown calculator that tracks event rates and adjusts threshold.

    Usage:
        cfg = AdaptiveCooldownConfig(min_cooldown_ms=10, max_cooldown_ms=500)
        cooldown = AdaptiveCooldown(cfg)

        now = time.time()
        if cooldown.allow(now):
            # Emit event
            ...

    The cooldown threshold adjusts dynamically:
    - If observed rate > target: increase cooldown (slow down).
    - If observed rate < target: decrease cooldown (speed up).
    """

    def __init__(self, config: AdaptiveCooldownConfig) -> None:
        """Initialize adaptive cooldown with config.

        Args:
            config: AdaptiveCooldownConfig instance.
        """
        self.cfg = config
        self._event_times: List[float] = []
        # Start at midpoint between min and max.
        self._current_cooldown_ms: float = (
            config.min_cooldown_ms + config.max_cooldown_ms
        ) / 2.0
        self._last_emit_at: Optional[float] = None

    def allow(self, now_s: float) -> bool:
        """Check if sufficient cooldown has elapsed; if so, accept and adjust.

        Args:
            now_s: Current time in seconds (e.g., from time.time()).

        Returns:
            True if the event is accepted (cooldown has elapsed).
            False if the event is rate-limited.

        Side effects:
            If accepted:
            - Appends now_s to event history.
            - Prunes history older than window_seconds.
            - Recalculates cooldown based on observed rate vs. target.
        """
        # First event or cooldown has elapsed?
        if self._last_emit_at is None:
            elapsed_ms = float('inf')
        else:
            elapsed_ms = (now_s - self._last_emit_at) * 1000.0

        if elapsed_ms >= self._current_cooldown_ms:
            # Accept event.
            self._last_emit_at = now_s
            self._event_times.append(now_s)

            # Prune events older than window.
            cutoff = now_s - self.cfg.window_seconds
            self._event_times = [t for t in self._event_times if t >= cutoff]

            # Recalculate cooldown.
            self._recalculate_cooldown(now_s)

            return True
        else:
            return False

    def _recalculate_cooldown(self, now_s: float) -> None:
        """Adjust cooldown based on observed rate vs. target.

        If observed_rate > target: we're running too fast → increase cooldown.
        If observed_rate < target: we're too slow → decrease cooldown.

        Args:
            now_s: Current time in seconds.
        """
        observed_rate = self.observed_rate(now_s)
        
        if observed_rate > self.cfg.target_rate_hz:
            # Too fast: increase cooldown.
            # Scale adjustment by the rate error as a fraction of target.
            error_ratio = (observed_rate - self.cfg.target_rate_hz) / self.cfg.target_rate_hz
            adjustment = (
                self.cfg.learn_rate
                * (self._current_cooldown_ms * 0.1)
                * error_ratio
            )
            self._current_cooldown_ms += adjustment
        elif observed_rate < self.cfg.target_rate_hz:
            # Too slow: decrease cooldown.
            adjustment = self.cfg.learn_rate * (self._current_cooldown_ms * 0.1)
            self._current_cooldown_ms -= adjustment

        # Clamp to [min, max].
        self._current_cooldown_ms = max(
            self.cfg.min_cooldown_ms,
            min(self.cfg.max_cooldown_ms, self._current_cooldown_ms),
        )

    def current_cooldown_ms(self) -> float:
        """Return the current cooldown threshold in milliseconds.

        Returns:
            Current cooldown in ms, clamped to [min, max].
        """
        return self._current_cooldown_ms

    def observed_rate(self, now_s: float) -> float:
        """Return observed event rate in Hz within the trailing window.

        Args:
            now_s: Current time in seconds.

        Returns:
            Events per second within window_seconds.
        """
        if self.cfg.window_seconds <= 0:
            return 0.0
        return len(self._event_times) / self.cfg.window_seconds

    def reset(self) -> None:
        """Clear state and reset cooldown to midpoint.

        Useful for re-initialization or when changing modes.
        """
        self._event_times = []
        self._current_cooldown_ms = (
            self.cfg.min_cooldown_ms + self.cfg.max_cooldown_ms
        ) / 2.0
        self._last_emit_at = None
