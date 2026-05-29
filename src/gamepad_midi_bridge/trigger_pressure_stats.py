"""Track trigger pressure (L2/R2) over time with peak/mean/heatmap analytics.

Pure stdlib (statistics module); no Qt dependency so it can be imported from
the bridge worker thread without GUI complications.
"""
from __future__ import annotations

import statistics
from dataclasses import asdict, dataclass
from typing import Dict, List, Optional, Tuple


@dataclass
class TriggerPressureConfig:
    """Configuration for trigger pressure tracking."""

    bucket_count: int = 10  # Histogram buckets for heatmap (pressure bands)
    max_samples: int = 20000  # Maximum samples to retain (FIFO eviction)

    def __post_init__(self) -> None:
        """Clamp bucket_count and max_samples to valid ranges."""
        self.bucket_count = max(4, min(64, self.bucket_count))
        self.max_samples = max(100, min(1000000, self.max_samples))

    def to_dict(self) -> dict:
        """Serialize config to dict."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> TriggerPressureConfig:
        """Deserialize config from dict."""
        return cls(**data)


class TriggerPressureStats:
    """Tracks normalized trigger pressure (0..1) over time with histogram bucketing.

    Maintains:
    - Raw samples (FIFO ring buffer, clamped to max_samples)
    - Histogram buckets (pressure bands for heatmap visualization)
    - Peak/mean aggregations
    """

    def __init__(self, cfg: TriggerPressureConfig) -> None:
        """Initialize trigger pressure tracker with config.

        Args:
            cfg: TriggerPressureConfig instance with bucket_count and max_samples.
        """
        self.config = cfg
        # Per-trigger sample buffers: trigger name (e.g., "L2", "R2") → list of pressures
        self._samples: Dict[str, List[float]] = {"L2": [], "R2": []}
        # Per-trigger histogram buckets: trigger name → list of bucket counts
        self._buckets: Dict[str, List[int]] = {
            "L2": [0] * self.config.bucket_count,
            "R2": [0] * self.config.bucket_count,
        }

    def record(self, trigger: str, pressure: float) -> None:
        """Record a pressure reading for a trigger.

        Clamps pressure to 0..1 and ignores unknown trigger names.
        Appends to samples with FIFO eviction when max_samples exceeded.
        Updates histogram bucket.

        Args:
            trigger: Trigger name ("L2" or "R2"); unknown names are silently ignored.
            pressure: Normalized pressure value (will be clamped to 0..1).
        """
        # Ignore unknown trigger names
        if trigger not in self._samples:
            return

        # Clamp pressure to 0..1
        pressure = max(0.0, min(1.0, pressure))

        # Enforce max_samples limit (FIFO eviction BEFORE adding new sample)
        if len(self._samples[trigger]) >= self.config.max_samples:
            # Evict oldest sample and decrement its bucket
            old_sample = self._samples[trigger].pop(0)
            old_bucket_idx = min(
                self.config.bucket_count - 1, int(old_sample * self.config.bucket_count)
            )
            self._buckets[trigger][old_bucket_idx] -= 1

        # Append new sample
        self._samples[trigger].append(pressure)

        # Increment new bucket
        new_bucket_idx = min(
            self.config.bucket_count - 1, int(pressure * self.config.bucket_count)
        )
        self._buckets[trigger][new_bucket_idx] += 1

    def peak(self, trigger: str) -> Optional[float]:
        """Return maximum pressure seen for trigger, or None if no samples.

        Args:
            trigger: Trigger name ("L2" or "R2").

        Returns:
            Peak pressure (0..1), or None if empty.
        """
        if trigger not in self._samples or len(self._samples[trigger]) == 0:
            return None
        return max(self._samples[trigger])

    def mean(self, trigger: str) -> Optional[float]:
        """Return mean pressure for trigger, or None if no samples.

        Args:
            trigger: Trigger name ("L2" or "R2").

        Returns:
            Mean pressure (0..1), or None if empty.
        """
        if trigger not in self._samples or len(self._samples[trigger]) == 0:
            return None
        return statistics.mean(self._samples[trigger])

    def percentile(self, trigger: str, p: float) -> Optional[float]:
        """Return pth percentile of pressures for trigger.

        Args:
            trigger: Trigger name ("L2" or "R2").
            p: Percentile value (0..100).

        Returns:
            Percentile pressure (0..1), or None if empty.
        """
        if trigger not in self._samples or len(self._samples[trigger]) == 0:
            return None

        # Clamp p to 0..100
        p = max(0.0, min(100.0, p))
        sorted_samples = sorted(self._samples[trigger])

        # Handle boundary cases
        if p == 0.0:
            return sorted_samples[0]
        if p == 100.0:
            return sorted_samples[-1]

        # For very small samples, return the min or max
        if len(sorted_samples) < 2:
            return sorted_samples[0]

        # Use quantiles for intermediate percentiles
        # quantiles(data, n=100) returns 99 cut points (indices 0-98)
        # p=1 maps to index 0, p=99 maps to index 98
        idx = int(p) - 1
        if idx < 0:
            idx = 0
        quantiles_list = statistics.quantiles(sorted_samples, n=100)
        if idx >= len(quantiles_list):
            return sorted_samples[-1]
        return quantiles_list[idx]

    def buckets(self, trigger: str) -> List[int]:
        """Return copy of histogram bucket counts for trigger.

        Args:
            trigger: Trigger name ("L2" or "R2").

        Returns:
            List of bucket counts (length = bucket_count), or empty list if unknown trigger.
        """
        if trigger not in self._buckets:
            return []
        return list(self._buckets[trigger])

    def bucket_ranges(self) -> List[Tuple[float, float]]:
        """Return pressure band boundaries for each bucket.

        Returns:
            List of (lo, hi) pressure ranges with length = bucket_count.
            First bucket: (0.0, 1/bucket_count)
            Last bucket: ((bucket_count-1)/bucket_count, 1.0)
        """
        ranges = []
        step = 1.0 / self.config.bucket_count
        for i in range(self.config.bucket_count):
            lo = i * step
            hi = (i + 1) * step
            # Ensure last bucket's hi is exactly 1.0 (floating-point safety)
            if i == self.config.bucket_count - 1:
                hi = 1.0
            ranges.append((lo, hi))
        return ranges

    def heatmap_normalized(self, trigger: str) -> List[float]:
        """Return histogram buckets normalized 0..1 relative to peak bucket.

        Useful for rendering pressure heatmap. Peak bucket always maps to 1.0.

        Args:
            trigger: Trigger name ("L2" or "R2").

        Returns:
            List of normalized values (0..1), or empty list if unknown trigger or no samples.
        """
        if trigger not in self._buckets or len(self._samples[trigger]) == 0:
            return []

        buckets = self._buckets[trigger]
        max_count = max(buckets) if buckets else 0

        if max_count == 0:
            return [0.0] * len(buckets)

        return [float(b) / float(max_count) for b in buckets]

    def total_samples(self, trigger: str) -> int:
        """Return total number of samples for trigger.

        Args:
            trigger: Trigger name ("L2" or "R2").

        Returns:
            Sample count, or 0 if unknown trigger.
        """
        if trigger not in self._samples:
            return 0
        return len(self._samples[trigger])

    def clear(self) -> None:
        """Reset all samples and buckets to initial state."""
        for trigger in self._samples:
            self._samples[trigger].clear()
            self._buckets[trigger] = [0] * self.config.bucket_count

    def comparison(self) -> Dict[str, Optional[float]]:
        """Return summary stats for both triggers as dict.

        Useful for UI display panels showing pressure comparison.

        Returns:
            Dict with keys: "l2_mean", "l2_peak", "r2_mean", "r2_peak"
            (values are Optional[float]).
        """
        return {
            "l2_mean": self.mean("L2"),
            "l2_peak": self.peak("L2"),
            "r2_mean": self.mean("R2"),
            "r2_peak": self.peak("R2"),
        }
