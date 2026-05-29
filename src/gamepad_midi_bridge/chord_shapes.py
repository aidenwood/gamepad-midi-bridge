"""Chord shape utilities — pure-function transformations for MIDI note lists.

Inversions, 7th/9th additions, drop voicings, octave doubling, and voice-leading.
All functions return new lists; no mutation of inputs.
"""
from __future__ import annotations

from typing import List


def invert_up(notes: List[int], inversions: int = 1) -> List[int]:
    """Move the bottom note up an octave, `inversions` times.

    inversions=0 returns the input unchanged.
    Empty list returns empty list.

    Args:
        notes: List of MIDI note numbers.
        inversions: Number of times to move the bottom note up an octave (12 semitones).

    Returns:
        New list with inversions applied.
    """
    if not notes or inversions <= 0:
        return list(notes)

    result = list(notes)
    for _ in range(inversions):
        if result:
            bottom = result.pop(0)
            result.append(bottom + 12)
    return result


def invert_down(notes: List[int], inversions: int = 1) -> List[int]:
    """Move the top note down an octave, `inversions` times.

    inversions=0 returns the input unchanged.
    Empty list returns empty list.

    Args:
        notes: List of MIDI note numbers.
        inversions: Number of times to move the top note down an octave (12 semitones).

    Returns:
        New list with inversions applied.
    """
    if not notes or inversions <= 0:
        return list(notes)

    result = list(notes)
    for _ in range(inversions):
        if result:
            top = result.pop()
            result.insert(0, top - 12)
    return result


def add_seventh(notes: List[int], minor: bool = False) -> List[int]:
    """Append a 7th interval above the root.

    Minor 7th = 10 semitones above root.
    Major 7th = 11 semitones above root.
    Empty list returns empty list.

    Args:
        notes: List of MIDI note numbers.
        minor: If True, add minor 7th (10 semitones); else major 7th (11 semitones).

    Returns:
        New list with 7th appended.
    """
    if not notes:
        return []

    result = list(notes)
    root = result[0]
    seventh = root + (10 if minor else 11)
    result.append(seventh)
    return result


def add_ninth(notes: List[int]) -> List[int]:
    """Append a 9th interval above the root.

    9th = 14 semitones above root.
    Empty list returns empty list.

    Args:
        notes: List of MIDI note numbers.

    Returns:
        New list with 9th appended.
    """
    if not notes:
        return []

    result = list(notes)
    root = result[0]
    ninth = root + 14
    result.append(ninth)
    return result


def drop_2(notes: List[int]) -> List[int]:
    """Drop the 2nd-from-top note down an octave.

    Requires >= 4 notes; else returns input unchanged.
    Returns a new list without sorting.

    Args:
        notes: List of MIDI note numbers.

    Returns:
        New list with the 2nd-from-top note dropped down 12 semitones,
        or input unchanged if < 4 notes.
    """
    if len(notes) < 4:
        return list(notes)

    result = list(notes)
    # 2nd from top is at index len(notes) - 2
    idx = len(result) - 2
    result[idx] = result[idx] - 12
    return result


def drop_3(notes: List[int]) -> List[int]:
    """Drop the 3rd-from-top note down an octave.

    Requires >= 4 notes; else returns input unchanged.
    Returns a new list without sorting.

    Args:
        notes: List of MIDI note numbers.

    Returns:
        New list with the 3rd-from-top note dropped down 12 semitones,
        or input unchanged if < 4 notes.
    """
    if len(notes) < 4:
        return list(notes)

    result = list(notes)
    # 3rd from top is at index len(notes) - 3
    idx = len(result) - 3
    result[idx] = result[idx] - 12
    return result


def octave_double(notes: List[int], octaves: int = 1) -> List[int]:
    """Append each note + 12*octaves above, skipping notes that exceed 127.

    Args:
        notes: List of MIDI note numbers.
        octaves: Number of octaves to double (each = 12 semitones).

    Returns:
        New list with each note doubled at the given octave offset.
        Notes that would exceed MIDI range (>127) are skipped.
        If octaves <= 0, returns input unchanged.
    """
    if not notes or octaves <= 0:
        return list(notes)

    result = list(notes)
    offset = 12 * octaves
    for note in notes:
        doubled = note + offset
        if doubled <= 127:
            result.append(doubled)
    return result


def clamp_to_midi(notes: List[int]) -> List[int]:
    """Filter notes outside the MIDI range (0..127).

    Args:
        notes: List of MIDI note numbers (may include out-of-range values).

    Returns:
        New list with only notes in 0..127 range.
    """
    return [n for n in notes if 0 <= n <= 127]


def voice_lead(prev: List[int], next: List[int]) -> List[int]:
    """Rearrange `next` to be closest to `prev` voice-by-voice (greedy).

    For each note in `prev`, find the closest note in `next` after octave adjustment,
    consuming each `next` note only once. If lists are different lengths, return `next` unchanged.

    Args:
        prev: Previous chord as a list of MIDI notes.
        next: Next chord as a list of MIDI notes.

    Returns:
        Rearranged version of `next` minimizing voice-leading distance,
        or `next` unchanged if lengths don't match.
    """
    if len(prev) != len(next):
        return list(next)

    if not prev:
        return list(next)

    result = []
    available = list(next)

    for prev_note in prev:
        # Find the closest available note, trying octave adjustments
        best_note = None
        best_distance = float('inf')
        best_idx = -1

        for idx, next_note in enumerate(available):
            # Try the note as-is and with ±1 octave adjustments
            for octave_adj in (0, -12, 12):
                adjusted = next_note + octave_adj
                distance = abs(adjusted - prev_note)
                if distance < best_distance:
                    best_distance = distance
                    best_note = adjusted
                    best_idx = idx

        if best_idx >= 0:
            result.append(best_note)
            available.pop(best_idx)

    return result
