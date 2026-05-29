"""Random-walk modulation source: CC values drift smoothly within bounds.
Organic, less predictable alternative to LFO.

Pure stdlib + random, no Qt, no global state.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Optional


@dataclass
class RandomWalkConfig:
    """Configuration for a random-walk modulation source."""
    enabled: bool = False
    cc: int = 1  # clamp 0..127
    channel: int = 1  # clamp 1..16
    min_value: int = 0  # clamp 0..127
    max_value: int = 127  # clamp 0..127; if max < min, swap on deserialize
    step_size: int = 5  # clamp 1..64; how far each step can drift
    step_rate_hz: float = 4.0  # clamp 0.1..50.0
    seed: Optional[int] = None  # optional seed for deterministic RNG

    def __post_init__(self):
        """Validate and clamp all fields to legal ranges."""
        self.enabled = bool(self.enabled)
        self.cc = max(0, min(127, int(self.cc)))
        self.channel = max(1, min(16, int(self.channel)))
        self.min_value = max(0, min(127, int(self.min_value)))
        self.max_value = max(0, min(127, int(self.max_value)))
        self.step_size = max(1, min(64, int(self.step_size)))
        self.step_rate_hz = max(0.1, min(50.0, float(self.step_rate_hz)))

        # Swap min/max if inverted
        if self.max_value < self.min_value:
            self.min_value, self.max_value = self.max_value, self.min_value

        # Seed is optional; None is valid
        if self.seed is not None:
            self.seed = int(self.seed)

    def to_dict(self) -> dict:
        """Round-trip serialization to dict."""
        return {
            "enabled": self.enabled,
            "cc": self.cc,
            "channel": self.channel,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "step_size": self.step_size,
            "step_rate_hz": self.step_rate_hz,
            "seed": self.seed,
        }

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> RandomWalkConfig:
        """Deserialize from dict; missing keys use defaults."""
        if data is None:
            return cls()
        return cls(
            enabled=data.get("enabled", False),
            cc=data.get("cc", 1),
            channel=data.get("channel", 1),
            min_value=data.get("min_value", 0),
            max_value=data.get("max_value", 127),
            step_size=data.get("step_size", 5),
            step_rate_hz=data.get("step_rate_hz", 4.0),
            seed=data.get("seed", None),
        )


class RandomWalk:
    """Stateful random-walk engine: drifts a CC value smoothly within bounds.
    Uses reflection at boundaries to keep values within [min_value, max_value].
    """

    def __init__(self, cfg: RandomWalkConfig, start_value: Optional[int] = None):
        """Initialize with config and optional start value.

        Args:
            cfg: RandomWalkConfig instance
            start_value: initial value (clamped to [min, max]). If None, use midpoint.
        """
        self.cfg = cfg
        self.rng = random.Random(cfg.seed)

        # Set current value
        if start_value is None:
            self.current = (cfg.min_value + cfg.max_value) // 2
        else:
            self.current = max(cfg.min_value, min(cfg.max_value, int(start_value)))

        self.last_step_at: Optional[float] = None

    def step(self, now_s: float) -> Optional[int]:
        """Attempt to step the random walk at the configured rate.

        Returns the new value (int in [min_value, max_value]) if enough time
        has elapsed since the last step. Returns None if called too soon.

        Uses reflection at boundaries: if a step would exceed the bounds,
        reflect it back (e.g., if max is 127 and candidate is 135, reflect
        to 127 - (135 - 127) = 119).
        """
        # Check if enough time has elapsed
        min_step_interval = 1.0 / self.cfg.step_rate_hz
        if self.last_step_at is not None and (now_s - self.last_step_at) < min_step_interval:
            return None

        # Generate random step
        delta = self.rng.randint(-self.cfg.step_size, self.cfg.step_size)
        candidate = self.current + delta

        # Reflect at boundaries
        if candidate < self.cfg.min_value:
            candidate = self.cfg.min_value + (self.cfg.min_value - candidate)
        elif candidate > self.cfg.max_value:
            candidate = self.cfg.max_value - (candidate - self.cfg.max_value)

        # Final clamp to [min, max] after reflection
        self.current = max(self.cfg.min_value, min(self.cfg.max_value, candidate))
        self.last_step_at = now_s

        return self.current

    def value(self) -> int:
        """Return current value without stepping."""
        return self.current

    def reset(self, value: Optional[int] = None) -> None:
        """Reset state: current value and last_step_at.

        Args:
            value: new current value. If None, use midpoint of range.
        """
        if value is None:
            self.current = (self.cfg.min_value + self.cfg.max_value) // 2
        else:
            self.current = max(self.cfg.min_value, min(self.cfg.max_value, int(value)))
        self.last_step_at = None

    def set_seed(self, seed: int) -> None:
        """Re-seed the internal RNG for deterministic replay."""
        self.rng = random.Random(int(seed))
