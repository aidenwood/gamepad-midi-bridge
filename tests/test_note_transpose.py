"""Note transposition helper — shifts, clamping, chords, and serialization."""
from __future__ import annotations

import pytest

from gamepad_midi_bridge.note_transpose import (
    NoteTransposeConfig,
    apply,
    apply_chord,
    octave_down,
    octave_up,
    reset,
    semitone_down,
    semitone_up,
    total_shift,
)


class TestNoteTransposeConfigDefaults:
    """NoteTransposeConfig dataclass — defaults and clamping."""

    def test_default_config_disabled(self):
        """Default config is disabled with both shifts at 0."""
        cfg = NoteTransposeConfig()
        assert cfg.enabled is False
        assert cfg.octave_shift == 0
        assert cfg.semitone_shift == 0
        assert cfg.clamp_to_midi is True
        assert cfg.apply_to_chords is True

    def test_octave_shift_clamped_to_negative_four(self):
        """octave_shift is clamped to >= -4."""
        cfg = NoteTransposeConfig(octave_shift=-10)
        assert cfg.octave_shift == -4

    def test_octave_shift_clamped_to_positive_four(self):
        """octave_shift is clamped to <= +4."""
        cfg = NoteTransposeConfig(octave_shift=10)
        assert cfg.octave_shift == 4

    def test_semitone_shift_clamped_to_negative_eleven(self):
        """semitone_shift is clamped to >= -11."""
        cfg = NoteTransposeConfig(semitone_shift=-20)
        assert cfg.semitone_shift == -11

    def test_semitone_shift_clamped_to_positive_eleven(self):
        """semitone_shift is clamped to <= +11."""
        cfg = NoteTransposeConfig(semitone_shift=20)
        assert cfg.semitone_shift == 11

    def test_clamping_happens_in_post_init(self):
        """Clamping is applied during __post_init__."""
        cfg = NoteTransposeConfig(octave_shift=5, semitone_shift=15)
        assert cfg.octave_shift == 4
        assert cfg.semitone_shift == 11


class TestTotalShift:
    """total_shift function — combining octaves and semitones."""

    def test_total_shift_disabled_returns_zero(self):
        """Disabled config always returns 0."""
        cfg = NoteTransposeConfig(enabled=False, octave_shift=2, semitone_shift=5)
        assert total_shift(cfg) == 0

    def test_total_shift_zero_when_both_zero(self):
        """Shifts at 0,0 give total 0."""
        cfg = NoteTransposeConfig(enabled=True, octave_shift=0, semitone_shift=0)
        assert total_shift(cfg) == 0

    def test_total_shift_octave_only(self):
        """octave_shift=1 gives total 12."""
        cfg = NoteTransposeConfig(enabled=True, octave_shift=1, semitone_shift=0)
        assert total_shift(cfg) == 12

    def test_total_shift_semitone_only(self):
        """semitone_shift=5 gives total 5."""
        cfg = NoteTransposeConfig(enabled=True, octave_shift=0, semitone_shift=5)
        assert total_shift(cfg) == 5

    def test_total_shift_combined(self):
        """octave_shift=1, semitone_shift=2 gives total 14."""
        cfg = NoteTransposeConfig(enabled=True, octave_shift=1, semitone_shift=2)
        assert total_shift(cfg) == 14

    def test_total_shift_negative_octave(self):
        """octave_shift=-1 gives total -12."""
        cfg = NoteTransposeConfig(enabled=True, octave_shift=-1, semitone_shift=0)
        assert total_shift(cfg) == -12

    def test_total_shift_negative_semitone(self):
        """semitone_shift=-3 gives total -3."""
        cfg = NoteTransposeConfig(enabled=True, octave_shift=0, semitone_shift=-3)
        assert total_shift(cfg) == -3

    def test_total_shift_combined_negative(self):
        """octave_shift=-2, semitone_shift=-5 gives total -29."""
        cfg = NoteTransposeConfig(enabled=True, octave_shift=-2, semitone_shift=-5)
        assert total_shift(cfg) == -29


