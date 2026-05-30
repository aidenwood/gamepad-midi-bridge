"""Trigger noise gate — squelches small fluctuations in analog trigger pressure.

Holds the current output value until pressure changes by more than a threshold,
filtering out jitter and contact noise from analog trigger streams.

This is a pure-stdlib, non-Qt module. Stateful class with hysteresis: upward
changes require larger deltas than downward changes.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class TriggerNoiseGateConfig:
    """Configuration for trigger noise gate filtering."""

    enabled: bool = False
    threshold: float = 0.01
    release_threshold: float = 0.005
    hysteresis_factor: float = 1.5

    def __post_init__(self) -> None:
        """Clamp thresholds and hysteresis_factor to valid ranges."""
        # Clamp threshold to 0..0.5
        if self.threshold < 0:
            self.threshold = 0
        elif self.threshold > 0.5:
            self.threshold = 0.5

        # Clamp release_threshold to 0..0.5
        if self.release_threshold < 0:
            self.release_threshold = 0
        elif self.release_threshold > 0.5:
            self.release_threshold = 0.5

        # Clamp hysteresis_factor to 1..5
        if self.hysteresis_factor < 1:
            self.hysteresis_factor = 1
        elif self.hysteresis_factor > 5:
            self.hysteresis_factor = 5

    def to_dict(self) -> dict[str, Any]:
        """Serialize config to a dict."""
        return {
            "enabled": self.enabled,
            "threshold": self.threshold,
            "release_threshold": self.release_threshold,
            "hysteresis_factor": self.hysteresis_factor,
        }

    @staticmethod
    def from_dict(d: dict[str, Any]) -> TriggerNoiseGateConfig:
        """Deserialize config from a dict, with safe defaults."""
        return TriggerNoiseGateConfig(
            enabled=d.get("enabled", False),
            threshold=d.get("threshold", 0.01),
            release_threshold=d.get("release_threshold", 0.005),
            hysteresis_factor=d.get("hysteresis_factor", 1.5),
        )


class TriggerNoiseGate:
    """Stateful trigger noise gate that filters pressure fluctuations."""

    # Small epsilon for floating-point comparison to handle precision issues
    _EPSILON = 1e-9

    def __init__(self, cfg: TriggerNoiseGateConfig) -> None:
        """Initialize the gate with the given config.

        Args:
            cfg: TriggerNoiseGateConfig instance.
        """
        self.cfg = cfg
        self._last_value: Optional[float] = None
        self._suppressed_count: int = 0
        self._passed_count: int = 0

    def feed(self, pressure: float) -> Optional[float]:
        """Feed a pressure value through the noise gate.

        Clamps pressure to 0..1 and applies hysteresis filtering. Returns
        the pressure if it should pass, or None if suppressed by the gate.

        Args:
            pressure: Analog trigger pressure (0..1). Automatically clamped.

        Returns:
            Pressure value (0..1) if passed, or None if suppressed by gate.
        """
        # Clamp pressure to 0..1
        if pressure < 0:
            pressure = 0
        elif pressure > 1:
            pressure = 1

        # If not enabled, return pressure unchanged
        if not self.cfg.enabled:
            return pressure

        # First feed: emit initial value
        if self._last_value is None:
            self._last_value = pressure
            self._passed_count += 1
            return pressure

        # Release condition: if pressure drops below release_threshold
        # and last_value was above it, emit 0 (release)
        if pressure <= self.cfg.release_threshold and self._last_value > self.cfg.release_threshold:
            self._last_value = 0
            self._passed_count += 1
            return 0

        # Calculate delta
        delta = abs(pressure - self._last_value)

        # Determine required threshold based on direction
        if pressure > self._last_value:
            # Upward change: apply hysteresis multiplier
            required_delta = self.cfg.threshold * self.cfg.hysteresis_factor
        else:
            # Downward change: use raw threshold
            required_delta = self.cfg.threshold

        # If delta is below required threshold, suppress
        # Use epsilon for floating-point comparison
        if delta < required_delta - self._EPSILON:
            self._suppressed_count += 1
            return None

        # Emit new value
        self._last_value = pressure
        self._passed_count += 1
        return pressure

    def last_emitted(self) -> Optional[float]:
        """Return the last emitted pressure value, or None if nothing emitted yet.

        Returns:
            The last pressure value that passed the gate, or None.
        """
        return self._last_value

    def reset(self) -> None:
        """Reset the gate state and statistics."""
        self._last_value = None
        self._suppressed_count = 0
        self._passed_count = 0

    def stats(self) -> dict[str, int]:
        """Return a dict of current statistics.

        Returns:
            {"suppressed": int, "passed": int}
        """
        return {
            "suppressed": self._suppressed_count,
            "passed": self._passed_count,
        }
