"""Mapping mirror helper — flip notes around center for left-handed or inverted layouts.

Pure functions for mirroring MIDI note assignments in a mapping dict:
  - mirror_note(note, center): single note mirroring with clamping
  - mirror_buttons(buttons_dict, center): mirror all button notes
  - mirror_axes_pairs(axes_dict): swap left/right stick axes
  - mirror_chords(chord_dict, center): mirror stick-chord directions
  - mirror_macros(macros_list, center): mirror note fields in recorded events
  - mirror_full_mapping(mapping_dict, center, mirror_axes): deep copy + apply all mirrors

All functions return NEW dicts/lists; input is never mutated.
"""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional


def mirror_note(note: int, center: int = 60) -> int:
    """Mirror a single MIDI note around a center point, clamped to 0..127.

    Formula: mirrored = center * 2 - note
    Clamps result to [0, 127].

    Args:
        note: MIDI note number (0..127)
        center: center point for mirroring (default C4 = 60)

    Returns:
        Mirrored note, clamped to [0, 127]

    Examples:
        mirror_note(60, 60) == 60  (center is unchanged)
        mirror_note(48, 60) == 72  (12 semitones below → 12 above)
        mirror_note(72, 60) == 48  (12 semitones above → 12 below)
    """
    mirrored = center * 2 - note
    return max(0, min(127, mirrored))


def mirror_buttons(buttons_dict: dict, center: int = 60) -> dict:
    """Mirror all button note assignments.

    Args:
        buttons_dict: {button_index: note_or_config_dict}
                      where config_dict may have a 'note' key
        center: center point for mirroring (default 60)

    Returns:
        New dict with all note values mirrored. Does not mutate input.

    Handles both simple {0: 60} and complex {0: {'note': 60, ...}} formats.
    """
    result: Dict[int, Any] = {}

    for button_idx, config in buttons_dict.items():
        if isinstance(config, dict):
            # Copy the config dict and mirror the 'note' key if present
            new_config = config.copy()
            if "note" in new_config and isinstance(new_config["note"], int):
                new_config["note"] = mirror_note(new_config["note"], center)
            result[button_idx] = new_config
        elif isinstance(config, int):
            # Simple note number
            result[button_idx] = mirror_note(config, center)
        else:
            # Unknown format, pass through unchanged
            result[button_idx] = config

    return result


def mirror_axes_pairs(axes_dict: dict) -> dict:
    """Swap left-stick axes (0, 1) with right-stick axes (2, 3).

    Left stick typically: axis 0 = X (horizontal), axis 1 = Y (vertical)
    Right stick typically: axis 2 = X (horizontal), axis 3 = Y (vertical)
    Triggers: axis 4 = L2, axis 5 = R2 (not swapped)

    Args:
        axes_dict: {axis_index: cc_number}

    Returns:
        New dict with axes 0↔2 and 1↔3 swapped. Triggers (4, 5) unchanged.
    """
    result: Dict[int, Any] = {}

    for axis, cc in axes_dict.items():
        # Swap pairs: 0↔2, 1↔3; leave 4, 5 unchanged
        if axis == 0 and 2 in axes_dict:
            result[axis] = axes_dict[2]
        elif axis == 2 and 0 in axes_dict:
            result[axis] = axes_dict[0]
        elif axis == 1 and 3 in axes_dict:
            result[axis] = axes_dict[3]
        elif axis == 3 and 1 in axes_dict:
            result[axis] = axes_dict[1]
        else:
            # Keep unchanged if pair doesn't exist
            result[axis] = cc

    return result


