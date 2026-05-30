"""Bucket note hold durations into categorical distribution for UI display."""
from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Optional


# Bucket boundaries in seconds: 4 boundaries define 5 buckets
BUCKET_BOUNDS_S = [0.1, 0.3, 1.0, 3.0]

# Names for each bucket (must have 5 entries to match 5 buckets)
BUCKET_NAMES = ["stab", "short", "medium", "long", "sustained"]


@dataclass
class HoldDistribution:
    """Result of analyzing note hold durations into buckets."""

    bucket_counts: list[int] = field(default_factory=lambda: [0] * 5)
    total_notes: int = 0
    dominant_bucket_index: Optional[int] = None
    dominant_bucket_name: Optional[str] = None
    bucket_percentages: list[float] = field(default_factory=lambda: [0.0] * 5)

    def to_dict(self) -> dict:
        """Serialize distribution to dict."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> HoldDistribution:
        """Deserialize distribution from dict."""
        return cls(**data)


@dataclass
class HoldDistributionConfig:
    """Configuration for note hold distribution tracking."""

    max_samples: int = 5000

    def __post_init__(self) -> None:
        """Clamp max_samples to valid range."""
        self.max_samples = max(100, min(1000000, self.max_samples))

    def to_dict(self) -> dict:
        """Serialize config to dict."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> HoldDistributionConfig:
        """Deserialize config from dict."""
        return cls(**data)


class NoteHoldDistribution:
    """Buckets note hold durations into categorical distribution."""

    def __init__(self, config: HoldDistributionConfig) -> None:
        """Initialize distribution tracker with config.

        Args:
            config: HoldDistributionConfig instance with max_samples.
        """
        self.config = config
        self._durations: list[float] = []  # FIFO ring buffer of durations in seconds
        self._bucket_counts: list[int] = [0] * 5  # Count for each bucket

    def bucket_for(self, duration_s: float) -> int:
        """Find bucket index (0..4) for a given duration.

        Args:
            duration_s: Duration in seconds (clamped to >= 0).

        Returns:
            Bucket index 0..4.
        """
        duration_s = max(0.0, duration_s)

        # Linear scan over boundaries
        for i, boundary in enumerate(BUCKET_BOUNDS_S):
            if duration_s < boundary:
                return i
        return 4  # Sustained (>= 3.0s)

    def record(self, duration_s: float) -> None:
        """Record a note hold duration.

        Clamps to >= 0. Increments bucket count. Appends to FIFO with eviction
        when max_samples exceeded (also decrements bucket for evicted sample).

        Args:
            duration_s: Duration in seconds.
        """
        duration_s = max(0.0, duration_s)
        bucket_idx = self.bucket_for(duration_s)

        # Enforce max_samples limit (FIFO eviction from front) before appending
        if len(self._durations) >= self.config.max_samples:
            evicted_duration = self._durations.pop(0)
            evicted_bucket = self.bucket_for(evicted_duration)
            self._bucket_counts[evicted_bucket] -= 1

        # Increment bucket count
        self._bucket_counts[bucket_idx] += 1

        # Append to FIFO
        self._durations.append(duration_s)

    def analyze(self) -> HoldDistribution:
        """Build HoldDistribution from current state.

        Returns:
            HoldDistribution with bucket counts, percentages, and dominant bucket.
        """
        total = sum(self._bucket_counts)

        # Compute percentages
        percentages = [
            (count / total * 100.0) if total > 0 else 0.0
            for count in self._bucket_counts
        ]

        # Find dominant bucket (highest count, break ties by first index)
        dominant_idx = None
        dominant_name = None
        if total > 0:
            dominant_idx = max(range(5), key=lambda i: self._bucket_counts[i])
            dominant_name = BUCKET_NAMES[dominant_idx]

        return HoldDistribution(
            bucket_counts=self._bucket_counts[:],
            total_notes=total,
            dominant_bucket_index=dominant_idx,
            dominant_bucket_name=dominant_name,
            bucket_percentages=percentages,
        )

    def clear(self) -> None:
        """Reset all samples and bucket counts."""
        self._durations.clear()
        self._bucket_counts = [0] * 5

    def total(self) -> int:
        """Return total number of notes recorded."""
        return len(self._durations)
