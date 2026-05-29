"""Pure-function preview generator for dual-CC crossfade curves.

Generates rich metadata and both curves for the crossfade UI: curve samples,
labels, midpoints, crossover detection, and side-by-side comparisons.

All functions are pure and stdlib-only (math module), suitable for offline
rendering or live preview generation during UI interaction.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class CrossfadePreview:
    """Rich crossfade curve preview with metadata.

    Attributes:
        samples: Number of sample points in the curves.
        curve: Response curve exponent (0.1..4.0).
        curve_label: Human-readable curve type ("linear", "ease_in", "ease_out").
        a_curve: List of MIDI 7-bit values (0..127) for curve A (rising).
        b_curve: List of MIDI 7-bit values (0..127) for curve B (falling).
        midpoint_a: CC value of curve A at pressure 0.5.
        midpoint_b: CC value of curve B at pressure 0.5.
    """
    samples: int
    curve: float
    curve_label: str
    a_curve: List[int]
    b_curve: List[int]
    midpoint_a: int
    midpoint_b: int

    def to_dict(self) -> dict:
        """Serialize to a plain dict for JSON transport or storage."""
        return {
            "samples": self.samples,
            "curve": self.curve,
            "curve_label": self.curve_label,
            "a_curve": self.a_curve,
            "b_curve": self.b_curve,
            "midpoint_a": self.midpoint_a,
            "midpoint_b": self.midpoint_b,
        }

    @staticmethod
    def from_dict(data: dict) -> CrossfadePreview:
        """Deserialize from a plain dict."""
        return CrossfadePreview(
            samples=data["samples"],
            curve=data["curve"],
            curve_label=data["curve_label"],
            a_curve=data["a_curve"],
            b_curve=data["b_curve"],
            midpoint_a=data["midpoint_a"],
            midpoint_b=data["midpoint_b"],
        )


def curve_label_for(curve: float) -> str:
    """Return a human-readable label for a curve value.

    Args:
        curve: Response curve exponent (typically 0.1..4.0).

    Returns:
        "linear" if 0.95 < curve < 1.05,
        "ease_in" if curve < 0.95,
        "ease_out" if curve > 1.05.
    """
    if 0.95 < curve < 1.05:
        return "linear"
    elif curve < 0.95:
        return "ease_in"
    else:
        return "ease_out"


def compute_pair(pressure_0_1: float, curve: float = 1.0) -> Tuple[int, int]:
    """Compute one (a, b) pair at a given pressure with a given curve.

    Args:
        pressure_0_1: Normalised pressure, clamped to [0.0, 1.0].
        curve: Response curve exponent, clamped to [0.1, 4.0].

    Returns:
        Tuple of (a_value, b_value) both in 0..127 ready for MIDI.
        a_value = round(pressure^curve * 127)
        b_value = 127 - a_value
    """
    p = max(0.0, min(1.0, pressure_0_1))
    c = max(0.1, min(4.0, curve))

    if c == 1.0:
        shaped_p = p
    else:
        shaped_p = p ** c

    a_value = int(round(shaped_p * 127.0))
    a_value = max(0, min(127, a_value))
    b_value = 127 - a_value

    return (a_value, b_value)


def sample_pair(samples: int = 32, curve: float = 1.0) -> Tuple[List[int], List[int]]:
    """Sample two parallel crossfade curves across the pressure range.

    Args:
        samples: Number of points to generate, clamped to [2, 256].
        curve: Response curve exponent, clamped to [0.1, 4.0].

    Returns:
        Tuple of (a_curve, b_curve), each a list of `samples` integers.
        At each position, a[i] + b[i] ≈ 127 (within rounding).
    """
    n = max(2, min(256, samples))
    c = max(0.1, min(4.0, curve))

    a_curve: List[int] = []
    b_curve: List[int] = []

    for i in range(n):
        t = i / (n - 1)  # 0..1 across the range
        a_val, b_val = compute_pair(t, c)
        a_curve.append(a_val)
        b_curve.append(b_val)

    return (a_curve, b_curve)


def build_preview(samples: int = 32, curve: float = 1.0) -> CrossfadePreview:
    """Build a complete crossfade preview with metadata.

    Args:
        samples: Number of points to generate (default 32).
        curve: Response curve exponent (default 1.0).

    Returns:
        CrossfadePreview with curves, label, and midpoint metadata.
    """
    a_curve, b_curve = sample_pair(samples, curve)
    label = curve_label_for(curve)
    mid_a, mid_b = compute_pair(0.5, curve)

    return CrossfadePreview(
        samples=len(a_curve),
        curve=curve,
        curve_label=label,
        a_curve=a_curve,
        b_curve=b_curve,
        midpoint_a=mid_a,
        midpoint_b=mid_b,
    )


def crossover_point(curve: float = 1.0, samples: int = 256) -> float:
    """Find the pressure value where a ≈ b (crossover point).

    Uses high-resolution sampling to locate where the two curves intersect.

    Args:
        curve: Response curve exponent (clamped to [0.1, 4.0]).
        samples: Resolution for search, clamped to [2, 256].

    Returns:
        Pressure value (0.0..1.0) where a == b (or within 1 unit).
        For curve=1.0 (linear), returns ~0.5.
    """
    a_curve, b_curve = sample_pair(samples, curve)

    best_idx = 0
    best_diff = abs(a_curve[0] - b_curve[0])

    for i in range(len(a_curve)):
        diff = abs(a_curve[i] - b_curve[i])
        if diff < best_diff:
            best_diff = diff
            best_idx = i

    # If only 2 samples, best_idx is either 0 or 1.
    # Map back to 0..1 pressure range.
    if len(a_curve) <= 1:
        return 0.5
    crossover_pressure = best_idx / (len(a_curve) - 1)
    return crossover_pressure


def compare_curves(curves: List[float], samples: int = 32) -> List[CrossfadePreview]:
    """Generate previews for multiple curve values (side-by-side comparison).

    Args:
        curves: List of curve exponents to preview.
        samples: Number of points per curve (default 32).

    Returns:
        List of CrossfadePreview objects, one per input curve, in the same order.
    """
    return [build_preview(samples, c) for c in curves]
