"""Stick deadzone analyzer.

Analyzes rest-state stick samples to recommend optimal deadzone radius with
tunable confidence levels (tight, balanced, loose). Different from stick_calibration
which computes a single radius; this offers percentile-based recommendations.
Pure stdlib, no Qt.
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class DeadzoneAnalysis:
    """Result of analyzing stick deadzone rest samples."""
    sample_count: int
    mean_distance: float
    max_distance: float
    p50_distance: float
    p90_distance: float
    p99_distance: float
    recommended_tight: float
    recommended_balanced: float
    recommended_loose: float
    stable: bool

    def to_dict(self) -> dict:
        """Serialize to dictionary for storage."""
        return {
            "sample_count": self.sample_count,
            "mean_distance": self.mean_distance,
            "max_distance": self.max_distance,
            "p50_distance": self.p50_distance,
            "p90_distance": self.p90_distance,
            "p99_distance": self.p99_distance,
            "recommended_tight": self.recommended_tight,
            "recommended_balanced": self.recommended_balanced,
            "recommended_loose": self.recommended_loose,
            "stable": self.stable,
        }

    @staticmethod
    def from_dict(d: dict) -> DeadzoneAnalysis:
        """Deserialize from dictionary."""
        return DeadzoneAnalysis(
            sample_count=int(d["sample_count"]),
            mean_distance=float(d["mean_distance"]),
            max_distance=float(d["max_distance"]),
            p50_distance=float(d["p50_distance"]),
            p90_distance=float(d["p90_distance"]),
            p99_distance=float(d["p99_distance"]),
            recommended_tight=float(d["recommended_tight"]),
            recommended_balanced=float(d["recommended_balanced"]),
            recommended_loose=float(d["recommended_loose"]),
            stable=bool(d["stable"]),
        )


@dataclass
class DeadzoneAnalyzerConfig:
    """Configuration for deadzone analyzer."""
    min_samples: int = 100
    stable_std_threshold: float = 0.03

    def __post_init__(self):
        """Clamp all values to valid ranges."""
        self.min_samples = max(10, min(10000, self.min_samples))
        self.stable_std_threshold = max(0.0, min(0.5, self.stable_std_threshold))

    def to_dict(self) -> dict:
        """Serialize to dictionary for storage."""
        return {
            "min_samples": self.min_samples,
            "stable_std_threshold": self.stable_std_threshold,
        }

    @staticmethod
    def from_dict(d: dict) -> DeadzoneAnalyzerConfig:
        """Deserialize from dictionary."""
        return DeadzoneAnalyzerConfig(
            min_samples=int(d.get("min_samples", 100)),
            stable_std_threshold=float(d.get("stable_std_threshold", 0.03)),
        )


class StickDeadzoneAnalyzer:
    """Analyze stick samples and compute deadzone recommendations."""

    def __init__(self, cfg: DeadzoneAnalyzerConfig):
        """Initialize analyzer with config."""
        self.cfg = cfg
        self._samples: List[Tuple[float, float]] = []

    def add_sample(self, x: float, y: float) -> None:
        """Add a raw stick sample, clamped to -1..1."""
        x_clamped = max(-1.0, min(1.0, x))
        y_clamped = max(-1.0, min(1.0, y))
        self._samples.append((x_clamped, y_clamped))

    def analyze(self) -> Optional[DeadzoneAnalysis]:
        """Analyze samples and compute deadzone recommendations.

        Returns None if fewer than min_samples collected.
        """
        if len(self._samples) < self.cfg.min_samples:
            return None

        # Compute distance from origin for each sample
        distances = [
            math.sqrt(x ** 2 + y ** 2)
            for x, y in self._samples
        ]

        # Compute statistics
        mean_distance = statistics.mean(distances)
        max_distance = max(distances)
        p50_distance = statistics.median(distances)
        p90_distance = statistics.quantiles(distances, n=10)[8]
        p99_distance = statistics.quantiles(distances, n=100)[98]

        # Recommendation profiles
        recommended_tight = p90_distance + 0.01
        recommended_balanced = p99_distance + 0.02
        recommended_loose = max_distance + 0.05

        # Stability: stddev of distances vs threshold
        std_distance = statistics.stdev(distances) if len(distances) > 1 else 0.0
        stable = std_distance < self.cfg.stable_std_threshold

        return DeadzoneAnalysis(
            sample_count=len(self._samples),
            mean_distance=mean_distance,
            max_distance=max_distance,
            p50_distance=p50_distance,
            p90_distance=p90_distance,
            p99_distance=p99_distance,
            recommended_tight=recommended_tight,
            recommended_balanced=recommended_balanced,
            recommended_loose=recommended_loose,
            stable=stable,
        )

    def clear(self) -> None:
        """Clear all samples."""
        self._samples = []

    def recommend(self, profile: str = "balanced") -> Optional[float]:
        """Get recommended deadzone radius for a profile.

        Profiles: "tight", "balanced", "loose".
        Returns None if not enough samples or unknown profile.
        """
        analysis = self.analyze()
        if analysis is None:
            return None

        if profile == "tight":
            return analysis.recommended_tight
        elif profile == "balanced":
            return analysis.recommended_balanced
        elif profile == "loose":
            return analysis.recommended_loose
        else:
            return None
