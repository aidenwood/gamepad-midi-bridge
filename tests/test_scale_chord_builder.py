"""Tests for scale_chord_builder — scale-aware chord composition."""
import pytest

from gamepad_midi_bridge.scale_chord_builder import (
    DEGREE_TO_INDEX,
    available_progressions,
    build_pop_progression,
    build_progression,
    build_seventh,
    build_triad,
)


class TestDegreeToIndex:
    """Test DEGREE_TO_INDEX mapping."""

    def test_has_required_entries(self):
        """DEGREE_TO_INDEX has at least 7 entries."""
        assert len(DEGREE_TO_INDEX) >= 7

    def test_major_degrees(self):
        """Test uppercase major degrees."""
        assert DEGREE_TO_INDEX["I"] == 0
        assert DEGREE_TO_INDEX["IV"] == 3
        assert DEGREE_TO_INDEX["V"] == 4

    def test_minor_degrees(self):
        """Test lowercase minor degrees."""
        assert DEGREE_TO_INDEX["vi"] == 5
        assert DEGREE_TO_INDEX["vii"] == 6

    def test_mixed_case(self):
        """Test both cases map to same index."""
        assert DEGREE_TO_INDEX["II"] == DEGREE_TO_INDEX["ii"]
        assert DEGREE_TO_INDEX["VI"] == DEGREE_TO_INDEX["vi"]


class TestBuildTriad:
    """Test build_triad function."""

    def test_c_major_i_triad(self):
        """C major I triad = [60, 64, 67] (C, E, G)."""
        result = build_triad(0, "major", "I", octave=4)
        assert len(result) == 3
        assert result == [60, 64, 67]

    def test_c_major_iv_triad(self):
        """C major IV triad = [65, 69, 72] (F, A, C5)."""
        result = build_triad(0, "major", "IV", octave=4)
        assert len(result) == 3
        assert result == [65, 69, 72]

    def test_c_major_v_triad(self):
        """C major V triad = [67, 71, 74] (G, B, D5)."""
        result = build_triad(0, "major", "V", octave=4)
        assert len(result) == 3
        assert result == [67, 71, 74]

    def test_c_major_vi_triad(self):
        """C major vi triad (A minor) = [69, 72, 76] (A, C5, E5)."""
        result = build_triad(0, "major", "vi", octave=4)
        assert len(result) == 3
        assert result == [69, 72, 76]

    def test_c_minor_i_triad(self):
        """C minor I triad = [60, 63, 67] (C, Eb, G)."""
        result = build_triad(0, "minor", "I", octave=4)
        assert len(result) == 3
        assert result == [60, 63, 67]

    def test_d_major_i_triad(self):
        """D major I triad = [62, 66, 69] (D, F#, A)."""
        result = build_triad(2, "major", "I", octave=4)
        assert len(result) == 3
        assert result == [62, 66, 69]

    def test_all_notes_in_midi_range(self):
        """All returned notes are in 0..127."""
        result = build_triad(0, "major", "I", octave=4)
        assert all(0 <= note <= 127 for note in result)

    def test_higher_octave_produces_higher_notes(self):
        """Octave=5 produces higher notes than octave=4."""
        result_oct4 = build_triad(0, "major", "I", octave=4)
        result_oct5 = build_triad(0, "major", "I", octave=5)
        assert result_oct5[0] > result_oct4[0]
        assert result_oct5[1] > result_oct4[1]
        assert result_oct5[2] > result_oct4[2]

    def test_case_insensitive_degree(self):
        """Uppercase I and lowercase i produce same result."""
        result_upper = build_triad(0, "major", "I", octave=4)
        result_lower = build_triad(0, "major", "i", octave=4)
        assert result_upper == result_lower

    def test_unknown_degree_raises_keyerror(self):
        """Unknown degree raises KeyError."""
        with pytest.raises(KeyError):
            build_triad(0, "major", "VIII")

    def test_unknown_scale_raises_valueerror(self):
        """Unknown scale raises ValueError."""
        with pytest.raises(ValueError):
            build_triad(0, "unknown_scale", "I")


class TestBuildSeventh:
    """Test build_seventh function."""

    def test_c_major_i_seventh(self):
        """C major 7th = [60, 64, 67, 71] (C, E, G, B = Cmaj7)."""
        result = build_seventh(0, "major", "I", octave=4)
        assert len(result) == 4
        assert result == [60, 64, 67, 71]

    def test_seventh_has_4_notes(self):
        """Seventh chords have exactly 4 notes."""
        result = build_seventh(0, "major", "IV", octave=4)
        assert len(result) == 4

    def test_c_major_v_seventh(self):
        """C major V 7th = [67, 71, 74, 78] (G, B, D5, F#5)."""
        result = build_seventh(0, "major", "V", octave=4)
        assert len(result) == 4
        # G (67), B (71), D (74), F# (78)
        assert result[0] == 67

    def test_all_seventh_notes_in_midi_range(self):
        """All seventh chord notes are in 0..127."""
        result = build_seventh(0, "major", "I", octave=4)
        assert all(0 <= note <= 127 for note in result)

    def test_higher_octave_seventh(self):
        """Octave affects seventh notes too."""
        result_oct3 = build_seventh(0, "major", "I", octave=3)
        result_oct4 = build_seventh(0, "major", "I", octave=4)
        assert result_oct4[0] > result_oct3[0]

    def test_unknown_degree_raises_keyerror(self):
        """Unknown degree in seventh raises KeyError."""
        with pytest.raises(KeyError):
            build_seventh(0, "major", "VIII")

    def test_unknown_scale_raises_valueerror(self):
        """Unknown scale in seventh raises ValueError."""
        with pytest.raises(ValueError):
            build_seventh(0, "unknown_scale", "I")


