"""Pretty-print and minify helpers for mapping JSON structures.

Provides deterministic key ordering tailored to mapping files: metadata first,
then control sections (buttons, axes, triggers, sticks, touchpad), then
advanced features and settings.

Pure stdlib (json only), no Qt dependencies.
"""
from __future__ import annotations

import json
from typing import Dict, List, Tuple


# Canonical key ordering for mapping files
# Metadata first, then control sections, then advanced features
KEY_ORDER: List[str] = [
    # Schema and metadata
    "schema_version",
    "description",
    "name",
    "channel",

    # Main control sections
    "buttons",
    "axes",
    "triggers",
    "left_stick",
    "right_stick",
    "touchpad",

    # Advanced layers and features
    "shift_layer",
    "ab_compare",
    "setlist",
    "macros",
    "macro_bindings",

    # Transport and clock
    "program_change",
    "battery_alert",
    "passthrough",
    "rtp_midi",
    "quantize",
    "midi_clock",
    "midi2",

    # LED and visual
    "lightbar_enabled",
    "lightbar_red",
    "lightbar_green",
    "lightbar_blue",
    "player_led_bitmask",

    # UI and connection
    "color_tag",
    "favourite",
    "theme",
    "port_name_override",
    "auto_reconnect_enabled",

    # Misc
    "update",
    "midi_learn",
]


def sort_mapping_keys(mapping_dict: dict) -> dict:
    """Return a new dict with keys in canonical KEY_ORDER.

    Keys in KEY_ORDER appear first in that order. Unknown keys are appended
    at the end, sorted alphabetically. Recursively sorts nested dicts that
    are not themselves in KEY_ORDER (i.e., dicts within control sections
    like buttons, axes, etc. are sorted by their own key order).

    Args:
        mapping_dict: Input mapping dictionary

    Returns:
        New dict with sorted keys (original unchanged)
    """
    result = {}

    # First, add keys in KEY_ORDER (if present in input)
    for key in KEY_ORDER:
        if key in mapping_dict:
            value = mapping_dict[key]
            # Recursively sort nested dicts (but not nested lists)
            if isinstance(value, dict):
                result[key] = sort_mapping_keys(value)
            else:
                result[key] = value

    # Then, add remaining keys alphabetically
    remaining_keys = sorted(set(mapping_dict.keys()) - set(KEY_ORDER))
    for key in remaining_keys:
        value = mapping_dict[key]
        if isinstance(value, dict):
            result[key] = sort_mapping_keys(value)
        else:
            result[key] = value

    return result


def pretty(mapping_dict: dict, indent: int = 2) -> str:
    """Return pretty-printed JSON with sorted keys.

    Args:
        mapping_dict: Input mapping dictionary
        indent: Indentation width (clamped 0..8, default 2)

    Returns:
        Pretty-printed JSON string with sorted keys
    """
    indent = max(0, min(indent, 8))  # Clamp 0..8
    sorted_dict = sort_mapping_keys(mapping_dict)
    return json.dumps(sorted_dict, indent=indent if indent > 0 else None)


def minify(mapping_dict: dict) -> str:
    """Return single-line JSON with no whitespace, keys in KEY_ORDER.

    Args:
        mapping_dict: Input mapping dictionary

    Returns:
        Minified JSON string (no newlines, no spaces after separators)
    """
    sorted_dict = sort_mapping_keys(mapping_dict)
    return json.dumps(sorted_dict, separators=(",", ":"))


def format_size(json_str: str) -> str:
    """Return human-readable byte count for JSON string.

    Uses kibibytes (1024) for calculations but displays as KB/MB for brevity.

    Args:
        json_str: JSON string to measure

    Returns:
        Human-readable size (e.g., "1.5 KB", "523 B", "3.5 MB")
    """
    byte_count = len(json_str.encode("utf-8"))

    if byte_count < 1024:
        return f"{byte_count} B"
    elif byte_count < 1024 * 1024:
        kb = byte_count / 1024.0
        # Format with 1 decimal place, removing trailing zero if .0
        formatted = f"{kb:.1f}".rstrip("0").rstrip(".")
        return f"{formatted} KB"
    else:
        mb = byte_count / (1024.0 * 1024)
        formatted = f"{mb:.1f}".rstrip("0").rstrip(".")
        return f"{formatted} MB"


def size_savings(pretty_str: str, mini_str: str) -> Tuple[int, float]:
    """Calculate compression savings from pretty to minified.

    Args:
        pretty_str: Pretty-printed JSON string
        mini_str: Minified JSON string

    Returns:
        Tuple of (bytes_saved, fraction_saved) where fraction = saved/pretty
    """
    pretty_bytes = len(pretty_str.encode("utf-8"))
    mini_bytes = len(mini_str.encode("utf-8"))

    bytes_saved = pretty_bytes - mini_bytes
    fraction_saved = bytes_saved / pretty_bytes if pretty_bytes > 0 else 0.0

    return (bytes_saved, fraction_saved)


def count_lines(json_str: str) -> int:
    """Count newline-separated lines in JSON string.

    Args:
        json_str: JSON string to count lines in

    Returns:
        Line count (count of newlines + 1 if non-empty)
    """
    if not json_str:
        return 0
    return json_str.count("\n") + (1 if json_str else 0)


def count_keys_at_depth(mapping_dict: dict, depth: int = 0) -> Dict[int, int]:
    """Count keys at each nesting depth.

    Recursively traverses the dict structure and counts how many keys appear
    at each depth level. Useful for "tree depth" analysis.

    Args:
        mapping_dict: Input mapping dictionary
        depth: Current depth (usually starts at 0)

    Returns:
        Dict mapping {depth_level: key_count} for all depths in the tree
    """
    result = {}

    # Count keys at current depth
    if depth not in result:
        result[depth] = 0
    result[depth] += len(mapping_dict)

    # Recurse into nested dicts
    for value in mapping_dict.values():
        if isinstance(value, dict):
            nested_counts = count_keys_at_depth(value, depth + 1)
            for d, count in nested_counts.items():
                result[d] = result.get(d, 0) + count

    return result
