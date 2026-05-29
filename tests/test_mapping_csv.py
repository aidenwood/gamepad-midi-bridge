"""Tests for CSV export helper (mapping_csv module).

Pure stdlib tests — no Qt, no fixtures required. Tests verify CSV export
logic for buttons, axes, triggers, sticks, and graceful handling of
missing/partial mappings.
"""
from __future__ import annotations

import csv
import io
import sys
from pathlib import Path

import pytest

# Ensure src/ is importable.
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gamepad_midi_bridge import mapping_csv as mc


def test_empty_mapping_returns_header_only():
    """Empty mapping_dict returns just the header row."""
    empty = {}
    rows = mc.mapping_to_rows(empty)
    assert len(rows) == 1
    assert rows[0] == ["Control Type", "Control Name", "Output", "Channel", "Velocity / Value", "Notes"]


def test_single_mapped_button():
    """Mapping with one mapped button produces header + button row."""
    mapping = {
        "buttons": {"0": 60},
        "midi_channel": 0,
    }
    rows = mc.mapping_to_rows(mapping)
    assert len(rows) == 2
    assert rows[0][0] == "Control Type"  # header
    assert rows[1][0] == "Button"
    assert rows[1][1] == "0"
    assert rows[1][2] == "Note 60"
    assert rows[1][3] == "0"  # channel


def test_multiple_mapped_buttons():
    """Mapping with multiple mapped buttons produces N+1 rows."""
    mapping = {
        "buttons": {"0": 60, "1": 62, "2": 64},
        "midi_channel": 0,
    }
    rows = mc.mapping_to_rows(mapping)
    assert len(rows) == 4  # header + 3 buttons
    assert rows[1][1] == "0"
    assert rows[2][1] == "1"
    assert rows[3][1] == "2"


def test_unmapped_buttons_skipped():
    """Buttons with note==0 are skipped."""
    mapping = {
        "buttons": {"0": 60, "1": 0, "2": 64},
        "midi_channel": 0,
    }
    rows = mc.mapping_to_rows(mapping)
    # Should have header + 2 (skipping button 1)
    assert len(rows) == 3
    assert rows[1][2] == "Note 60"
    assert rows[2][2] == "Note 64"


def test_button_velocity_from_config():
    """Button velocity comes from button_configs if present."""
    mapping = {
        "buttons": {"5": 60},
        "button_configs": {
            "5": {"velocity": 127}
        },
        "midi_channel": 0,
    }
    rows = mc.mapping_to_rows(mapping)
    assert rows[1][4] == "127"  # Velocity / Value column


def test_button_with_gate():
    """Button with gate_button in config appears in notes."""
    mapping = {
        "buttons": {"5": 60},
        "button_configs": {
            "5": {"velocity": 100, "gate_button": 10}
        },
        "midi_channel": 0,
    }
    rows = mc.mapping_to_rows(mapping)
    assert "gated by button 10" in rows[1][5]


def test_button_with_repeat():
    """Button with repeat_enabled appears in notes."""
    mapping = {
        "buttons": {"5": 60},
        "button_configs": {
            "5": {"velocity": 100, "repeat_enabled": True, "repeat_rate_hz": 8.0}
        },
        "midi_channel": 0,
    }
    rows = mc.mapping_to_rows(mapping)
    assert "repeat @ 8.0 Hz" in rows[1][5]


def test_axes_appear_as_axis_rows():
    """Axes (0-3: sticks, 4-5: triggers) appear as Axis/Trigger rows."""
    mapping = {
        "axes": {"0": 3, "1": 4, "2": 5, "3": 6},
        "midi_channel": 0,
    }
    rows = mc.mapping_to_rows(mapping)
    # Header + 4 axes
    assert len(rows) == 5
    assert rows[1][0] == "Axis"
    assert rows[1][1] == "Left Stick X"
    assert rows[2][1] == "Left Stick Y"
    assert rows[3][1] == "Right Stick X"
    assert rows[4][1] == "Right Stick Y"


def test_triggers_appear_as_trigger_rows():
    """Trigger axes (4, 5) appear as Trigger control type."""
    mapping = {
        "axes": {"4": 1, "5": 2},
        "l2_trigger": {"mode": "linear"},
        "r2_trigger": {"mode": "ceiling", "ceiling": 100},
        "midi_channel": 0,
    }
    rows = mc.mapping_to_rows(mapping)
    # Header + 2 triggers
    assert len(rows) == 3
    assert rows[1][0] == "Trigger"
    assert rows[1][1] == "L2"
    assert rows[1][5] == "linear"  # mode in notes
    assert rows[2][0] == "Trigger"
    assert rows[2][1] == "R2"
    assert "ceiling" in rows[2][5]  # mode in notes


def test_unmapped_axes_skipped():
    """Axes with cc==0 are skipped."""
    mapping = {
        "axes": {"0": 3, "1": 0, "2": 5},
        "midi_channel": 0,
    }
    rows = mc.mapping_to_rows(mapping)
    # Header + 2 axes (skipping axis 1)
    assert len(rows) == 3


