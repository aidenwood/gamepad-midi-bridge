"""Tests for mapping_export_text module.

Pure stdlib tests — no Qt, no fixtures required. Tests verify that render_mapping
and render_compact produce readable, compact text suitable for Discord/Reddit/Slack.
"""
from __future__ import annotations

import pytest

from gamepad_midi_bridge.mapping_export_text import (
    _note_name,
    count_mapped,
    format_note_range,
    render_mapping,
    render_compact,
)


# ---------------------------------------------------------------------------
# Test _note_name
# ---------------------------------------------------------------------------

def test_note_name_middle_c():
    """MIDI note 60 should be C4."""
    assert _note_name(60) == "C4"


def test_note_name_c_sharp():
    """MIDI note 61 should be C#4."""
    assert _note_name(61) == "C#4"


def test_note_name_g():
    """MIDI note 67 should be G4."""
    assert _note_name(67) == "G4"


def test_note_name_low():
    """MIDI note 0 should be C-1."""
    assert _note_name(0) == "C-1"


def test_note_name_high():
    """MIDI note 127 should be G9."""
    assert _note_name(127) == "G9"


# ---------------------------------------------------------------------------
# Test count_mapped
# ---------------------------------------------------------------------------

def test_count_mapped_buttons_empty():
    """Empty mapping has no mapped buttons."""
    mapping = {}
    assert count_mapped(mapping, "buttons") == 0


def test_count_mapped_buttons_single():
    """Mapping with one button returns 1."""
    mapping = {"buttons": {"0": 60}}
    assert count_mapped(mapping, "buttons") == 1


def test_count_mapped_buttons_multiple():
    """Mapping with multiple buttons."""
    mapping = {"buttons": {"0": 60, "1": 62, "2": 64}}
    assert count_mapped(mapping, "buttons") == 3


def test_count_mapped_buttons_excludes_zero():
    """Unmapped buttons (note 0) are excluded."""
    mapping = {"buttons": {"0": 60, "1": 0, "2": 64}}
    assert count_mapped(mapping, "buttons") == 2


def test_count_mapped_axes_empty():
    """Empty mapping has no mapped axes."""
    mapping = {}
    assert count_mapped(mapping, "axes") == 0


def test_count_mapped_axes_single():
    """Mapping with one axis."""
    mapping = {"axes": {"0": 1}}
    assert count_mapped(mapping, "axes") == 1


def test_count_mapped_axes_multiple():
    """Mapping with multiple axes."""
    mapping = {"axes": {"0": 1, "1": 11, "2": 74}}
    assert count_mapped(mapping, "axes") == 3


def test_count_mapped_axes_excludes_zero():
    """Unmapped axes (cc 0) are excluded."""
    mapping = {"axes": {"0": 1, "1": 0, "2": 74}}
    assert count_mapped(mapping, "axes") == 2


def test_count_mapped_triggers_none():
    """No trigger configs = 0 count."""
    mapping = {}
    assert count_mapped(mapping, "triggers") == 0


def test_count_mapped_triggers_linear_not_mapped():
    """Linear mode (default) does not count as mapped."""
    mapping = {"l2_trigger": {"mode": "linear"}}
    assert count_mapped(mapping, "triggers") == 0


def test_count_mapped_triggers_latch():
    """Latch mode counts as 1 mapped trigger."""
    mapping = {"l2_trigger": {"mode": "latch"}}
    assert count_mapped(mapping, "triggers") == 1


def test_count_mapped_triggers_both():
    """Both L2 and R2 latch = 2."""
    mapping = {
        "l2_trigger": {"mode": "latch"},
        "r2_trigger": {"mode": "ceiling"},
    }
    assert count_mapped(mapping, "triggers") == 2


def test_count_mapped_triggers_gate_button():
    """Gate button set counts as mapped even if mode is linear."""
    mapping = {"l2_trigger": {"mode": "linear", "gate_button": 5}}
    assert count_mapped(mapping, "triggers") == 1


def test_count_mapped_macros_empty():
    """Empty macros dict."""
    mapping = {"macros": {}}
    assert count_mapped(mapping, "macros") == 0


def test_count_mapped_macros_single():
    """Single macro."""
    mapping = {"macros": {"0": {"name": "Arpeggio"}}}
    assert count_mapped(mapping, "macros") == 1


def test_count_mapped_setlist_empty():
    """Empty setlist."""
    mapping = {"setlist": {"presets": []}}
    assert count_mapped(mapping, "setlist") == 0


def test_count_mapped_setlist_multiple():
    """Multiple presets in setlist."""
    mapping = {"setlist": {"presets": ["Intro", "Verse", "Chorus"]}}
    assert count_mapped(mapping, "setlist") == 3


# ---------------------------------------------------------------------------
# Test format_note_range
# ---------------------------------------------------------------------------

def test_format_note_range_empty():
    """Empty list returns empty string."""
    assert format_note_range([]) == ""


