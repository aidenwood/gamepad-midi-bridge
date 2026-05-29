"""Pure-function velocity curve transforms for pressure and button inputs.

This module maps a normalised input value in the range [0.0, 1.0]
(e.g. trigger pressure or "how fast was the button pressed") into a MIDI
velocity value (1..127) using several response curves.

Every helper here is stateless and deterministic. Why a separate module:
  - Unit-test the velocity math in isolation, without bridge.py side effects.
  - Lets the UI preview curves (sparkline, graph) without launching MIDI.
  - Keeps bridge.py focused on I/O and per-tick polling.
  - Room for new curve modes (sigmoid, inverse sqrt, etc.) without bloat.

Curve shapes:
  - linear: y = x (1:1 response)
  - soft: y = x^0.5 (boosts low input, softens the touch)
  - hard: y = x^2 (penalises low input, needs confident press)
  - exponential: curved growth, biases high
  - logarithmic: curved growth the other way, biases low
  - s_curve: smooth ease-in-out (slow ramp start, then quick middle, slow finish)
  - fixed: always returns a fixed value, ignoring input
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List


# Canonical list of curve modes — used by UI dropdowns and validation.
VELOCITY_CURVE_MODES = ("linear", "soft", "hard", "fixed", "exponential", "logarithmic", "s_curve")
DEFAULT_VELOCITY_CURVE_MODE = "linear"


@dataclass
class VelocityCurveConfig:
    """Configuration for velocity curve transformation.

    Attributes:
        enabled: Whether velocity curve is active. If False, the consumer
                 should not call compute_velocity (the module doesn't enforce it).
        curve: Curve mode. One of VELOCITY_CURVE_MODES; unknown → "linear".
        fixed_velocity: When curve="fixed", the output value (1..127).
                       Clamped on deserialize.
        min_velocity: Minimum output velocity (1..127). Clamped on deserialize.
        max_velocity: Maximum output velocity (1..127). If < min_velocity on
                     deserialize, they are swapped. Clamped on deserialize.
    """
    enabled: bool = False
    curve: str = "linear"
    fixed_velocity: int = 100
    min_velocity: int = 1
    max_velocity: int = 127

    def __post_init__(self) -> None:
        """Normalize and clamp all velocity values after construction."""
        # Normalise curve mode: unknown → linear.
        if self.curve not in VELOCITY_CURVE_MODES:
            self.curve = "linear"

        # Clamp fixed_velocity to 1..127.
        self.fixed_velocity = max(1, min(127, self.fixed_velocity))

        # Clamp min/max to 1..127.
        self.min_velocity = max(1, min(127, self.min_velocity))
        self.max_velocity = max(1, min(127, self.max_velocity))

        # If max < min, swap them.
        if self.max_velocity < self.min_velocity:
            self.min_velocity, self.max_velocity = self.max_velocity, self.min_velocity

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "enabled": self.enabled,
            "curve": self.curve,
            "fixed_velocity": self.fixed_velocity,
            "min_velocity": self.min_velocity,
            "max_velocity": self.max_velocity,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> VelocityCurveConfig:
        """Deserialize from a dict (e.g. from JSON).

        Missing keys fall back to dataclass defaults. __post_init__ handles
        normalisation and clamping.
        """
        return cls(
            enabled=data.get("enabled", False),
            curve=data.get("curve", "linear"),
            fixed_velocity=data.get("fixed_velocity", 100),
            min_velocity=data.get("min_velocity", 1),
            max_velocity=data.get("max_velocity", 127),
        )


def _apply_curve_shape(input_0_1: float, curve: str) -> float:
    """Apply a curve transformation to a normalised input.

    Args:
        input_0_1: Normalised input [0.0, 1.0]. Will be clamped by caller.
        curve: One of VELOCITY_CURVE_MODES.

    Returns:
        Transformed value in [0.0, 1.0].
    """
    # Clamp input in case it sneaks through.
    x = max(0.0, min(1.0, input_0_1))

    if curve == "soft":
        # y = x^0.5 — boost low input, soften the touch.
        return math.sqrt(x)
    elif curve == "hard":
        # y = x^2 — penalise low input, needs confident press.
        return x * x
    elif curve == "exponential":
        # y = (exp(2*x) - 1) / (exp(2) - 1) — curved growth biased high.
        exp_2 = math.exp(2.0)
        return (math.exp(2.0 * x) - 1.0) / (exp_2 - 1.0)
    elif curve == "logarithmic":
        # y = log(1 + 9*x) / log(10) — curved growth biased low.
        return math.log(1.0 + 9.0 * x) / math.log(10.0)
    elif curve == "s_curve":
        # y = (1 - cos(x*pi)) / 2 — smooth ease-in-out.
        return (1.0 - math.cos(x * math.pi)) / 2.0
    else:
        # linear (or unknown) — y = x.
        return x


def compute_velocity(input_0_1: float, cfg: VelocityCurveConfig) -> int:
    """Compute a MIDI velocity value from a normalised input.

    Args:
        input_0_1: Normalised input [0.0, 1.0], e.g. trigger pressure or
                  button press speed. Values outside this range are clamped.
        cfg: VelocityCurveConfig describing the curve, range, and mode.

    Returns:
        MIDI velocity value (1..127).
    """
    # Clamp input to [0, 1].
    x = max(0.0, min(1.0, input_0_1))

    # Fixed mode: return fixed_velocity regardless of input.
    if cfg.curve == "fixed":
        return max(cfg.min_velocity, min(cfg.max_velocity, cfg.fixed_velocity))

    # Apply the curve transformation.
    y = _apply_curve_shape(x, cfg.curve)

    # Lerp from min_velocity to max_velocity using the transformed input.
    output = cfg.min_velocity + y * (cfg.max_velocity - cfg.min_velocity)

    # Round to nearest int and clamp to 1..127 as a safety net.
    return max(1, min(127, round(output)))


def preview_curve(cfg: VelocityCurveConfig, samples: int = 16) -> List[int]:
    """Generate a list of velocity samples for UI sparkline/graph preview.

    Samples the curve at evenly spaced input points from 0 to 1.

    Args:
        cfg: VelocityCurveConfig to preview.
        samples: Number of samples (must be >= 2). Defaults to 16.

    Returns:
        List of MIDI velocity values (1..127).
    """
    if samples < 2:
        samples = 2

    result = []
    for i in range(samples):
        # Sample at i/(samples-1), so we get 0.0 at start and 1.0 at end.
        t = i / (samples - 1) if samples > 1 else 0.0
        velocity = compute_velocity(t, cfg)
        result.append(velocity)

    return result
