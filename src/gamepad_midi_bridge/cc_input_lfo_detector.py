"""
CC Input LFO Detector

Detects if a CC (Control Change) value is oscillating, indicating an LFO
(Low-Frequency Oscillator) from a DAW or controller.

Pure stdlib + math, no Qt, self-contained.
"""

from dataclasses import dataclass, asdict
from typing import List, Optional, Tuple
import math


@dataclass
class LfoDetection:
    """Result of LFO analysis on CC value samples."""
    is_oscillating: bool
    estimated_period_s: Optional[float]
    estimated_amplitude: Optional[float]  # peak-to-trough, 0..127
    confidence: float  # 0..1
    sample_count: int

    def to_dict(self) -> dict:
        """Serialize to dict."""
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "LfoDetection":
        """Deserialize from dict."""
        return cls(**d)


@dataclass
class LfoDetectorConfig:
    """Configuration for CC LFO detection."""
    min_samples: int = 20
    max_samples: int = 500
    min_amplitude: float = 8.0
    min_zero_crossings: int = 4

    def __post_init__(self):
        """Clamp config values to safe ranges."""
        self.min_samples = max(4, min(1000, self.min_samples))
        self.max_samples = max(10, min(100000, self.max_samples))
        self.min_amplitude = max(1.0, min(127.0, self.min_amplitude))
        self.min_zero_crossings = max(2, min(100, self.min_zero_crossings))

    def to_dict(self) -> dict:
        """Serialize to dict."""
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "LfoDetectorConfig":
        """Deserialize from dict."""
        return cls(**d)


class CcInputLfoDetector:
    """
    Detects LFO oscillation in timestamped CC value samples.
    """

    def __init__(self, cfg: LfoDetectorConfig):
        """
        Args:
            cfg: LfoDetectorConfig instance.
        """
        self.cfg = cfg
        self._samples: List[Tuple[float, int]] = []  # (timestamp, value)

    def record(self, value: int, now_s: float) -> None:
        """
        Record a CC value sample.

        Args:
            value: CC value, clamped to 0..127.
            now_s: Timestamp in seconds.
        """
        clamped_value = max(0, min(127, value))
        self._samples.append((now_s, clamped_value))

        # Maintain FIFO: discard oldest if we exceed max_samples
        if len(self._samples) > self.cfg.max_samples:
            self._samples = self._samples[1:]

    def analyze(self) -> LfoDetection:
        """
        Analyze recorded samples and detect LFO.

        Returns:
            LfoDetection with oscillation status, period, amplitude, confidence.
        """
        sample_count = len(self._samples)

        # Not enough samples
        if sample_count < self.cfg.min_samples:
            return LfoDetection(
                is_oscillating=False,
                estimated_period_s=None,
                estimated_amplitude=None,
                confidence=0.0,
                sample_count=sample_count,
            )

        values = [v for _, v in self._samples]

        # Compute mean
        mean_value = sum(values) / len(values)

        # Count zero-crossings: where signal crosses the mean
        zero_crossings = 0
        for i in range(len(values) - 1):
            curr = values[i] - mean_value
            next_val = values[i + 1] - mean_value
            # Cross if sign changes
            if curr * next_val < 0:
                zero_crossings += 1

        # Determine oscillating
        is_oscillating = zero_crossings >= self.cfg.min_zero_crossings

        # Compute amplitude (peak-to-trough)
        min_val = min(values)
        max_val = max(values)
        amplitude = max_val - min_val

        # Check amplitude threshold
        if amplitude < self.cfg.min_amplitude:
            is_oscillating = False

        # Estimate period
        estimated_period_s: Optional[float] = None
        if is_oscillating and sample_count > 1:
            time_span = self._samples[-1][0] - self._samples[0][0]
            if time_span > 0 and zero_crossings > 0:
                # Each complete cycle has 2 zero-crossings
                cycles = zero_crossings / 2.0
                estimated_period_s = time_span / cycles if cycles > 0 else None

        # Confidence: how many zero-crossings relative to minimum required
        confidence = 0.0
        if self.cfg.min_zero_crossings > 0:
            confidence = min(1.0, zero_crossings / (2 * self.cfg.min_zero_crossings))

        return LfoDetection(
            is_oscillating=is_oscillating,
            estimated_period_s=estimated_period_s,
            estimated_amplitude=amplitude if is_oscillating else None,
            confidence=confidence,
            sample_count=sample_count,
        )

    def clear(self) -> None:
        """Clear all recorded samples."""
        self._samples = []

    def total(self) -> int:
        """Return total number of recorded samples."""
        return len(self._samples)
