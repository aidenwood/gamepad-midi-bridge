"""Mapping mirror helper — flip notes around center for left-handed or inverted layouts."""
from __future__ import annotations

import pytest

from gamepad_midi_bridge.mapping_mirror import (
    mirror_note,
    mirror_buttons,
    mirror_axes_pairs,
    mirror_chords,
    mirror_macros,
    mirror_full_mapping,
)


class TestMirrorNote:
    """mirror_note function — single note mirroring with clamping."""

    def test_mirror_at_center_unchanged(self):
        """Mirroring the center note returns the center note itself."""
        assert mirror_note(60, 60) == 60

    def test_mirror_below_center(self):
        """Note 12 semitones below center mirrors to 12 above."""
        assert mirror_note(48, 60) == 72

    def test_mirror_above_center(self):
        """Note 12 semitones above center mirrors to 12 below."""
        assert mirror_note(72, 60) == 48

    def test_mirror_clamps_at_zero(self):
        """Mirroring a note that would go below 0 clamps to 0."""
        # mirror_note(130, 60) = 60*2 - 130 = -10, clamped to 0
        result = mirror_note(130, 60)
        assert result == 0

    def test_mirror_clamps_at_max(self):
        """Mirroring a note that would exceed 127 clamps to 127."""
        result = mirror_note(127, 60)
        assert result == 0

    def test_mirror_low_note_at_center_60(self):
        """Low notes mirror to high notes at center 60."""
        assert mirror_note(0, 60) == 120
        assert mirror_note(30, 60) == 90

    def test_mirror_high_note_at_center_60(self):
        """High notes mirror to low notes at center 60."""
        assert mirror_note(120, 60) == 0
        assert mirror_note(90, 60) == 30

    def test_mirror_different_center(self):
        """Mirroring works with different center points."""
        assert mirror_note(72, 72) == 72
        assert mirror_note(60, 72) == 84
        assert mirror_note(84, 72) == 60


class TestMirrorButtons:
    """mirror_buttons function — mirror button note assignments."""

    def test_simple_button_notes(self):
        """Mirror simple integer note assignments."""
        buttons = {0: 60, 1: 48, 2: 72}
        result = mirror_buttons(buttons, 60)
        assert result == {0: 60, 1: 72, 2: 48}

    def test_complex_button_configs(self):
        """Mirror note field in complex button config dicts."""
        buttons = {0: {"note": 48, "velocity": 127}, 1: {"note": 72, "channel": 0}}
        result = mirror_buttons(buttons, 60)
        assert result[0]["note"] == 72
        assert result[0]["velocity"] == 127
        assert result[1]["note"] == 48
        assert result[1]["channel"] == 0

    def test_button_without_note_key(self):
        """Buttons with config but no 'note' key are passed through unchanged."""
        buttons = {0: {"velocity": 100}, 1: 60}
        result = mirror_buttons(buttons, 60)
        assert result[0] == {"velocity": 100}
        assert result[1] == 60

    def test_returns_new_dict(self):
        """mirror_buttons returns a new dict, not a mutation."""
        buttons = {0: 60, 1: 48}
        result = mirror_buttons(buttons, 60)
        assert result is not buttons
        assert buttons == {0: 60, 1: 48}

    def test_empty_buttons_dict(self):
        """Empty buttons dict returns empty result."""
        assert mirror_buttons({}, 60) == {}

    def test_unknown_config_format_passthrough(self):
        """Unknown config formats are passed through unchanged."""
        buttons = {0: "string_value", 1: 100.5}
        result = mirror_buttons(buttons, 60)
        assert result[0] == "string_value"
        assert result[1] == 100.5


class TestMirrorAxesPairs:
    """mirror_axes_pairs function — swap left/right stick axes."""

    def test_swap_left_right_sticks(self):
        """Axes 0↔2 and 1↔3 are swapped."""
        axes = {0: 3, 1: 4, 2: 5, 3: 6}
        result = mirror_axes_pairs(axes)
        assert result[0] == 5
        assert result[1] == 6
        assert result[2] == 3
        assert result[3] == 4

    def test_triggers_unchanged(self):
        """Axes 4 and 5 (triggers) are not swapped."""
        axes = {0: 3, 1: 4, 2: 5, 3: 6, 4: 1, 5: 2}
        result = mirror_axes_pairs(axes)
        assert result[4] == 1
        assert result[5] == 2

    def test_missing_swap_pair_passthrough(self):
        """If one axis of a pair is missing, the other passes through unchanged."""
        axes = {0: 3, 1: 4}
        result = mirror_axes_pairs(axes)
        assert result[0] == 3
        assert result[1] == 4

    def test_empty_axes_dict(self):
        """Empty axes dict returns empty result."""
        assert mirror_axes_pairs({}) == {}

    def test_returns_new_dict(self):
        """mirror_axes_pairs returns a new dict."""
        axes = {0: 3, 1: 4, 2: 5, 3: 6}
        result = mirror_axes_pairs(axes)
        assert result is not axes


