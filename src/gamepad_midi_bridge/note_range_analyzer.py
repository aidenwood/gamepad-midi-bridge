"""Analyze note pitch range: highest, lowest, span, octave coverage, and distribution."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional


# Note names for display
NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


@dataclass
class NoteRangeAnalysis:
    """Result of analyzing a session's note range."""

    low_note: Optional[int]  # Lowest MIDI note (0..127), or None if no samples
    high_note: Optional[int]  # Highest MIDI note (0..127), or None if no samples
    span_semitones: int  # high_note - low_note (0 if only one note or no samples)
    span_octaves: float  # span_semitones / 12.0
    unique_notes: int  # Count of unique notes played
    octave_distribution: dict[int, int]  # octave number → note-on count
    most_used_octave: Optional[int]  # Octave with highest note-on count

    def to_dict(self) -> dict:
        """Serialize analysis to dict."""
        return {
            "low_note": self.low_note,
            "high_note": self.high_note,
            "span_semitones": self.span_semitones,
            "span_octaves": self.span_octaves,
            "unique_notes": self.unique_notes,
            "octave_distribution": self.octave_distribution,
            "most_used_octave": self.most_used_octave,
        }

    @classmethod
    def from_dict(cls, data: dict) -> NoteRangeAnalysis:
        """Deserialize analysis from dict."""
        return cls(
            low_note=data.get("low_note"),
            high_note=data.get("high_note"),
            span_semitones=int(data.get("span_semitones", 0)),
            span_octaves=float(data.get("span_octaves", 0.0)),
            unique_notes=int(data.get("unique_notes", 0)),
            octave_distribution=dict(data.get("octave_distribution", {})),
            most_used_octave=data.get("most_used_octave"),
        )


@dataclass
class NoteRangeConfig:
    """Configuration for note range analyzer."""

    max_samples: int = 10000

    def __post_init__(self) -> None:
        """Clamp max_samples to valid range."""
        self.max_samples = max(100, min(1000000, self.max_samples))

    def to_dict(self) -> dict:
        """Serialize config to dict."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> NoteRangeConfig:
        """Deserialize config from dict."""
        return cls(**data)


class NoteRangeAnalyzer:
    """Track the highest and lowest notes played in a session.

    Analyzes:
    - Low and high notes
    - Semitone and octave span
    - Unique notes (sticky: once a note is played, it counts as unique even if window-evicted)
    - Octave distribution (per-octave note-on counts)
    - Most-used octave
    """

    def __init__(self, cfg: NoteRangeConfig) -> None:
        """Initialize note range analyzer.

        Args:
            cfg: NoteRangeConfig instance.
        """
        self.config = cfg
        self._samples: list[int] = []  # FIFO list of recorded notes
        self._octave_counts: dict[int, int] = {}  # octave → count (updated on record)
        self._unique: set[int] = set()  # All notes ever played (sticky)

    def record(self, note: int) -> None:
        """Record a note play.

        Clamps note to 0..127. Updates octave distribution. Maintains FIFO with
        max_samples eviction. Unique notes set is persistent (doesn't shrink with eviction).

        Args:
            note: MIDI note number (0..127), will be clamped.
        """
        # Clamp note to valid range
        note = max(0, min(127, note))

        # Calculate octave: octave 0 = C-1..B-1, so MIDI 60 (C4) = octave 4
        octave = (note // 12) - 1

        # Enforce max_samples limit before adding (evict oldest from front if at capacity)
        if len(self._samples) >= self.config.max_samples:
            evicted_note = self._samples.pop(0)
            evicted_octave = (evicted_note // 12) - 1
            self._octave_counts[evicted_octave] -= 1
            # Note: _unique is NOT decremented (sticky)

        # Update octave count
        self._octave_counts[octave] = self._octave_counts.get(octave, 0) + 1

        # Add to unique set
        self._unique.add(note)

        # Append to FIFO
        self._samples.append(note)

    def analyze(self) -> NoteRangeAnalysis:
        """Analyze current note range.

        Returns:
            NoteRangeAnalysis with low/high notes, span, octave distribution, etc.
        """
        if not self._samples:
            return NoteRangeAnalysis(
                low_note=None,
                high_note=None,
                span_semitones=0,
                span_octaves=0.0,
                unique_notes=0,
                octave_distribution={},
                most_used_octave=None,
            )

        low_note = min(self._samples)
        high_note = max(self._samples)
        span_semitones = high_note - low_note

        # Find most-used octave
        most_used_octave = None
        max_count = 0
        for octave, count in self._octave_counts.items():
            if count > max_count:
                max_count = count
                most_used_octave = octave

        return NoteRangeAnalysis(
            low_note=low_note,
            high_note=high_note,
            span_semitones=span_semitones,
            span_octaves=span_semitones / 12.0,
            unique_notes=len(self._unique),
            octave_distribution=dict(self._octave_counts),
            most_used_octave=most_used_octave,
        )

    def clear(self) -> None:
        """Clear all samples, counts, and unique set."""
        self._samples = []
        self._octave_counts = {}
        self._unique = set()

    def total_notes(self) -> int:
        """Get total number of note plays (size of FIFO window).

        Returns:
            Count of notes in the current sample window.
        """
        return len(self._samples)

    @staticmethod
    def note_name(note: int) -> str:
        """Convert MIDI note number to note name.

        Args:
            note: MIDI note number (0..127).

        Returns:
            Note name string, e.g. "C4", "C#4", "D4", etc.
            For notes outside 0..127, returns "?" followed by the note number.

        Examples:
            >>> NoteRangeAnalyzer.note_name(60)
            'C4'
            >>> NoteRangeAnalyzer.note_name(61)
            'C#4'
            >>> NoteRangeAnalyzer.note_name(72)
            'C5'
        """
        if note < 0 or note > 127:
            return f"?{note}"

        pitch_class = note % 12
        octave = (note // 12) - 1
        return f"{NOTE_NAMES[pitch_class]}{octave}"
