"""Track duration of held MIDI notes (note-on to note-off) with statistical analysis."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional
import statistics


@dataclass
class NoteDurationConfig:
    """Configuration for note duration tracking."""

    max_samples: int = 5000

    def __post_init__(self) -> None:
        """Clamp max_samples to valid range."""
        self.max_samples = max(100, min(200000, self.max_samples))

    def to_dict(self) -> dict:
        """Serialize config to dict."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> NoteDurationConfig:
        """Deserialize config from dict."""
        return cls(**data)


class NoteDurationStats:
    """Tracks duration of MIDI notes from on to off with statistical analysis."""

    def __init__(self, config: NoteDurationConfig) -> None:
        """Initialize note duration tracker with config.

        Args:
            config: NoteDurationConfig instance with max_samples.
        """
        self.config = config
        self._open_notes: dict[tuple[int, int], float] = {}  # (note, channel) -> start_time_s
        self._samples: list[float] = []  # FIFO ring buffer of durations in seconds

    def on_note_on(self, note: int, channel: int, now_s: float) -> None:
        """Record a note-on event.

        If the same note/channel is already open, treat as retrigger and replace start time.

        Args:
            note: MIDI note number (0-127).
            channel: MIDI channel (0-15).
            now_s: Current time in seconds.
        """
        key = (note, channel)
        self._open_notes[key] = now_s

    def on_note_off(self, note: int, channel: int, now_s: float) -> Optional[float]:
        """Record a note-off event and compute duration.

        Appends duration to samples with FIFO eviction when max_samples exceeded.

        Args:
            note: MIDI note number (0-127).
            channel: MIDI channel (0-15).
            now_s: Current time in seconds.

        Returns:
            Duration in seconds, or None if note was not open.
        """
        key = (note, channel)
        if key not in self._open_notes:
            return None

        start_time = self._open_notes.pop(key)
        duration = now_s - start_time
        duration = max(0.0, duration)  # Clamp to non-negative

        self._samples.append(duration)

        # Enforce max_samples limit (FIFO eviction from front)
        while len(self._samples) > self.config.max_samples:
            self._samples.pop(0)

        return duration

    def mean(self) -> Optional[float]:
        """Return mean note duration in seconds, or None if empty."""
        if len(self._samples) == 0:
            return None
        return statistics.mean(self._samples)

    def median(self) -> Optional[float]:
        """Return median note duration in seconds, or None if empty."""
        if len(self._samples) == 0:
            return None
        return statistics.median(self._samples)

    def percentile(self, p: float) -> Optional[float]:
        """Return pth percentile of note durations in seconds.

        Args:
            p: Percentile value (0..100).

        Returns:
            Percentile duration in seconds, or None if empty.
        """
        if len(self._samples) == 0:
            return None
        # Clamp p to 0..100
        p = max(0.0, min(100.0, p))
        sorted_samples = sorted(self._samples)
        # For p=0, return min; for p=100, return max
        if p == 0.0:
            return sorted_samples[0]
        if p == 100.0:
            return sorted_samples[-1]
        # For other percentiles, use quantiles if we have enough samples
        if len(sorted_samples) < 2:
            return sorted_samples[0]
        # quantiles returns n-1 cut points for n groups
        # So quantiles(data, n=100) returns 99 cut points (indices 0-98)
        # p=1 maps to index 0, p=99 maps to index 98
        idx = int(p) - 1
        if idx < 0:
            idx = 0
        quantiles_list = statistics.quantiles(sorted_samples, n=100)
        if idx >= len(quantiles_list):
            return sorted_samples[-1]
        return quantiles_list[idx]

    def min_duration(self) -> Optional[float]:
        """Return minimum note duration in seconds, or None if empty."""
        if len(self._samples) == 0:
            return None
        return min(self._samples)

    def max_duration(self) -> Optional[float]:
        """Return maximum note duration in seconds, or None if empty."""
        if len(self._samples) == 0:
            return None
        return max(self._samples)

    def sample_count(self) -> int:
        """Return number of note-off samples currently retained."""
        return len(self._samples)

    def open_count(self) -> int:
        """Return number of notes currently held (still in note-on state)."""
        return len(self._open_notes)

    def clear(self) -> None:
        """Reset all open notes and samples to initial state."""
        self._open_notes.clear()
        self._samples.clear()

    def category(self) -> Optional[str]:
        """Return descriptive category based on mean duration.

        Categories:
        - "stab": < 0.1s
        - "short": < 0.3s
        - "medium": < 1.0s
        - "long": < 3.0s
        - "sustained": >= 3.0s
        - None if no samples

        Returns:
            Category string, or None if empty.
        """
        m = self.mean()
        if m is None:
            return None
        if m < 0.1:
            return "stab"
        if m < 0.3:
            return "short"
        if m < 1.0:
            return "medium"
        if m < 3.0:
            return "long"
        return "sustained"
