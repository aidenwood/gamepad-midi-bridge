"""MIDI scale intervals — semitone offsets from the root, modulo 12."""
from __future__ import annotations

SCALES: dict[str, list[int]] = {
    "chromatic":        [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
    "major":            [0, 2, 4, 5, 7, 9, 11],
    "minor":            [0, 2, 3, 5, 7, 8, 10],   # natural minor
    "dorian":           [0, 2, 3, 5, 7, 9, 10],
    "phrygian":         [0, 1, 3, 5, 7, 8, 10],
    "lydian":           [0, 2, 4, 6, 7, 9, 11],
    "mixolydian":       [0, 2, 4, 5, 7, 9, 10],
    "locrian":          [0, 1, 3, 5, 6, 8, 10],
    "pentatonic_major": [0, 2, 4, 7, 9],
    "pentatonic_minor": [0, 3, 5, 7, 10],
    "blues":            [0, 3, 5, 6, 7, 10],
    "harmonic_minor":   [0, 2, 3, 5, 7, 8, 11],
    "melodic_minor":    [0, 2, 3, 5, 7, 9, 11],
    "whole_tone":       [0, 2, 4, 6, 8, 10],
    "diminished":       [0, 2, 3, 5, 6, 8, 9, 11],
}


def note_for_sector(root: int, scale_name: str, sector: int, sector_count: int) -> int:  # noqa: ARG001
    """Return the MIDI note for a given quantize sector under a scale.

    Walks scale degrees in ascending order starting at root, wrapping the
    octave at scale-length boundaries.  e.g. with major scale + 8 sectors,
    sectors 0..6 map to C4..B4 and sector 7 wraps to C5.
    """
    intervals = SCALES.get(scale_name, SCALES["chromatic"])
    octave_offset = (sector // len(intervals)) * 12
    interval = intervals[sector % len(intervals)]
    note = root + interval + octave_offset
    return max(0, min(127, note))
