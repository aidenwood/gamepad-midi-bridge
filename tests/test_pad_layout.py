"""Pad-layout auto-assigner — ergonomic button-to-note mapping."""
from __future__ import annotations

import pytest

from gamepad_midi_bridge.pad_layout import (
    PadLayoutConfig,
    available_modes,
    build_layout,
    inverse_lookup,
    notes_per_button,
)


class TestPadLayoutConfigDefaults:
    """PadLayoutConfig dataclass — defaults and clamping."""

    def test_default_config_values(self):
        """Default config has sensible defaults."""
        cfg = PadLayoutConfig()
        assert cfg.button_count == 8
        assert cfg.root == 60
        assert cfg.scale == "major"
        assert cfg.mode == "sequential"
        assert cfg.start_octave == 4
        assert cfg.octave_span == 2

    def test_button_count_clamped_to_minimum(self):
        """button_count is clamped to >= 1."""
        cfg = PadLayoutConfig(button_count=0)
        assert cfg.button_count == 1

    def test_button_count_clamped_to_maximum(self):
        """button_count is clamped to <= 32."""
        cfg = PadLayoutConfig(button_count=50)
        assert cfg.button_count == 32

    def test_root_clamped_to_minimum(self):
        """root is clamped to >= 0."""
        cfg = PadLayoutConfig(root=-10)
        assert cfg.root == 0

    def test_root_clamped_to_maximum(self):
        """root is clamped to <= 127."""
        cfg = PadLayoutConfig(root=200)
        assert cfg.root == 127

    def test_octave_span_clamped_to_minimum(self):
        """octave_span is clamped to >= 1."""
        cfg = PadLayoutConfig(octave_span=0)
        assert cfg.octave_span == 1

    def test_octave_span_clamped_to_maximum(self):
        """octave_span is clamped to <= 6."""
        cfg = PadLayoutConfig(octave_span=10)
        assert cfg.octave_span == 6

    def test_unknown_mode_falls_back_to_sequential(self):
        """Unknown mode is replaced with 'sequential'."""
        cfg = PadLayoutConfig(mode="unknown_mode")
        assert cfg.mode == "sequential"


class TestSequentialMode:
    """Sequential mode: ascending scale notes."""

    def test_sequential_8_button_c_major(self):
        """Sequential 8-button C major returns [60, 62, 64, 65, 67, 69, 71, 72]."""
        cfg = PadLayoutConfig(button_count=8, root=60, scale="major", mode="sequential")
        layout = build_layout(cfg)
        # Major scale from C4 over 2 octaves: C, D, E, F, G, A, B, C5
        assert layout == [60, 62, 64, 65, 67, 69, 71, 72]

    def test_sequential_4_button_minor_pentatonic(self):
        """Sequential 4-button minor pentatonic from C returns 4 notes."""
        cfg = PadLayoutConfig(
            button_count=4, root=60, scale="pentatonic_minor", mode="sequential"
        )
        layout = build_layout(cfg)
        # Minor pentatonic: C, Eb, F, G, Bb (intervals 0, 3, 5, 7, 10)
        # Should pick first 4 scale notes
        assert len(layout) == 4
        assert layout[0] == 60  # C
        assert all(0 <= note <= 127 for note in layout)

    def test_sequential_pads_with_last_note_if_insufficient(self):
        """Sequential pads with last note when scale has fewer notes than buttons."""
        cfg = PadLayoutConfig(button_count=20, root=60, scale="pentatonic_minor", mode="sequential")
        layout = build_layout(cfg)
        assert len(layout) == 20
        # Should pad with the last available note
        assert all(0 <= note <= 127 for note in layout)


class TestSpreadMode:
    """Spread mode: evenly distribute across scale notes."""

    def test_spread_4_button_major_scale(self):
        """Spread 4-button across major scale distributes evenly."""
        cfg = PadLayoutConfig(button_count=4, root=60, scale="major", mode="spread")
        layout = build_layout(cfg)
        assert len(layout) == 4
        # Should pick evenly spaced notes from the major scale
        assert layout[0] == 60  # First note
        assert all(0 <= note <= 127 for note in layout)
        # Spread should pick roughly every Nth note
        assert layout[0] < layout[1]
        assert layout[1] < layout[2]
        assert layout[2] < layout[3]


