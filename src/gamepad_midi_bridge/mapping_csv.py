"""CSV export helper for mappings.

Pure stdlib (csv module) utilities to export a mapping dict as a flat CSV
suitable for Excel or sharing with non-technical collaborators.
"""
from __future__ import annotations

import csv
import io
from typing import List


def mapping_to_rows(mapping_dict: dict) -> List[List[str]]:
    """Convert a Mapping.to_dict() result to a list of CSV rows.

    First row is the header. Subsequent rows represent each control.
    Columns: ["Control Type", "Control Name", "Output", "Channel", "Velocity / Value", "Notes"]

    Walks mapping_dict["buttons"], ["axes"], ["triggers"], ["left_stick"], ["right_stick"].
    Skips unmapped entries (note==0 and cc==0).

    Args:
        mapping_dict: A dict returned by Mapping.to_dict().

    Returns:
        List of rows, where each row is a list of strings (including header).
    """
    rows = []

    # Header row
    header = ["Control Type", "Control Name", "Output", "Channel", "Velocity / Value", "Notes"]
    rows.append(header)

    # Helper to resolve channel
    def get_channel_label(channel_override: int | None, global_channel: int) -> str:
        if channel_override is None or channel_override < 0:
            return str(global_channel)
        return str(channel_override)

    global_channel = mapping_dict.get("midi_channel", 0)

    # --- BUTTONS ---
    buttons = mapping_dict.get("buttons", {})
    button_channels = mapping_dict.get("button_channels", {})
    button_configs = mapping_dict.get("button_configs", {})

    # Normalize button_channels to int keys (from_dict uses int keys)
    button_channels_int = {}
    for k, v in button_channels.items():
        try:
            button_channels_int[int(k)] = int(v)
        except (ValueError, TypeError):
            pass
    button_channels = button_channels_int

    # Normalize button_configs keys to int
    button_configs_int = {}
    for k, v in button_configs.items():
        try:
            button_configs_int[int(k)] = v
        except (ValueError, TypeError):
            pass
    button_configs = button_configs_int

    for btn_idx_str, note in buttons.items():
        try:
            btn_idx = int(btn_idx_str)
            note = int(note)
        except (ValueError, TypeError):
            continue

        # Skip unmapped buttons
        if note == 0:
            continue

        # Get channel and velocity from button config if present
        channel_override = button_channels.get(btn_idx)
        channel_label = get_channel_label(channel_override, global_channel)

        config = button_configs.get(btn_idx, {})
        velocity = config.get("velocity", 100)

        # Build notes field
        notes_parts = []
        if config and config.get("repeat_enabled"):
            notes_parts.append(f"repeat @ {config.get('repeat_rate_hz', 8.0)} Hz")
        if config and config.get("gate_button") is not None:
            notes_parts.append(f"gated by button {config.get('gate_button')}")
        if config and config.get("poly_aftertouch", {}).get("enabled"):
            notes_parts.append(f"poly-AT from {config['poly_aftertouch'].get('pressure_source', 'unknown')}")

        notes_str = "; ".join(notes_parts) if notes_parts else ""

        row = [
            "Button",
            str(btn_idx),
            f"Note {note}",
            channel_label,
            str(velocity),
            notes_str,
        ]
        rows.append(row)

    # --- AXES (sticks and triggers) ---
    axes = mapping_dict.get("axes", {})
    axis_channels = mapping_dict.get("axis_channels", {})

    # Normalize axis_channels to int keys
    axis_channels_int = {}
    for k, v in axis_channels.items():
        try:
            axis_channels_int[int(k)] = int(v)
        except (ValueError, TypeError):
            pass
    axis_channels = axis_channels_int

    l2_trigger = mapping_dict.get("l2_trigger", {})
    r2_trigger = mapping_dict.get("r2_trigger", {})

    for axis_idx_str, cc in axes.items():
        try:
            axis_idx = int(axis_idx_str)
            cc = int(cc)
        except (ValueError, TypeError):
            continue

        # Skip unmapped axes
        if cc == 0:
            continue

        channel_override = axis_channels.get(axis_idx)
        channel_label = get_channel_label(channel_override, global_channel)

        # Determine control type and notes
        if axis_idx < 4:
            # Stick axis (0-3: left X/Y, right X/Y)
            stick_name = (
                "Left Stick X" if axis_idx == 0
                else "Left Stick Y" if axis_idx == 1
                else "Right Stick X" if axis_idx == 2
                else "Right Stick Y"
            )
            control_type = "Axis"
            control_name = stick_name

            # Check for stick features
            stick_key = "left_stick" if axis_idx < 2 else "right_stick"
            stick_config = mapping_dict.get(stick_key, {})

            notes_parts = []
            if stick_config.get("polar_mode"):
                notes_parts.append("polar mode")
            if stick_config.get("chord_enabled"):
                notes_parts.append("chord enabled")
            if stick_config.get("lfo", {}).get("enabled"):
                notes_parts.append(f"LFO {stick_config['lfo'].get('waveform', 'sine')}")

            notes_str = "; ".join(notes_parts) if notes_parts else ""
        elif axis_idx in (4, 5):
            # Trigger axis (4=L2, 5=R2)
            control_type = "Trigger"
            control_name = "L2" if axis_idx == 4 else "R2"

            # Get trigger config
            trigger_cfg = l2_trigger if axis_idx == 4 else r2_trigger
            trigger_cfg = trigger_cfg if isinstance(trigger_cfg, dict) else {}

            mode = trigger_cfg.get("mode", "linear")
            notes_parts = [mode]

            if trigger_cfg.get("bow_mode"):
                notes_parts.append(f"bow CC {trigger_cfg.get('bow_cc', 11)}")
            if trigger_cfg.get("crossfade_enabled"):
                notes_parts.append(f"crossfade with CC {trigger_cfg.get('crossfade_cc_b', 0)}")
            if trigger_cfg.get("aftertouch", {}).get("enabled"):
                notes_parts.append("aftertouch enabled")

            notes_str = "; ".join(notes_parts)
        else:
            # Unknown axis type
            control_type = "Axis"
            control_name = f"Axis {axis_idx}"
            notes_str = ""

        row = [
            control_type,
            control_name,
            f"CC {cc}",
            channel_label,
            "",  # No velocity/value range for axes by default
            notes_str,
        ]
        rows.append(row)

    # --- HATS ---
    hats = mapping_dict.get("hats", {})
    hat_channels = mapping_dict.get("hat_channels", {})

    # Normalize hat_channels to string keys (hat indices are strings like "up", "down")
    hat_channels_str = {}
    for k, v in hat_channels.items():
        try:
            hat_channels_str[str(k)] = int(v)
        except (ValueError, TypeError):
            pass
    hat_channels = hat_channels_str

    for hat_dir, note in hats.items():
        try:
            note = int(note)
        except (ValueError, TypeError):
            continue

        # Skip unmapped hats
        if note == 0:
            continue

        channel_override = hat_channels.get(hat_dir)
        channel_label = get_channel_label(channel_override, global_channel)

        row = [
            "D-Pad",
            hat_dir.capitalize(),
            f"Note {note}",
            channel_label,
            "100",
            "",
        ]
        rows.append(row)

    # --- LEFT STICK (if polar or chord features) ---
    left_stick = mapping_dict.get("left_stick", {})
    if left_stick.get("polar_mode"):
        angle_cc = left_stick.get("polar_angle_cc", 7)
        mag_cc = left_stick.get("polar_mag_cc", 8)
        channel_override = axis_channels.get(0)  # axis 0 = left stick X
        channel_label = get_channel_label(channel_override, global_channel)

        row = [
            "Stick",
            "Left Stick (Polar)",
            f"Angle CC {angle_cc}, Mag CC {mag_cc}",
            channel_label,
            "",
            "polar mode",
        ]
        rows.append(row)

    if left_stick.get("chord_enabled"):
        chord_parts = []
        if left_stick.get("chord_north"):
            chord_parts.append(f"N:{','.join(str(n) for n in left_stick['chord_north'])}")
        if left_stick.get("chord_east"):
            chord_parts.append(f"E:{','.join(str(n) for n in left_stick['chord_east'])}")
        if left_stick.get("chord_south"):
            chord_parts.append(f"S:{','.join(str(n) for n in left_stick['chord_south'])}")
        if left_stick.get("chord_west"):
            chord_parts.append(f"W:{','.join(str(n) for n in left_stick['chord_west'])}")

        if chord_parts:
            notes_str = "; ".join(chord_parts)
            row = [
                "Stick",
                "Left Stick (Chord)",
                "Multiple Notes",
                str(left_stick.get("chord_channel", global_channel)),
                str(left_stick.get("chord_velocity", 100)),
                notes_str,
            ]
            rows.append(row)

    # --- RIGHT STICK (if polar or chord features) ---
    right_stick = mapping_dict.get("right_stick", {})
    if right_stick.get("polar_mode"):
        angle_cc = right_stick.get("polar_angle_cc", 7)
        mag_cc = right_stick.get("polar_mag_cc", 8)
        channel_override = axis_channels.get(2)  # axis 2 = right stick X
        channel_label = get_channel_label(channel_override, global_channel)

        row = [
            "Stick",
            "Right Stick (Polar)",
            f"Angle CC {angle_cc}, Mag CC {mag_cc}",
            channel_label,
            "",
            "polar mode",
        ]
        rows.append(row)

    if right_stick.get("chord_enabled"):
        chord_parts = []
        if right_stick.get("chord_north"):
            chord_parts.append(f"N:{','.join(str(n) for n in right_stick['chord_north'])}")
        if right_stick.get("chord_east"):
            chord_parts.append(f"E:{','.join(str(n) for n in right_stick['chord_east'])}")
        if right_stick.get("chord_south"):
            chord_parts.append(f"S:{','.join(str(n) for n in right_stick['chord_south'])}")
        if right_stick.get("chord_west"):
            chord_parts.append(f"W:{','.join(str(n) for n in right_stick['chord_west'])}")

        if chord_parts:
            notes_str = "; ".join(chord_parts)
            row = [
                "Stick",
                "Right Stick (Chord)",
                "Multiple Notes",
                str(right_stick.get("chord_channel", global_channel)),
                str(right_stick.get("chord_velocity", 100)),
                notes_str,
            ]
            rows.append(row)

    return rows


def rows_to_csv(rows: List[List[str]]) -> str:
    """Write rows to a CSV string using csv.writer.

    Args:
        rows: List of rows, where each row is a list of strings.

    Returns:
        CSV-formatted string.
    """
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerows(rows)
    return output.getvalue()


def mapping_to_csv(mapping_dict: dict) -> str:
    """Convenience wrapper: Mapping.to_dict() → CSV string.

    Args:
        mapping_dict: A dict returned by Mapping.to_dict().

    Returns:
        CSV-formatted string.
    """
    rows = mapping_to_rows(mapping_dict)
    return rows_to_csv(rows)
