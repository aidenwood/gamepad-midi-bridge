"""Stick drift detector: identifies when stick is drifting at rest.

Collects rest-state samples (stick untouched) and flags if the stick is drifting
away from origin (0, 0). Returns a binary 'is_drifting' check with severity level.
Pure stdlib, no Qt.
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class DriftReport:
    """Result of a stick drift detection analysis."""
    is_drifting: bool
    drift_magnitude: float  # distance from origin: 0..sqrt(2)
    drift_x: float  # mean x offset from zero
    drift_y: float  # mean y offset from zero
    severity: str  # "none", "minor", "moderate", "severe"
    sample_count: int

    def to_dict(self) -> dict:
        """Serialize to dictionary for storage."""
        return {
            "is_drifting": self.is_drifting,
            "drift_magnitude": self.drift_magnitude,
            "drift_x": self.drift_x,
            "drift_y": self.drift_y,
            "severity": self.severity,
            "sample_count": self.sample_count,
        }

    @staticmethod
    def from_dict(d: dict) -> DriftReport:
        """Deserialize from dictionary."""
        return DriftReport(
            is_drifting=bool(d["is_drifting"]),
            drift_magnitude=float(d["drift_magnitude"]),
            drift_x=float(d["drift_x"]),
            drift_y=float(d["drift_y"]),
            severity=str(d["severity"]),
            sample_count=int(d["sample_count"]),
        )


@dataclass
class DriftDetectorConfig:
    """Configuration for stick drift detection."""
    min_samples: int = 50
    minor_threshold: float = 0.05
    moderate_threshold: float = 0.15
    severe_threshold: float = 0.3

    def __post_init__(self):
        """Clamp all values to valid ranges."""
        self.min_samples = max(10, min(10000, self.min_samples))
        self.minor_threshold = max(0.0, min(0.5, self.minor_threshold))
        self.moderate_threshold = max(0.0, min(0.5, self.moderate_threshold))
        self.severe_threshold = max(0.0, min(1.0, self.severe_threshold))

    def to_dict(self) -> dict:
        """Serialize to dictionary for storage."""
        return {
            "min_samples": self.min_samples,
            "minor_threshold": self.minor_threshold,
            "moderate_threshold": self.moderate_threshold,
            "severe_threshold": self.severe_threshold,
        }

    @staticmethod
    def from_dict(d: dict) -> DriftDetectorConfig:
        """Deserialize from dictionary."""
        return DriftDetectorConfig(
            min_samples=int(d.get("min_samples", 50)),
            minor_threshold=float(d.get("minor_threshold", 0.05)),
            moderate_threshold=float(d.get("moderate_threshold", 0.15)),
            severe_threshold=float(d.get("severe_threshold", 0.3)),
        )


class StickDriftDetector:
    """Detect stick drift by analyzing rest-state samples."""

    def __init__(self, cfg: DriftDetectorConfig):
        """Initialize drift detector with config."""
        self.cfg = cfg
        self._samples: List[Tuple[float, float]] = []

    def add_sample(self, x: float, y: float) -> None:
        """Add a raw stick sample, clamped to -1..1."""
        x_clamped = max(-1.0, min(1.0, x))
        y_clamped = max(-1.0, min(1.0, y))
        self._samples.append((x_clamped, y_clamped))

    def analyze(self) -> DriftReport:
        """Analyze samples and return drift report."""
        # Insufficient samples: no drift detected
        if len(self._samples) < self.cfg.min_samples:
            return DriftReport(
                is_drifting=False,
                drift_magnitude=0.0,
                drift_x=0.0,
                drift_y=0.0,
                severity="none",
                sample_count=len(self._samples),
            )

        # Compute mean x and y (expected at origin 0, 0 for rest state)
        xs = [s[0] for s in self._samples]
        ys = [s[1] for s in self._samples]

        drift_x = statistics.mean(xs)
        drift_y = statistics.mean(ys)

        # Magnitude = distance from origin
        drift_magnitude = math.sqrt(drift_x ** 2 + drift_y ** 2)

        # Determine severity based on magnitude thresholds
        if drift_magnitude >= self.cfg.severe_threshold:
            severity = "severe"
            is_drifting = True
        elif drift_magnitude >= self.cfg.moderate_threshold:
            severity = "moderate"
            is_drifting = True
        elif drift_magnitude >= self.cfg.minor_threshold:
            severity = "minor"
            is_drifting = True
        else:
            severity = "none"
            is_drifting = False

        return DriftReport(
            is_drifting=is_drifting,
            drift_magnitude=drift_magnitude,
            drift_x=drift_x,
            drift_y=drift_y,
            severity=severity,
            sample_count=len(self._samples),
        )

    def clear(self) -> None:
        """Clear all samples."""
        self._samples = []

    def sample_count(self) -> int:
        """Return number of samples collected."""
        return len(self._samples)