class TestThirdsMode:
    """Thirds mode: every 3rd scale note (broken-thirds pattern)."""

    def test_thirds_4_button_c_major(self):
        """Thirds 4-button C major returns broken-thirds pattern."""
        cfg = PadLayoutConfig(button_count=4, root=60, scale="major", mode="thirds")
        layout = build_layout(cfg)
        # Major scale: [60, 62, 64, 65, 67, 69, 71, 72, ...]
        # Every 3rd: [60, 65, 71, 60] (indices 0, 3, 6, 9%8=1 → wraps)
        # Or: 0->60, 3->65, 6->71, 9%8=1->62
        assert len(layout) == 4
        assert layout[0] == 60
        assert all(0 <= note <= 127 for note in layout)

    def test_thirds_fills_all_buttons(self):
        """Thirds mode fills exactly button_count buttons."""
        cfg = PadLayoutConfig(button_count=8, root=60, scale="major", mode="thirds")
        layout = build_layout(cfg)
        assert len(layout) == 8


class TestChromaticMode:
    """Chromatic mode: ignore scale, return chromatic notes."""

    def test_chromatic_8_button_from_60(self):
        """Chromatic 8-button from 60 returns [60, 61, 62, 63, 64, 65, 66, 67]."""
        cfg = PadLayoutConfig(button_count=8, root=60, scale="major", mode="chromatic")
        layout = build_layout(cfg)
        assert layout == [60, 61, 62, 63, 64, 65, 66, 67]

    def test_chromatic_ignores_scale(self):
        """Chromatic mode ignores the scale parameter."""
        cfg1 = PadLayoutConfig(button_count=5, root=60, scale="major", mode="chromatic")
        cfg2 = PadLayoutConfig(button_count=5, root=60, scale="pentatonic_minor", mode="chromatic")
        layout1 = build_layout(cfg1)
        layout2 = build_layout(cfg2)
        assert layout1 == layout2

    def test_chromatic_clamps_to_127(self):
        """Chromatic wraps/clamps notes above 127."""
        cfg = PadLayoutConfig(button_count=10, root=120, scale="major", mode="chromatic")
        layout = build_layout(cfg)
        assert all(0 <= note <= 127 for note in layout)
        # Should have [120, 121, 122, 123, 124, 125, 126, 127, 127, 127]
        assert layout[0] == 120
        assert layout[-1] == 127


class TestDoubledMode:
    """Doubled mode: each pair of buttons holds note + octave-up."""

    def test_doubled_4_button_from_60(self):
        """Doubled 4-button starting at 60 returns [60, 72, 62, 74]."""
        cfg = PadLayoutConfig(button_count=4, root=60, scale="major", mode="doubled")
        layout = build_layout(cfg)
        # Major scale from C: [60, 62, 64, 65, 67, 69, 71, 72, ...]
        # Pair 1: 60 (even), 60+12=72 (odd)
        # Pair 2: 62 (even), 62+12=74 (odd)
        assert layout == [60, 72, 62, 74]

    def test_doubled_fills_all_buttons(self):
        """Doubled mode fills exactly button_count buttons."""
        cfg = PadLayoutConfig(button_count=8, root=60, scale="major", mode="doubled")
        layout = build_layout(cfg)
        assert len(layout) == 8

    def test_doubled_pairs_alternate_octaves(self):
        """Doubled mode alternates: base note, then +12 semitones."""
        cfg = PadLayoutConfig(button_count=6, root=60, scale="major", mode="doubled")
        layout = build_layout(cfg)
        # Pairs: (60, 72), (62, 74), (64, 76)
        # Check octave differences for odd indices
        for i in range(1, len(layout), 2):
            # Odd indices should be higher than preceding even index
            assert layout[i] > layout[i - 1]


class TestNotesPerButton:
    """notes_per_button returns a dict mapping index → note."""

    def test_notes_per_button_returns_dict(self):
        """notes_per_button returns a dict."""
        layout = [60, 62, 64, 65]
        result = notes_per_button(layout)
        assert isinstance(result, dict)
        assert result == {0: 60, 1: 62, 2: 64, 3: 65}

    def test_notes_per_button_empty_layout(self):
        """notes_per_button handles empty layout."""
        result = notes_per_button([])
        assert result == {}