def test_format_note_range_single():
    """Single note."""
    assert format_note_range([60]) == "C4"


def test_format_note_range_two():
    """Two notes comma-separated."""
    result = format_note_range([60, 64])
    assert result == "C4, E4"


def test_format_note_range_three():
    """Three notes comma-separated."""
    result = format_note_range([60, 64, 67])
    assert result == "C4, E4, G4"


def test_format_note_range_four_or_more_uses_range():
    """Four or more notes use range format."""
    result = format_note_range([60, 62, 64, 65, 67])
    assert result == "C4–G4"


def test_format_note_range_unsorted_input():
    """Unsorted input is sorted before processing."""
    result = format_note_range([67, 60, 64])
    assert result == "C4, E4, G4"


def test_format_note_range_duplicates_removed():
    """Duplicate notes are deduplicated."""
    result = format_note_range([60, 60, 64, 64])
    assert result == "C4, E4"


def test_format_note_range_large_range():
    """Large range is properly formatted."""
    result = format_note_range([60, 70, 80, 90])
    assert "–" in result
    assert "C4" in result


# ---------------------------------------------------------------------------
# Test render_mapping
# ---------------------------------------------------------------------------

def test_render_mapping_empty():
    """Empty mapping renders minimal output."""
    mapping = {}
    result = render_mapping(mapping)
    assert isinstance(result, str)
    assert "Channel: 1" in result


def test_render_mapping_returns_multiline():
    """render_mapping returns multi-line string."""
    mapping = {"buttons": {"0": 60}}
    result = render_mapping(mapping)
    lines = result.split("\n")
    assert len(lines) >= 2


def test_render_mapping_includes_preset_name():
    """Preset name appears on first line."""
    mapping = {"name": "Lead Piano"}
    result = render_mapping(mapping)
    assert "Preset: Lead Piano" in result


def test_render_mapping_includes_channel():
    """Global channel (1-based) is shown."""
    mapping = {"midi_channel": 5}
    result = render_mapping(mapping)
    assert "Channel: 6" in result


def test_render_mapping_buttons_single():
    """Single button shows note."""
    mapping = {"buttons": {"0": 60}}
    result = render_mapping(mapping)
    assert "Buttons: 1 mapped" in result
    assert "C4" in result


def test_render_mapping_buttons_multiple():
    """Multiple buttons show note range."""
    mapping = {"buttons": {"0": 60, "1": 62, "2": 64}}
    result = render_mapping(mapping)
    assert "Buttons: 3 mapped" in result


def test_render_mapping_axes_single():
    """Single axis CC shown."""
    mapping = {"axes": {"0": 1}}
    result = render_mapping(mapping)
    assert "Axes: 1 mapped (CC 1)" in result


def test_render_mapping_axes_multiple():
    """Multiple axes CCs listed."""
    mapping = {"axes": {"0": 1, "1": 11, "2": 74}}
    result = render_mapping(mapping)
    assert "Axes: 3 mapped (CC 1, 11, 74)" in result


def test_render_mapping_triggers_latch():
    """Latch trigger mode shown."""
    mapping = {"l2_trigger": {"mode": "latch"}}
    result = render_mapping(mapping)
    assert "Triggers:" in result
    assert "latch" in result


def test_render_mapping_triggers_both():
    """Both L2 and R2 shown if both mapped."""
    mapping = {
        "l2_trigger": {"mode": "latch"},
        "r2_trigger": {"mode": "ceiling"},
    }
    result = render_mapping(mapping)
    assert "Triggers:" in result
    assert "L2" in result
    assert "R2" in result


def test_render_mapping_sticks_chord():
    """Chord mode on stick shown."""
    mapping = {"left_stick": {"chord_mode_enabled": True}}
    result = render_mapping(mapping)
    assert "Sticks:" in result
    assert "chord" in result


def test_render_mapping_sticks_flick():
    """Flick mode on stick shown."""
    mapping = {"left_stick": {"flick_enabled": True}}
    result = render_mapping(mapping)
    assert "Sticks:" in result
    assert "flick" in result


def test_render_mapping_macros():
    """Macro count shown."""
    mapping = {"macros": {"0": {"name": "Arp"}, "1": {"name": "Roll"}}}
    result = render_mapping(mapping)
    assert "Macros: 2 saved" in result


def test_render_mapping_setlist():
    """Setlist presets count shown."""
    mapping = {"setlist": {"presets": ["Intro", "Verse", "Chorus"]}}
    result = render_mapping(mapping)
    assert "Setlist: 3 presets" in result


def test_render_mapping_max_lines_truncates():
    """Output truncates to max_lines with ..."""
    mapping = {
        "name": "Test",
        "buttons": {"0": 60, "1": 62},
        "axes": {"0": 1, "1": 11},
        "left_stick": {"chord_mode_enabled": True},
        "macros": {"0": {"name": "A"}},
        "setlist": {"presets": ["P1"]},
    }
    result = render_mapping(mapping, max_lines=3)
    lines = result.split("\n")
    assert len(lines) <= 3
    if len(lines) == 3:
        assert lines[-1] == "..."


