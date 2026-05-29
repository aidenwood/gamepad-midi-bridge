"""Track velocity distribution of outgoing MIDI notes using ring-buffered histograms."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class HistogramConfig:
    """Configuration for velocity histogram tracking."""

    bucket_count: int = 8
    max_samples: int = 10000

    def __post_init__(self) -> None:
        """Clamp values to valid ranges."""
        self.bucket_count = max(4, min(32, self.bucket_count))
        self.max_samples = max(100, min(1000000, self.max_samples))

    def to_dict(self) -> dict:
        """Serialize config to dict."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> HistogramConfig:
        """Deserialize config from dict."""
        return cls(**data)


class VelocityHistogram:
    """Ring-buffered histogram of MIDI note velocities (0..127)."""

    def __init__(self, config: HistogramConfig) -> None:
        """Initialize histogram with config.

        Args:
            config: HistogramConfig instance with bucket_count and max_samples.
        """
        self.config = config
        self._buckets: list[int] = [0] * config.bucket_count
        self._samples: list[int] = []  # FIFO ring buffer of actual velocities
        self._total = 0

    def record(self, velocity: int) -> None:
        """Record a single note velocity (0..127) into the histogram.

        Automatically enforces ring-buffer eviction when max_samples is exceeded.
        When evicting, decrements the bucket of the oldest sample.

        Args:
            velocity: MIDI note velocity (0..127), will be clamped.
        """
        # Clamp velocity to valid range
        velocity = max(0, min(127, velocity))

        # Compute bucket index
        bucket_idx = min(
            self.config.bucket_count - 1,
            (velocity * self.config.bucket_count) // 128,
        )

        # Record in bucket
        self._buckets[bucket_idx] += 1
        self._total += 1

        # Append to FIFO
        self._samples.append(velocity)

        # Enforce max_samples limit (evict oldest from front)
        while len(self._samples) > self.config.max_samples:
            evicted = self._samples.pop(0)
            evicted_bucket = min(
                self.config.bucket_count - 1,
                (evicted * self.config.bucket_count) // 128,
            )
            self._buckets[evicted_bucket] -= 1
            self._total -= 1

    def buckets(self) -> list[int]:
        """Return a copy of bucket counts."""
        return self._buckets.copy()

    def bucket_ranges(self) -> list[tuple[int, int]]:
        """Return (lo, hi) MIDI velocity range for each bucket.

        Last bucket always includes 127.

        Returns:
            List of (lo, hi) tuples, one per bucket.
        """
        ranges = []
        bucket_size = 128 // self.config.bucket_count
        for i in range(self.config.bucket_count):
            lo = i * bucket_size
            if i == self.config.bucket_count - 1:
                hi = 127
            else:
                hi = (i + 1) * bucket_size - 1
            ranges.append((lo, hi))
        return ranges

    def total(self) -> int:
        """Return total samples currently retained (may be < sum(buckets()) if evicted)."""
        return self._total

    def peak_bucket(self) -> Optional[int]:
        """Return index of bucket with highest count, or None if no samples recorded."""
        if self._total == 0:
            return None
        return self._buckets.index(max(self._buckets))

    def mean(self) -> Optional[float]:
        """Return mean velocity of currently-retained samples, or None if empty."""
        if len(self._samples) == 0:
            return None
        return sum(self._samples) / len(self._samples)

    def clear(self) -> None:
        """Reset histogram and samples to initial state."""
        self._buckets = [0] * self.config.bucket_count
        self._samples.clear()
        self._total = 0

    def to_normalised(self) -> list[float]:
        """Return bucket counts normalised to 0..1 relative to peak.

        If all buckets are zero, returns all zeros.

        Returns:
            List of floats in range [0.0, 1.0].
        """
        if self._total == 0:
            return [0.0] * self.config.bucket_count

        peak_count = max(self._buckets)
        if peak_count == 0:
            return [0.0] * self.config.bucket_count

        return [float(count) / peak_count for count in self._buckets]
