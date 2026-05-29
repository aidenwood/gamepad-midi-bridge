"""Scale-quantize helper — note_for_sector correctness."""
from __future__ import annotations

import pytest

from gamepad_midi_bridge.scales import (
    SCALES,
    magnitude_to_scale_note,
    note_for_sector,
    notes_in_scale,
    quantize_to_scale,
)


# ------------------------------------------------------------------ SCALES dict


def test_all_scale_names_present():
    expected = {
        "chromatic", "major", "minor", "dorian", "phrygian", "lydian",
        "mixolydian", "locrian", "pentatonic_major", "pentatonic_minor",
        "blues", "harmonic_minor", "melodic_minor", "whole_tone", "diminished",
    }
    assert expected == set(SCALES.keys())


def test_major_intervals():
    assert SCALES["major"] == [0, 2, 4, 5, 7, 9, 11]


def test_minor_intervals():
    assert SCALES["minor"] == [0, 2, 3, 5, 7, 8, 10]


def test_pentatonic_major_length():
    assert len(SCALES["pentatonic_major"]) == 5


def test_chromatic_has_12_tones():
    assert len(SCALES["chromatic"]) == 12


# ------------------------------------------------------------------ note_for_sector


def test_major_8_sectors_from_c4():
    """Major scale + 8 sectors from C4: C4 D4 E4 F4 G4 A4 B4 C5."""
    root = 60  # C4
    expected = [60, 62, 64, 65, 67, 69, 71, 72]  # C D E F G A B C(+1oct)
    result = [note_for_sector(root, "major", s, 8) for s in range(8)]
    assert result == expected


def test_sector_0_always_equals_root_chromatic():
    for root in (0, 48, 60, 100, 127):
        assert note_for_sector(root, "chromatic", 0, 12) == root


def test_major_sector_wrap_to_next_octave():
    """Sector 7 in a major scale (len=7) wraps to root+12."""
    root = 60
    # sector 7 → octave 1, interval index 0 → root + 0 + 12 = 72
    assert note_for_sector(root, "major", 7, 8) == 72


def test_chromatic_second_octave():
    """Sector 12 on chromatic from C4 should be C5 (note 72)."""
    assert note_for_sector(60, "chromatic", 12, 24) == 72


def test_unknown_scale_falls_back_to_chromatic():
    """An unrecognised scale name falls back to chromatic intervals."""
    chromatic_note = note_for_sector(60, "chromatic", 3, 12)
    unknown_note = note_for_sector(60, "totally_made_up", 3, 12)
    assert unknown_note == chromatic_note


def test_out_of_range_high_root_clamped():
    """Root + offsets that would push past 127 are clamped to 127."""
    # Root 120, chromatic sector 11 → 131 → clamped to 127
    note = note_for_sector(120, "chromatic", 11, 12)
    assert note == 127


def test_out_of_range_low_root_clamped():
    """Root 0, no offset → note 0, never negative."""
    note = note_for_sector(0, "chromatic", 0, 12)
    assert note == 0


def test_pentatonic_major_4_sectors():
    """4 sectors over pentatonic_major from C4: C D E G."""
    root = 60
    expected = [60, 62, 64, 67]  # intervals [0,2,4,7]
    result = [note_for_sector(root, "pentatonic_major", s, 4) for s in range(4)]
    assert result == expected


def test_blues_scale_sector_sequence():
    """Blues scale [0,3,5,6,7,10] from root 48 (C3)."""
    root = 48
    intervals = SCALES["blues"]
    for i, interval in enumerate(intervals):
        assert note_for_sector(root, "blues", i, len(intervals)) == root + interval


def test_diminished_wraps_at_8():
    """Diminished (8 notes) sector 8 wraps to next octave."""
    root = 60
    # sector 8 → octave 1, index 0 → root + 12
    assert note_for_sector(root, "diminished", 8, 16) == 72


def test_whole_tone_6_sectors():
    """Whole-tone (6 notes) sectors 0..5 from C4."""
    root = 60
    expected = [60, 62, 64, 66, 68, 70]
    result = [note_for_sector(root, "whole_tone", s, 6) for s in range(6)]
    assert result == expected


def test_note_always_in_midi_range():
    """Every (root, scale, sector) combination stays 0..127."""
    for root in (0, 60, 120, 127):
        for scale_name in SCALES:
            for sector in range(32):
                n = note_for_sector(root, scale_name, sector, 32)
                assert 0 <= n <= 127, f"Out of range: root={root} scale={scale_name} sector={sector} → {n}"


def test_sector_count_param_unused_in_calculation():
    """sector_count is intentionally unused; result must not change with it."""
    n1 = note_for_sector(60, "major", 3, 8)
    n2 = note_for_sector(60, "major", 3, 16)
    assert n1 == n2


# ------------------------------------------------------------------ notes_in_scale


