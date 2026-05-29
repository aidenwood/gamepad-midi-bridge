"""Note-flow timeline bucketing helper — bins note events into time buckets for visualization.

Takes timestamps of note events and buckets them into fixed-size time intervals,
enabling activity-timeline visualization (e.g. heatmaps of MIDI activity).
Pure stdlib, no Qt dependencies.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class NoteFlowConfig:
    """Configuration for NoteFlow bucketing.

    Attributes:
        bucket_seconds: Duration of each bucket in seconds (clamped 0.05..3600).
        max_buckets: Maximum number of buckets to retain (clamped 10..100000).
    """
    bucket_seconds: float = 1.0
    max_buckets: int = 600

    def __post_init__(self) -> None:
        """Clamp parameters to valid ranges."""
        self.bucket_seconds = max(0.05, min(3600.0, self.bucket_seconds))
        self.max_buckets = max(10, min(100000, self.max_buckets))

    def to_dict(self) -> dict:
        """Serialize to JSON-friendly dict."""
        return {
            "bucket_seconds": self.bucket_seconds,
            "max_buckets": self.max_buckets,
        }

    @classmethod
    def from_dict(cls, d: dict) -> NoteFlowConfig:
        """Deserialize from JSON-friendly dict."""
        return cls(
            bucket_seconds=float(d.get("bucket_seconds", 1.0)),
            max_buckets=int(d.get("max_buckets", 600)),
        )


class NoteFlow:
    """Bins note event timestamps into fixed-size time buckets for activity visualization.

    Tracks note activity over time by bucketing events. Supports queries for peak activity,
    normalization, and time-series summaries. Automatically truncates oldest buckets when
    max_buckets is exceeded.
    """

    def __init__(self, cfg: NoteFlowConfig) -> None:
        """Initialize with config.

        Args:
            cfg: NoteFlowConfig instance.
        """
        self.cfg = cfg
        self._buckets: List[int] = []
        self._bucket_start_at: Optional[float] = None

    # ---------------------------------------------------------------- record

    def record(self, now_s: float) -> None:
        """Record a note event at the given timestamp.

        Bins the event into the appropriate bucket based on elapsed time since
        _bucket_start_at. If this is the first event, initializes state.
        If bucketing would exceed max_buckets, truncates oldest buckets and
        shifts _bucket_start_at forward.

        Args:
            now_s: Timestamp in seconds (typically time.time() or similar).
        """
        if self._bucket_start_at is None:
            # First event: initialize
            self._bucket_start_at = now_s
            self._buckets = [1]
            return

        # Compute which bucket this event belongs in
        elapsed = now_s - self._bucket_start_at
        bucket_index = int(elapsed / self.cfg.bucket_seconds)

        # Extend buckets if needed (fill gaps with 0)
        if bucket_index >= len(self._buckets):
            # Extend to include the new bucket
            self._buckets.extend([0] * (bucket_index - len(self._buckets) + 1))

        # Increment the target bucket
        self._buckets[bucket_index] += 1

        # If we exceeded max_buckets, truncate from the start
        if len(self._buckets) > self.cfg.max_buckets:
            # Remove oldest buckets
            buckets_to_remove = len(self._buckets) - self.cfg.max_buckets
            self._buckets = self._buckets[buckets_to_remove:]

            # Shift start time forward
            if self._bucket_start_at is not None:
                self._bucket_start_at += buckets_to_remove * self.cfg.bucket_seconds

    # ---------------------------------------------------------------- query

    def buckets(self) -> List[int]:
        """Return a copy of the current bucket list.

        Returns:
            List of bucket counts.
        """
        return list(self._buckets)

    def total(self) -> int:
        """Return the total count across all buckets.

        Returns:
            Sum of all bucket counts.
        """
        return sum(self._buckets)

    def peak(self) -> int:
        """Return the maximum bucket count.

        Returns 0 if no buckets exist.

        Returns:
            The highest count in any bucket.
        """
        if not self._buckets:
            return 0
        return max(self._buckets)

    def peak_index(self) -> Optional[int]:
        """Return the index of the peak bucket.

        Returns None if no buckets exist.

        Returns:
            Index of the bucket with the highest count, or None.
        """
        if not self._buckets:
            return None
        return self._buckets.index(max(self._buckets))

    def recent(self, n: int = 60) -> List[int]:
        """Return the last n buckets.

        If fewer than n buckets exist, returns all buckets.

        Args:
            n: Number of recent buckets to return.

        Returns:
            List of the last n bucket counts.
        """
        if n <= 0:
            return []
        if len(self._buckets) <= n:
            return list(self._buckets)
        return list(self._buckets[-n:])

    def normalize(self) -> List[float]:
        """Return buckets normalized to 0..1 relative to peak.

        If peak is 0, returns empty list. Each value is (bucket_count / peak).

        Returns:
            List of floats in range [0.0, 1.0].
        """
        if not self._buckets:
            return []

        peak_count = max(self._buckets)
        if peak_count == 0:
            return []

        return [count / peak_count for count in self._buckets]

    def duration_s(self) -> float:
        """Return the total time span covered by all buckets.

        Computed as len(_buckets) * bucket_seconds.

        Returns:
            Duration in seconds.
        """
        return len(self._buckets) * self.cfg.bucket_seconds

    # ---------------------------------------------------------------- control

    def clear(self) -> None:
        """Clear all buckets and reset state."""
        self._buckets.clear()
        self._bucket_start_at = None

    # ---------------------------------------------------------------- summary

    def summary(self) -> Dict[str, Any]:
        """Return a summary dict of current state.

        Returns:
            Dict with keys:
                - "buckets": List of bucket counts.
                - "total": Total count.
                - "peak": Peak bucket count.
                - "peak_index": Index of peak bucket (or None).
                - "duration_s": Total time span.
                - "num_buckets": Number of buckets.
        """
        return {
            "buckets": self.buckets(),
            "total": self.total(),
            "peak": self.peak(),
            "peak_index": self.peak_index(),
            "duration_s": self.duration_s(),
            "num_buckets": len(self._buckets),
        }