class TestMirrorChords:
    """mirror_chords function — mirror stick-chord note assignments."""

    def test_mirror_and_swap_north_south(self):
        """chord_north and chord_south are swapped and notes mirrored."""
        chords = {
            "chord_north": [60, 62, 64],
            "chord_south": [72, 74, 76],
        }
        result = mirror_chords(chords, 60)
        assert result["chord_north"] == [48, 46, 44]
        assert result["chord_south"] == [60, 58, 56]

    def test_mirror_and_swap_east_west(self):
        """chord_east and chord_west are swapped and notes mirrored."""
        chords = {
            "chord_east": [60, 64],
            "chord_west": [72, 76],
        }
        result = mirror_chords(chords, 60)
        assert result["chord_east"] == [48, 44]
        assert result["chord_west"] == [60, 56]

    def test_mirror_all_four_directions(self):
        """All four directions are mirrored and opposite pairs swapped."""
        chords = {
            "chord_north": [60],
            "chord_south": [72],
            "chord_east": [64],
            "chord_west": [68],
        }
        result = mirror_chords(chords, 60)
        assert result["chord_north"] == [48]
        assert result["chord_south"] == [60]
        assert result["chord_east"] == [52]
        assert result["chord_west"] == [56]

    def test_preserves_other_keys(self):
        """Non-chord keys are preserved."""
        chords = {
            "chord_north": [60],
            "chord_velocity": 100,
            "other_key": "value",
        }
        result = mirror_chords(chords, 60)
        assert result["chord_velocity"] == 100
        assert result["other_key"] == "value"

    def test_missing_directions_ignored(self):
        """Missing chord direction keys don't cause errors."""
        chords = {"chord_north": [60]}
        result = mirror_chords(chords, 60)
        assert result["chord_north"] == [60]
        assert "chord_south" not in result
        assert "chord_east" not in result
        assert "chord_west" not in result

    def test_empty_chord_dict(self):
        """Empty chord dict is returned as-is."""
        assert mirror_chords({}, 60) == {}

    def test_different_center_point(self):
        """Chords are mirrored around a custom center point."""
        chords = {"chord_north": [72], "chord_south": [60]}
        result = mirror_chords(chords, 72)
        # Center 72: mirror([72]) = [72], mirror([60]) = [84]
        # Swap: north <- [84], south <- [72]
        assert result["chord_north"] == [84]
        assert result["chord_south"] == [72]


class TestMirrorMacros:
    """mirror_macros function — mirror note fields in recorded macro events."""

    def test_mirror_macro_note_events(self):
        """Macro note fields are mirrored."""
        macros = [
            {
                "name": "test",
                "events": [
                    {"delay_ms": 0, "status": 0x90, "data1": 60, "data2": 100},
                    {"delay_ms": 100, "status": 0x80, "data1": 60, "data2": 0},
                ],
            }
        ]
        result = mirror_macros(macros, 60)
        assert result[0]["events"][0]["data1"] == 60
        assert result[0]["events"][1]["data1"] == 60

    def test_mirror_preserves_macro_metadata(self):
        """Non-event fields in macros are preserved."""
        macros = [
            {
                "name": "test_macro",
                "events": [{"delay_ms": 0, "status": 0x90, "data1": 48, "data2": 100}],
                "duration_ms": 1000,
                "arp_mode": True,
            }
        ]
        result = mirror_macros(macros, 60)
        assert result[0]["name"] == "test_macro"
        assert result[0]["duration_ms"] == 1000
        assert result[0]["arp_mode"] is True
        assert result[0]["events"][0]["data1"] == 72

    def test_missing_events_key_defensive(self):
        """Macros missing 'events' key don't cause errors."""
        macros = [{"name": "test"}]
        result = mirror_macros(macros, 60)
        assert result[0]["name"] == "test"

    def test_missing_data1_key_defensive(self):
        """Events missing 'data1' key are left unchanged."""
        macros = [
            {
                "name": "test",
                "events": [{"delay_ms": 0, "status": 0x90, "data2": 100}],
            }
        ]
        result = mirror_macros(macros, 60)
        assert result[0]["events"][0]["data2"] == 100

    def test_returns_new_list(self):
        """mirror_macros returns a new list, not mutating input."""
        macros = [{"name": "test", "events": [{"delay_ms": 0, "data1": 60}]}]
        result = mirror_macros(macros, 60)
        assert result is not macros
        assert macros[0]["events"][0]["data1"] == 60

    def test_empty_macros_list(self):
        """Empty macros list returns empty result."""
        assert mirror_macros([], 60) == []

    def test_multiple_macros(self):
        """Multiple macros are all processed."""
        macros = [
            {"name": "m1", "events": [{"delay_ms": 0, "data1": 48}]},
            {"name": "m2", "events": [{"delay_ms": 0, "data1": 72}]},
        ]
        result = mirror_macros(macros, 60)
        assert result[0]["events"][0]["data1"] == 72
        assert result[1]["events"][0]["data1"] == 48


