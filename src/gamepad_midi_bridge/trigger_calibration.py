"""Track trigger pressure to recommend calibration bounds for velocity/CC scaling.

Analyzes the maximum trigger pressure a user actually reaches and recommends a
"soft clamp" for output scaling. Useful for users who never push triggers fully down.

Pure stdlib (statistics module); no Qt dependency so it can be imported from
the bridge worker thread without GUI complications.
"""
from __future__ import annotations

import statistics
from dataclasses import asdict, dataclass
from typing import Dict, List, Optional


@dataclass
class TriggerCalibrationConfig:
    """Configuration for trigger pressure calibration tracking."""

    peak_window: int = 50  # Average top-N samples to compute mean_peak
    min_samples: int = 100  # Require this many samples before analyze() returns a result
    padding_above: float = 0.02  # Round up recommended_max by this amount

    def __post_init__(self) -> None:
        """Clamp config values to valid ranges."""
        self.peak_window = max(3, min(1000, self.peak_window))
        self.min_samples = max(10, min(10000, self.min_samples))
        self.padding_above = max(0.0, min(0.5, self.padding_above))

    def to_dict(self) -> dict:
        """Serialize config to dict."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> TriggerCalibrationConfig:
        """Deserialize config from dict."""
        return cls(**data)


@dataclass
class TriggerCalibrationResult:
    """Result of trigger pressure calibration analysis."""

    trigger: str  # "L2" or "R2"
    observed_peak: float  # Maximum pressure seen (0..1)
    mean_peak: float  # Average of top peak_window samples (0..1)
    sample_count: int  # Total samples analyzed
    recommended_max: float  # Suggested upper bound for scaling (0..1)
    recommended_min: float  # Suggested lower bound for scaling (0..1)

    def to_dict(self) -> dict:
        """Serialize result to dict."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> TriggerCalibrationResult:
        """Deserialize result from dict."""
        return cls(**data)


class TriggerCalibrator:
    """Tracks trigger pressure samples and recommends calibration bounds.

    Maintains per-trigger sample buffers and computes:
    - observed_peak: the single highest pressure reading
    - mean_peak: average of the top peak_window samples
    - recommended_max: mean_peak rounded up by padding_above (clamped to 0..1)
    - recommended_min: minimum sample (or 0.0 if all > 0)
    """

    def __init__(self, cfg: TriggerCalibrationConfig) -> None:
        """Initialize trigger calibrator with config.

        Args:
            cfg: TriggerCalibrationConfig instance.
        """
        self.config = cfg
        # Per-trigger sample buffers: trigger name (e.g., "L2", "R2") → list of pressures
        self._samples: Dict[str, List[float]] = {"L2": [], "R2": []}

    def add_sample(self, trigger: str, pressure: float) -> None:
        """Record a pressure reading for a trigger.

        Clamps pressure to 0..1 and ignores unknown trigger names.

        Args:
            trigger: Trigger name ("L2" or "R2"); unknown names are silently ignored.
            pressure: Normalized pressure value (will be clamped to 0..1).
        """
        # Ignore unknown trigger names
        if trigger not in self._samples:
            return

        # Clamp pressure to 0..1
        pressure = max(0.0, min(1.0, pressure))

        # Append sample
        self._samples[trigger].append(pressure)

    def analyze(self, trigger: str) -> Optional[TriggerCalibrationResult]:
        """Analyze accumulated samples and return calibration recommendation.

        Returns None if fewer than min_samples have been recorded.

        Args:
            trigger: Trigger name ("L2" or "R2").

        Returns:
            TriggerCalibrationResult if enough samples, else None.
        """
        if trigger not in self._samples:
            return None

        samples = self._samples[trigger]
        if len(samples) < self.config.min_samples:
            return None

        # Compute observed_peak (absolute maximum)
        observed_peak = max(samples)

        # Compute mean_peak (average of top peak_window samples)
        sorted_descending = sorted(samples, reverse=True)
        top_samples = sorted_descending[: self.config.peak_window]
        mean_peak = statistics.mean(top_samples)

        # Compute recommended_max: mean_peak + padding, clamped to 0..1
        recommended_max = min(1.0, mean_peak + self.config.padding_above)

        # Compute recommended_min: minimum sample
        recommended_min = min(samples) if samples else 0.0

        return TriggerCalibrationResult(
            trigger=trigger,
            observed_peak=observed_peak,
            mean_peak=mean_peak,
            sample_count=len(samples),
            recommended_max=recommended_max,
            recommended_min=recommended_min,
        )

    def clear(self, trigger: Optional[str] = None) -> None:
        """Clear samples for one or both triggers.

        Args:
            trigger: Trigger name ("L2", "R2"), or None to clear both.
        """
        if trigger is None:
            # Clear both
            for t in self._samples:
                self._samples[t].clear()
        elif trigger in self._samples:
            self._samples[trigger].clear()

    def sample_count(self, trigger: str) -> int:
        """Return total number of samples for a trigger.

        Args:
            trigger: Trigger name ("L2" or "R2").

        Returns:
            Sample count, or 0 if unknown trigger.
        """
        if trigger not in self._samples:
            return 0
        return len(self._samples[trigger])

    def peak_so_far(self, trigger: str) -> Optional[float]:
        """Return the highest pressure recorded so far for a trigger.

        Args:
            trigger: Trigger name ("L2" or "R2").

        Returns:
            Peak pressure (0..1), or None if no samples.
        """
        if trigger not in self._samples or len(self._samples[trigger]) == 0:
            return None
        return max(self._samples[trigger])