class TestApplyDisabledAndUnchanged:
    """apply function — disabled config and identity cases."""

    def test_apply_disabled_returns_note_unchanged(self):
        """Disabled config returns note unchanged."""
        cfg = NoteTransposeConfig(enabled=False, octave_shift=2, semitone_shift=5)
        assert apply(60, cfg) == 60
        assert apply(0, cfg) == 0
        assert apply(127, cfg) == 127

    def test_apply_zero_shift_returns_note_unchanged(self):
        """Both shifts at 0 returns note unchanged."""
        cfg = NoteTransposeConfig(enabled=True, octave_shift=0, semitone_shift=0)
        assert apply(60, cfg) == 60
        assert apply(72, cfg) == 72


class TestApplyWithOctaveShift:
    """apply function — octave transposition."""

    def test_apply_octave_up_one(self):
        """octave_shift=1 shifts C4 (60) to C5 (72)."""
        cfg = NoteTransposeConfig(enabled=True, octave_shift=1)
        assert apply(60, cfg) == 72

    def test_apply_octave_down_one(self):
        """octave_shift=-1 shifts C4 (60) to C3 (48)."""
        cfg = NoteTransposeConfig(enabled=True, octave_shift=-1)
        assert apply(60, cfg) == 48

    def test_apply_octave_up_four(self):
        """octave_shift=4 shifts C4 (60) to C8 (108)."""
        cfg = NoteTransposeConfig(enabled=True, octave_shift=4)
        assert apply(60, cfg) == 108

    def test_apply_octave_down_four(self):
        """octave_shift=-4 shifts C4 (60) to C0 (12)."""
        cfg = NoteTransposeConfig(enabled=True, octave_shift=-4)
        assert apply(60, cfg) == 12


class TestApplyWithSemitoneShift:
    """apply function — semitone transposition."""

    def test_apply_semitone_up_one(self):
        """semitone_shift=1 shifts C4 (60) to C#4 (61)."""
        cfg = NoteTransposeConfig(enabled=True, semitone_shift=1)
        assert apply(60, cfg) == 61

    def test_apply_semitone_up_two(self):
        """semitone_shift=2 shifts C4 (60) to D4 (62)."""
        cfg = NoteTransposeConfig(enabled=True, semitone_shift=2)
        assert apply(60, cfg) == 62

    def test_apply_semitone_down_one(self):
        """semitone_shift=-1 shifts C4 (60) to B3 (59)."""
        cfg = NoteTransposeConfig(enabled=True, semitone_shift=-1)
        assert apply(60, cfg) == 59

    def test_apply_semitone_down_eleven(self):
        """semitone_shift=-11 shifts C4 (60) to C#3 (49)."""
        cfg = NoteTransposeConfig(enabled=True, semitone_shift=-11)
        assert apply(60, cfg) == 49


class TestApplyWithCombinedShift:
    """apply function — octave + semitone transposition."""

    def test_apply_combined_up(self):
        """octave_shift=1, semitone_shift=2 shifts C4 (60) to D5 (74)."""
        cfg = NoteTransposeConfig(enabled=True, octave_shift=1, semitone_shift=2)
        assert apply(60, cfg) == 74

    def test_apply_combined_down(self):
        """octave_shift=-1, semitone_shift=-5 shifts C4 (60) to G2 (43)."""
        cfg = NoteTransposeConfig(enabled=True, octave_shift=-1, semitone_shift=-5)
        assert apply(60, cfg) == 43

    def test_apply_combined_mixed(self):
        """octave_shift=2, semitone_shift=-3 shifts C4 (60) to A5 (81)."""
        cfg = NoteTransposeConfig(enabled=True, octave_shift=2, semitone_shift=-3)
        assert apply(60, cfg) == 81


