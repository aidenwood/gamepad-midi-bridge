"""Pure-function LED brightness curve transforms for smooth lightbar fades.

This module provides stateless brightness curve transforms in the range [0.0, 1.0]
used for smooth LED fades and oscillatory breathing effects on the DualSense lightbar.

Every helper here is pure math (stdlib + math only). Why a separate module:
  - Unit-test brightness math in isolation, without Qt or bridge.py side effects.
  - Lets the UI preview curves (sparkline, graph) without launching MIDI.
  - Stateful fade state (BrightnessFade) encapsulates timing and looping.
  - Room for new curve modes without bloat.

Curve shapes:
  - linear: y = x (1:1 fade, no easing)
  - ease_in: y = x^2 (slow start, accelerate)
  - ease_out: y = 1 - (1-x)^2 (fast start, decelerate)
  - ease_in_out_cubic: smoothstep cubic (slow → fast → slow)
  - exponential: biases low, exponential growth
  - breathing: cosine oscillation, pulsing wave (periods controls frequency)
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, Optional


# Canonical list of curve modes — used by UI dropdowns and validation.
BRIGHTNESS_CURVE_MODES = (
    "linear",
    "ease_in",
    "ease_out",
    "ease_in_out_cubic",
    "exponential",
    "breathing",
)
DEFAULT_BRIGHTNESS_CURVE_MODE = "ease_in_out_cubic"


# ============================================================================
# Pure curve functions
# ============================================================================


def linear(progress: float) -> float:
    """Linear fade: y = x (1:1).

    Args:
        progress: Normalised progress [0.0, 1.0].

    Returns:
        Clamped output in [0.0, 1.0].
    """
    return max(0.0, min(1.0, progress))


def ease_in(progress: float) -> float:
    """Ease-in (quadratic): y = x^2.

    Slow start, accelerating end. Useful for subtle opens.

    Args:
        progress: Normalised progress [0.0, 1.0].

    Returns:
        Clamped output in [0.0, 1.0].
    """
    p = max(0.0, min(1.0, progress))
    return p * p


def ease_out(progress: float) -> float:
    """Ease-out (inverse quadratic): y = 1 - (1-x)^2.

    Fast start, decelerating end. Useful for smooth closes.

    Args:
        progress: Normalised progress [0.0, 1.0].

    Returns:
        Clamped output in [0.0, 1.0].
    """
    p = max(0.0, min(1.0, progress))
    return 1.0 - (1.0 - p) * (1.0 - p)


def ease_in_out_cubic(progress: float) -> float:
    """Smoothstep cubic: slow → fast → slow.

    If p < 0.5: 4*p^3; else: 1 - pow(-2*p + 2, 3) / 2.

    Args:
        progress: Normalised progress [0.0, 1.0].

    Returns:
        Clamped output in [0.0, 1.0].
    """
    p = max(0.0, min(1.0, progress))
    if p < 0.5:
        return 4.0 * p * p * p
    else:
        return 1.0 - ((-2.0 * p + 2.0) ** 3) / 2.0


def exponential(progress: float) -> float:
    """Exponential fade: (exp(2*p) - 1) / (exp(2) - 1).

    Biases low values, then accelerates sharply. Useful for sudden bright peaks.

    Args:
        progress: Normalised progress [0.0, 1.0].

    Returns:
        Clamped output in [0.0, 1.0].
    """
    p = max(0.0, min(1.0, progress))
    exp_2 = math.exp(2.0)
    return (math.exp(2.0 * p) - 1.0) / (exp_2 - 1.0)


def breathing(progress: float, periods: float = 2.0) -> float:
    """Cosine oscillation: (1 - cos(periods * 2π * p)) / 2.

    Pulsing wave oscillating between 0 and 1. Periods controls how many
    complete breaths occur over progress = [0.0, 1.0].

    Args:
        progress: Normalised progress [0.0, 1.0].
        periods: Number of complete oscillations in [0.0, 1.0]. Default 2.0.

    Returns:
        Output in [0.0, 1.0].
    """
    p = max(0.0, min(1.0, progress))
    return (1.0 - math.cos(periods * 2.0 * math.pi * p)) / 2.0


def apply_curve(curve_name: str, progress: float, **kwargs) -> float:
    """Dispatcher: apply named curve or fallback to linear.

    Args:
        curve_name: One of BRIGHTNESS_CURVE_MODES; unknown → "linear".
        progress: Normalised progress [0.0, 1.0].
        **kwargs: Extra args for specific curves (e.g., periods for breathing).

    Returns:
        Clamped output in [0.0, 1.0].
    """
    if curve_name == "ease_in":
        return ease_in(progress)
    elif curve_name == "ease_out":
        return ease_out(progress)
    elif curve_name == "ease_in_out_cubic":
        return ease_in_out_cubic(progress)
    elif curve_name == "exponential":
        return exponential(progress)
    elif curve_name == "breathing":
        periods = kwargs.get("periods", 2.0)
        return breathing(progress, periods)
    else:
        # Unknown curve → linear
        return linear(progress)


def to_brightness_byte(value_0_1: float, max_byte: int = 255) -> int:
    """Convert normalised brightness [0.0, 1.0] to 8-bit byte [0, max_byte].

    Args:
        value_0_1: Value in [0.0, 1.0].
        max_byte: Upper clamp (default 255).

    Returns:
        Integer byte value [0, max_byte].
    """
    clamped = max(0.0, min(1.0, value_0_1))
    return int(round(clamped * max_byte))


# ============================================================================
# Stateful fade configuration and runtime
# ============================================================================


@dataclass
class BrightnessFadeConfig:
    """Configuration for a brightness fade transition.

    Attributes:
        enabled: Whether fade is active. If False, consumer should not use it.
        start_value: Initial brightness byte (0..255). Clamped on __post_init__.
        end_value: Final brightness byte (0..255). Clamped on __post_init__.
        duration_s: Fade duration in seconds (0.01..60). Clamped on __post_init__.
        curve: Curve mode (one of BRIGHTNESS_CURVE_MODES; unknown → "linear").
        loop: If True, reverses and loops; if False, stops at end_value.
    """

    enabled: bool = False
    start_value: int = 0
    end_value: int = 255
    duration_s: float = 1.0
    curve: str = "ease_in_out_cubic"
    loop: bool = False

    def __post_init__(self) -> None:
        """Normalize and clamp all values after construction."""
        # Normalise curve mode: unknown → linear.
        if self.curve not in BRIGHTNESS_CURVE_MODES:
            self.curve = "linear"

        # Clamp start_value to 0..255.
        self.start_value = max(0, min(255, self.start_value))

        # Clamp end_value to 0..255.
        self.end_value = max(0, min(255, self.end_value))

        # Clamp duration to 0.01..60 seconds.
        self.duration_s = max(0.01, min(60.0, self.duration_s))

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "enabled": self.enabled,
            "start_value": self.start_value,
            "end_value": self.end_value,
            "duration_s": self.duration_s,
            "curve": self.curve,
            "loop": self.loop,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> BrightnessFadeConfig:
        """Deserialize from a dict (e.g. from JSON).

        Unknown keys are ignored; missing keys use defaults.
        """
        return cls(
            enabled=data.get("enabled", False),
            start_value=data.get("start_value", 0),
            end_value=data.get("end_value", 255),
            duration_s=data.get("duration_s", 1.0),
            curve=data.get("curve", "ease_in_out_cubic"),
            loop=data.get("loop", False),
        )


class BrightnessFade:
    """Stateful brightness fade runtime.

    Encapsulates timing and direction for smooth LED brightness transitions.
    Call start(now_s) to begin, then value(now_s) to poll the current brightness.

    Attributes:
        cfg: BrightnessFadeConfig (stores mode, values, duration).
    """

    def __init__(self, cfg: BrightnessFadeConfig) -> None:
        """Initialize fade state.

        Args:
            cfg: Configuration object (BrightnessFadeConfig).
        """
        self.cfg = cfg
        self._start_time: Optional[float] = None
        self._direction: int = 1  # 1 = forward, -1 = reverse

    def start(self, now_s: float) -> None:
        """Stamp the fade start time.

        Args:
            now_s: Current time in seconds (e.g. time.time()).
        """
        self._start_time = now_s
        self._direction = 1

    def value(self, now_s: float) -> int:
        """Compute current brightness byte.

        If not started, returns start_value. If loop=True, reverses direction
        when progress >= 1. If loop=False and progress >= 1, returns end_value
        and stops.

        Args:
            now_s: Current time in seconds (e.g. time.time()).

        Returns:
            Brightness byte (0..255).
        """
        if self._start_time is None:
            return self.cfg.start_value

        elapsed = now_s - self._start_time
        progress = elapsed / self.cfg.duration_s

        # Handle looping: reverse direction and reset start time
        if self.cfg.loop and progress >= 1.0:
            self._direction *= -1
            self._start_time = now_s - (progress - 1.0) * self.cfg.duration_s
            progress = (now_s - self._start_time) / self.cfg.duration_s

        # Clamp progress to [0.0, 1.0] for curve evaluation
        curve_progress = max(0.0, min(1.0, progress))

        # Apply curve
        eased = apply_curve(self.cfg.curve, curve_progress)

        # Determine start and end based on direction
        if self._direction == 1:
            start = self.cfg.start_value
            end = self.cfg.end_value
        else:
            start = self.cfg.end_value
            end = self.cfg.start_value

        # Lerp between start and end
        brightness_0_1 = start / 255.0 + eased * (end - start) / 255.0
        return to_brightness_byte(brightness_0_1, max_byte=255)

    def is_done(self, now_s: float) -> bool:
        """Check if fade is complete (only True when loop=False and progress >= 1).

        Args:
            now_s: Current time in seconds.

        Returns:
            True if fade finished and not looping.
        """
        if self._start_time is None or self.cfg.loop:
            return False

        elapsed = now_s - self._start_time
        progress = elapsed / self.cfg.duration_s
        return progress >= 1.0

    def reset(self) -> None:
        """Clear all internal state."""
        self._start_time = None
        self._direction = 1