def test_hats_appear():
    """Hat directions appear as D-Pad rows."""
    mapping = {
        "hats": {"up": 78, "down": 79, "left": 80, "right": 81},
        "midi_channel": 0,
    }
    rows = mc.mapping_to_rows(mapping)
    # Header + 4 hats
    assert len(rows) == 5
    assert rows[1][0] == "D-Pad"
    assert rows[1][1] == "Up"
    assert rows[1][2] == "Note 78"


def test_unmapped_hats_skipped():
    """Hats with note==0 are skipped."""
    mapping = {
        "hats": {"up": 78, "down": 0, "left": 80},
        "midi_channel": 0,
    }
    rows = mc.mapping_to_rows(mapping)
    # Header + 2 hats (skipping down)
    assert len(rows) == 3


def test_button_channel_override():
    """Button channel override appears in Channel column."""
    mapping = {
        "buttons": {"0": 60},
        "button_channels": {"0": 5},
        "midi_channel": 0,
    }
    rows = mc.mapping_to_rows(mapping)
    assert rows[1][3] == "5"  # Channel column


def test_axis_channel_override():
    """Axis channel override appears in Channel column."""
    mapping = {
        "axes": {"0": 3},
        "axis_channels": {"0": 10},
        "midi_channel": 0,
    }
    rows = mc.mapping_to_rows(mapping)
    assert rows[1][3] == "10"  # Channel column


def test_global_channel_default():
    """Without override, uses global midi_channel."""
    mapping = {
        "buttons": {"0": 60},
        "midi_channel": 5,
    }
    rows = mc.mapping_to_rows(mapping)
    assert rows[1][3] == "5"  # Channel column


def test_stick_polar_mode():
    """Stick with polar_mode gets polar in notes."""
    mapping = {
        "left_stick": {"polar_mode": True, "polar_angle_cc": 7, "polar_mag_cc": 8},
        "axis_channels": {},
        "midi_channel": 0,
    }
    rows = mc.mapping_to_rows(mapping)
    # Should have header + stick polar row
    assert any("polar mode" in row[5] for row in rows)
    assert any("Left Stick (Polar)" in row[1] for row in rows)


def test_stick_chord_enabled():
    """Stick with chord_enabled gets chord notes in notes."""
    mapping = {
        "left_stick": {
            "chord_enabled": True,
            "chord_north": [60, 62],
            "chord_east": [64, 65],
            "chord_south": [],
            "chord_west": [],
            "chord_velocity": 100,
        },
        "midi_channel": 0,
    }
    rows = mc.mapping_to_rows(mapping)
    # Should have header + stick chord row
    assert any("chord" in row[1].lower() for row in rows)
    chord_row = [row for row in rows if "chord" in row[1].lower()][0]
    assert "60" in chord_row[5] and "62" in chord_row[5]


def test_right_stick_features():
    """Right stick features appear correctly."""
    mapping = {
        "right_stick": {"polar_mode": True, "polar_angle_cc": 7, "polar_mag_cc": 8},
        "axis_channels": {},
        "midi_channel": 0,
    }
    rows = mc.mapping_to_rows(mapping)
    assert any("Right Stick (Polar)" in row[1] for row in rows)


def test_trigger_with_bow_mode():
    """Trigger with bow_mode shows bow CC in notes."""
    mapping = {
        "axes": {"4": 1},
        "l2_trigger": {
            "mode": "linear",
            "bow_mode": True,
            "bow_cc": 11,
        },
        "midi_channel": 0,
    }
    rows = mc.mapping_to_rows(mapping)
    assert "bow CC 11" in rows[1][5]


def test_trigger_with_crossfade():
    """Trigger with crossfade shows crossfade CC in notes."""
    mapping = {
        "axes": {"4": 1},
        "l2_trigger": {
            "mode": "linear",
            "crossfade_enabled": True,
            "crossfade_cc_b": 20,
        },
        "midi_channel": 0,
    }
    rows = mc.mapping_to_rows(mapping)
    assert "crossfade with CC 20" in rows[1][5]


def test_rows_to_csv_format():
    """rows_to_csv produces parseable CSV."""
    rows = [
        ["Control Type", "Control Name", "Output", "Channel", "Velocity / Value", "Notes"],
        ["Button", "0", "Note 60", "0", "100", ""],
        ["Axis", "Left Stick X", "CC 3", "0", "", ""],
    ]
    csv_str = mc.rows_to_csv(rows)

    # Re-parse and verify
    reader = csv.reader(io.StringIO(csv_str))
    parsed_rows = list(reader)
    assert parsed_rows == rows


def test_rows_to_csv_escapes_commas():
    """rows_to_csv properly escapes commas in fields."""
    rows = [
        ["Control Type", "Control Name", "Output", "Channel", "Velocity / Value", "Notes"],
        ["Button", "0", "Note 60", "0", "100", "repeat @ 8.0 Hz; gated by button 10"],
    ]
    csv_str = mc.rows_to_csv(rows)

    # Re-parse and verify the notes field is preserved
    reader = csv.reader(io.StringIO(csv_str))
    parsed_rows = list(reader)
    assert parsed_rows[1][5] == "repeat @ 8.0 Hz; gated by button 10"