class TestApplyWithClamping:
    """apply function — MIDI range clamping (0..127)."""

    def test_apply_clamp_true_above_127(self):
        """With clamp=True, C8 (124) + octave up gives 127 (clamped)."""
        cfg = NoteTransposeConfig(enabled=True, octave_shift=1, clamp_to_midi=True)
        # 124 + 12 = 136, clamped to 127
        assert apply(124, cfg) == 127

    def test_apply_clamp_true_below_0(self):
        """With clamp=True, C-1 (0) + octave down gives 0 (clamped)."""
        cfg = NoteTransposeConfig(enabled=True, octave_shift=-1, clamp_to_midi=True)
        # 0 - 12 = -12, clamped to 0
        assert apply(0, cfg) == 0

    def test_apply_clamp_false_above_127(self):
        """With clamp=False, out-of-range notes return None."""
        cfg = NoteTransposeConfig(enabled=True, octave_shift=1, clamp_to_midi=False)
        # 124 + 12 = 136, out of range
        assert apply(124, cfg) is None

    def test_apply_clamp_false_below_0(self):
        """With clamp=False, negative notes return None."""
        cfg = NoteTransposeConfig(enabled=True, octave_shift=-1, clamp_to_midi=False)
        # 0 - 12 = -12, out of range
        assert apply(0, cfg) is None

    def test_apply_clamp_false_in_range(self):
        """With clamp=False, in-range notes return normally."""
        cfg = NoteTransposeConfig(enabled=True, octave_shift=1, clamp_to_midi=False)
        assert apply(60, cfg) == 72

    def test_apply_clamp_true_middle_range(self):
        """Clamping doesn't affect in-range notes."""
        cfg = NoteTransposeConfig(enabled=True, octave_shift=-1, clamp_to_midi=True)
        assert apply(60, cfg) == 48


class TestApplyChord:
    """apply_chord function — transposing multiple notes."""

    def test_apply_chord_empty_list(self):
        """Empty chord returns empty list."""
        cfg = NoteTransposeConfig(enabled=True, octave_shift=1)
        assert apply_chord([], cfg) == []

    def test_apply_chord_enabled_octave_up(self):
        """Chord [60, 64, 67] + octave up gives [72, 76, 79]."""
        cfg = NoteTransposeConfig(enabled=True, octave_shift=1, apply_to_chords=True)
        assert apply_chord([60, 64, 67], cfg) == [72, 76, 79]

    def test_apply_chord_enabled_semitone_up(self):
        """Chord [60, 64, 67] + semitone 2 gives [62, 66, 69]."""
        cfg = NoteTransposeConfig(enabled=True, semitone_shift=2, apply_to_chords=True)
        assert apply_chord([60, 64, 67], cfg) == [62, 66, 69]

    def test_apply_chord_disabled_returns_unchanged(self):
        """Disabled config returns chord unchanged."""
        cfg = NoteTransposeConfig(enabled=False, octave_shift=1, apply_to_chords=True)
        assert apply_chord([60, 64, 67], cfg) == [60, 64, 67]

    def test_apply_chord_apply_to_chords_false(self):
        """apply_to_chords=False returns chord unchanged regardless of shift."""
        cfg = NoteTransposeConfig(enabled=True, octave_shift=1, apply_to_chords=False)
        assert apply_chord([60, 64, 67], cfg) == [60, 64, 67]

    def test_apply_chord_with_clamping_true(self):
        """Chords with clamping clamp individual notes."""
        cfg = NoteTransposeConfig(enabled=True, octave_shift=1, clamp_to_midi=True, apply_to_chords=True)
        # [120, 124, 127] + octave → [132, 136, 139] → [127, 127, 127]
        assert apply_chord([120, 124, 127], cfg) == [127, 127, 127]

    def test_apply_chord_with_clamping_false_filters_out_of_range(self):
        """Chords with clamp=False filters out out-of-range notes."""
        cfg = NoteTransposeConfig(enabled=True, octave_shift=1, clamp_to_midi=False, apply_to_chords=True)
        # [60, 120, 70] + octave → [72, 132, 82]; 132 is out of range
        assert apply_chord([60, 120, 70], cfg) == [72, 82]

    def test_apply_chord_negative_transposition_with_clamp_false(self):
        """Chords with negative shift and clamp=False filters low notes."""
        cfg = NoteTransposeConfig(enabled=True, octave_shift=-1, clamp_to_midi=False, apply_to_chords=True)
        # [5, 60, 70] - octave → [-7, 48, 58]; -7 is out of range
        assert apply_chord([5, 60, 70], cfg) == [48, 58]

    def test_apply_chord_single_note(self):
        """Single-note chord works like apply."""
        cfg = NoteTransposeConfig(enabled=True, octave_shift=1, apply_to_chords=True)
        assert apply_chord([60], cfg) == [72]


