"""Pure-function aftertouch pressure curve transforms for pressure inputs.

This module maps a normalised input value in the range [0.0, 1.0]
(e.g. trigger pressure or button pressure) into a MIDI aftertouch value (0..127)
using several response curves with optional threshold (dead-zone) and ceiling (clip).

Every helper here is stateless and deterministic. Why a separate module:
  - Unit-test the aftertouch math in isolation, without bridge.py side effects.
  - Lets the UI preview curves (sparkline, graph) without launching MIDI.
  - Keeps bridge.py focused on I/O and per-tick polling.
  - Room for new curve modes (sigmoid, inverse sqrt, etc.) without bloat.

Curve shapes:
  - linear: y = x (1:1 response)
  - soft: y = x^0.5 (boosts low input, softens the touch)
  - hard: y = x^2 (penalises low input, needs confident press)
  - stepped: y = floor(x * step_count) / (step_count - 1) (quantised levels)
  - exponential: curved growth, biases high
  - logarithmic: curved growth the other way, biases low
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List


# Canonical list of curve modes — used by UI dropdowns and validation.
AFTERTOUCH_CURVE_MODES = ("linear", "soft", "hard", "stepped", "exponential", "logarithmic")
DEFAULT_AFTERTOUCH_CURVE_MODE = "linear"


@dataclass
class AftertouchCurveConfig:
    """Configuration for aftertouch pressure curve transformation.

    Attributes:
        enabled: Whether aftertouch curve is active. If False, the consumer
                 should not call compute_pressure (the module doesn't enforce it).
        curve: Curve mode. One of AFTERTOUCH_CURVE_MODES; unknown → "linear".
        threshold: Dead-zone below which output is min_output (0.0..0.95).
                  Clamped on deserialize.
        ceiling: Clip point above which output is max_output (0.05..1.0).
                If < threshold on deserialize, they are swapped. Clamped on deserialize.
        step_count: Number of discrete levels for stepped curve (2..32).
                   Clamped on deserialize. Only used when curve="stepped".
        min_output: Minimum output aftertouch (0..127). Clamped on deserialize.
        max_output: Maximum output aftertouch (0..127). If < min_output on
                   deserialize, they are swapped. Clamped on deserialize.
    """
    enabled: bool = False
    curve: str = "linear"
    threshold: float = 0.0
    ceiling: float = 1.0
    step_count: int = 4
    min_output: int = 0
    max_output: int = 127

    def __post_init__(self) -> None:
        """Normalize and clamp all pressure values after construction."""
        # Normalise curve mode: unknown → linear.
        if self.curve not in AFTERTOUCH_CURVE_MODES:
            self.curve = "linear"

        # Clamp threshold to 0.0..0.95.
        self.threshold = max(0.0, min(0.95, self.threshold))

        # Clamp ceiling to 0.05..1.0.
        self.ceiling = max(0.05, min(1.0, self.ceiling))

        # Ensure ceiling >= threshold. If not, swap them.
        if self.ceiling < self.threshold:
            self.threshold, self.ceiling = self.ceiling, self.threshold

        # Clamp step_count to 2..32.
        self.step_count = max(2, min(32, self.step_count))

        # Clamp min/max output to 0..127.
        self.min_output = max(0, min(127, self.min_output))
        self.max_output = max(0, min(127, self.max_output))

        # If max < min, swap them.
        if self.max_output < self.min_output:
            self.min_output, self.max_output = self.max_output, self.min_output

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "enabled": self.enabled,
            "curve": self.curve,
            "threshold": self.threshold,
            "ceiling": self.ceiling,
            "step_count": self.step_count,
            "min_output": self.min_output,
            "max_output": self.max_output,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AftertouchCurveConfig:
        """Deserialize from a dict (e.g. from JSON).

        Missing keys fall back to dataclass defaults. __post_init__ handles
        normalisation and clamping.
        """
        return cls(
            enabled=data.get("enabled", False),
            curve=data.get("curve", "linear"),
            threshold=data.get("threshold", 0.0),
            ceiling=data.get("ceiling", 1.0),
            step_count=data.get("step_count", 4),
            min_output=data.get("min_output", 0),
            max_output=data.get("max_output", 127),
        )


def _apply_curve_shape(input_0_1: float, curve: str, step_count: int = 4) -> float:
    """Apply a curve transformation to a normalised input.

    Args:
        input_0_1: Normalised input [0.0, 1.0]. Will be clamped by caller.
        curve: One of AFTERTOUCH_CURVE_MODES.
        step_count: Number of steps for stepped curve (ignored for other modes).

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
    elif curve == "stepped":
        # y = floor(x * step_count) / (step_count - 1) — quantised levels.
        # Clamp to step_count - 1 to avoid division by zero (though we validate it).
        if step_count < 2:
            step_count = 2
        level = min(step_count - 1, math.floor(x * step_count))
        return level / (step_count - 1)
    elif curve == "exponential":
        # y = (exp(2*x) - 1) / (exp(2) - 1) — curved growth biased high.
        exp_2 = math.exp(2.0)
        return (math.exp(2.0 * x) - 1.0) / (exp_2 - 1.0)
    elif curve == "logarithmic":
        # y = log(1 + 9*x) / log(10) — curved growth biased low.
        return math.log(1.0 + 9.0 * x) / math.log(10.0)
    else:
        # linear (or unknown) — y = x.
        return x


def compute_pressure(input_0_1: float, cfg: AftertouchCurveConfig) -> int:
    """Compute a MIDI aftertouch value from a normalised input.

    Args:
        input_0_1: Normalised input [0.0, 1.0], e.g. trigger pressure.
                  Values outside this range are clamped.
        cfg: AftertouchCurveConfig describing the curve, range, threshold, and ceiling.

    Returns:
        MIDI aftertouch value (0..127).
    """
    # Clamp input to [0, 1].
    x = max(0.0, min(1.0, input_0_1))

    # If input is below threshold, return min_output.
    if x < cfg.threshold:
        return cfg.min_output

    # Remap input from [threshold, ceiling] to [0, 1].
    # If x >= ceiling, the remapped value will be >= 1.0, which we clamp.
    remapped = (x - cfg.threshold) / (cfg.ceiling - cfg.threshold)
    remapped = max(0.0, min(1.0, remapped))

    # Apply the curve transformation.
    y = _apply_curve_shape(remapped, cfg.curve, cfg.step_count)

    # Lerp from min_output to max_output using the transformed input.
    output = cfg.min_output + y * (cfg.max_output - cfg.min_output)

    # Round to nearest int and clamp to 0..127 as a safety net.
    return max(0, min(127, round(output)))


def preview_curve(cfg: AftertouchCurveConfig, samples: int = 16) -> List[int]:
    """Generate a list of aftertouch samples for UI sparkline/graph preview.

    Samples the curve at evenly spaced input points from 0 to 1.

    Args:
        cfg: AftertouchCurveConfig to preview.
        samples: Number of samples (must be >= 2). Defaults to 16.

    Returns:
        List of MIDI aftertouch values (0..127).
    """
    if samples < 2:
        samples = 2

    result = []
    for i in range(samples):
        # Sample at i/(samples-1), so we get 0.0 at start and 1.0 at end.
        t = i / (samples - 1) if samples > 1 else 0.0
        pressure = compute_pressure(t, cfg)
        result.append(pressure)

    return result
