"""Pure-function stick velocity and acceleration tracker.

This module provides stateless stick motion analysis: takes timestamped (x, y)
samples and computes instantaneous and smoothed velocity, speed, and acceleration
in axis_units/second.

Why separate:
  - Stateful per-stick (needs mutable sample history).
  - Deterministic, repeatable, testable.
  - Pure stdlib + math only (no Qt, no global state).
  - Room for expansion (e.g. jerk, direction, spin detection).
  - Velocity and acceleration are useful for adaptive MIDI mapping:
    e.g. trigger haptics when speed crosses a threshold, or scale CC
    range based on movement rate.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class StickVelocityConfig:
    """Configuration for stick velocity / acceleration tracking.

    Attributes:
        enabled: Whether tracking is active. If False, sample() still accepts
                data but returns zeros.
        smoothing: Alpha for one-pole filter on velocity (0.0..0.99).
                  Higher = more lag, less noise. Clamped on deserialize.
        velocity_scale: Linear multiplier for vx/vy output (0.01..100).
                       Clamped on deserialize.
        max_history: Max sample history to keep (2..256).
                    Clamped on deserialize.
    """
    enabled: bool = False
    smoothing: float = 0.3
    velocity_scale: float = 1.0
    max_history: int = 16

    def __post_init__(self) -> None:
        """Normalise and clamp all values after construction."""
        # Clamp smoothing to 0.0..0.99.
        self.smoothing = max(0.0, min(0.99, self.smoothing))

        # Clamp velocity_scale to 0.01..100.
        self.velocity_scale = max(0.01, min(100.0, self.velocity_scale))

        # Clamp max_history to 2..256.
        self.max_history = max(2, min(256, self.max_history))

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "enabled": self.enabled,
            "smoothing": self.smoothing,
            "velocity_scale": self.velocity_scale,
            "max_history": self.max_history,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> StickVelocityConfig:
        """Deserialize from a dict (e.g. from JSON).

        Missing keys fall back to dataclass defaults. __post_init__ handles
        normalisation and clamping.
        """
        return cls(
            enabled=data.get("enabled", False),
            smoothing=data.get("smoothing", 0.3),
            velocity_scale=data.get("velocity_scale", 1.0),
            max_history=data.get("max_history", 16),
        )


class StickVelocityTracker:
    """Stateful stick motion tracker.

    Each stick gets its own tracker instance to maintain independent state
    (sample history, smoothed velocity).
    """

    def __init__(self, cfg: StickVelocityConfig) -> None:
        """Initialize tracker with config.

        Args:
            cfg: StickVelocityConfig describing tracking parameters.
        """
        self.cfg = cfg
        # History: list of (timestamp, x, y) tuples.
        self._history: List[Tuple[float, float, float]] = []
        # Smoothed velocity components (axis_units/sec).
        self._smoothed_vx: float = 0.0
        self._smoothed_vy: float = 0.0
        # Last computed values (for current() calls).
        self._last_result: Dict[str, float] = {
            "vx": 0.0,
            "vy": 0.0,
            "speed": 0.0,
            "ax": 0.0,
            "ay": 0.0,
        }

    def sample(self, x: float, y: float, now_s: float) -> Dict[str, float]:
        """Feed a timestamped stick position and return computed motion.

        Args:
            x: X position (axis units, typically -1.0..1.0).
            y: Y position (axis units, typically -1.0..1.0).
            now_s: Timestamp in seconds (e.g. from time.time()).

        Returns:
            Dict with keys:
              - "vx", "vy": velocity components (axis_units/sec, smoothed).
              - "speed": magnitude of velocity (always >= 0).
              - "ax", "ay": acceleration components (velocity_units/sec^2).
        """
        # Append to history (capped at max_history).
        self._history.append((now_s, x, y))
        if len(self._history) > self.cfg.max_history:
            self._history = self._history[-self.cfg.max_history :]

        # Compute velocity from last two samples.
        vx, vy = 0.0, 0.0
        if len(self._history) >= 2:
            t_now, x_now, y_now = self._history[-1]
            t_prev, x_prev, y_prev = self._history[-2]
            dt = t_now - t_prev
            if dt > 0:
                vx = (x_now - x_prev) / dt
                vy = (y_now - y_prev) / dt

        # Apply velocity_scale.
        vx *= self.cfg.velocity_scale
        vy *= self.cfg.velocity_scale

        # One-pole smooth: smoothed = smoothed * alpha + raw * (1 - alpha).
        # Higher smoothing = more retention of previous value = more lag.
        if self.cfg.enabled:
            self._smoothed_vx = (
                self._smoothed_vx * self.cfg.smoothing
                + vx * (1.0 - self.cfg.smoothing)
            )
            self._smoothed_vy = (
                self._smoothed_vy * self.cfg.smoothing
                + vy * (1.0 - self.cfg.smoothing)
            )
        else:
            # If disabled, still track raw values (no smoothing).
            self._smoothed_vx = vx
            self._smoothed_vy = vy

        # Compute speed (magnitude).
        speed = math.sqrt(self._smoothed_vx ** 2 + self._smoothed_vy ** 2)

        # Compute acceleration from last three samples.
        ax, ay = 0.0, 0.0
        if len(self._history) >= 3:
            # Current and previous velocities.
            t_now, _, _ = self._history[-1]
            t_prev1, x_prev1, y_prev1 = self._history[-2]
            t_prev2, x_prev2, y_prev2 = self._history[-3]

            dt1 = t_now - t_prev1
            dt2 = t_prev1 - t_prev2

            if dt1 > 0 and dt2 > 0:
                # Velocity at t_prev1.
                vx_prev = (x_prev1 - x_prev2) / dt2 * self.cfg.velocity_scale
                vy_prev = (y_prev1 - y_prev2) / dt2 * self.cfg.velocity_scale

                # Acceleration: (v_now - v_prev) / dt.
                ax = (self._smoothed_vx - vx_prev) / dt1
                ay = (self._smoothed_vy - vy_prev) / dt1

        # Build result dict and cache it.
        self._last_result = {
            "vx": self._smoothed_vx,
            "vy": self._smoothed_vy,
            "speed": speed,
            "ax": ax,
            "ay": ay,
        }

        return self._last_result

    def current(self) -> Dict[str, float]:
        """Return the last computed motion values.

        Returns:
            Dict with keys "vx", "vy", "speed", "ax", "ay".
            If no samples have been fed, returns all zeros.
        """
        return self._last_result.copy()

    def reset(self) -> None:
        """Reset the tracker state (clear history and smoothed values)."""
        self._history = []
        self._smoothed_vx = 0.0
        self._smoothed_vy = 0.0
        self._last_result = {
            "vx": 0.0,
            "vy": 0.0,
            "speed": 0.0,
            "ax": 0.0,
            "ay": 0.0,
        }

    def to_cc(
        self,
        axis: str = "speed",
        min_value: int = 0,
        max_value: int = 127,
        clip_at_speed: float = 5.0,
    ) -> int:
        """Map a motion axis to a MIDI CC value (0..127).

        Args:
            axis: Which axis to map. One of "speed", "vx", "vy", "ax", "ay".
                 "speed" and acceleration magnitudes are always >= 0.
                 "vx"/"vy" can be negative (direction-aware).
            min_value: CC value at 0 motion (0..127).
            max_value: CC value at clip_at_speed motion (0..127).
            clip_at_speed: Motion magnitude that saturates at max_value.

        Returns:
            Clamped CC value (min_value..max_value).
        """
        # Get the raw value from the appropriate axis.
        if axis == "speed":
            raw = self._last_result["speed"]
        elif axis == "vx":
            raw = abs(self._last_result["vx"])
        elif axis == "vy":
            raw = abs(self._last_result["vy"])
        elif axis == "ax":
            raw = abs(self._last_result["ax"])
        elif axis == "ay":
            raw = abs(self._last_result["ay"])
        else:
            # Unknown axis defaults to speed.
            raw = self._last_result["speed"]

        # Linear interpolation: raw=0 → min_value, raw=clip_at_speed → max_value.
        if clip_at_speed <= 0:
            # Edge case: no clipping.
            cc_value = max_value
        else:
            # Normalized [0, 1].
            norm = min(1.0, raw / clip_at_speed)
            # Interpolate between min and max.
            cc_value = min_value + norm * (max_value - min_value)

        # Clamp to [min_value, max_value] and round to int.
        cc_value = max(min_value, min(max_value, cc_value))
        return round(cc_value)