class TestOctaveUp:
    """octave_up function — immutability and clamping."""

    def test_octave_up_default_increments_by_one(self):
        """octave_up() increments octave_shift by 1."""
        cfg = NoteTransposeConfig(enabled=True, octave_shift=0)
        cfg2 = octave_up(cfg)
        assert cfg2.octave_shift == 1

    def test_octave_up_with_by_parameter(self):
        """octave_up(by=2) increments octave_shift by 2."""
        cfg = NoteTransposeConfig(enabled=True, octave_shift=0)
        cfg2 = octave_up(cfg, by=2)
        assert cfg2.octave_shift == 2

    def test_octave_up_clamped_to_four(self):
        """octave_up clamps to +4."""
        cfg = NoteTransposeConfig(enabled=True, octave_shift=3)
        cfg2 = octave_up(cfg, by=2)
        assert cfg2.octave_shift == 4

    def test_octave_up_non_mutating(self):
        """octave_up returns new config, doesn't mutate original."""
        cfg = NoteTransposeConfig(enabled=True, octave_shift=0)
        cfg2 = octave_up(cfg)
        assert cfg.octave_shift == 0
        assert cfg2.octave_shift == 1

    def test_octave_up_preserves_other_fields(self):
        """octave_up preserves enabled, semitone_shift, clamp_to_midi, apply_to_chords."""
        cfg = NoteTransposeConfig(
            enabled=True,
            octave_shift=0,
            semitone_shift=2,
            clamp_to_midi=False,
            apply_to_chords=False,
        )
        cfg2 = octave_up(cfg)
        assert cfg2.enabled is True
        assert cfg2.semitone_shift == 2
        assert cfg2.clamp_to_midi is False
        assert cfg2.apply_to_chords is False


class TestOctaveDown:
    """octave_down function — inverse of octave_up."""

    def test_octave_down_default_decrements_by_one(self):
        """octave_down() decrements octave_shift by 1."""
        cfg = NoteTransposeConfig(enabled=True, octave_shift=2)
        cfg2 = octave_down(cfg)
        assert cfg2.octave_shift == 1

    def test_octave_down_with_by_parameter(self):
        """octave_down(by=2) decrements octave_shift by 2."""
        cfg = NoteTransposeConfig(enabled=True, octave_shift=2)
        cfg2 = octave_down(cfg, by=2)
        assert cfg2.octave_shift == 0

    def test_octave_down_clamped_to_negative_four(self):
        """octave_down clamps to -4."""
        cfg = NoteTransposeConfig(enabled=True, octave_shift=-3)
        cfg2 = octave_down(cfg, by=2)
        assert cfg2.octave_shift == -4

    def test_octave_down_non_mutating(self):
        """octave_down returns new config, doesn't mutate original."""
        cfg = NoteTransposeConfig(enabled=True, octave_shift=2)
        cfg2 = octave_down(cfg)
        assert cfg.octave_shift == 2
        assert cfg2.octave_shift == 1