def test_mapping_to_csv_header():
    """mapping_to_csv first line is the header."""
    mapping = {
        "buttons": {"0": 60},
        "midi_channel": 0,
    }
    csv_str = mc.mapping_to_csv(mapping)
    lines = csv_str.strip().split('\n')
    assert "Control Type" in lines[0]
    assert "Control Name" in lines[0]


def test_mapping_to_csv_with_data():
    """mapping_to_csv produces valid CSV with data rows."""
    mapping = {
        "buttons": {"0": 60, "1": 62},
        "axes": {"0": 3},
        "midi_channel": 0,
    }
    csv_str = mc.mapping_to_csv(mapping)

    reader = csv.DictReader(io.StringIO(csv_str))
    rows = list(reader)
    # Should have 3 data rows (2 buttons + 1 axis)
    assert len(rows) == 3
    assert rows[0]["Control Type"] == "Button"
    assert rows[1]["Control Type"] == "Button"
    assert rows[2]["Control Type"] == "Axis"


def test_mapping_to_csv_missing_keys():
    """mapping_to_csv handles missing nested keys gracefully."""
    # Minimal mapping — no buttons, axes, hats, etc.
    mapping = {"midi_channel": 0}
    csv_str = mc.mapping_to_csv(mapping)

    # Should just have header
    lines = csv_str.strip().split('\n')
    assert len(lines) == 1
    assert "Control Type" in lines[0]


def test_mapping_to_csv_partial_mapping():
    """mapping_to_csv tolerates partial/sparse mappings."""
    mapping = {
        "buttons": {"0": 60},
        # No axes, hats, sticks, etc.
        "midi_channel": 1,
    }
    csv_str = mc.mapping_to_csv(mapping)

    reader = csv.DictReader(io.StringIO(csv_str))
    rows = list(reader)
    assert len(rows) == 1
    assert rows[0]["Control Type"] == "Button"
    assert rows[0]["Channel"] == "1"


def test_comprehensive_mapping():
    """Comprehensive mapping with buttons, axes, triggers, hats, sticks."""
    mapping = {
        "buttons": {
            "0": 60,
            "1": 62,
            "5": 67,
        },
        "button_channels": {"0": 5},
        "button_configs": {
            "5": {
                "velocity": 120,
                "gate_button": 4,
                "repeat_enabled": True,
                "repeat_rate_hz": 10.0,
            }
        },
        "axes": {
            "0": 3,
            "1": 4,
            "4": 1,
            "5": 2,
        },
        "axis_channels": {"4": 8},
        "l2_trigger": {"mode": "latch", "latch_threshold": 0.5},
        "r2_trigger": {"mode": "linear"},
        "hats": {"up": 78, "down": 79},
        "hat_channels": {"up": 2},
        "left_stick": {
            "polar_mode": True,
            "polar_angle_cc": 7,
            "polar_mag_cc": 8,
        },
        "right_stick": {
            "chord_enabled": True,
            "chord_north": [60, 62],
            "chord_velocity": 100,
        },
        "midi_channel": 0,
    }
    rows = mc.mapping_to_rows(mapping)

    # Should have many rows
    assert len(rows) > 5

    # Verify we have the expected control types
    control_types = [row[0] for row in rows]
    assert "Button" in control_types
    assert "Axis" in control_types
    assert "Trigger" in control_types
    assert "D-Pad" in control_types
    assert "Stick" in control_types

    # Verify CSV is parseable
    csv_str = mc.rows_to_csv(rows)
    reader = csv.DictReader(io.StringIO(csv_str))
    csv_rows = list(reader)
    assert len(csv_rows) == len(rows) - 1  # -1 for header


def test_button_with_poly_aftertouch():
    """Button with poly_aftertouch in config appears in notes."""
    mapping = {
        "buttons": {"5": 60},
        "button_configs": {
            "5": {
                "velocity": 100,
                "poly_aftertouch": {
                    "enabled": True,
                    "pressure_source": "left_stick_mag",
                }
            }
        },
        "midi_channel": 0,
    }
    rows = mc.mapping_to_rows(mapping)
    assert "poly-AT from left_stick_mag" in rows[1][5]


def test_trigger_with_aftertouch():
    """Trigger with aftertouch in config appears in notes."""
    mapping = {
        "axes": {"4": 1},
        "l2_trigger": {
            "mode": "linear",
            "aftertouch": {"enabled": True, "threshold": 0.85},
        },
        "midi_channel": 0,
    }
    rows = mc.mapping_to_rows(mapping)
    assert "aftertouch enabled" in rows[1][5]


def test_stick_lfo_feature():
    """Stick with LFO enabled shows in notes."""
    mapping = {
        "axes": {"0": 3},
        "left_stick": {
            "lfo": {"enabled": True, "waveform": "sine"},
        },
        "axis_channels": {},
        "midi_channel": 0,
    }
    rows = mc.mapping_to_rows(mapping)
    # Should have axis row + stick lfo detail
    assert any("LFO" in row[5] for row in rows)