def test_notes_in_scale_major_one_octave():
    """Major scale from C4 across 1 octave: [C D E F G A B]."""
    result = notes_in_scale(0, "major", octaves=1, base_octave=4)
    expected = [60, 62, 64, 65, 67, 69, 71]
    assert result == expected


def test_notes_in_scale_minor_pentatonic_one_octave():
    """Minor pentatonic from C4 across 1 octave: [C Eb F G Bb]."""
    result = notes_in_scale(0, "pentatonic_minor", octaves=1, base_octave=4)
    expected = [60, 63, 65, 67, 70]
    assert result == expected


def test_notes_in_scale_major_base_octave_3():
    """Major scale from C3 (root=0, base_octave=3) across 1 octave."""
    result = notes_in_scale(0, "major", octaves=1, base_octave=3)
    # base_octave=3 → MIDI octave 4 → C3 = MIDI 48
    expected = [48, 50, 52, 53, 55, 57, 59]
    assert result == expected


def test_notes_in_scale_blues_length():
    """Blues scale should have 6 tones per octave."""
    result = notes_in_scale(0, "blues", octaves=1, base_octave=4)
    assert len(result) == 6


def test_notes_in_scale_whole_tone_length():
    """Whole tone scale should have 6 tones per octave."""
    result = notes_in_scale(0, "whole_tone", octaves=1, base_octave=4)
    assert len(result) == 6


def test_notes_in_scale_chromatic_length():
    """Chromatic scale should have 12 tones per octave."""
    result = notes_in_scale(0, "chromatic", octaves=1, base_octave=4)
    assert len(result) == 12


def test_notes_in_scale_two_octaves():
    """Major scale across 2 octaves from C4."""
    result = notes_in_scale(0, "major", octaves=2, base_octave=4)
    # First octave: C D E F G A B (60, 62, 64, 65, 67, 69, 71)
    # Second octave: C D E F G A B (72, 74, 76, 77, 79, 81, 83)
    assert len(result) == 14
    assert result[0] == 60
    assert result[7] == 72
    assert result[-1] == 83


def test_notes_in_scale_unknown_scale_raises():
    """Unknown scale name raises ValueError."""
    with pytest.raises(ValueError, match="Unknown scale"):
        notes_in_scale(0, "totally_made_up", octaves=1)


def test_notes_in_scale_clamped_at_127():
    """Notes beyond MIDI range (127) are excluded."""
    # Start at high octave, should clamp
    result = notes_in_scale(0, "major", octaves=2, base_octave=9)
    # Should not exceed 127
    assert len(result) > 0  # Should have at least some notes
    assert all(0 <= n <= 127 for n in result)
    assert max(result) <= 127


def test_notes_in_scale_with_different_root():
    """Major scale from D (root=2) across 1 octave."""
    result = notes_in_scale(2, "major", octaves=1, base_octave=4)
    # D4 = 62, then add major intervals: [0, 2, 4, 5, 7, 9, 11]
    expected = [62, 64, 66, 67, 69, 71, 73]
    assert result == expected


def test_notes_in_scale_sorted():
    """Result is always sorted."""
    result = notes_in_scale(5, "minor", octaves=3, base_octave=3)
    assert result == sorted(result)


# ------------------------------------------------------------------ quantize_to_scale


def test_quantize_to_scale_major_already_in_scale():
    """C (60) in major scale from C returns 60."""
    result = quantize_to_scale(60, 0, "major")
    assert result == 60


def test_quantize_to_scale_major_closer_to_lower():
    """F# (66) is closer to G (67) than E (64) in C major."""
    result = quantize_to_scale(66, 0, "major")
    assert result == 67


def test_quantize_to_scale_major_closer_to_upper():
    """C# (61) is closer to D (62) than C (60) in C major."""
    result = quantize_to_scale(61, 0, "major")
    assert result == 62


def test_quantize_to_scale_exact_tie_rounds_up():
    """On tie, chooses the higher note. C# (61) is equidistant from C (60) and D (62)."""
    result = quantize_to_scale(61, 0, "major")
    # Distance to C: 1, distance to D: 1 → tie, round up to D (62)
    assert result == 62


def test_quantize_to_scale_pentatonic_minor():
    """Minor pentatonic from C: [C Eb F G Bb]. E (64) → closest is F (65)."""
    result = quantize_to_scale(64, 0, "pentatonic_minor")
    assert result == 65


def test_quantize_to_scale_unknown_scale_raises():
    """Unknown scale raises ValueError."""
    with pytest.raises(ValueError, match="Unknown scale"):
        quantize_to_scale(60, 0, "totally_made_up")


def test_quantize_to_scale_very_low_note():
    """MIDI note 0 (lowest) quantizes correctly."""
    result = quantize_to_scale(0, 0, "chromatic")
    assert result == 0
    assert 0 <= result <= 127


def test_quantize_to_scale_very_high_note():
    """MIDI note 127 (highest) quantizes correctly."""
    result = quantize_to_scale(127, 0, "chromatic")
    assert result == 127
    assert 0 <= result <= 127