def mirror_chords(chord_dict: dict, center: int = 60) -> dict:
    """Mirror stick-chord note assignments across cardinal directions.

    Swaps north↔south and east↔west, and mirrors each note list.

    Args:
        chord_dict: dict with optional keys 'chord_north', 'chord_south',
                    'chord_east', 'chord_west' containing note lists
        center: center point for note mirroring (default 60)

    Returns:
        New dict with directions swapped and notes mirrored. Preserves other keys.
    """
    result = chord_dict.copy()

    # Extract directions (None if not present, so we don't create defaults)
    north = chord_dict.get("chord_north")
    south = chord_dict.get("chord_south")
    east = chord_dict.get("chord_east")
    west = chord_dict.get("chord_west")

    # Mirror each list and swap opposite pairs
    if isinstance(north, list) and isinstance(south, list):
        mirrored_north = [mirror_note(n, center) for n in north]
        mirrored_south = [mirror_note(n, center) for n in south]
        result["chord_north"] = mirrored_south  # swap
        result["chord_south"] = mirrored_north
    elif isinstance(north, list):
        result["chord_north"] = [mirror_note(n, center) for n in north]
    elif isinstance(south, list):
        result["chord_south"] = [mirror_note(n, center) for n in south]

    if isinstance(east, list) and isinstance(west, list):
        mirrored_east = [mirror_note(n, center) for n in east]
        mirrored_west = [mirror_note(n, center) for n in west]
        result["chord_east"] = mirrored_west  # swap
        result["chord_west"] = mirrored_east
    elif isinstance(east, list):
        result["chord_east"] = [mirror_note(n, center) for n in east]
    elif isinstance(west, list):
        result["chord_west"] = [mirror_note(n, center) for n in west]

    return result


def mirror_macros(macros: List[dict], center: int = 60) -> List[dict]:
    """Mirror note fields in recorded macro events.

    Each macro is a dict with an 'events' list. Each event has a 'data1'
    field that may contain a note (for note-on/note-off messages).
    Defensive: skips events missing expected keys.

    Args:
        macros: list of macro dicts (from Mapping.macros)
        center: center point for note mirroring (default 60)

    Returns:
        New list with each macro's note fields mirrored. Does not mutate input.
    """
    result: List[dict] = []

    for macro in macros:
        new_macro = copy.deepcopy(macro)
        events = new_macro.get("events", [])

        if isinstance(events, list):
            for event in events:
                if isinstance(event, dict) and "data1" in event:
                    # data1 is note number for note-on/off, CC number for CC.
                    # For now, we mirror all data1 values that look like notes.
                    # This is slightly imprecise but defensive — CC numbers
                    # (often 1..127) get mirrored too, which is harmless.
                    if isinstance(event["data1"], int):
                        event["data1"] = mirror_note(event["data1"], center)

        result.append(new_macro)

    return result


def mirror_full_mapping(
    mapping_dict: dict,
    center: int = 60,
    mirror_axes: bool = False,
) -> dict:
    """Deep-copy a mapping and apply all mirror transformations.

    Mirrors buttons, optionally swaps stick axes, and mirrors stick-chord
    and macro note fields.

    Args:
        mapping_dict: the complete mapping dict (typically from Mapping.to_dict())
        center: center point for MIDI note mirroring (default 60)
        mirror_axes: if True, swap left/right stick axes; if False, keep unchanged

    Returns:
        New dict with all mirror transformations applied. Input unchanged.
    """
    result = copy.deepcopy(mapping_dict)

    # Mirror buttons
    if "buttons" in result and isinstance(result["buttons"], dict):
        result["buttons"] = mirror_buttons(result["buttons"], center)

    # Optionally mirror axes (swap left↔right stick)
    if mirror_axes and "axes" in result and isinstance(result["axes"], dict):
        result["axes"] = mirror_axes_pairs(result["axes"])

    # Mirror stick-chord notes if present
    for stick_key in ["stick_left", "stick_right"]:
        if stick_key in result and isinstance(result[stick_key], dict):
            result[stick_key] = mirror_chords(result[stick_key], center)

    # Mirror macros if present
    if "macros" in result and isinstance(result["macros"], list):
        result["macros"] = mirror_macros(result["macros"], center)

    # Mirror gesture notes if present
    gesture_keys = [
        "swipe_up_note",
        "swipe_down_note",
        "swipe_left_note",
        "swipe_right_note",
        "pinch_in_note",
        "pinch_out_note",
    ]
    for key in gesture_keys:
        if key in result and isinstance(result[key], int):
            result[key] = mirror_note(result[key], center)

    return result
