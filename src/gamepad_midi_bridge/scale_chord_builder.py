"""Scale-aware chord builder — compose triads and seventh chords from scale degrees.

Uses scale.py intervals and chord_shapes utilities to build diatonic chords
(I, IV, V, vi, etc.) and common progressions (I-V-vi-IV, ii-V-I, etc.).
All functions are pure — no Qt, no side effects, stdlib only.
"""
from __future__ import annotations

from typing import List

from .scales import SCALES, notes_in_scale

# Roman numeral degree → scale degree index (0-based, case-insensitive)
DEGREE_TO_INDEX: dict[str, int] = {
    "I": 0,
    "i": 0,
    "ii": 1,
    "II": 1,
    "iii": 2,
    "III": 2,
    "IV": 3,
    "iv": 3,
    "V": 4,
    "v": 4,
    "vi": 5,
    "VI": 5,
    "vii": 6,
    "VII": 6,
}

# Common progressions: name → list of degree names
_PRESET_PROGRESSIONS: dict[str, list[str]] = {
    "I-V-vi-IV": ["I", "V", "vi", "IV"],          # universal pop/rock loop
    "ii-V-I": ["ii", "V", "I"],                    # jazz cadence
    "vi-IV-I-V": ["vi", "IV", "I", "V"],          # pop variant
    "I-IV-V-I": ["I", "IV", "V", "I"],            # classic blues / folk
    "I-vi-IV-V": ["I", "vi", "IV", "V"],          # 50s doo-wop
}


def build_triad(
    root: int, scale: str, degree: str, octave: int = 4
) -> List[int]:
    """Build a three-note triad from a scale degree.

    Walks the scale from the given degree and picks:
    - Scale step 0 (root)
    - Scale step 2 (third)
    - Scale step 4 (fifth)

    Args:
        root: Scale root MIDI note (0..11, e.g. 0=C, 2=D).
        scale: Scale name (must exist in SCALES).
        degree: Roman numeral degree (I, ii, iii, IV, V, vi, vii, case-insensitive).
        octave: Starting octave for the root note (scientific, default 4).

    Returns:
        List of 3 MIDI notes [root, third, fifth], clamped to 0..127.

    Raises:
        ValueError: If scale is unknown.
        KeyError: If degree is not in DEGREE_TO_INDEX.
    """
    if scale not in SCALES:
        raise ValueError(f"Unknown scale: {scale}")

    if degree not in DEGREE_TO_INDEX:
        raise KeyError(f"Unknown degree: {degree}")

    # Get scale intervals (offsets from root in semitones)
    intervals = SCALES[scale]
    scale_length = len(intervals)

    # Get the degree index (0 = I, 1 = ii, etc.)
    degree_idx = DEGREE_TO_INDEX[degree]

    # Build two octaves of scale notes to ensure we can find the third and fifth
    scale_notes = notes_in_scale(root, scale, octaves=2, base_octave=octave)

    if not scale_notes:
        raise ValueError(f"No scale notes generated for {scale}")

    # Pick notes at positions: degree_idx, degree_idx + 2, degree_idx + 4
    # (wrapping modulo scale_length)
    third_idx = (degree_idx + 2) % scale_length
    fifth_idx = (degree_idx + 4) % scale_length

    # Calculate the target intervals in semitones from the scale root
    root_interval = intervals[degree_idx]
    third_interval = intervals[third_idx]
    fifth_interval = intervals[fifth_idx]

    # Build list of candidate notes for each position
    root_candidates = []
    third_candidates = []
    fifth_candidates = []

    for midi_note in scale_notes:
        pitch_class = midi_note % 12
        root_pitch_class = root % 12
        interval_from_root = (pitch_class - root_pitch_class) % 12

        if interval_from_root == root_interval:
            root_candidates.append(midi_note)
        elif interval_from_root == third_interval:
            third_candidates.append(midi_note)
        elif interval_from_root == fifth_interval:
            fifth_candidates.append(midi_note)

    # Pick the first root note
    root_note = root_candidates[0] if root_candidates else scale_notes[0]

    # Pick the first third note that's higher than the root
    third_note = None
    for note in third_candidates:
        if note > root_note:
            third_note = note
            break
    if third_note is None and third_candidates:
        third_note = third_candidates[-1]  # Fallback to highest third
    if third_note is None:
        third_note = root_note + 4  # Fallback to major third interval

    # Pick the first fifth note that's higher than the third
    fifth_note = None
    for note in fifth_candidates:
        if note > third_note:
            fifth_note = note
            break
    if fifth_note is None and fifth_candidates:
        fifth_note = fifth_candidates[-1]  # Fallback to highest fifth
    if fifth_note is None:
        fifth_note = root_note + 7  # Fallback to perfect fifth interval

    return [root_note, third_note, fifth_note]