class TestSemitoneUp:
    """semitone_up function — immutability and clamping."""

    def test_semitone_up_default_increments_by_one(self):
        """semitone_up() increments semitone_shift by 1."""
        cfg = NoteTransposeConfig(enabled=True, semitone_shift=0)
        cfg2 = semitone_up(cfg)
        assert cfg2.semitone_shift == 1

    def test_semitone_up_with_by_parameter(self):
        """semitone_up(by=5) increments semitone_shift by 5."""
        cfg = NoteTransposeConfig(enabled=True, semitone_shift=0)
        cfg2 = semitone_up(cfg, by=5)
        assert cfg2.semitone_shift == 5

    def test_semitone_up_clamped_to_eleven(self):
        """semitone_up clamps to +11."""
        cfg = NoteTransposeConfig(enabled=True, semitone_shift=10)
        cfg2 = semitone_up(cfg, by=2)
        assert cfg2.semitone_shift == 11

    def test_semitone_up_non_mutating(self):
        """semitone_up returns new config, doesn't mutate original."""
        cfg = NoteTransposeConfig(enabled=True, semitone_shift=0)
        cfg2 = semitone_up(cfg)
        assert cfg.semitone_shift == 0
        assert cfg2.semitone_shift == 1

    def test_semitone_up_preserves_other_fields(self):
        """semitone_up preserves enabled, octave_shift, clamp_to_midi, apply_to_chords."""
        cfg = NoteTransposeConfig(
            enabled=True,
            octave_shift=2,
            semitone_shift=0,
            clamp_to_midi=False,
            apply_to_chords=False,
        )
        cfg2 = semitone_up(cfg)
        assert cfg2.enabled is True
        assert cfg2.octave_shift == 2
        assert cfg2.clamp_to_midi is False
        assert cfg2.apply_to_chords is False


class TestSemitoneDown:
    """semitone_down function — inverse of semitone_up."""

    def test_semitone_down_default_decrements_by_one(self):
        """semitone_down() decrements semitone_shift by 1."""
        cfg = NoteTransposeConfig(enabled=True, semitone_shift=5)
        cfg2 = semitone_down(cfg)
        assert cfg2.semitone_shift == 4

    def test_semitone_down_with_by_parameter(self):
        """semitone_down(by=3) decrements semitone_shift by 3."""
        cfg = NoteTransposeConfig(enabled=True, semitone_shift=5)
        cfg2 = semitone_down(cfg, by=3)
        assert cfg2.semitone_shift == 2

    def test_semitone_down_clamped_to_negative_eleven(self):
        """semitone_down clamps to -11."""
        cfg = NoteTransposeConfig(enabled=True, semitone_shift=-10)
        cfg2 = semitone_down(cfg, by=2)
        assert cfg2.semitone_shift == -11

    def test_semitone_down_non_mutating(self):
        """semitone_down returns new config, doesn't mutate original."""
        cfg = NoteTransposeConfig(enabled=True, semitone_shift=5)
        cfg2 = semitone_down(cfg)
        assert cfg.semitone_shift == 5
        assert cfg2.semitone_shift == 4


class TestReset:
    """reset function — zeroing both shifts while preserving enabled state."""

    def test_reset_clears_both_shifts(self):
        """reset() clears octave_shift and semitone_shift to 0."""
        cfg = NoteTransposeConfig(enabled=True, octave_shift=2, semitone_shift=5)
        cfg2 = reset(cfg)
        assert cfg2.octave_shift == 0
        assert cfg2.semitone_shift == 0

    def test_reset_preserves_enabled_when_true(self):
        """reset() preserves enabled=True."""
        cfg = NoteTransposeConfig(enabled=True, octave_shift=2, semitone_shift=5)
        cfg2 = reset(cfg)
        assert cfg2.enabled is True

    def test_reset_preserves_enabled_when_false(self):
        """reset() preserves enabled=False."""
        cfg = NoteTransposeConfig(enabled=False, octave_shift=2, semitone_shift=5)
        cfg2 = reset(cfg)
        assert cfg2.enabled is False

    def test_reset_preserves_other_fields(self):
        """reset() preserves clamp_to_midi and apply_to_chords."""
        cfg = NoteTransposeConfig(
            enabled=True,
            octave_shift=2,
            semitone_shift=5,
            clamp_to_midi=False,
            apply_to_chords=False,
        )
        cfg2 = reset(cfg)
        assert cfg2.clamp_to_midi is False
        assert cfg2.apply_to_chords is False

    def test_reset_non_mutating(self):
        """reset() returns new config, doesn't mutate original."""
        cfg = NoteTransposeConfig(enabled=True, octave_shift=2, semitone_shift=5)
        cfg2 = reset(cfg)
        assert cfg.octave_shift == 2
        assert cfg.semitone_shift == 5
        assert cfg2.octave_shift == 0
        assert cfg2.semitone_shift == 0