def test_quantize_to_scale_with_different_root():
    """Major scale from D (root=2): D E F# G A B C#. C (60) → closest is D (62)."""
    result = quantize_to_scale(60, 2, "major")
    # D major intervals from D (pitch class 2): [0, 2, 4, 5, 7, 9, 11]
    # C (60) is pitch class 0, not in D major
    # Closest notes: C# (61, distance 1) and D (62, distance 2)
    # So result should be 61 (C#)
    assert result == 61


def test_quantize_to_scale_returns_in_midi_range():
    """Result is always a valid MIDI note (0..127)."""
    for note in [0, 30, 60, 90, 127]:
        for scale in SCALES:
            result = quantize_to_scale(note, 0, scale)
            assert 0 <= result <= 127


# ------------------------------------------------------------------ magnitude_to_scale_note


def test_magnitude_to_scale_note_zero():
    """Magnitude 0.0 returns the lowest scale note."""
    result = magnitude_to_scale_note(0.0, 0, "major", octaves=1, base_octave=4)
    expected = 60  # C4
    assert result == expected


def test_magnitude_to_scale_note_one():
    """Magnitude 1.0 returns the highest scale note."""
    result = magnitude_to_scale_note(1.0, 0, "major", octaves=1, base_octave=4)
    expected = 71  # B4 (major scale highest in 1 octave from C4)
    assert result == expected


def test_magnitude_to_scale_note_middle():
    """Magnitude 0.5 with 7-note major scale returns the median note."""
    result = magnitude_to_scale_note(0.5, 0, "major", octaves=1, base_octave=4)
    # Major has 7 notes: C D E F G A B (60, 62, 64, 65, 67, 69, 71)
    # 0.5 * 6 = 3.0 → index 3 → F4 (65)
    assert result == 65


def test_magnitude_to_scale_note_clamped_below_zero():
    """Magnitude < 0 is clamped to 0.0."""
    result_negative = magnitude_to_scale_note(-0.5, 0, "major", octaves=1, base_octave=4)
    result_zero = magnitude_to_scale_note(0.0, 0, "major", octaves=1, base_octave=4)
    assert result_negative == result_zero


def test_magnitude_to_scale_note_clamped_above_one():
    """Magnitude > 1 is clamped to 1.0."""
    result_high = magnitude_to_scale_note(1.5, 0, "major", octaves=1, base_octave=4)
    result_one = magnitude_to_scale_note(1.0, 0, "major", octaves=1, base_octave=4)
    assert result_high == result_one


def test_magnitude_to_scale_note_with_different_root():
    """Magnitude with root D (2) from D4."""
    result = magnitude_to_scale_note(0.0, 2, "major", octaves=1, base_octave=4)
    # Major from D4: D E F# G A B C# (62, 64, 66, 67, 69, 71, 73)
    expected = 62
    assert result == expected


def test_magnitude_to_scale_note_two_octaves():
    """Magnitude 0.5 with 2 octaves of major scale."""
    result = magnitude_to_scale_note(0.5, 0, "major", octaves=2, base_octave=4)
    # 14 notes total: C4 D4 E4 F4 G4 A4 B4 C5 D5 E5 F5 G5 A5 B5
    # 0.5 * 13 = 6.5 → round to 6 (banker's rounding) → index 6 → B4 (71)
    assert result == 71


def test_magnitude_to_scale_note_unknown_scale_raises():
    """Unknown scale raises ValueError."""
    with pytest.raises(ValueError, match="Unknown scale"):
        magnitude_to_scale_note(0.5, 0, "totally_made_up")


def test_magnitude_to_scale_note_returns_in_midi_range():
    """Result is always a valid MIDI note (0..127)."""
    for magnitude in [0.0, 0.25, 0.5, 0.75, 1.0]:
        for scale in SCALES:
            result = magnitude_to_scale_note(magnitude, 0, scale, octaves=2, base_octave=3)
            assert 0 <= result <= 127


def test_magnitude_to_scale_note_pentatonic_minor():
    """Minor pentatonic has 5 notes per octave."""
    result = magnitude_to_scale_note(0.5, 0, "pentatonic_minor", octaves=1, base_octave=4)
    # 5 notes: C4 Eb4 F4 G4 Bb4 (60, 63, 65, 67, 70)
    # 0.5 * 4 = 2.0 → index 2 → F4 (65)
    assert result == 65


def test_magnitude_to_scale_note_blues():
    """Blues scale has 6 notes per octave."""
    notes = notes_in_scale(0, "blues", octaves=1, base_octave=4)
    assert len(notes) == 6
    result_zero = magnitude_to_scale_note(0.0, 0, "blues", octaves=1, base_octave=4)
    result_one = magnitude_to_scale_note(1.0, 0, "blues", octaves=1, base_octave=4)
    assert result_zero == notes[0]
    assert result_one == notes[-1]
