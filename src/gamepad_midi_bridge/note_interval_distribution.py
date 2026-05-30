"""Analyze interval distribution: semitone intervals between consecutive notes."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional


# Interval names: semitones → musical interval name
INTERVAL_NAMES = {
    0: "unison",
    1: "min2",
    2: "maj2",
    3: "min3",
    4: "maj3",
    5: "perf4",
    6: "tritone",
    7: "perf5",
    8: "min6",
    9: "maj6",
    10: "min7",
    11: "maj7",
    12: "octave",
}


@dataclass
class IntervalAnalysis:
    """Result of analyzing interval distribution."""

    interval_counts: dict[int, int]  # semitones → count; keys 0..24+ (beyond octave folded)
    total_intervals: int  # Total number of intervals recorded
    dominant_interval: Optional[int]  # Most common interval (semitones), or None if no data
    dominant_name: Optional[str]  # Name of dominant interval, or None if no data
    mean_interval: Optional[float]  # Mean absolute semitone interval, or None if no data
    largest_interval: Optional[int]  # Maximum absolute interval observed, or None if no data
    melodic_ratio: float  # Proportion of intervals <= 2 semitones (stepwise feel), 0.0..1.0

    def to_dict(self) -> dict:
        """Serialize analysis to dict."""
        return {
            "interval_counts": self.interval_counts,
            "total_intervals": self.total_intervals,
            "dominant_interval": self.dominant_interval,
            "dominant_name": self.dominant_name,
            "mean_interval": self.mean_interval,
            "largest_interval": self.largest_interval,
            "melodic_ratio": self.melodic_ratio,
        }

    @classmethod
    def from_dict(cls, data: dict) -> IntervalAnalysis:
        """Deserialize analysis from dict."""
        return cls(
            interval_counts=dict(data.get("interval_counts", {})),
            total_intervals=int(data.get("total_intervals", 0)),
            dominant_interval=data.get("dominant_interval"),
            dominant_name=data.get("dominant_name"),
            mean_interval=data.get("mean_interval"),
            largest_interval=data.get("largest_interval"),
            melodic_ratio=float(data.get("melodic_ratio", 0.0)),
        )


@dataclass
class IntervalConfig:
    """Configuration for interval distribution analyzer."""

    max_samples: int = 50000  # Maximum intervals to keep (FIFO buffer)
    fold_octaves: bool = True  # If True, intervals > 12 are reduced mod 12 (but 24→0, 12→12)

    def __post_init__(self) -> None:
        """Clamp max_samples to valid range."""
        self.max_samples = max(100, min(1000000, self.max_samples))

    def to_dict(self) -> dict:
        """Serialize config to dict."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> IntervalConfig:
        """Deserialize config from dict."""
        return cls(**data)


class NoteIntervalDistribution:
    """Track and analyze intervals between consecutive notes.

    Records the semitone interval between each pair of consecutive notes,
    exposes histogram, dominant interval, mean interval, and melodic character.
    """

    def __init__(self, cfg: IntervalConfig) -> None:
        """Initialize with config.

        Args:
            cfg: IntervalConfig for max_samples and fold_octaves.
        """
        self.config = cfg
        self._intervals: list[int] = []  # FIFO buffer of intervals
        self._last_note: Optional[int] = None  # Previous note for interval computation

    def record(self, note: int) -> None:
        """Record a note and compute interval from previous note.

        Args:
            note: MIDI note number (will be clamped to 0..127).
        """
        # Clamp note to valid range
        note = max(0, min(127, note))

        # First note: just store, no interval yet
        if self._last_note is None:
            self._last_note = note
            return

        # Compute interval: absolute semitone distance
        interval = abs(note - self._last_note)

        # Fold octaves if requested: intervals > 12 → mod 12 (e.g., 24→0, 13→1, 19→7)
        if self.config.fold_octaves and interval > 12:
            folded = interval % 12
            interval = folded if folded != 0 else 12

        # Enforce max_samples limit (FIFO eviction from front)
        if len(self._intervals) >= self.config.max_samples:
            self._intervals.pop(0)

        # Append interval
        self._intervals.append(interval)

        # Update last_note for next iteration
        self._last_note = note

    def analyze(self) -> IntervalAnalysis:
        """Analyze current interval distribution.

        Returns:
            IntervalAnalysis with counts, dominant, mean, melodic_ratio, etc.
        """
        if not self._intervals:
            return IntervalAnalysis(
                interval_counts={},
                total_intervals=0,
                dominant_interval=None,
                dominant_name=None,
                mean_interval=None,
                largest_interval=None,
                melodic_ratio=0.0,
            )

        # Count intervals
        counts: dict[int, int] = {}
        for interval in self._intervals:
            counts[interval] = counts.get(interval, 0) + 1

        # Find dominant interval (most common)
        dominant_interval = None
        max_count = 0
        for interval, count in counts.items():
            if count > max_count:
                max_count = count
                dominant_interval = interval

        # Get dominant name
        dominant_name = None
        if dominant_interval is not None:
            dominant_name = self.interval_name(dominant_interval)

        # Compute mean interval
        mean_interval = sum(self._intervals) / len(self._intervals)

        # Largest interval
        largest_interval = max(self._intervals) if self._intervals else None

        # Melodic ratio: proportion of intervals <= 2 semitones (stepwise)
        stepwise_count = sum(1 for iv in self._intervals if iv <= 2)
        melodic_ratio = stepwise_count / len(self._intervals) if self._intervals else 0.0

        return IntervalAnalysis(
            interval_counts=counts,
            total_intervals=len(self._intervals),
            dominant_interval=dominant_interval,
            dominant_name=dominant_name,
            mean_interval=mean_interval,
            largest_interval=largest_interval,
            melodic_ratio=melodic_ratio,
        )

    def interval_name(self, semitones: int) -> str:
        """Get musical name for an interval.

        Args:
            semitones: Interval in semitones.

        Returns:
            Interval name (e.g. "perf5", "maj3") or f"{semitones}st" if not in mapping.
        """
        return INTERVAL_NAMES.get(semitones, f"{semitones}st")

    def clear(self) -> None:
        """Clear all intervals and reset last_note."""
        self._intervals = []
        self._last_note = None

    def total(self) -> int:
        """Get total number of intervals recorded.

        Returns:
            Count of intervals in current buffer.
        """
        return len(self._intervals)
