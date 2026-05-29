"""Glide/portamento helper: smoothly interpolate target values (notes, CC) over time."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional


@dataclass
class GlideConfig:
    """Configuration for glide/portamento behavior."""

    enabled: bool = False
    glide_time_s: float = 0.1
    mode: str = "linear"

    def __post_init__(self) -> None:
        """Clamp glide_time_s to valid range."""
        self.glide_time_s = max(0.001, min(5.0, self.glide_time_s))
        if self.mode not in ("linear", "exponential"):
            self.mode = "linear"

    def to_dict(self) -> dict:
        """Serialize to dict."""
        return {
            "enabled": self.enabled,
            "glide_time_s": self.glide_time_s,
            "mode": self.mode,
        }

    @staticmethod
    def from_dict(d: dict) -> GlideConfig:
        """Deserialize from dict."""
        return GlideConfig(
            enabled=d.get("enabled", False),
            glide_time_s=d.get("glide_time_s", 0.1),
            mode=d.get("mode", "linear"),
        )


class Glider:
    """Smoothly interpolates a target value (note or CC) over time."""

    def __init__(self, cfg: GlideConfig) -> None:
        """Initialize glider with config."""
        self.cfg = cfg
        self.current: Optional[float] = None
        self.target: Optional[float] = None
        self.target_set_at: Optional[float] = None
        self.source_value: Optional[float] = None

    def set_target(self, target: float, now_s: float) -> None:
        """
        Set the target value.

        If current is None, snap current to target immediately.
        Otherwise, first compute current value at now_s, stash it as source, and begin glide.
        """
        if self.current is None:
            self.current = target
            self.target = target
            self.source_value = target
            self.target_set_at = now_s
        else:
            # Update current to where it would be at now_s before changing target.
            current_at_now = self.value_at(now_s)
            self.source_value = current_at_now if current_at_now is not None else self.current
            self.target = target
            self.target_set_at = now_s

    def value_at(self, now_s: float) -> Optional[float]:
        """
        Return interpolated value at a given time.

        - If current is None, return None.
        - If glide disabled or glide_time <= 0, snap current to target and return target.
        - Otherwise, interpolate from source_value to target based on elapsed time.
        """
        if self.current is None:
            return None

        if not self.cfg.enabled or self.cfg.glide_time_s <= 0.0:
            assert self.target is not None
            self.current = self.target
            return self.target

        # If target_set_at is None, we've snapped but haven't moved yet.
        # Treat as if we just started gliding from current to target.
        if self.target_set_at is None:
            self.target_set_at = now_s
            self.source_value = self.current

        assert self.target is not None and self.target_set_at is not None
        assert self.source_value is not None

        elapsed = now_s - self.target_set_at
        progress = elapsed / self.cfg.glide_time_s

        if progress >= 1.0:
            self.current = self.target
            return self.target

        # Interpolate based on mode.
        if self.cfg.mode == "exponential":
            # Exponential: fast initial approach, asymptotic finish.
            # 1 - exp(-x * 5) goes from 0 to ~0.993 as x goes 0 to 1.
            ease = 1.0 - math.exp(-progress * 5.0)
        else:
            # Linear (default).
            ease = progress

        value = self.source_value + (self.target - self.source_value) * ease
        self.current = value
        return value

    def is_settled(self, now_s: float) -> bool:
        """
        Return True when glide has finished.

        True if value_at == target (i.e. progress >= 1.0 or source == target).
        """
        if self.current is None or self.target is None:
            return True
        if self.source_value == self.target:
            return True
        if not self.cfg.enabled or self.cfg.glide_time_s <= 0.0:
            return True

        assert self.target_set_at is not None
        elapsed = now_s - self.target_set_at
        progress = elapsed / self.cfg.glide_time_s
        return progress >= 1.0

    def snap(self, value: float) -> None:
        """Jump immediately to a value."""
        self.current = value
        self.target = value
        self.source_value = value
        self.target_set_at = None

    def reset(self) -> None:
        """Clear all state."""
        self.current = None
        self.target = None
        self.source_value = None
        self.target_set_at = None
