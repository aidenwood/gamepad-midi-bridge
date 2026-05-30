"""Polyphony tracker — counts max simultaneous notes held and reports stats."""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PolyphonyConfig:
    """Configuration for polyphony tracking."""

    max_samples: int = 20000

    def __post_init__(self) -> None:
        """Clamp max_samples to valid range."""
        self.max_samples = max(100, min(1000000, self.max_samples))

    def to_dict(self) -> dict:
        """Round-trip to dict (for JSON serialization)."""
        return {
            "max_samples": self.max_samples,
        }

    @classmethod
    def from_dict(cls, data: dict) -> PolyphonyConfig:
        """Deserialize from dict, clamping values."""
        max_samples = int(data.get("max_samples", 20000))
        return cls(max_samples=max_samples)


@dataclass
class PolyphonyReport:
    """Report of polyphony statistics from a session."""

    peak_polyphony: int
    peak_at_s: Optional[float]
    mean_polyphony: float
    median_polyphony: float
    current_held: int
    total_samples: int

    def to_dict(self) -> dict:
        """Round-trip to dict (for JSON serialization)."""
        return {
            "peak_polyphony": self.peak_polyphony,
            "peak_at_s": self.peak_at_s,
            "mean_polyphony": self.mean_polyphony,
            "median_polyphony": self.median_polyphony,
            "current_held": self.current_held,
            "total_samples": self.total_samples,
        }

    @classmethod
    def from_dict(cls, data: dict) -> PolyphonyReport:
        """Deserialize from dict."""
        return cls(
            peak_polyphony=int(data.get("peak_polyphony", 0)),
            peak_at_s=data.get("peak_at_s"),
            mean_polyphony=float(data.get("mean_polyphony", 0.0)),
            median_polyphony=float(data.get("median_polyphony", 0.0)),
            current_held=int(data.get("current_held", 0)),
            total_samples=int(data.get("total_samples", 0)),
        )


class NotePolyphonyTracker:
    """Track simultaneous notes held and compute polyphony statistics."""

    def __init__(self, cfg: PolyphonyConfig) -> None:
        """Initialize tracker with config."""
        self.cfg = cfg
        self._held: set[tuple[int, int]] = set()  # (note, channel) pairs currently held
        self._samples: list[int] = []  # snapshots of held count at each event
        self._peak: int = 0
        self._peak_at: Optional[float] = None

    def on_note_on(self, note: int, channel: int, now_s: float) -> None:
        """Record a note-on event."""
        self._held.add((note, channel))
        current_count = len(self._held)
        self._snapshot_sample(current_count)

        if current_count > self._peak:
            self._peak = current_count
            self._peak_at = now_s

    def on_note_off(self, note: int, channel: int, now_s: float) -> None:
        """Record a note-off event."""
        self._held.discard((note, channel))
        current_count = len(self._held)
        self._snapshot_sample(current_count)

    def _snapshot_sample(self, count: int) -> None:
        """Add a sample of current polyphony, maintaining max_samples FIFO."""
        self._samples.append(count)
        if len(self._samples) > self.cfg.max_samples:
            self._samples.pop(0)

    def current(self) -> int:
        """Return number of notes currently held."""
        return len(self._held)

    def report(self) -> PolyphonyReport:
        """Generate a polyphony report from current state and samples."""
        current_held = self.current()

        # Compute mean
        if self._samples:
            mean_poly = statistics.mean(self._samples)
        else:
            mean_poly = 0.0

        # Compute median
        if self._samples:
            median_poly = statistics.median(self._samples)
        else:
            median_poly = 0.0

        return PolyphonyReport(
            peak_polyphony=self._peak,
            peak_at_s=self._peak_at,
            mean_polyphony=mean_poly,
            median_polyphony=median_poly,
            current_held=current_held,
            total_samples=len(self._samples),
        )

    def clear(self) -> None:
        """Reset all state."""
        self._held.clear()
        self._samples.clear()
        self._peak = 0
        self._peak_at = None
