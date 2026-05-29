"""Track per-note play counts and analyze frequency distribution."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class NoteFrequencyConfig:
    """Configuration for note frequency tracking."""

    max_samples: int = 50000
    decay_enabled: bool = False
    decay_half_life_s: float = 60.0

    def __post_init__(self) -> None:
        """Clamp values to valid ranges."""
        self.max_samples = max(100, min(1000000, self.max_samples))
        if self.decay_enabled:
            self.decay_half_life_s = max(1.0, min(3600.0, self.decay_half_life_s))

    def to_dict(self) -> dict:
        """Serialize config to dict."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> NoteFrequencyConfig:
        """Deserialize config from dict."""
        return cls(**data)


def apply_decay(
    counts: list[float], elapsed_s: float, half_life_s: float
) -> list[float]:
    """Apply exponential decay to counts.

    Counts halve every half_life_s seconds.

    Args:
        counts: List of counts to decay.
        elapsed_s: Seconds elapsed since last decay.
        half_life_s: Half-life in seconds.

    Returns:
        New list with decayed counts.
    """
    factor = 0.5 ** (elapsed_s / half_life_s)
    return [c * factor for c in counts]


class NoteFrequency:
    """Track play count for each MIDI note (0..127)."""

    def __init__(self, config: NoteFrequencyConfig) -> None:
        """Initialize note frequency tracker.

        Args:
            config: NoteFrequencyConfig instance.
        """
        self.config = config
        self._counts: list[float] = [0.0] * 128
        self._samples: list[tuple[int, float]] = []  # (note, time) FIFO
        self._last_decay_at: Optional[float] = None

    def record(self, note: int, now_s: float = 0.0) -> None:
        """Record a note play.

        Clamps note to 0..127. Applies decay if enabled.
        Enforces ring-buffer eviction when max_samples is exceeded.

        Args:
            note: MIDI note number (0..127), will be clamped.
            now_s: Current time in seconds (for decay calculations).
        """
        # Clamp note to valid range
        note = max(0, min(127, note))

        # Apply decay if enabled
        if self.config.decay_enabled and self._last_decay_at is not None:
            elapsed = now_s - self._last_decay_at
            if elapsed > 0:
                self._counts = apply_decay(
                    self._counts, elapsed, self.config.decay_half_life_s
                )
                self._last_decay_at = now_s

        if self.config.decay_enabled:
            self._last_decay_at = now_s

        # Increment count for this note
        self._counts[note] += 1.0

        # Append to FIFO
        self._samples.append((note, now_s))

        # Enforce max_samples limit (evict oldest from front)
        while len(self._samples) > self.config.max_samples:
            evicted_note, _ = self._samples.pop(0)
            self._counts[evicted_note] -= 1.0

    def count(self, note: int) -> float:
        """Get play count for a single note.

        Args:
            note: MIDI note number (0..127).

        Returns:
            Play count for that note (clamped to non-negative).
        """
        note = max(0, min(127, note))
        return max(0.0, self._counts[note])

    def top_n(self, n: int = 5) -> list[tuple[int, float]]:
        """Get top n most-played notes.

        Args:
            n: Number of top notes to return.

        Returns:
            List of (note, count) tuples, descending by count.
            Skips notes with count 0.
        """
        notes_with_counts = [
            (i, self._counts[i]) for i in range(128) if self._counts[i] > 0
        ]
        notes_with_counts.sort(key=lambda x: x[1], reverse=True)
        return notes_with_counts[:n]

    def total_plays(self) -> float:
        """Get total number of note plays.

        Returns:
            Sum of all counts.
        """
        return sum(self._counts)

    def key_center_guess(self) -> Optional[int]:
        """Guess the key center based on pitch class distribution.

        Returns:
            Pitch class (0..11) with highest cumulative count, or None if no plays.
        """
        dist = self.pitch_class_distribution()
        total = sum(dist)
        if total == 0:
            return None
        return dist.index(max(dist))

    def pitch_class_distribution(self) -> list[float]:
        """Get counts per pitch class (C, C#, D, ..., B).

        Sums counts across all octaves for each pitch class.

        Returns:
            12-element list of counts per pitch class.
        """
        distribution = [0.0] * 12
        for note in range(128):
            pitch_class = note % 12
            distribution[pitch_class] += self._counts[note]
        return distribution

    def clear(self) -> None:
        """Clear all counts and samples."""
        self._counts = [0.0] * 128
        self._samples = []
        self._last_decay_at = None
