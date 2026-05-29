"""Trigger asymmetry analyzer — detects L2 vs R2 handedness and preference patterns.

Compares L2 vs R2 trigger usage across a session to detect handedness / preference patterns.
Tracks usage counts and pressure profiles (mean, peak) per trigger. Pure stdlib, no Qt.
"""
from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Any, Dict, List


@dataclass
class AsymmetryReport:
    """Analysis of trigger asymmetry across L2 and R2.

    Attributes:
        l2_total_uses: Total number of L2 trigger uses recorded.
        r2_total_uses: Total number of R2 trigger uses recorded.
        l2_mean_pressure: Average pressure (0..1) for L2 samples, or 0.0 if no samples.
        r2_mean_pressure: Average pressure (0..1) for R2 samples, or 0.0 if no samples.
        l2_peak_pressure: Maximum pressure (0..1) for L2 samples, or 0.0 if no samples.
        r2_peak_pressure: Maximum pressure (0..1) for R2 samples, or 0.0 if no samples.
        usage_ratio: L2 uses / (L2 uses + R2 uses), 0..1. 0.5 = even, 0.0 = all R2, 1.0 = all L2.
        dominant_trigger: "L2" (>0.5 + threshold), "R2" (<0.5 - threshold), or "balanced".
        dominance_strength: Absolute dominance magnitude, 0..1 (0 = balanced, 1 = extreme).
    """
    l2_total_uses: int
    r2_total_uses: int
    l2_mean_pressure: float
    r2_mean_pressure: float
    l2_peak_pressure: float
    r2_peak_pressure: float
    usage_ratio: float
    dominant_trigger: str
    dominance_strength: float

    def to_dict(self) -> dict:
        """Serialize to JSON-friendly dict."""
        return {
            "l2_total_uses": self.l2_total_uses,
            "r2_total_uses": self.r2_total_uses,
            "l2_mean_pressure": self.l2_mean_pressure,
            "r2_mean_pressure": self.r2_mean_pressure,
            "l2_peak_pressure": self.l2_peak_pressure,
            "r2_peak_pressure": self.r2_peak_pressure,
            "usage_ratio": self.usage_ratio,
            "dominant_trigger": self.dominant_trigger,
            "dominance_strength": self.dominance_strength,
        }

    @classmethod
    def from_dict(cls, d: dict) -> AsymmetryReport:
        """Deserialize from JSON-friendly dict."""
        return cls(
            l2_total_uses=int(d.get("l2_total_uses", 0)),
            r2_total_uses=int(d.get("r2_total_uses", 0)),
            l2_mean_pressure=float(d.get("l2_mean_pressure", 0.0)),
            r2_mean_pressure=float(d.get("r2_mean_pressure", 0.0)),
            l2_peak_pressure=float(d.get("l2_peak_pressure", 0.0)),
            r2_peak_pressure=float(d.get("r2_peak_pressure", 0.0)),
            usage_ratio=float(d.get("usage_ratio", 0.5)),
            dominant_trigger=str(d.get("dominant_trigger", "balanced")),
            dominance_strength=float(d.get("dominance_strength", 0.0)),
        )


@dataclass
class AsymmetryConfig:
    """Configuration for TriggerAsymmetryAnalyzer.

    Attributes:
        max_samples: Maximum number of samples per trigger (clamped 100..1000000).
        balanced_threshold: Threshold for "balanced" determination. If |ratio - 0.5| <= threshold,
                           trigger is "balanced" (clamped 0..0.5).
    """
    max_samples: int = 10000
    balanced_threshold: float = 0.1

    def __post_init__(self) -> None:
        """Clamp parameters to valid ranges."""
        self.max_samples = max(100, min(1000000, self.max_samples))
        self.balanced_threshold = max(0.0, min(0.5, self.balanced_threshold))

    def to_dict(self) -> dict:
        """Serialize to JSON-friendly dict."""
        return {
            "max_samples": self.max_samples,
            "balanced_threshold": self.balanced_threshold,
        }

    @classmethod
    def from_dict(cls, d: dict) -> AsymmetryConfig:
        """Deserialize from JSON-friendly dict."""
        return cls(
            max_samples=int(d.get("max_samples", 10000)),
            balanced_threshold=float(d.get("balanced_threshold", 0.1)),
        )


