"""Per-octave note usage tracker — record note plays bucketed by octave (C-1..G9).

Tracks note frequencies across 11 MIDI octaves, computes octave transitions,
identifies dominant octave, and exposes frequency distribution. Pure stdlib, no Qt.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class OctaveStats:
    """Summary statistics of octave usage.

    Attributes:
        octave_counts: List of 11 integers (octaves -1..9), count of notes per octave.
        total_plays: Total number of notes recorded.
        dominant_octave: Octave with highest play count, or None if empty.
        octave_transitions: Number of times consecutive notes landed in different octaves.
        most_common_transition: Tuple (from_octave, to_octave) for the most-frequent pair,
            or None if no transitions or tied.
    """
    octave_counts: List[int] = field(default_factory=lambda: [0] * 11)
    total_plays: int = 0
    dominant_octave: Optional[int] = None
    octave_transitions: int = 0
    most_common_transition: Optional[Tuple[int, int]] = None

    def to_dict(self) -> dict:
        """Serialize to JSON-friendly dict."""
        return {
            "octave_counts": self.octave_counts,
            "total_plays": self.total_plays,
            "dominant_octave": self.dominant_octave,
            "octave_transitions": self.octave_transitions,
            "most_common_transition": list(self.most_common_transition) if self.most_common_transition else None,
        }

    @classmethod
    def from_dict(cls, d: dict) -> OctaveStats:
        """Deserialize from JSON-friendly dict."""
        mct = d.get("most_common_transition")
        mct_tuple = tuple(mct) if mct else None
        return cls(
            octave_counts=list(d.get("octave_counts", [0] * 11)),
            total_plays=int(d.get("total_plays", 0)),
            dominant_octave=d.get("dominant_octave"),
            octave_transitions=int(d.get("octave_transitions", 0)),
            most_common_transition=mct_tuple,
        )


@dataclass
class OctaveTrackerConfig:
    """Configuration for NoteOctaveTracker.

    Attributes:
        max_samples: Maximum number of note samples to keep (clamped 100..1000000).
    """
    max_samples: int = 10000

    def __post_init__(self) -> None:
        """Clamp max_samples to valid range."""
        self.max_samples = max(100, min(1000000, self.max_samples))

    def to_dict(self) -> dict:
        """Serialize to JSON-friendly dict."""
        return {"max_samples": self.max_samples}

    @classmethod
    def from_dict(cls, d: dict) -> OctaveTrackerConfig:
        """Deserialize from JSON-friendly dict."""
        return cls(max_samples=int(d.get("max_samples", 10000)))


class NoteOctaveTracker:
    """Track MIDI note usage bucketed by octave.

    Records individual note plays, computes octave frequency distribution,
    detects octave transitions, and identifies dominant octave.
    """

    def __init__(self, cfg: OctaveTrackerConfig) -> None:
        """Initialize tracker with config.

        Args:
            cfg: OctaveTrackerConfig instance.
        """
        self._cfg = cfg
        self._counts: List[int] = [0] * 11  # octaves -1..9
        self._samples: List[int] = []  # FIFO of recorded octaves
        self._last_oct: Optional[int] = None  # octave of last recorded note
        self._transition_counts: Dict[Tuple[int, int], int] = {}  # (from_oct, to_oct) -> count
        self._transitions: int = 0  # total transition count

    def record(self, note: int) -> None:
        """Record a single MIDI note.

        Args:
            note: MIDI note number 0..127. Converted to octave -1..9 and clamped to 0..10 index.
        """
        # Clamp note to valid MIDI range
        note = max(0, min(127, note))

        # Compute octave: MIDI C-1 (note 0) = octave -1, C4 (note 60) = octave 4
        octave = (note // 12) - 1

        # Clamp octave index to 0..10 (representing octaves -1..9)
        octave_idx = max(0, min(10, octave + 1))  # shift -1..9 to 0..10

        # Increment count for this octave
        self._counts[octave_idx] += 1

        # Track transitions: if last_oct exists and differs, count the transition
        if self._last_oct is not None and self._last_oct != octave_idx:
            self._transitions += 1
            key = (self._last_oct, octave_idx)
            self._transition_counts[key] = self._transition_counts.get(key, 0) + 1

        # Update last octave
        self._last_oct = octave_idx

        # Append to samples and maintain FIFO (max_samples limit)
        self._samples.append(octave_idx)
        if len(self._samples) > self._cfg.max_samples:
            self._samples.pop(0)

    def analyze(self) -> OctaveStats:
        """Compute current octave usage statistics.

        Returns:
            OctaveStats with counts, total plays, dominant octave, transitions,
            and most-common transition pair.
        """
        total = sum(self._counts)

        # Find dominant octave (highest count)
        dominant = None
        max_count = 0
        for idx, count in enumerate(self._counts):
            if count > max_count:
                max_count = count
                dominant = idx - 1  # shift 0..10 back to -1..9

        # Find most-common transition
        most_common_trans = None
        max_trans_count = 0
        for (from_oct, to_oct), count in self._transition_counts.items():
            if count > max_trans_count:
                max_trans_count = count
                # Convert indices back to octave numbers (-1..9)
                most_common_trans = (from_oct - 1, to_oct - 1)

        return OctaveStats(
            octave_counts=self._counts[:],
            total_plays=total,
            dominant_octave=dominant,
            octave_transitions=self._transitions,
            most_common_transition=most_common_trans,
        )

    def clear(self) -> None:
        """Clear all recorded data."""
        self._counts = [0] * 11
        self._samples = []
        self._last_oct = None
        self._transition_counts = {}
        self._transitions = 0

    def total(self) -> int:
        """Return total number of notes recorded (before FIFO eviction)."""
        return sum(self._counts)
