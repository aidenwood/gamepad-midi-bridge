"""Export a Mapping as compact plain text for pasting into chats/forums.

Pure stdlib — no Qt, no third-party dependencies. Different from mapping_docs
(full Markdown) and mapping_csv (spreadsheet) — this is short, single-message-friendly
text suitable for Discord, Reddit, Slack, etc.

Usage::

    from gamepad_midi_bridge.mapping_export_text import render_mapping, render_compact

    text = render_mapping(mapping_dict)
    summary = render_compact(mapping_dict)
    print(text)
"""
from __future__ import annotations

from typing import List, Dict, Any


def _note_name(n: int) -> str:
    """Return MIDI note name + octave, e.g. C4 for note 60.

    Uses 12-tone scientific pitch notation (C4 = middle C = MIDI 60).
    """
    names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    return f"{names[n % 12]}{(n // 12) - 1}"


def count_mapped(mapping_dict: dict, section: str) -> int:
    """Count non-default entries in a section.

    Args:
        mapping_dict: A dict representing a Mapping (from Mapping.to_dict()).
        section: One of "buttons", "axes", "triggers", "macros", "setlist".

    Returns:
        Number of non-default entries. For buttons/axes, excludes note/cc == 0.
    """
    if section == "buttons":
        buttons = mapping_dict.get("buttons", {})
        return sum(1 for n in buttons.values() if int(n) != 0)
    elif section == "axes":
        axes = mapping_dict.get("axes", {})
        return sum(1 for cc in axes.values() if int(cc) != 0)
    elif section == "triggers":
        # Triggers are l2_trigger and r2_trigger configs; count as mapped
        # if they have a non-default mode or gate_button set
        l2 = mapping_dict.get("l2_trigger", {})
        r2 = mapping_dict.get("r2_trigger", {})
        count = 0
        if isinstance(l2, dict) and (l2.get("mode") not in (None, "linear") or l2.get("gate_button")):
            count += 1
        if isinstance(r2, dict) and (r2.get("mode") not in (None, "linear") or r2.get("gate_button")):
            count += 1
        return count
    elif section == "macros":
        macros = mapping_dict.get("macros", {})
        return len([m for m in macros.values() if m])
    elif section == "setlist":
        setlist = mapping_dict.get("setlist", {})
        if isinstance(setlist, dict):
            presets = setlist.get("presets", [])
            return len(presets) if presets else 0
        return 0
    return 0


def format_note_range(notes: List[int]) -> str:
    """Format a list of MIDI notes as compact range or comma-separated list.

    If 4 or more notes, returns range like "C4–G4".
    Otherwise returns comma-separated like "C4, E4, G4".

    Args:
        notes: List of MIDI note numbers (0–127).

    Returns:
        Compact string representation.
    """
    if not notes:
        return ""

    sorted_notes = sorted(set(notes))

    if len(sorted_notes) <= 3:
        # Comma-separated for short lists
        return ", ".join(_note_name(n) for n in sorted_notes)
    else:
        # Range format for long lists
        min_note = sorted_notes[0]
        max_note = sorted_notes[-1]
        return f"{_note_name(min_note)}–{_note_name(max_note)}"