class TestSerialization:
    """to_dict and from_dict — round-trip serialization."""

    def test_to_dict_defaults(self):
        """to_dict serializes default config correctly."""
        cfg = NoteTransposeConfig()
        data = cfg.to_dict()
        assert data == {
            "enabled": False,
            "octave_shift": 0,
            "semitone_shift": 0,
            "clamp_to_midi": True,
            "apply_to_chords": True,
        }

    def test_to_dict_full_config(self):
        """to_dict serializes all fields."""
        cfg = NoteTransposeConfig(
            enabled=True,
            octave_shift=2,
            semitone_shift=-3,
            clamp_to_midi=False,
            apply_to_chords=False,
        )
        data = cfg.to_dict()
        assert data == {
            "enabled": True,
            "octave_shift": 2,
            "semitone_shift": -3,
            "clamp_to_midi": False,
            "apply_to_chords": False,
        }

    def test_from_dict_defaults(self):
        """from_dict with empty dict uses defaults."""
        cfg = NoteTransposeConfig.from_dict({})
        assert cfg.enabled is False
        assert cfg.octave_shift == 0
        assert cfg.semitone_shift == 0
        assert cfg.clamp_to_midi is True
        assert cfg.apply_to_chords is True

    def test_from_dict_full_config(self):
        """from_dict loads all fields."""
        data = {
            "enabled": True,
            "octave_shift": 2,
            "semitone_shift": -3,
            "clamp_to_midi": False,
            "apply_to_chords": False,
        }
        cfg = NoteTransposeConfig.from_dict(data)
        assert cfg.enabled is True
        assert cfg.octave_shift == 2
        assert cfg.semitone_shift == -3
        assert cfg.clamp_to_midi is False
        assert cfg.apply_to_chords is False

    def test_from_dict_clamps_octave_shift(self):
        """from_dict clamps octave_shift to -4..+4."""
        cfg = NoteTransposeConfig.from_dict({"octave_shift": 10})
        assert cfg.octave_shift == 4

    def test_from_dict_clamps_semitone_shift(self):
        """from_dict clamps semitone_shift to -11..+11."""
        cfg = NoteTransposeConfig.from_dict({"semitone_shift": -20})
        assert cfg.semitone_shift == -11

    def test_round_trip_serialization(self):
        """to_dict and from_dict preserve config exactly."""
        cfg = NoteTransposeConfig(
            enabled=True,
            octave_shift=1,
            semitone_shift=-2,
            clamp_to_midi=False,
            apply_to_chords=True,
        )
        data = cfg.to_dict()
        cfg2 = NoteTransposeConfig.from_dict(data)
        assert cfg == cfg2

    def test_round_trip_serialization_default(self):
        """Round-trip preserves default config."""
        cfg = NoteTransposeConfig()
        data = cfg.to_dict()
        cfg2 = NoteTransposeConfig.from_dict(data)
        assert cfg == cfg2


