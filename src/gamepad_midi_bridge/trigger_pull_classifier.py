"""Trigger pull style classifier — categorizes user playing style based on trigger pressure curves.

Analyzes pressure waveforms to classify into named buckets: "slammy" (fast 0→max),
"gradual" (slow ramp), "two_stage" (plateau then snap), "feathery" (low peak, soft),
"twitchy" (lots of partial pulls). Pure stdlib, no Qt.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# ================================================================ data classes

@dataclass
class PullSample:
    """A single pressure sample during a trigger pull.

    Attributes:
        pressure: Instantaneous trigger pressure (0..1).
        timestamp_s: Unix timestamp in seconds when sample was recorded.
    """
    pressure: float
    timestamp_s: float

    def to_dict(self) -> dict:
        """Serialize to JSON-friendly dict."""
        return {
            "pressure": float(self.pressure),
            "timestamp_s": float(self.timestamp_s),
        }

    @classmethod
    def from_dict(cls, d: dict) -> PullSample:
        """Deserialize from JSON-friendly dict."""
        return cls(
            pressure=float(d.get("pressure", 0.0)),
            timestamp_s=float(d.get("timestamp_s", 0.0)),
        )


@dataclass
class PullCurve:
    """A complete trigger pull curve from start to finish.

    Attributes:
        samples: List of PullSample objects in chronological order.
        peak_pressure: Maximum pressure reached during the pull (0..1).
        duration_ms: Total time from first to last sample in milliseconds.
    """
    samples: List[PullSample] = field(default_factory=list)
    peak_pressure: float = 0.0
    duration_ms: float = 0.0

    def to_dict(self) -> dict:
        """Serialize to JSON-friendly dict."""
        return {
            "samples": [s.to_dict() for s in self.samples],
            "peak_pressure": float(self.peak_pressure),
            "duration_ms": float(self.duration_ms),
        }

    @classmethod
    def from_dict(cls, d: dict) -> PullCurve:
        """Deserialize from JSON-friendly dict."""
        samples = [PullSample.from_dict(s) for s in d.get("samples", [])]
        return cls(
            samples=samples,
            peak_pressure=float(d.get("peak_pressure", 0.0)),
            duration_ms=float(d.get("duration_ms", 0.0)),
        )


# ================================================================ constants

STYLES: List[str] = ["slammy", "gradual", "two_stage", "feathery", "twitchy"]


# ================================================================ feature computation

def compute_pull_features(curve: PullCurve) -> Dict[str, float]:
    """Compute a rich feature set for a single pull curve.

    Args:
        curve: PullCurve to analyze.

    Returns:
        Dict with keys:
            - "peak_pressure": Curve's peak_pressure value.
            - "duration_ms": Curve's duration_ms value.
            - "time_to_peak_ratio": Index of peak sample divided by total samples (0..1).
            - "ramp_slope": Peak pressure per second (pressure-per-second).
            - "plateau_ratio": Fraction of samples within 0.1 of peak (0..1).
            - "variance": Variance of pressure samples across the curve.
    """
    features = {
        "peak_pressure": float(curve.peak_pressure),
        "duration_ms": float(curve.duration_ms),
        "time_to_peak_ratio": 0.0,
        "ramp_slope": 0.0,
        "plateau_ratio": 0.0,
        "variance": 0.0,
    }

    # Handle empty or single-sample curves
    if not curve.samples or len(curve.samples) == 0:
        return features

    # Find index of peak pressure
    peak_idx = 0
    max_pressure = 0.0
    for i, sample in enumerate(curve.samples):
        if sample.pressure > max_pressure:
            max_pressure = sample.pressure
            peak_idx = i

    # time_to_peak_ratio: how far through the pull did we reach peak?
    features["time_to_peak_ratio"] = peak_idx / max(1, len(curve.samples) - 1) if len(curve.samples) > 1 else 0.0

    # ramp_slope: peak_pressure / (duration in seconds)
    if curve.duration_ms > 0:
        duration_sec = curve.duration_ms / 1000.0
        features["ramp_slope"] = curve.peak_pressure / duration_sec

    # plateau_ratio: fraction of samples within 0.1 of peak
    if curve.peak_pressure > 0:
        plateau_threshold = 0.1
        plateau_count = sum(
            1 for s in curve.samples
            if abs(s.pressure - curve.peak_pressure) <= plateau_threshold
        )
        features["plateau_ratio"] = plateau_count / len(curve.samples)
    else:
        features["plateau_ratio"] = 0.0

    # variance: variance of all pressure values
    if len(curve.samples) > 1:
        pressures = [s.pressure for s in curve.samples]
        try:
            features["variance"] = statistics.variance(pressures)
        except statistics.StatisticsError:
            features["variance"] = 0.0
    else:
        features["variance"] = 0.0

    return features


# ================================================================ classification

def classify(curve: PullCurve) -> Tuple[str, float]:
    """Classify a single pull curve into a style bucket.

    Decision rules (applied in order):
        1. peak < 0.5 → "feathery" (light touch). Confidence ∝ 1 - (peak / 0.5).
        2. duration_ms < 50 AND peak > 0.6 → "slammy" (quick slam). Confidence ∝ 1 - (duration / 50).
        3. variance > 0.15 → "twitchy" (oscillating). Confidence ∝ min(variance / 0.3, 1.0).
        4. plateau_ratio > 0.35 AND peak > 0.6 → "two_stage" (long plateau then snap).
           Confidence = plateau_ratio.
        5. default → "gradual" (smooth ramp up). Confidence = 0.5.

    Args:
        curve: PullCurve to classify.

    Returns:
        Tuple of (style_name: str, confidence: float 0..1).
    """
    # Empty curve defaults to feathery with low confidence
    if not curve.samples or curve.peak_pressure == 0:
        return ("feathery", 0.2)

    features = compute_pull_features(curve)
    peak = features["peak_pressure"]
    duration = features["duration_ms"]
    plateau_ratio = features["plateau_ratio"]
    variance = features["variance"]

    # Rule 1: Feathery (light touch)
    if peak < 0.5:
        confidence = max(0.0, 1.0 - (peak / 0.5))
        return ("feathery", confidence)

    # Rule 2: Slammy (quick slam, only if peak is already high)
    if duration < 50 and peak > 0.6:
        confidence = max(0.0, 1.0 - (duration / 50.0))
        return ("slammy", confidence)

    # Rule 3: Twitchy (oscillating, check before two_stage so high variance wins)
    if variance > 0.15:
        confidence = min(variance / 0.3, 1.0)
        return ("twitchy", confidence)

    # Rule 4: Two-stage (plateau then snap)
    if plateau_ratio > 0.35 and peak > 0.6:
        return ("two_stage", plateau_ratio)

    # Rule 5: Default to gradual
    return ("gradual", 0.5)


def classify_history(curves: List[PullCurve]) -> Dict[str, float]:
    """Classify a list of pull curves and return style distribution.

    Args:
        curves: List of PullCurve objects.

    Returns:
        Dict mapping style names to their fractional occurrence (sums to 1.0, or 0 if empty).
    """
    # Initialize distribution
    distribution = {style: 0.0 for style in STYLES}

    if not curves:
        return distribution

    # Classify each curve and tally
    style_counts = {style: 0 for style in STYLES}
    for curve in curves:
        style, _ = classify(curve)
        style_counts[style] += 1

    # Normalize to fractions
    total = len(curves)
    for style in STYLES:
        distribution[style] = style_counts[style] / total

    return distribution


def dominant_style(curves: List[PullCurve]) -> Optional[Tuple[str, float]]:
    """Determine the dominant (most common) style in a history of pulls.

    Args:
        curves: List of PullCurve objects.

    Returns:
        Tuple of (style_name: str, fraction: float) for the most common style.
        Returns None if the list is empty.
    """
    if not curves:
        return None

    distribution = classify_history(curves)

    # Find the style with highest fraction
    max_style = None
    max_fraction = -1.0
    for style, fraction in distribution.items():
        if fraction > max_fraction:
            max_fraction = fraction
            max_style = style

    return (max_style, max_fraction) if max_style is not None else None