class TestInverseLookup:
    """inverse_lookup finds button index for a given note."""

    def test_inverse_lookup_finds_existing_note(self):
        """inverse_lookup returns index for existing note."""
        layout = [60, 62, 64, 65, 67]
        assert inverse_lookup(62, layout) == 1
        assert inverse_lookup(67, layout) == 4

    def test_inverse_lookup_returns_none_for_missing_note(self):
        """inverse_lookup returns None for missing note."""
        layout = [60, 62, 64, 65, 67]
        assert inverse_lookup(61, layout) is None
        assert inverse_lookup(100, layout) is None

    def test_inverse_lookup_first_occurrence(self):
        """inverse_lookup returns first occurrence if note appears multiple times."""
        layout = [60, 62, 60, 65]
        assert inverse_lookup(60, layout) == 0


class TestAvailableModes:
    """available_modes returns list of mode names."""

    def test_available_modes_returns_five_entries(self):
        """available_modes returns exactly 5 modes."""
        modes = available_modes()
        assert len(modes) == 5

    def test_available_modes_contains_expected(self):
        """available_modes contains the expected mode names."""
        modes = available_modes()
        expected = {"sequential", "spread", "thirds", "chromatic", "doubled"}
        assert set(modes) == expected

    def test_available_modes_returns_copy(self):
        """available_modes returns a copy (modifications don't affect internal list)."""
        modes1 = available_modes()
        modes2 = available_modes()
        assert modes1 == modes2
        # Modifying one shouldn't affect the other
        modes1.append("fake_mode")
        modes2_check = available_modes()
        assert len(modes2_check) == 5


class TestNoteRangeValidity:
    """All notes in layouts should be valid MIDI (0..127)."""

    def test_all_notes_valid_sequential(self):
        """Sequential mode produces valid MIDI notes."""
        for root in [0, 60, 100, 127]:
            for button_count in [1, 8, 16, 32]:
                cfg = PadLayoutConfig(button_count=button_count, root=root, mode="sequential")
                layout = build_layout(cfg)
                assert all(0 <= note <= 127 for note in layout)

    def test_all_notes_valid_chromatic(self):
        """Chromatic mode clamps notes to 0..127."""
        cfg = PadLayoutConfig(button_count=20, root=115, mode="chromatic")
        layout = build_layout(cfg)
        assert all(0 <= note <= 127 for note in layout)

    def test_all_notes_valid_doubled(self):
        """Doubled mode produces valid MIDI notes."""
        cfg = PadLayoutConfig(button_count=16, root=60, mode="doubled")
        layout = build_layout(cfg)
        assert all(0 <= note <= 127 for note in layout)


class TestSerializationRoundTrip:
    """to_dict / from_dict round-trip."""

    def test_config_round_trip(self):
        """Config serializes and deserializes correctly."""
        original = PadLayoutConfig(
            button_count=12,
            root=62,
            scale="dorian",
            mode="spread",
            start_octave=3,
            octave_span=4,
        )
        data = original.to_dict()
        restored = PadLayoutConfig.from_dict(data)
        assert restored.button_count == 12
        assert restored.root == 62
        assert restored.scale == "dorian"
        assert restored.mode == "spread"
        assert restored.start_octave == 3
        assert restored.octave_span == 4

    def test_from_dict_with_none(self):
        """from_dict(None) returns default config."""
        cfg = PadLayoutConfig.from_dict(None)
        assert cfg.button_count == 8
        assert cfg.root == 60
        assert cfg.scale == "major"
        assert cfg.mode == "sequential"

    def test_from_dict_with_partial_dict(self):
        """from_dict with missing keys uses defaults."""
        data = {"button_count": 16, "root": 48}
        cfg = PadLayoutConfig.from_dict(data)
        assert cfg.button_count == 16
        assert cfg.root == 48
        assert cfg.scale == "major"  # default
        assert cfg.mode == "sequential"  # default


class TestRootVariations:
    """Layouts shift when root changes."""

    def test_changing_root_shifts_layout(self):
        """Layout shifts when root changes."""
        cfg1 = PadLayoutConfig(button_count=4, root=60, scale="major", mode="sequential")
        cfg2 = PadLayoutConfig(button_count=4, root=62, scale="major", mode="sequential")
        layout1 = build_layout(cfg1)
        layout2 = build_layout(cfg2)
        # All notes in layout2 should be 2 semitones higher than layout1
        for note1, note2 in zip(layout1, layout2):
            assert note2 == note1 + 2