def render_mapping(mapping_dict: dict, max_lines: int = 30) -> str:
    """Render a mapping dict as readable multi-line plain text.

    Output is designed for pasting into Discord, Reddit, Slack, etc.
    Lines include:
      - Preset name (if present)
      - Global MIDI channel
      - Buttons summary (count + note range)
      - Axes summary (count + CC numbers)
      - Triggers summary (mode + crossfade info)
      - Sticks summary (if chord mode or flick enabled)
      - Macros count
      - Setlist count

    Args:
        mapping_dict: A dict representing a Mapping (from Mapping.to_dict()).
        max_lines: Maximum lines to output. Truncates with "..." if exceeded.

    Returns:
        Multi-line string suitable for chat/forum pasting.
    """
    lines = []

    # Preset name
    name = mapping_dict.get("name")
    if name:
        lines.append(f"Preset: {name}")

    # Global MIDI channel (1-based for display)
    channel = mapping_dict.get("midi_channel", 0)
    lines.append(f"Channel: {channel + 1}")

    # Buttons
    buttons = mapping_dict.get("buttons", {})
    button_count = count_mapped(mapping_dict, "buttons")
    if button_count > 0:
        button_notes = [int(n) for n in buttons.values() if int(n) != 0]
        if button_count <= 8:
            note_str = format_note_range(button_notes)
            lines.append(f"Buttons: {button_count} mapped ({note_str})")
        else:
            note_str = format_note_range(button_notes)
            lines.append(f"Buttons: {button_count} mapped ({note_str})")

    # Axes
    axes = mapping_dict.get("axes", {})
    axis_count = count_mapped(mapping_dict, "axes")
    if axis_count > 0:
        axis_ccs = sorted([int(cc) for cc in axes.values() if int(cc) != 0])
        cc_str = ", ".join(str(cc) for cc in axis_ccs)
        lines.append(f"Axes: {axis_count} mapped (CC {cc_str})")

    # Triggers
    l2_cfg = mapping_dict.get("l2_trigger", {})
    r2_cfg = mapping_dict.get("r2_trigger", {})

    trigger_modes = []
    if isinstance(l2_cfg, dict) and l2_cfg.get("mode") and l2_cfg.get("mode") != "linear":
        trigger_modes.append(f"L2 {l2_cfg.get('mode')}")
    if isinstance(r2_cfg, dict) and r2_cfg.get("mode") and r2_cfg.get("mode") != "linear":
        trigger_modes.append(f"R2 {r2_cfg.get('mode')}")

    # Check for crossfade
    crossfade_enabled = False
    if isinstance(l2_cfg, dict) and l2_cfg.get("crossfade_enabled"):
        crossfade_enabled = True
        crossfade_cc_b = l2_cfg.get("crossfade_cc_b", 0)
        l2_cc = axes.get("4", 0)
        if trigger_modes and trigger_modes[0].startswith("L2"):
            trigger_modes[0] += f" crossfade with CC {crossfade_cc_b}"

    if trigger_modes:
        lines.append(f"Triggers: {', '.join(trigger_modes)}")

    # Sticks (chord mode / flick)
    left_stick = mapping_dict.get("left_stick", {})
    right_stick = mapping_dict.get("right_stick", {})
    stick_modes = []

    if isinstance(left_stick, dict):
        if left_stick.get("chord_mode_enabled"):
            stick_modes.append("left_stick chord")
        if left_stick.get("flick_enabled"):
            stick_modes.append("left_stick flick")

    if isinstance(right_stick, dict):
        if right_stick.get("chord_mode_enabled"):
            stick_modes.append("right_stick chord")
        if right_stick.get("flick_enabled"):
            stick_modes.append("right_stick flick")

    if stick_modes:
        lines.append(f"Sticks: {', '.join(stick_modes)}")

    # Macros
    macro_count = count_mapped(mapping_dict, "macros")
    if macro_count > 0:
        lines.append(f"Macros: {macro_count} saved")

    # Setlist
    setlist_count = count_mapped(mapping_dict, "setlist")
    if setlist_count > 0:
        lines.append(f"Setlist: {setlist_count} presets")

    # Truncate to max_lines if needed
    if len(lines) > max_lines:
        lines = lines[:max_lines - 1]
        lines.append("...")

    return "\n".join(lines)


def render_compact(mapping_dict: dict) -> str:
    """Render a mapping dict as a single-line summary.

    Example output:
        "C4-G4 on 3 buttons | CC 1,11,74 on axes | L2 latch | 2 macros"

    Args:
        mapping_dict: A dict representing a Mapping (from Mapping.to_dict()).

    Returns:
        Single-line string summary suitable for one-liner chat replies.
    """
    parts = []

    # Buttons
    buttons = mapping_dict.get("buttons", {})
    button_count = count_mapped(mapping_dict, "buttons")
    if button_count > 0:
        button_notes = [int(n) for n in buttons.values() if int(n) != 0]
        note_range = format_note_range(button_notes)
        parts.append(f"{note_range} on {button_count} buttons")

    # Axes
    axes = mapping_dict.get("axes", {})
    axis_count = count_mapped(mapping_dict, "axes")
    if axis_count > 0:
        axis_ccs = sorted([int(cc) for cc in axes.values() if int(cc) != 0])
        cc_str = ",".join(str(cc) for cc in axis_ccs)
        parts.append(f"CC {cc_str} on axes")

    # Triggers
    l2_cfg = mapping_dict.get("l2_trigger", {})
    r2_cfg = mapping_dict.get("r2_trigger", {})

    trigger_info = []
    if isinstance(l2_cfg, dict) and l2_cfg.get("mode") and l2_cfg.get("mode") != "linear":
        trigger_info.append(f"L2 {l2_cfg.get('mode')}")
    if isinstance(r2_cfg, dict) and r2_cfg.get("mode") and r2_cfg.get("mode") != "linear":
        trigger_info.append(f"R2 {r2_cfg.get('mode')}")

    if trigger_info:
        parts.append(" | ".join(trigger_info))

    # Macros
    macro_count = count_mapped(mapping_dict, "macros")
    if macro_count > 0:
        parts.append(f"{macro_count} macros")

    # Setlist
    setlist_count = count_mapped(mapping_dict, "setlist")
    if setlist_count > 0:
        parts.append(f"{setlist_count} presets")

    if not parts:
        return "Empty preset"

    return " | ".join(parts)