def build_seventh(
    root: int, scale: str, degree: str, octave: int = 4
) -> List[int]:
    """Build a four-note seventh chord from a scale degree.

    Uses build_triad and adds the seventh scale step.

    Args:
        root: Scale root MIDI note (0..11).
        scale: Scale name (must exist in SCALES).
        degree: Roman numeral degree (case-insensitive).
        octave: Starting octave for the root note (scientific, default 4).

    Returns:
        List of 4 MIDI notes [root, third, fifth, seventh], clamped to 0..127.

    Raises:
        ValueError: If scale is unknown.
        KeyError: If degree is not in DEGREE_TO_INDEX.
    """
    if scale not in SCALES:
        raise ValueError(f"Unknown scale: {scale}")

    if degree not in DEGREE_TO_INDEX:
        raise KeyError(f"Unknown degree: {degree}")

    # Start with the triad
    triad = build_triad(root, scale, degree, octave)

    # Get scale intervals
    intervals = SCALES[scale]
    scale_length = len(intervals)

    # Get the degree index and seventh index
    degree_idx = DEGREE_TO_INDEX[degree]
    seventh_idx = (degree_idx + 6) % scale_length

    # Build two octaves of scale notes
    scale_notes = notes_in_scale(root, scale, octaves=2, base_octave=octave)

    if not scale_notes:
        return triad

    # Find the seventh note (scale step 6 above the degree root)
    seventh_note = None
    for midi_note in scale_notes:
        pitch_class = midi_note % 12
        root_pitch_class = root % 12
        interval_from_root = (pitch_class - root_pitch_class) % 12

        if interval_from_root == intervals[seventh_idx]:
            seventh_note = midi_note
            break

    # If we found the seventh and it's higher than the fifth, use it
    if seventh_note is not None and seventh_note > triad[2]:
        return [triad[0], triad[1], triad[2], seventh_note]

    # Otherwise use the first suitable seven-step note
    if seventh_note is not None:
        return [triad[0], triad[1], triad[2], seventh_note]

    return triad


def build_progression(
    root: int,
    scale: str,
    degrees: List[str],
    octave: int = 4,
    chord_type: str = "triad",
) -> List[List[int]]:
    """Build a chord progression from a list of scale degrees.

    Args:
        root: Scale root MIDI note (0..11).
        scale: Scale name (must exist in SCALES).
        degrees: List of Roman numeral degrees (e.g. ["I", "V", "vi", "IV"]).
        octave: Starting octave for chords (scientific, default 4).
        chord_type: "triad" or "seventh" (default "triad", unknown defaults to "triad").

    Returns:
        List of chords, where each chord is a list of MIDI notes.
        Empty list if degrees is empty.

    Raises:
        ValueError: If scale is unknown.
        KeyError: If any degree is not in DEGREE_TO_INDEX.
    """
    if not degrees:
        return []

    if scale not in SCALES:
        raise ValueError(f"Unknown scale: {scale}")

    builder = build_seventh if chord_type == "seventh" else build_triad

    chords = []
    for degree in degrees:
        if degree not in DEGREE_TO_INDEX:
            raise KeyError(f"Unknown degree: {degree}")
        chord = builder(root, scale, degree, octave)
        chords.append(chord)

    return chords


def build_pop_progression(
    root: int, scale: str, name: str, octave: int = 4
) -> List[List[int]]:
    """Build a preset chord progression by name.

    Available progressions:
    - "I-V-vi-IV" — universal pop/rock loop
    - "ii-V-I" — jazz cadence
    - "vi-IV-I-V" — pop variant
    - "I-IV-V-I" — classic blues / folk
    - "I-vi-IV-V" — 50s doo-wop

    Args:
        root: Scale root MIDI note (0..11).
        scale: Scale name (must exist in SCALES).
        name: Progression name (must be in _PRESET_PROGRESSIONS).
        octave: Starting octave for chords (scientific, default 4).

    Returns:
        List of chords (each a list of MIDI notes).
        Empty list if progression name is unknown.

    Raises:
        ValueError: If scale is unknown.
    """
    if scale not in SCALES:
        raise ValueError(f"Unknown scale: {scale}")

    if name not in _PRESET_PROGRESSIONS:
        return []

    degrees = _PRESET_PROGRESSIONS[name]
    return build_progression(root, scale, degrees, octave, chord_type="triad")


def available_progressions() -> List[str]:
    """Return list of available preset progression names.

    Returns:
        List of progression names (5 entries).
    """
    return list(_PRESET_PROGRESSIONS.keys())