class TriggerAsymmetryAnalyzer:
    """Analyzes trigger usage asymmetry between L2 and R2.

    Records pressure samples per trigger, computes usage counts/ratios,
    and detects handedness dominance patterns.
    """

    def __init__(self, cfg: AsymmetryConfig) -> None:
        """Initialize with config.

        Args:
            cfg: AsymmetryConfig instance.
        """
        self.cfg = cfg
        self._l2_pressures: List[float] = []
        self._r2_pressures: List[float] = []

    # ---------------------------------------------------------------- record

    def record(self, trigger: str, pressure: float) -> None:
        """Record a trigger pressure sample.

        Clamps pressure to 0..1. Accepts only "L2" or "R2"; other triggers ignored.
        If sample count for the trigger exceeds max_samples, FIFO-removes oldest.

        Args:
            trigger: Trigger identifier, "L2" or "R2".
            pressure: Pressure value (clamped to 0..1).
        """
        # Clamp pressure
        pressure = max(0.0, min(1.0, pressure))

        # Route to appropriate list
        if trigger == "L2":
            self._l2_pressures.append(pressure)
            if len(self._l2_pressures) > self.cfg.max_samples:
                self._l2_pressures.pop(0)
        elif trigger == "R2":
            self._r2_pressures.append(pressure)
            if len(self._r2_pressures) > self.cfg.max_samples:
                self._r2_pressures.pop(0)
        # else: ignore unknown trigger

    # ---------------------------------------------------------------- analyze

    def analyze(self) -> AsymmetryReport:
        """Analyze current trigger usage asymmetry.

        Computes usage counts, pressure statistics, ratio, dominance, and strength.

        Returns:
            AsymmetryReport with all statistics.
        """
        l2_count = len(self._l2_pressures)
        r2_count = len(self._r2_pressures)
        total = l2_count + r2_count

        # Compute usage ratio (0.5 if no samples)
        if total == 0:
            usage_ratio = 0.5
        else:
            usage_ratio = l2_count / total

        # Compute pressure statistics
        l2_mean = mean(self._l2_pressures) if self._l2_pressures else 0.0
        l2_peak = max(self._l2_pressures) if self._l2_pressures else 0.0
        r2_mean = mean(self._r2_pressures) if self._r2_pressures else 0.0
        r2_peak = max(self._r2_pressures) if self._r2_pressures else 0.0

        # Determine dominant trigger
        ratio_offset = abs(usage_ratio - 0.5)
        if ratio_offset <= self.cfg.balanced_threshold:
            dominant_trigger = "balanced"
        elif usage_ratio > 0.5:
            dominant_trigger = "L2"
        else:
            dominant_trigger = "R2"

        # Compute dominance strength (0..1)
        dominance_strength = min(1.0, ratio_offset * 2.0)

        return AsymmetryReport(
            l2_total_uses=l2_count,
            r2_total_uses=r2_count,
            l2_mean_pressure=l2_mean,
            r2_mean_pressure=r2_mean,
            l2_peak_pressure=l2_peak,
            r2_peak_pressure=r2_peak,
            usage_ratio=usage_ratio,
            dominant_trigger=dominant_trigger,
            dominance_strength=dominance_strength,
        )

    # ---------------------------------------------------------------- query

    def total_records(self) -> int:
        """Return total number of trigger samples across both triggers.

        Returns:
            Sum of L2 and R2 sample counts.
        """
        return len(self._l2_pressures) + len(self._r2_pressures)

    def l2_count(self) -> int:
        """Return number of L2 samples."""
        return len(self._l2_pressures)

    def r2_count(self) -> int:
        """Return number of R2 samples."""
        return len(self._r2_pressures)

    # ---------------------------------------------------------------- clear

    def clear(self) -> None:
        """Delete all recorded samples."""
        self._l2_pressures.clear()
        self._r2_pressures.clear()

    # ---------------------------------------------------------------- summary

    def summary(self) -> Dict[str, Any]:
        """Return a summary dict of current state.

        Returns:
            Dict with keys:
                - "l2_count": Number of L2 samples (int).
                - "r2_count": Number of R2 samples (int).
                - "total_records": Total samples (int).
                - "usage_ratio": L2 / (L2 + R2), 0..1 (float).
                - "dominant_trigger": "L2", "R2", or "balanced" (str).
                - "dominance_strength": Magnitude of dominance, 0..1 (float).
        """
        report = self.analyze()
        return {
            "l2_count": report.l2_total_uses,
            "r2_count": report.r2_total_uses,
            "total_records": self.total_records(),
            "usage_ratio": report.usage_ratio,
            "dominant_trigger": report.dominant_trigger,
            "dominance_strength": report.dominance_strength,
        }
