"""Tests for the note_range module — pure-function note constraint logic.

Covers all three modes (transpose, drop, clamp) plus config round-trip
serialization, boundary cases, and edge ranges.
"""
from __future__ import annotations

import pytest

from gamepad_midi_bridge import note_range


# ─────────────────────────────────────────────────────────────────────
# Disabled constraint
# ─────────────────────────────────────────────────────────────────────

def test_disabled_passes_through_any_note():
    """When enabled=False, apply_range returns note unchanged regardless of range."""
    cfg = note_range.NoteRangeConfig(enabled=False, low_note=60, high_note=72)
    assert note_range.apply_range(40, cfg) == 40
    assert note_range.apply_range(80, cfg) == 80
    assert note_range.apply_range(127, cfg) == 127


# ─────────────────────────────────────────────────────────────────────
# In-range notes (all modes)
# ─────────────────────────────────────────────────────────────────────

def test_in_range_passes_through_all_modes():
    """A note already in range should pass through unchanged, regardless of mode."""
    for mode in ("transpose", "drop", "clamp"):
        cfg = note_range.NoteRangeConfig(enabled=True, low_note=60, high_note=72, mode=mode)
        assert note_range.apply_range(60, cfg) == 60
        assert note_range.apply_range(66, cfg) == 66
        assert note_range.apply_range(72, cfg) == 72


# ─────────────────────────────────────────────────────────────────────
# Drop mode — out-of-range notes are discarded
# ─────────────────────────────────────────────────────────────────────

def test_drop_mode_below_low_returns_none():
    """Note below low_note should return None."""
    cfg = note_range.NoteRangeConfig(enabled=True, low_note=60, high_note=72, mode="drop")
    assert note_range.apply_range(40, cfg) is None
    assert note_range.apply_range(59, cfg) is None


def test_drop_mode_above_high_returns_none():
    """Note above high_note should return None."""
    cfg = note_range.NoteRangeConfig(enabled=True, low_note=60, high_note=72, mode="drop")
    assert note_range.apply_range(73, cfg) is None
    assert note_range.apply_range(100, cfg) is None


# ─────────────────────────────────────────────────────────────────────
# Clamp mode — out-of-range notes are clipped to boundary
# ─────────────────────────────────────────────────────────────────────

def test_clamp_mode_below_low_clamps_to_low():
    """Note below low_note should be clamped to low_note."""
    cfg = note_range.NoteRangeConfig(enabled=True, low_note=60, high_note=72, mode="clamp")
    assert note_range.apply_range(40, cfg) == 60
    assert note_range.apply_range(59, cfg) == 60


def test_clamp_mode_above_high_clamps_to_high():
    """Note above high_note should be clamped to high_note."""
    cfg = note_range.NoteRangeConfig(enabled=True, low_note=60, high_note=72, mode="clamp")
    assert note_range.apply_range(73, cfg) == 72
    assert note_range.apply_range(100, cfg) == 72


# ─────────────────────────────────────────────────────────────────────
# Transpose mode — shift by octaves (±12) until in range
# ─────────────────────────────────────────────────────────────────────

def test_transpose_mode_shifts_up_by_one_octave():
    """A note 12 semitones below range should shift up by one octave."""
    cfg = note_range.NoteRangeConfig(enabled=True, low_note=60, high_note=72, mode="transpose")
    # C4 (48) → should shift up to C5 (60)
    assert note_range.apply_range(48, cfg) == 60


def test_transpose_mode_shifts_down_to_first_fit():
    """A note above range should shift down to the first octave that fits."""
    cfg = note_range.NoteRangeConfig(enabled=True, low_note=60, high_note=72, mode="transpose")
    # C6 (84, pitch class 0) → pitch class 0 first fits at C4 (60)
    assert note_range.apply_range(84, cfg) == 60


def test_transpose_mode_multiple_octaves():
    """A note far below range may need multiple octave shifts."""
    cfg = note_range.NoteRangeConfig(enabled=True, low_note=60, high_note=72, mode="transpose")
    # Note 24 (C2) → pitch class C (0)
    # Range low is 60 (C4, pitch class 0)
    # Try octaves: 0→0, 1→12, 2→24, 3→36, 4→48, 5→60 (in range!)
    assert note_range.apply_range(24, cfg) == 60


def test_transpose_mode_respects_pitch_class():
    """Transpose should preserve pitch class; only octave changes."""
    cfg = note_range.NoteRangeConfig(enabled=True, low_note=60, high_note=72, mode="transpose")
    # Note 37 is F#2 (pitch class 6 = F#)
    # Range covers C4..C5 (pitch classes 0..11)
    # So F# should appear at octave 4 → F#4 = 54... wait, let me recalc.
    # pitch_class = 37 % 12 = 1 (C#)
    # Try octaves: 0→1, 1→13, 2→25, 3→37, 4→49, 5→61 (in range!)
    result = note_range.apply_range(37, cfg)
    assert result == 61
    assert result % 12 == 37 % 12


def test_transpose_mode_returns_none_if_no_octave_fits():
    """If no octave shift puts the note in range, return None."""
    cfg = note_range.NoteRangeConfig(enabled=True, low_note=62, high_note=63, mode="transpose")
    # Range is [62, 63] — only D4 and D#4 fit
    # Note 60 (C4, pitch class 0)
    # Pitch class 0 never appears in [62, 63]
    # Try octaves: 0→0, 1→12, 2→24, ... 10→120 (all out of range)
    assert note_range.apply_range(60, cfg) is None