class TestBuildProgression:
    """Test build_progression function."""

    def test_two_chord_progression(self):
        """I-V progression returns 2 chords."""
        result = build_progression(0, "major", ["I", "V"], octave=4)
        assert len(result) == 2
        assert all(len(chord) == 3 for chord in result)

    def test_four_chord_progression(self):
        """I-V-vi-IV progression returns 4 chords."""
        result = build_progression(0, "major", ["I", "V", "vi", "IV"], octave=4)
        assert len(result) == 4
        assert all(len(chord) == 3 for chord in result)

    def test_seventh_chord_progression(self):
        """chord_type='seventh' returns 4-note chords."""
        result = build_progression(
            0, "major", ["I", "IV", "V"], octave=4, chord_type="seventh"
        )
        assert len(result) == 3
        assert all(len(chord) == 4 for chord in result)

    def test_unknown_chord_type_defaults_to_triad(self):
        """Unknown chord_type defaults to triad (3 notes)."""
        result = build_progression(
            0, "major", ["I", "V"], octave=4, chord_type="unknown"
        )
        assert all(len(chord) == 3 for chord in result)

    def test_empty_degrees_returns_empty_list(self):
        """Empty degree list returns empty list."""
        result = build_progression(0, "major", [], octave=4)
        assert result == []

    def test_all_notes_in_midi_range(self):
        """All progression notes are in 0..127."""
        result = build_progression(
            0, "major", ["I", "IV", "V", "vi"], octave=4, chord_type="seventh"
        )
        for chord in result:
            assert all(0 <= note <= 127 for note in chord)

    def test_unknown_degree_raises_keyerror(self):
        """Unknown degree in progression raises KeyError."""
        with pytest.raises(KeyError):
            build_progression(0, "major", ["I", "VIII"], octave=4)

    def test_unknown_scale_raises_valueerror(self):
        """Unknown scale in progression raises ValueError."""
        with pytest.raises(ValueError):
            build_progression(0, "unknown_scale", ["I", "V"], octave=4)


class TestBuildPopProgression:
    """Test build_pop_progression function."""

    def test_i_v_vi_iv_progression(self):
        """I-V-vi-IV progression returns 4 triads."""
        result = build_pop_progression(0, "major", "I-V-vi-IV", octave=4)
        assert len(result) == 4
        assert all(len(chord) == 3 for chord in result)

    def test_ii_v_i_progression(self):
        """ii-V-I progression returns 3 triads."""
        result = build_pop_progression(0, "major", "ii-V-I", octave=4)
        assert len(result) == 3
        assert all(len(chord) == 3 for chord in result)

    def test_vi_iv_i_v_progression(self):
        """vi-IV-I-V progression returns 4 triads."""
        result = build_pop_progression(0, "major", "vi-IV-I-V", octave=4)
        assert len(result) == 4

    def test_i_iv_v_i_progression(self):
        """I-IV-V-I progression (blues) returns 4 triads."""
        result = build_pop_progression(0, "major", "I-IV-V-I", octave=4)
        assert len(result) == 4

    def test_i_vi_iv_v_progression(self):
        """I-vi-IV-V progression (doo-wop) returns 4 triads."""
        result = build_pop_progression(0, "major", "I-vi-IV-V", octave=4)
        assert len(result) == 4

    def test_unknown_progression_returns_empty_list(self):
        """Unknown progression name returns empty list."""
        result = build_pop_progression(0, "major", "unknown_name", octave=4)
        assert result == []

    def test_all_notes_in_midi_range(self):
        """All progression notes are in 0..127."""
        result = build_pop_progression(0, "major", "I-V-vi-IV", octave=4)
        for chord in result:
            assert all(0 <= note <= 127 for note in chord)

    def test_unknown_scale_raises_valueerror(self):
        """Unknown scale raises ValueError."""
        with pytest.raises(ValueError):
            build_pop_progression(0, "unknown_scale", "I-V-vi-IV", octave=4)

    def test_higher_octave_produces_higher_notes(self):
        """Octave=5 produces higher notes than octave=4."""
        result_oct4 = build_pop_progression(0, "major", "I-V-vi-IV", octave=4)
        result_oct5 = build_pop_progression(0, "major", "I-V-vi-IV", octave=5)
        for c4, c5 in zip(result_oct4, result_oct5):
            assert c5[0] > c4[0]


class TestAvailableProgressions:
    """Test available_progressions function."""

    def test_returns_list(self):
        """available_progressions returns a list."""
        result = available_progressions()
        assert isinstance(result, list)

    def test_returns_5_progressions(self):
        """available_progressions returns exactly 5 entries."""
        result = available_progressions()
        assert len(result) == 5

    def test_all_strings(self):
        """All returned progressions are strings."""
        result = available_progressions()
        assert all(isinstance(name, str) for name in result)

    def test_contains_expected_progressions(self):
        """Result contains the expected progression names."""
        result = available_progressions()
        expected = [
            "I-V-vi-IV",
            "ii-V-I",
            "vi-IV-I-V",
            "I-IV-V-I",
            "I-vi-IV-V",
        ]
        assert set(result) == set(expected)
