"""Velocity gate filter — drops or remaps note_on messages by velocity threshold.

Users can set low and high velocity thresholds with multiple modes:

- "drop": Note-on messages with velocity below low_threshold or above
  high_threshold are dropped (return None). In-range notes pass through.
- "clamp": Below-threshold notes are remapped to floor_value; above-threshold
  notes are remapped to ceiling_value; in-range notes pass through unchanged.
- "scale": Velocities below low_threshold or above high_threshold are first
  clipped to the range, then linearly remapped from [low_threshold, high_threshold]
  to [floor_value, ceiling_value].

All velocities are clamped to 1..127 after processing.

This is a pure-stdlib, non-Qt module. Stateless helper functions and a stateful
VelocityGate class for tracking dropped/passed counts.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class VelocityGateConfig:
    """Configuration for velocity gate filtering."""

    enabled: bool = False
    low_threshold: int = 1
    high_threshold: int = 127
    mode: str = "drop"
    floor_value: int = 1
    ceiling_value: int = 127

    def __post_init__(self) -> None:
        """Clamp thresholds and floor/ceiling to valid ranges; normalize mode."""
        # Clamp thresholds to 0..127
        if self.low_threshold < 0:
            self.low_threshold = 0
        elif self.low_threshold > 127:
            self.low_threshold = 127

        if self.high_threshold < 0:
            self.high_threshold = 0
        elif self.high_threshold > 127:
            self.high_threshold = 127

        # Ensure low_threshold <= high_threshold; swap if needed
        if self.low_threshold > self.high_threshold:
            self.low_threshold, self.high_threshold = self.high_threshold, self.low_threshold

        # Clamp floor and ceiling to 1..127
        if self.floor_value < 1:
            self.floor_value = 1
        elif self.floor_value > 127:
            self.floor_value = 127

        if self.ceiling_value < 1:
            self.ceiling_value = 1
        elif self.ceiling_value > 127:
            self.ceiling_value = 127

        # Normalize mode; unknown mode defaults to "drop"
        if self.mode not in ("drop", "clamp", "scale"):
            self.mode = "drop"

    def to_dict(self) -> dict[str, Any]:
        """Serialize config to a dict."""
        return {
            "enabled": self.enabled,
            "low_threshold": self.low_threshold,
            "high_threshold": self.high_threshold,
            "mode": self.mode,
            "floor_value": self.floor_value,
            "ceiling_value": self.ceiling_value,
        }

    @staticmethod
    def from_dict(d: dict[str, Any]) -> VelocityGateConfig:
        """Deserialize config from a dict, with safe defaults."""
        return VelocityGateConfig(
            enabled=d.get("enabled", False),
            low_threshold=d.get("low_threshold", 1),
            high_threshold=d.get("high_threshold", 127),
            mode=d.get("mode", "drop"),
            floor_value=d.get("floor_value", 1),
            ceiling_value=d.get("ceiling_value", 127),
        )


def apply(velocity: int, cfg: VelocityGateConfig) -> Optional[int]:
    """Apply velocity gate to a single velocity value.

    Args:
        velocity: MIDI velocity (0..127).
        cfg: VelocityGateConfig instance.

    Returns:
        Processed velocity (1..127), or None if the note should be dropped.
    """
    # If not enabled, pass through unchanged
    if not cfg.enabled:
        return velocity

    # Drop mode: return None if out of range
    if cfg.mode == "drop":
        if velocity < cfg.low_threshold or velocity > cfg.high_threshold:
            return None
        return velocity

    # Clamp mode: remap out-of-range to floor/ceiling
    if cfg.mode == "clamp":
        if velocity < cfg.low_threshold:
            result = cfg.floor_value
        elif velocity > cfg.high_threshold:
            result = cfg.ceiling_value
        else:
            result = velocity
        # Ensure final result is in 1..127
        if result < 1:
            result = 1
        elif result > 127:
            result = 127
        return result

    # Scale mode: linearly remap from [low, high] to [floor, ceiling]
    if cfg.mode == "scale":
        # Clip velocity to [low_threshold, high_threshold]
        clipped = velocity
        if clipped < cfg.low_threshold:
            clipped = cfg.low_threshold
        elif clipped > cfg.high_threshold:
            clipped = cfg.high_threshold

        # Linear interpolation: map [low, high] -> [floor, ceiling]
        low = cfg.low_threshold
        high = cfg.high_threshold
        floor = cfg.floor_value
        ceiling = cfg.ceiling_value

        if low == high:
            # Degenerate case: threshold range is a point; return floor
            result = floor
        else:
            # Linear remap: (clipped - low) / (high - low) * (ceiling - floor) + floor
            normalized = (clipped - low) / (high - low)
            result = int(normalized * (ceiling - floor) + floor)

        # Ensure final result is in 1..127
        if result < 1:
            result = 1
        elif result > 127:
            result = 127
        return result

    # Unknown mode (should not happen due to __post_init__, but be defensive)
    return velocity


class VelocityGate:
    """Stateful velocity gate that tracks dropped/passed counts."""

    def __init__(self, cfg: VelocityGateConfig) -> None:
        """Initialize the gate with the given config.

        Args:
            cfg: VelocityGateConfig instance.
        """
        self.cfg = cfg
        self._dropped_count: int = 0
        self._passed_count: int = 0

    def process(self, velocity: int) -> Optional[int]:
        """Process a velocity, update stats, and return the result.

        Args:
            velocity: MIDI velocity (0..127).

        Returns:
            Processed velocity (1..127), or None if dropped.
        """
        result = apply(velocity, self.cfg)
        if result is None:
            self._dropped_count += 1
        else:
            self._passed_count += 1
        return result

    def stats(self) -> dict[str, int]:
        """Return a dict of current statistics.

        Returns:
            {"dropped": int, "passed": int}
        """
        return {
            "dropped": self._dropped_count,
            "passed": self._passed_count,
        }

    def reset_stats(self) -> None:
        """Reset dropped and passed counts to zero."""
        self._dropped_count = 0
        self._passed_count = 0