def test_transpose_mode_narrow_range():
    """Transpose with a narrow range (< 12 semitones) is selective."""
    cfg = note_range.NoteRangeConfig(enabled=True, low_note=60, high_note=60, mode="transpose")
    # Range is exactly [60, 60] — only C4 (pitch class 0)
    # Note 60 (pitch class 0) → should fit at octave 4 → 60
    assert note_range.apply_range(60, cfg) == 60
    # Note 61 (pitch class 1, C#) → no octave of C# is exactly 60
    assert note_range.apply_range(61, cfg) is None
    # Note 72 (pitch class 0, C5) → octave shift back to 60
    assert note_range.apply_range(72, cfg) == 60


# ─────────────────────────────────────────────────────────────────────
# Config serialization and deserialization
# ─────────────────────────────────────────────────────────────────────

def test_config_round_trip():
    """Serialize to dict and back should preserve all fields."""
    cfg = note_range.NoteRangeConfig(enabled=True, low_note=50, high_note=100, mode="clamp")
    d = cfg.to_dict()
    cfg2 = note_range.NoteRangeConfig.from_dict(d)
    assert cfg2.enabled == cfg.enabled
    assert cfg2.low_note == cfg.low_note
    assert cfg2.high_note == cfg.high_note
    assert cfg2.mode == cfg.mode


def test_config_from_dict_clamps_low_note():
    """Values outside 0..127 should be clamped."""
    cfg = note_range.NoteRangeConfig.from_dict({"low_note": -10, "high_note": 130})
    assert cfg.low_note == 0
    assert cfg.high_note == 127


def test_config_from_dict_swaps_inverted_range():
    """If low > high, they should be swapped."""
    cfg = note_range.NoteRangeConfig.from_dict({"low_note": 100, "high_note": 50})
    assert cfg.low_note == 50
    assert cfg.high_note == 100


def test_config_from_dict_unknown_mode_defaults_to_transpose():
    """An unknown mode should be replaced with 'transpose'."""
    cfg = note_range.NoteRangeConfig.from_dict({"mode": "unknown_mode"})
    assert cfg.mode == "transpose"


def test_config_post_init_validates_mode():
    """Direct construction with bad mode should be corrected."""
    cfg = note_range.NoteRangeConfig(mode="invalid")
    assert cfg.mode == "transpose"


# ─────────────────────────────────────────────────────────────────────
# Edge cases and boundary conditions
# ─────────────────────────────────────────────────────────────────────

def test_full_range_always_passes():
    """Range [0, 127] should always pass any note through."""
    cfg = note_range.NoteRangeConfig(enabled=True, low_note=0, high_note=127, mode="transpose")
    for note in [0, 12, 60, 64, 127]:
        assert note_range.apply_range(note, cfg) == note


def test_clamp_zero_width_range():
    """Range [60, 60] in clamp mode should clamp everything to 60."""
    cfg = note_range.NoteRangeConfig(enabled=True, low_note=60, high_note=60, mode="clamp")
    assert note_range.apply_range(0, cfg) == 60
    assert note_range.apply_range(60, cfg) == 60
    assert note_range.apply_range(127, cfg) == 60


def test_drop_zero_width_range():
    """Range [60, 60] in drop mode should only accept 60 itself."""
    cfg = note_range.NoteRangeConfig(enabled=True, low_note=60, high_note=60, mode="drop")
    assert note_range.apply_range(59, cfg) is None
    assert note_range.apply_range(60, cfg) == 60
    assert note_range.apply_range(61, cfg) is None


def test_transpose_example_from_spec():
    """Specific example: note=40, range=[60, 84], expect transposed result."""
    cfg = note_range.NoteRangeConfig(enabled=True, low_note=60, high_note=84, mode="transpose")
    # Note 40 (E2, pitch class 4)
    # Range [60, 72] covers C4..C5 (pitch classes 0..11)
    # Octaves: 0→4, 1→16, 2→28, 3→40, 4→52, 5→64 (in range!)
    result = note_range.apply_range(40, cfg)
    assert result == 64
    assert 60 <= result <= 84


def test_midi_boundary_notes():
    """Test MIDI boundary notes 0 and 127."""
    cfg = note_range.NoteRangeConfig(enabled=True, low_note=60, high_note=72, mode="transpose")
    # Note 0 (C-1, pitch class 0) → shift to C4 (60)
    assert note_range.apply_range(0, cfg) == 60
    # Note 127 (G9, pitch class 7) → shift to G4 (67) which is in [60, 72]
    assert note_range.apply_range(127, cfg) == 67


def test_all_pitch_classes_within_range():
    """In a wide range like [0, 127], all pitch classes should appear at least once."""
    cfg = note_range.NoteRangeConfig(enabled=True, low_note=0, high_note=127, mode="transpose")
    # Every pitch class 0..11 should fit somewhere
    for note in range(12):
        result = note_range.apply_range(note, cfg)
        assert result is not None, f"Pitch class {note} should fit in [0, 127]"


# ─────────────────────────────────────────────────────────────────────
# Default and edge-case initialization
# ─────────────────────────────────────────────────────────────────────

def test_default_config_is_disabled():
    """NoteRangeConfig() with no args should be disabled by default."""
    cfg = note_range.NoteRangeConfig()
    assert cfg.enabled is False
    assert note_range.apply_range(50, cfg) == 50


def test_default_range_is_full_midi():
    """Default enabled config should use range [0, 127]."""
    cfg = note_range.NoteRangeConfig(enabled=True)
    assert cfg.low_note == 0
    assert cfg.high_note == 127
    assert note_range.apply_range(64, cfg) == 64
