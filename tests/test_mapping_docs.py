"""Tests for mapping_docs.render_mapping_docs."""
from __future__ import annotations

import pytest

from gamepad_midi_bridge.mapping import Mapping
from gamepad_midi_bridge.mapping_docs import render_mapping_docs


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _default() -> Mapping:
    return Mapping()


def _empty() -> Mapping:
    """Mapping with all collections empty — exercises zero-row table paths."""
    return Mapping(
        name="Empty",
        buttons={},
        axes={},
        hats={},
        button_channels={},
        axis_channels={},
        hat_channels={},
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_returns_non_empty_string():
    result = render_mapping_docs(_default())
    assert isinstance(result, str)
    assert len(result) > 0


def test_output_is_valid_utf8():
    result = render_mapping_docs(_default())
    # If encoding fails this raises UnicodeEncodeError
    encoded = result.encode("utf-8")
    assert len(encoded) > 0


def test_contains_preset_name_as_h1():
    m = Mapping(name="My Cool Preset")
    result = render_mapping_docs(m)
    assert "# My Cool Preset" in result


def test_contains_expected_section_headers():
    result = render_mapping_docs(_default())
    expected_headers = [
        "## Description",
        "## Buttons → Notes",
        "## Axes → CC",
        "## D-pad → Notes",
        "## Triggers",
        "## Sticks",
        "## Touchpad",
        "## Shift Layer",
        "## A/B Compare",
        "## Setlist",
        "## Program Change",
    ]
    for header in expected_headers:
        assert header in result, f"Missing section: {header!r}"


def test_empty_mapping_renders_without_crash():
    result = render_mapping_docs(_empty())
    assert isinstance(result, str)
    assert "# Empty" in result
    assert "_No button mappings._" in result
    assert "_No axis mappings._" in result
    assert "_No D-pad mappings._" in result


def test_footer_contains_version_and_date():
    import re
    result = render_mapping_docs(_default())
    # Should end with a footer line that includes a version number
    assert "Universal Controller MIDI Bridge" in result
    # Version like "1.0.0" or similar
    assert re.search(r"v\d+\.\d+", result) is not None
    # ISO date
    assert re.search(r"\d{4}-\d{2}-\d{2}", result) is not None


def test_button_table_contains_note_names():
    m = Mapping()
    result = render_mapping_docs(m)
    # Note 60 = C4
    assert "C4" in result


def test_dpad_table_contains_directions():
    result = render_mapping_docs(_default())
    assert "Up" in result or "up" in result.lower()
    assert "Down" in result or "down" in result.lower()


def test_trigger_section_shows_mode():
    from gamepad_midi_bridge.mapping import TriggerConfig
    m = Mapping(l2_trigger=TriggerConfig(mode="latch", latch_threshold=0.7))
    result = render_mapping_docs(m)
    assert "latch" in result
    assert "0.70" in result


def test_stick_section_shows_curve():
    from gamepad_midi_bridge.mapping import StickConfig
    m = Mapping(left_stick=StickConfig(curve="exponential", curve_amount=0.8))
    result = render_mapping_docs(m)
    assert "exponential" in result


def test_touchpad_disabled_shows_placeholder():
    m = Mapping()
    m.touchpad.enabled = False
    result = render_mapping_docs(m)
    assert "_Touchpad disabled._" in result


def test_touchpad_enabled_shows_ccs():
    m = Mapping()
    m.touchpad.enabled = True
    m.touchpad.x_cc = 22
    m.touchpad.y_cc = 23
    result = render_mapping_docs(m)
    assert "22" in result
    assert "23" in result


def test_shift_layer_disabled_shows_placeholder():
    result = render_mapping_docs(_default())
    assert "_Shift layer disabled._" in result


def test_shift_layer_enabled_shows_button():
    from gamepad_midi_bridge.mapping import ShiftLayerConfig
    m = Mapping(shift_layer=ShiftLayerConfig(enabled=True, shift_button=9, buttons={0: 72}))
    result = render_mapping_docs(m)
    assert "Shift button" in result
    assert "9" in result


def test_setlist_disabled_shows_placeholder():
    result = render_mapping_docs(_default())
    assert "_Setlist disabled._" in result


def test_setlist_enabled_shows_presets():
    from gamepad_midi_bridge.mapping import SetlistConfig
    m = Mapping(setlist=SetlistConfig(enabled=True, name="Show Night", presets=["intro", "verse"]))
    result = render_mapping_docs(m)
    assert "Show Night" in result
    assert "intro" in result
    assert "verse" in result


def test_program_change_disabled_shows_placeholder():
    result = render_mapping_docs(_default())
    assert "_Program change listener disabled._" in result


def test_program_change_enabled_shows_bindings():
    from gamepad_midi_bridge.mapping import ProgramChangeConfig
    m = Mapping(program_change=ProgramChangeConfig(enabled=True, bindings={5: "my_preset"}))
    result = render_mapping_docs(m)
    assert "my_preset" in result
    assert "PC 5" in result


def test_global_channel_is_1_based():
    m = Mapping(midi_channel=0)  # 0 internally = channel 1 externally
    result = render_mapping_docs(m)
    assert "Global MIDI channel | 1" in result


def test_schema_version_shown():
    from gamepad_midi_bridge.mapping import SCHEMA_VERSION
    result = render_mapping_docs(_default())
    assert str(SCHEMA_VERSION) in result