def test_render_mapping_non_mutating():
    """render_mapping does not mutate input dict."""
    mapping = {"name": "Test", "buttons": {"0": 60}}
    mapping_copy = mapping.copy()
    render_mapping(mapping)
    assert mapping == mapping_copy


# ---------------------------------------------------------------------------
# Test render_compact
# ---------------------------------------------------------------------------

def test_render_compact_empty():
    """Empty mapping returns 'Empty preset'."""
    mapping = {}
    result = render_compact(mapping)
    assert result == "Empty preset"


def test_render_compact_returns_string():
    """render_compact returns a string."""
    mapping = {"buttons": {"0": 60}}
    result = render_compact(mapping)
    assert isinstance(result, str)


def test_render_compact_single_line():
    """render_compact always returns single line (no newlines)."""
    mapping = {
        "buttons": {"0": 60, "1": 62, "2": 64},
        "axes": {"0": 1, "1": 11},
        "macros": {"0": {"name": "A"}},
    }
    result = render_compact(mapping)
    assert "\n" not in result


def test_render_compact_buttons_only():
    """Buttons mapped, nothing else."""
    mapping = {"buttons": {"0": 60, "1": 64, "2": 67}}
    result = render_compact(mapping)
    assert "buttons" in result
    assert "C4" in result


def test_render_compact_axes_only():
    """Axes mapped, nothing else."""
    mapping = {"axes": {"0": 1, "1": 11, "2": 74}}
    result = render_compact(mapping)
    assert "axes" in result
    assert "CC" in result


def test_render_compact_triggers():
    """Triggers shown."""
    mapping = {"l2_trigger": {"mode": "latch"}}
    result = render_compact(mapping)
    assert "latch" in result


def test_render_compact_macros():
    """Macro count shown."""
    mapping = {"macros": {"0": {"name": "A"}, "1": {"name": "B"}}}
    result = render_compact(mapping)
    assert "2 macros" in result


def test_render_compact_setlist():
    """Setlist count shown."""
    mapping = {"setlist": {"presets": ["P1", "P2"]}}
    result = render_compact(mapping)
    assert "2 presets" in result


def test_render_compact_complex():
    """Complex mapping with multiple sections."""
    mapping = {
        "buttons": {"0": 60, "1": 62, "2": 64},
        "axes": {"0": 1, "1": 11},
        "l2_trigger": {"mode": "latch"},
        "macros": {"0": {"name": "A"}},
    }
    result = render_compact(mapping)
    assert "C4" in result
    assert "CC" in result
    assert "latch" in result
    assert "1 macros" in result
    assert "|" in result


def test_render_compact_non_mutating():
    """render_compact does not mutate input dict."""
    mapping = {"buttons": {"0": 60}}
    mapping_copy = mapping.copy()
    render_compact(mapping)
    assert mapping == mapping_copy


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------

def test_render_mapping_and_compact_consistent():
    """render_mapping and render_compact show consistent info."""
    mapping = {
        "name": "Test Preset",
        "midi_channel": 1,
        "buttons": {"0": 60, "1": 64},
        "axes": {"0": 1},
    }
    multi = render_mapping(mapping)
    compact = render_compact(mapping)

    # Both should mention buttons
    assert "buttons" in multi.lower() or "C4" in multi
    assert "buttons" in compact.lower() or "C4" in compact

    # Compact should be single line
    assert "\n" not in compact


def test_typical_discord_paste():
    """Typical mapping suitable for Discord paste."""
    mapping = {
        "name": "Synth Lead",
        "midi_channel": 0,
        "buttons": {
            "0": 60, "1": 62, "2": 64, "3": 65, "4": 67,
            "5": 69, "6": 71, "7": 72,
        },
        "axes": {"0": 1, "1": 11, "2": 74, "3": 7},
        "l2_trigger": {"mode": "latch"},
        "r2_trigger": {"mode": "linear", "gate_button": 12},
        "macros": {"0": {"name": "Arpeggio"}, "1": {"name": "Sweep"}},
    }
    result = render_mapping(mapping)
    assert "Preset: Synth Lead" in result
    assert "Buttons: 8 mapped" in result
    assert "Axes: 4 mapped" in result
    assert "Triggers:" in result
    assert "Macros: 2 saved" in result

    # Should be readable in a Discord message
    lines = result.split("\n")
    assert len(lines) > 0


def test_typical_reddit_summary():
    """Typical mapping suitable for Reddit summary."""
    mapping = {
        "buttons": {"0": 60, "1": 62, "2": 64},
        "axes": {"0": 1, "1": 11},
        "macros": {"0": {"name": "Arp"}},
    }
    result = render_compact(mapping)

    # Should fit in a single sentence/line
    assert "\n" not in result
    assert "|" in result
    assert "C4" in result or "60" not in result  # Note name shown
