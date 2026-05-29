"""Pure-function CC value smoother for analog input smoothing.

This module provides stateful CC value smoothing filters to clean up jittery
raw analog input (stick position, trigger pressure, touchpad) into smooth CC
streams suitable for MIDI control.

Smoothing modes:
  - one_pole: Single-pole exponential low-pass filter (alpha blending).
             Higher smoothing = more lag, less jitter.
  - slew: Rate-limiter. Bounds change per call (max_delta_per_call).
          Gentler than one_pole, preserves detail better.
  - moving_avg: Simple windowed moving average over recent samples.
                Window size determines responsiveness vs noise.
  - none: Passthrough (no smoothing).

Every filter also supports deadband suppression: changes smaller than the
deadband threshold are ignored, output stays at last emitted value.

Why separate:
  - Stateful per-input (needs mutable history/state).
  - Deterministic, repeatable, testable.
  - Easy to debug jittery stick inputs in isolation.
  - Room for new modes (Butterworth, Kalman) without bridge.py bloat.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


# Canonical list of smoother modes — used by UI dropdowns and validation.
CC_SMOOTHER_MODES = ("one_pole", "slew", "moving_avg", "none")
DEFAULT_CC_SMOOTHER_MODE = "one_pole"


@dataclass
class SmootherConfig:
    """Configuration for CC value smoothing.

    Attributes:
        enabled: Whether smoothing is active. If False, feed() returns raw input unchanged.
        mode: Smoothing mode. One of CC_SMOOTHER_MODES; unknown → "one_pole".
        smoothing: Alpha for one_pole filter (0.0..0.99). Higher = more smoothing / more lag.
                  Clamped on deserialize.
        max_delta_per_call: Max change per feed() call for slew mode (1..127).
                           Clamped on deserialize.
        window_size: Number of samples to average in moving_avg mode (1..32).
                    Clamped on deserialize.
        deadband: Suppress output changes smaller than this (0..16).
                 Clamped on deserialize. Applied after filtering.
    """
    enabled: bool = False
    mode: str = "one_pole"
    smoothing: float = 0.3
    max_delta_per_call: int = 4
    window_size: int = 4
    deadband: int = 0

    def __post_init__(self) -> None:
        """Normalize and clamp all values after construction."""
        # Normalise mode: unknown → one_pole.
        if self.mode not in CC_SMOOTHER_MODES:
            self.mode = "one_pole"

        # Clamp smoothing to 0.0..0.99.
        self.smoothing = max(0.0, min(0.99, self.smoothing))

        # Clamp max_delta_per_call to 1..127.
        self.max_delta_per_call = max(1, min(127, self.max_delta_per_call))

        # Clamp window_size to 1..32.
        self.window_size = max(1, min(32, self.window_size))

        # Clamp deadband to 0..16.
        self.deadband = max(0, min(16, self.deadband))

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "enabled": self.enabled,
            "mode": self.mode,
            "smoothing": self.smoothing,
            "max_delta_per_call": self.max_delta_per_call,
            "window_size": self.window_size,
            "deadband": self.deadband,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SmootherConfig:
        """Deserialize from a dict (e.g. from JSON).

        Missing keys fall back to dataclass defaults. __post_init__ handles
        normalisation and clamping.
        """
        return cls(
            enabled=data.get("enabled", False),
            mode=data.get("mode", "one_pole"),
            smoothing=data.get("smoothing", 0.3),
            max_delta_per_call=data.get("max_delta_per_call", 4),
            window_size=data.get("window_size", 4),
            deadband=data.get("deadband", 0),
        )


class CcSmoother:
    """Stateful CC value smoother filter.

    Each input gets its own smoother instance to maintain independent state
    (current value, history, last emitted).
    """

    def __init__(self, cfg: SmootherConfig) -> None:
        """Initialize smoother with config.

        Args:
            cfg: SmootherConfig describing the filtering mode and parameters.
        """
        self.cfg = cfg
        self._current: Optional[float] = None
        self._history: List[float] = []
        self._last_emitted: Optional[int] = None

    def feed(self, raw_value: int) -> int:
        """Feed a raw value through the smoother and return the filtered output.

        Args:
            raw_value: Raw CC value (0..127).

        Returns:
            Smoothed CC value (0..127). If not enabled or mode == "none",
            returns raw_value unchanged (unless deadband suppresses it).
        """
        # Clamp input to 0..127.
        raw_value = max(0, min(127, raw_value))

        # If not enabled or mode is none, apply deadband and return raw.
        if not self.cfg.enabled or self.cfg.mode == "none":
            return self._apply_deadband(raw_value)

        # Compute the filtered value based on mode.
        if self.cfg.mode == "one_pole":
            filtered = self._feed_one_pole(raw_value)
        elif self.cfg.mode == "slew":
            filtered = self._feed_slew(raw_value)
        elif self.cfg.mode == "moving_avg":
            filtered = self._feed_moving_avg(raw_value)
        else:
            # Fallback to one_pole for unknown modes (shouldn't happen after __post_init__).
            filtered = self._feed_one_pole(raw_value)

        # Apply deadband: if change is smaller than threshold, keep last output.
        return self._apply_deadband(filtered)

    def _feed_one_pole(self, raw_value: int) -> int:
        """One-pole low-pass filter (exponential averaging)."""
        if self._current is None:
            self._current = float(raw_value)
        else:
            # _current = _current * smoothing + raw_value * (1 - smoothing)
            # Note: smoothing is the retention factor; higher smoothing = more lag.
            self._current = (
                self._current * self.cfg.smoothing
                + float(raw_value) * (1.0 - self.cfg.smoothing)
            )
        return round(self._current)

    def _feed_slew(self, raw_value: int) -> int:
        """Slew rate limiter (bounded delta per call)."""
        if self._current is None:
            self._current = float(raw_value)
        else:
            # Clamp delta to [-max_delta, +max_delta].
            delta = float(raw_value) - self._current
            delta = max(
                -self.cfg.max_delta_per_call,
                min(self.cfg.max_delta_per_call, delta),
            )
            self._current = self._current + delta
        return round(self._current)

    def _feed_moving_avg(self, raw_value: int) -> int:
        """Windowed moving average."""
        self._history.append(float(raw_value))

        # Truncate to window_size.
        if len(self._history) > self.cfg.window_size:
            self._history = self._history[-self.cfg.window_size :]

        # Compute mean.
        avg = sum(self._history) / len(self._history)
        return round(avg)

    def _apply_deadband(self, filtered: int) -> int:
        """Apply deadband suppression.

        If change from last_emitted is smaller than deadband, return last_emitted.
        Otherwise, update last_emitted and return filtered.
        """
        if self._last_emitted is None:
            # First call: emit unconditionally.
            self._last_emitted = filtered
            return filtered

        # Check if change is below deadband threshold.
        change = abs(filtered - self._last_emitted)
        if change < self.cfg.deadband:
            # Suppress; return previous output.
            return self._last_emitted

        # Change is significant; update and emit.
        self._last_emitted = filtered
        return filtered

    def reset(self, value: Optional[int] = None) -> None:
        """Reset the smoother state.

        Args:
            value: If provided, initialise _current and _last_emitted to this value.
                   If None, clear state completely.
        """
        if value is not None:
            self._current = float(value)
            self._last_emitted = value
        else:
            self._current = None
            self._last_emitted = None
        self._history = []

    def last(self) -> Optional[int]:
        """Return the last emitted value.

        Returns:
            Last output value, or None if no output has been emitted yet.
        """
        return self._last_emitted
