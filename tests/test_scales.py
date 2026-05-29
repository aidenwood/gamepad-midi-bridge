"""Scale-quantize helper — note_for_sector correctness."""
from __future__ import annotations

import pytest

from gamepad_midi_bridge.scales import SCALES, note_for_sector


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
