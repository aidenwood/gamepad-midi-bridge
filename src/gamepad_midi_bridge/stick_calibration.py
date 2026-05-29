"""Stick calibration helper.

Observes raw stick samples and computes per-stick centre offset + automatic
dead zone radius. Used for "I let go of the stick — please learn my drift".
Pure stdlib, no Qt.
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class StickCalibrationResult:
    """Result of a stick calibration observation."""
    center_x: float
    center_y: float
    deadzone_radius: float
    sample_count: int
    stable: bool

    def to_dict(self) -> dict:
        """Serialize to dictionary for storage."""
        return {
            "center_x": self.center_x,
            "center_y": self.center_y,
            "deadzone_radius": self.deadzone_radius,
            "sample_count": self.sample_count,
            "stable": self.stable,
        }

    @staticmethod
    def from_dict(d: dict) -> StickCalibrationResult:
        """Deserialize from dictionary."""
        return StickCalibrationResult(
            center_x=float(d["center_x"]),
            center_y=float(d["center_y"]),
            deadzone_radius=float(d["deadzone_radius"]),
            sample_count=int(d["sample_count"]),
            stable=bool(d["stable"]),
        )


@dataclass
class StickCalibrationConfig:
    """Configuration for stick calibration."""
    min_samples: int = 30
    deadzone_padding: float = 0.05
    stable_std_threshold: float = 0.05

    def __post_init__(self):
        """Clamp all values to valid ranges."""
        self.min_samples = max(5, min(1000, self.min_samples))
        self.deadzone_padding = max(0.0, min(0.5, self.deadzone_padding))
        self.stable_std_threshold = max(0.0, min(0.5, self.stable_std_threshold))

    def to_dict(self) -> dict:
        """Serialize to dictionary for storage."""
        return {
            "min_samples": self.min_samples,
            "deadzone_padding": self.deadzone_padding,
            "stable_std_threshold": self.stable_std_threshold,
        }

    @staticmethod
    def from_dict(d: dict) -> StickCalibrationConfig:
        """Deserialize from dictionary."""
        return StickCalibrationConfig(
            min_samples=int(d.get("min_samples", 30)),
            deadzone_padding=float(d.get("deadzone_padding", 0.05)),
            stable_std_threshold=float(d.get("stable_std_threshold", 0.05)),
        )


class StickCalibrator:
    """Observe stick samples and compute calibration result."""

    def __init__(self, cfg: StickCalibrationConfig):
        """Initialize calibrator with config."""
        self.cfg = cfg
        self._samples: List[Tuple[float, float]] = []

    def add_sample(self, x: float, y: float) -> None:
        """Add a raw stick sample, clamped to -1..1."""
        x_clamped = max(-1.0, min(1.0, x))
        y_clamped = max(-1.0, min(1.0, y))
        self._samples.append((x_clamped, y_clamped))

    def result(self) -> Optional[StickCalibrationResult]:
        """Compute calibration result. Returns None if too few samples."""
        if len(self._samples) < self.cfg.min_samples:
            return None

        xs = [s[0] for s in self._samples]
        ys = [s[1] for s in self._samples]

        center_x = statistics.mean(xs)
        center_y = statistics.mean(ys)

        # Compute distances from center for each sample
        distances = [
            math.sqrt((x - center_x) ** 2 + (y - center_y) ** 2)
            for x, y in self._samples
        ]

        # Deadzone radius = max distance + padding
        max_distance = max(distances)
        deadzone_radius = max_distance + self.cfg.deadzone_padding

        # Check stability: average of x and y std dev vs threshold
        std_x = statistics.stdev(xs) if len(xs) > 1 else 0.0
        std_y = statistics.stdev(ys) if len(ys) > 1 else 0.0
        avg_std = (std_x + std_y) / 2.0
        stable = avg_std < self.cfg.stable_std_threshold

        return StickCalibrationResult(
            center_x=center_x,
            center_y=center_y,
            deadzone_radius=deadzone_radius,
            sample_count=len(self._samples),
            stable=stable,
        )

    def clear(self) -> None:
        """Clear all samples."""
        self._samples = []

    @staticmethod
    def apply(
        x: float,
        y: float,
        result: StickCalibrationResult,
    ) -> Tuple[float, float]:
        """Apply calibration to raw sample.

        Centers the sample around the calibration center, applies deadzone
        clipping, and clamps output to -1..1.
        """
        dx = x - result.center_x
        dy = y - result.center_y

        distance = math.sqrt(dx ** 2 + dy ** 2)

        # Within deadzone: return origin
        if distance <= result.deadzone_radius:
            return (0.0, 0.0)

        # Outside deadzone: return centred values clamped to -1..1
        out_x = max(-1.0, min(1.0, dx))
        out_y = max(-1.0, min(1.0, dy))

        return (out_x, out_y)
