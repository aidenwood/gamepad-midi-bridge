"""Note chord detector — identify chords from simultaneous MIDI notes.

Given a set of simultaneously-held MIDI notes (integers 0..127),
identifies if they form a recognised chord (major, minor, 7th, sus, dim, etc)
and returns its name and confidence. Pure stdlib + dataclass, no Qt.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


# Interval patterns in semitones from root (sorted tuples).
CHORD_INTERVAL_PATTERNS: Dict[str, Tuple[int, ...]] = {
    "major": (0, 4, 7),
    "minor": (0, 3, 7),
    "dim": (0, 3, 6),
    "aug": (0, 4, 8),
    "sus4": (0, 5, 7),
    "sus2": (0, 2, 7),
    "maj7": (0, 4, 7, 11),
    "min7": (0, 3, 7, 10),
    "dom7": (0, 4, 7, 10),
    "min7b5": (0, 3, 6, 10),
    "dim7": (0, 3, 6, 9),
    "maj6": (0, 4, 7, 9),
    "min6": (0, 3, 7, 9),
}

# Note names for MIDI pitch display (C=0, C#=1, ..., B=11).
NOTE_NAMES: List[str] = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


@dataclass
class ChordIdentification:
    """Result of chord identification."""

    root_note: int  # MIDI note 0..127
    root_name: str  # e.g. "C", "F#"
    quality: str  # e.g. "major", "min7"
    display_name: str  # e.g. "C major", "F#m7"
    confidence: float  # 0.0..1.0
    inversion: int  # 0 = root position, 1 = first inversion, etc.

    def to_dict(self) -> dict:
        """Serialize to dict."""
        return {
            "root_note": self.root_note,
            "root_name": self.root_name,
            "quality": self.quality,
            "display_name": self.display_name,
            "confidence": self.confidence,
            "inversion": self.inversion,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ChordIdentification:
        """Deserialize from dict."""
        return cls(
            root_note=data["root_note"],
            root_name=data["root_name"],
            quality=data["quality"],
            display_name=data["display_name"],
            confidence=data["confidence"],
            inversion=data["inversion"],
        )


def chord_short_name(quality: str, root_name: str) -> str:
    """Abbreviate chord quality + root into short notation.

    e.g. ("major", "C") → "C", ("min7", "F#") → "F#m7"
    """
    quality_map = {
        "major": "",
        "minor": "m",
        "dim": "dim",
        "aug": "aug",
        "sus4": "sus4",
        "sus2": "sus2",
        "maj7": "maj7",
        "min7": "m7",
        "dom7": "7",
        "min7b5": "m7b5",
        "dim7": "dim7",
        "maj6": "6",
        "min6": "m6",
    }
    suffix = quality_map.get(quality, quality)
    return f"{root_name}{suffix}"


def detect_inversion(
    notes: List[int], root: int, pattern: Tuple[int, ...]
) -> int:
    """Detect inversion by finding which scale degree is in the bass.

    Returns 0 for root position, 1 for first inversion, etc.
    If lowest note is root, returns 0.
    If lowest note is second note of pattern, returns 1.
    """
    if not notes:
        return 0

    lowest_note = min(notes)
    lowest_pitch_class = lowest_note % 12

    # Try each note of the chord as the lowest note.
    for inversion, interval in enumerate(pattern):
        candidate_root = (lowest_pitch_class - interval) % 12
        candidate_note_from_root = (root + interval) % 12
        if candidate_root % 12 == (root % 12):
            return inversion

    # Fall back to root position.
    return 0


def identify_chord(notes: List[int]) -> Optional[ChordIdentification]:
    """Identify chord from list of simultaneously-held MIDI notes.

    Returns ChordIdentification if a match is found with at least 2 intervals
    matching the pattern. Returns None otherwise.

    Args:
        notes: List of MIDI notes (0..127).

    Returns:
        ChordIdentification or None.
    """
    if not notes or len(notes) < 2:
        return None

    # Normalize to pitch classes (0..11) and unique.
    pitch_classes = sorted(set(note % 12 for note in notes))

    if len(pitch_classes) < 2:
        # Only one unique pitch class — can't form a chord.
        return None

    best_match = None
    best_confidence = 0.0
    best_pattern_len = 0  # Tiebreaker: prefer longer patterns

    # Try each pitch class as the root.
    for root_pitch_class in pitch_classes:
        # Compute intervals from this root.
        intervals = tuple(
            sorted(set((pc - root_pitch_class) % 12 for pc in pitch_classes))
        )

        # Try to match against known patterns.
        for quality, pattern in CHORD_INTERVAL_PATTERNS.items():
            # Count how many pattern intervals match.
            pattern_set = set(pattern)
            matched = sum(1 for interval in intervals if interval in pattern_set)

            # Require at least 2 matched intervals.
            if matched < 2:
                continue

            # Confidence is the ratio of matched intervals to total pattern intervals.
            confidence = matched / len(pattern)

            # Choose this match if:
            # 1. It has higher confidence, OR
            # 2. Same confidence but longer pattern (more specific), OR
            # 3. Same confidence and same length but hasn't been set yet
            if (
                confidence > best_confidence
                or (confidence == best_confidence and len(pattern) > best_pattern_len)
            ):
                best_confidence = confidence
                best_pattern_len = len(pattern)
                # Pick the lowest MIDI note >= 0 that maps to this root pitch class.
                root_midi = next(
                    (n for n in sorted(notes) if n % 12 == root_pitch_class),
                    root_pitch_class,
                )
                root_name = NOTE_NAMES[root_pitch_class]

                # Detect inversion.
                inversion = detect_inversion(notes, root_midi, pattern)

                best_match = ChordIdentification(
                    root_note=root_midi,
                    root_name=root_name,
                    quality=quality,
                    display_name=f"{root_name} {quality}",
                    confidence=confidence,
                    inversion=inversion,
                )

    return best_match if best_confidence >= 0.4 else None
