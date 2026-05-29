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


def notes_in_scale(
    root: int, scale: str, octaves: int = 4, base_octave: int = 3
) -> list[int]:
    """Return sorted list of MIDI notes in the scale across octaves.

    Args:
        root: Root note (0..11, e.g. 0=C, 2=D, 5=F).
        scale: Scale name (must exist in SCALES dict).
        octaves: Number of octaves to generate.
        base_octave: Starting octave. Uses scientific pitch convention:
            base_octave=4 yields MIDI 60 (C4 = middle C) as the root note.

    Returns:
        Sorted list of MIDI notes (0..127), clamped to valid range.

    Raises:
        ValueError: If scale name is not in SCALES.
    """
    if scale not in SCALES:
        raise ValueError(f"Unknown scale: {scale}")

    intervals = SCALES[scale]
    notes = []
    # Convert scientific octave to MIDI octave: scientific octave N corresponds to MIDI octave (N+1)
    # So scientific octave 4 (C4 = MIDI 60) → MIDI octave 5 → MIDI 60 = (5)*12 + 0
    midi_octave = base_octave + 1
    start_midi_note = midi_octave * 12 + root

    for octave_offset in range(octaves):
        for interval in intervals:
            note = start_midi_note + (octave_offset * 12) + interval
            if 0 <= note <= 127:
                notes.append(note)

    return sorted(notes)


def quantize_to_scale(note: int, root: int, scale: str) -> int:
    """Return the nearest scale note to the given MIDI note.

    On tie (two equally distant notes), returns the higher note.

    Args:
        note: MIDI note to quantize (0..127).
        root: Scale root (0..11).
        scale: Scale name (must exist in SCALES dict).

    Returns:
        Nearest MIDI note in the scale (0..127).

    Raises:
        ValueError: If scale name is not in SCALES.
    """
    if scale not in SCALES:
        raise ValueError(f"Unknown scale: {scale}")

    intervals = SCALES[scale]

    # Build a full range of scale notes (0..127)
    scale_notes = []
    for midi_note in range(128):
        # Check if this note is in the scale
        octave = midi_note // 12
        pitch_class = midi_note % 12
        root_pitch_class = root % 12
        interval_from_root = (pitch_class - root_pitch_class) % 12
        if interval_from_root in intervals:
            scale_notes.append(midi_note)

    # Find the closest scale note, ties round up (higher)
    closest = scale_notes[0]
    min_distance = abs(note - closest)

    for scale_note in scale_notes:
        distance = abs(note - scale_note)
        # Tie: choose higher note
        if distance < min_distance or (distance == min_distance and scale_note > closest):
            closest = scale_note
            min_distance = distance

    return closest


def magnitude_to_scale_note(
    magnitude_0_1: float, root: int, scale: str, octaves: int = 2, base_octave: int = 3
) -> int:
    """Map a 0..1 magnitude to a scale note.

    Maps the magnitude linearly onto the list of scale notes:
    - magnitude <= 0 returns the lowest note.
    - magnitude >= 1 returns the highest note.
    - In-between values pick the nearest index: round(magnitude * (len(notes) - 1)).

    Args:
        magnitude_0_1: Normalized value in [0, 1].
        root: Scale root (0..11).
        scale: Scale name (must exist in SCALES dict).
        octaves: Number of octaves to generate.
        base_octave: Starting octave.

    Returns:
        MIDI note (0..127) in the scale.

    Raises:
        ValueError: If scale name is not in SCALES.
    """
    notes = notes_in_scale(root, scale, octaves, base_octave)

    if not notes:
        raise ValueError(f"No scale notes generated for {scale}")

    # Clamp magnitude to [0, 1]
    clamped = max(0.0, min(1.0, magnitude_0_1))

    # Map to index: [0, len-1]
    index = round(clamped * (len(notes) - 1))

    return notes[index]