class TestMirrorFullMapping:
    """mirror_full_mapping function — apply all mirror transformations."""

    def test_mirrors_buttons_only_by_default(self):
        """Full mapping mirrors buttons without swapping axes by default."""
        mapping = {
            "buttons": {0: 48, 1: 72},
            "axes": {0: 3, 1: 4, 2: 5, 3: 6},
        }
        result = mirror_full_mapping(mapping, 60, mirror_axes=False)
        assert result["buttons"] == {0: 72, 1: 48}
        assert result["axes"] == {0: 3, 1: 4, 2: 5, 3: 6}

    def test_mirrors_axes_when_enabled(self):
        """Full mapping swaps axes when mirror_axes=True."""
        mapping = {
            "buttons": {0: 60},
            "axes": {0: 3, 1: 4, 2: 5, 3: 6},
        }
        result = mirror_full_mapping(mapping, 60, mirror_axes=True)
        assert result["axes"] == {0: 5, 1: 6, 2: 3, 3: 4}

    def test_mirrors_stick_chords(self):
        """Full mapping mirrors stick chord notes."""
        mapping = {
            "buttons": {0: 60},
            "stick_left": {
                "chord_north": [60],
                "chord_south": [72],
            },
        }
        result = mirror_full_mapping(mapping, 60)
        assert result["stick_left"]["chord_north"] == [48]
        assert result["stick_left"]["chord_south"] == [60]

    def test_mirrors_gesture_notes(self):
        """Full mapping mirrors gesture note assignments."""
        mapping = {
            "swipe_up_note": 48,
            "swipe_down_note": 72,
            "swipe_left_note": 50,
            "swipe_right_note": 70,
            "pinch_in_note": 60,
            "pinch_out_note": 60,
        }
        result = mirror_full_mapping(mapping, 60)
        assert result["swipe_up_note"] == 72
        assert result["swipe_down_note"] == 48
        assert result["swipe_left_note"] == 70
        assert result["swipe_right_note"] == 50
        assert result["pinch_in_note"] == 60
        assert result["pinch_out_note"] == 60

    def test_mirrors_macros(self):
        """Full mapping mirrors macro note fields."""
        mapping = {
            "buttons": {0: 60},
            "macros": [
                {
                    "name": "test",
                    "events": [{"delay_ms": 0, "data1": 48}],
                }
            ],
        }
        result = mirror_full_mapping(mapping, 60)
        assert result["macros"][0]["events"][0]["data1"] == 72

    def test_deep_copy_prevents_mutation(self):
        """Full mapping is deep-copied; input is not mutated."""
        mapping = {
            "buttons": {0: 48},
            "axes": {0: 3},
            "stick_left": {"chord_north": [60]},
        }
        result = mirror_full_mapping(mapping, 60)
        assert mapping["buttons"] == {0: 48}
        assert result["buttons"] == {0: 72}

    def test_complete_mapping_transformation(self):
        """Full mapping with all features is transformed correctly."""
        mapping = {
            "name": "test",
            "buttons": {0: 48, 1: 72},
            "axes": {0: 3, 1: 4, 2: 5, 3: 6, 4: 1, 5: 2},
            "stick_left": {"chord_north": [60], "chord_south": [72]},
            "stick_right": {"chord_east": [64], "chord_west": [68]},
            "swipe_up_note": 48,
            "macros": [
                {
                    "name": "m1",
                    "events": [{"delay_ms": 0, "data1": 60}],
                }
            ],
        }
        result = mirror_full_mapping(mapping, 60, mirror_axes=True)

        assert result["buttons"] == {0: 72, 1: 48}
        assert result["axes"] == {0: 5, 1: 6, 2: 3, 3: 4, 4: 1, 5: 2}
        assert result["stick_left"]["chord_north"] == [48]
        assert result["stick_left"]["chord_south"] == [60]
        assert result["stick_right"]["chord_east"] == [52]
        assert result["stick_right"]["chord_west"] == [56]
        assert result["swipe_up_note"] == 72
        assert result["macros"][0]["events"][0]["data1"] == 60
        assert result["name"] == "test"

    def test_custom_center_point(self):
        """Full mapping respects custom center point for mirroring."""
        mapping = {
            "buttons": {0: 60, 1: 84},
        }
        result = mirror_full_mapping(mapping, 72)
        assert result["buttons"] == {0: 84, 1: 60}

    def test_missing_optional_fields(self):
        """Mapping with missing optional fields doesn't cause errors."""
        mapping = {
            "buttons": {0: 60},
        }
        result = mirror_full_mapping(mapping, 60)
        assert result["buttons"] == {0: 60}

    def test_returns_new_dict(self):
        """mirror_full_mapping returns a new dict."""
        mapping = {"buttons": {0: 60}}
        result = mirror_full_mapping(mapping, 60)
        assert result is not mapping