class TestIntegration:
    """Integration tests spanning multiple functions."""

    def test_octave_cycle_symmetry(self):
        """octave_up and octave_down are symmetric."""
        cfg = NoteTransposeConfig(enabled=True, octave_shift=0)
        cfg_up = octave_up(cfg, by=3)
        cfg_down = octave_down(cfg_up, by=3)
        assert cfg_down.octave_shift == 0

    def test_semitone_cycle_symmetry(self):
        """semitone_up and semitone_down are symmetric."""
        cfg = NoteTransposeConfig(enabled=True, semitone_shift=0)
        cfg_up = semitone_up(cfg, by=5)
        cfg_down = semitone_down(cfg_up, by=5)
        assert cfg_down.semitone_shift == 0

    def test_note_and_chord_consistency(self):
        """apply(note) matches apply_chord([note])."""
        cfg = NoteTransposeConfig(enabled=True, octave_shift=1, semitone_shift=3)
        note = apply(60, cfg)
        chord = apply_chord([60], cfg)
        assert chord == [note]

    def test_multiple_chord_notes_consistency(self):
        """apply_chord results match individual apply calls."""
        cfg = NoteTransposeConfig(enabled=True, octave_shift=1, semitone_shift=-2)
        notes = [60, 64, 67, 72]
        chord = apply_chord(notes, cfg)
        individual = [apply(n, cfg) for n in notes]
        assert chord == individual

    def test_disabled_chord_matches_disabled_note(self):
        """Disabled chord matches disabled individual notes."""
        cfg = NoteTransposeConfig(enabled=False, octave_shift=2, semitone_shift=5)
        notes = [60, 64, 67]
        chord = apply_chord(notes, cfg)
        individual = [apply(n, cfg) for n in notes]
        assert chord == individual == notes

    def test_apply_to_chords_false_matches_disabled(self):
        """apply_to_chords=False on chord matches disabled chord."""
        cfg1 = NoteTransposeConfig(enabled=True, octave_shift=1, apply_to_chords=False)
        cfg2 = NoteTransposeConfig(enabled=False, octave_shift=1, apply_to_chords=True)
        notes = [60, 64, 67]
        assert apply_chord(notes, cfg1) == apply_chord(notes, cfg2) == notes

    def test_stateless_operations(self):
        """All operations are stateless; repeated calls produce same result."""
        cfg = NoteTransposeConfig(enabled=True, octave_shift=0)
        cfg1 = octave_up(cfg)
        cfg2 = octave_up(cfg)
        assert cfg1 == cfg2

    def test_extreme_shifts_within_bounds(self):
        """Extreme shifts stay within MIDI range when clamped."""
        cfg = NoteTransposeConfig(enabled=True, octave_shift=4, clamp_to_midi=True)
        # Max note is 127; 127 + 48 = 175 → clamped to 127
        result = apply(127, cfg)
        assert 0 <= result <= 127

    def test_example_use_case_transpose_on_the_fly(self):
        """Example: user presses buttons to transpose up/down."""
        # Start at octave 0
        cfg = NoteTransposeConfig(enabled=True, octave_shift=0)
        note = 60

        # User presses "transpose up" twice
        cfg = octave_up(cfg)
        cfg = octave_up(cfg)
        assert apply(note, cfg) == 84  # C4 + 2 octaves = C6

        # User presses "transpose down" once
        cfg = octave_down(cfg)
        assert apply(note, cfg) == 72  # C4 + 1 octave = C5

        # User presses "reset"
        cfg = reset(cfg)
        assert apply(note, cfg) == 60  # Back to original

    def test_example_use_case_chord_with_clamping(self):
        """Example: transpose chord, clamping high notes."""
        cfg = NoteTransposeConfig(
            enabled=True,
            octave_shift=2,
            clamp_to_midi=True,
            apply_to_chords=True,
        )
        # Major triad on C4
        triad = [60, 64, 67]
        # All shift up by 2 octaves (24 semitones), all stay within 0..127
        transposed = apply_chord(triad, cfg)
        assert transposed == [84, 88, 91]

    def test_example_use_case_chord_with_drop(self):
        """Example: transpose chord, dropping out-of-range notes."""
        cfg = NoteTransposeConfig(
            enabled=True,
            octave_shift=3,
            clamp_to_midi=False,
            apply_to_chords=True,
        )
        # High notes
        triad = [100, 110, 120]
        # 100+36=136, 110+36=146, 120+36=156 — all out of range
        transposed = apply_chord(triad, cfg)
        assert transposed == []  # All dropped
