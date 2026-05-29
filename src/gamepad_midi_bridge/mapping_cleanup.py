"""Pure dict-based helpers for cleaning up mapping dictionaries.

Detects entries at default values and removes them to slim down serialized mappings.
Provides tools to identify and remove defaults, empty sections, and estimate size savings.
Uses only stdlib (json, copy) — no Qt or external dependencies.
"""

import json
from copy import deepcopy
from typing import Any, Dict, List, Tuple


# Default button configuration
DEFAULT_BUTTON: Dict[str, Any] = {
    "note": 0,
    "channel": 1,
    "velocity": 100,
}

# Default axis configuration
DEFAULT_AXIS: Dict[str, Any] = {
    "cc": 0,
    "channel": 1,
}


def is_default_button(button_dict: dict) -> bool:
    """Check if a button dict is at default values.

    A button is considered default if:
    - Every key in DEFAULT_BUTTON matches the default value
    - There are no extra meaningful keys beyond DEFAULT_BUTTON

    Args:
        button_dict: The button dict to check.

    Returns:
        True if the button is purely at defaults, False otherwise.
    """
    # Check that all DEFAULT_BUTTON keys match
    for key, default_val in DEFAULT_BUTTON.items():
        if button_dict.get(key) != default_val:
            return False

    # Check that there are no extra keys beyond DEFAULT_BUTTON
    # (and if there are, they should be empty/falsy)
    for key, val in button_dict.items():
        if key not in DEFAULT_BUTTON and val:
            # Extra key with meaningful value
            return False

    return True


def is_default_axis(axis_dict: dict) -> bool:
    """Check if an axis dict is at default values.

    An axis is considered default if:
    - Every key in DEFAULT_AXIS matches the default value
    - There are no extra meaningful keys beyond DEFAULT_AXIS

    Args:
        axis_dict: The axis dict to check.

    Returns:
        True if the axis is purely at defaults, False otherwise.
    """
    # Check that all DEFAULT_AXIS keys match
    for key, default_val in DEFAULT_AXIS.items():
        if axis_dict.get(key) != default_val:
            return False

    # Check that there are no extra keys beyond DEFAULT_AXIS
    for key, val in axis_dict.items():
        if key not in DEFAULT_AXIS and val:
            # Extra key with meaningful value
            return False

    return True


def remove_default_buttons(mapping_dict: dict) -> Tuple[dict, int]:
    """Remove button entries that are at default values.

    Filters out buttons whose configuration matches DEFAULT_BUTTON exactly.
    Non-mutating — returns a new mapping dict.

    Args:
        mapping_dict: The full mapping dict.

    Returns:
        Tuple of (new_mapping, count_removed).
    """
    result = deepcopy(mapping_dict)

    if "buttons" not in result or not result["buttons"]:
        return result, 0

    buttons = result["buttons"]
    if not isinstance(buttons, dict):
        return result, 0

    removed_count = 0
    new_buttons = {}

    for key, button_dict in buttons.items():
        if isinstance(button_dict, dict) and is_default_button(button_dict):
            removed_count += 1
        else:
            new_buttons[key] = button_dict

    if removed_count > 0:
        result["buttons"] = new_buttons
    else:
        result["buttons"] = buttons

    return result, removed_count


def remove_default_axes(mapping_dict: dict) -> Tuple[dict, int]:
    """Remove axis entries that are at default values.

    Filters out axes whose configuration matches DEFAULT_AXIS exactly.
    Non-mutating — returns a new mapping dict.

    Args:
        mapping_dict: The full mapping dict.

    Returns:
        Tuple of (new_mapping, count_removed).
    """
    result = deepcopy(mapping_dict)

    if "axes" not in result or not result["axes"]:
        return result, 0

    axes = result["axes"]
    if not isinstance(axes, dict):
        return result, 0

    removed_count = 0
    new_axes = {}

    for key, axis_dict in axes.items():
        if isinstance(axis_dict, dict) and is_default_axis(axis_dict):
            removed_count += 1
        else:
            new_axes[key] = axis_dict

    if removed_count > 0:
        result["axes"] = new_axes
    else:
        result["axes"] = axes

    return result, removed_count


def remove_empty_sections(mapping_dict: dict) -> Tuple[dict, List[str]]:
    """Remove top-level sections that are empty or falsy.

    Removes keys whose value is an empty dict, empty list, None, or 0.
    Non-mutating — returns a new mapping dict.

    Args:
        mapping_dict: The mapping dict to clean.

    Returns:
        Tuple of (new_mapping, list_of_removed_section_names).
    """
    result = {}
    removed_sections = []

    for key, val in mapping_dict.items():
        # Keep section if it has content
        if val is not None and val != 0 and val != {} and val != []:
            result[key] = val
        else:
            removed_sections.append(key)

    return result, removed_sections


def cleanup(
    mapping_dict: dict,
    remove_defaults: bool = True,
    remove_empty: bool = True,
) -> Tuple[dict, Dict[str, int]]:
    """Run full cleanup pipeline on a mapping dict.

    Optionally removes default entries and empty sections.
    Non-mutating — returns a new mapping dict.

    Args:
        mapping_dict: The mapping dict to clean.
        remove_defaults: Whether to remove entries at default values. Defaults to True.
        remove_empty: Whether to remove empty top-level sections. Defaults to True.

    Returns:
        Tuple of (cleaned_dict, stats_dict) where stats_dict contains:
        - "buttons_removed": count of default buttons removed
        - "axes_removed": count of default axes removed
        - "sections_removed": count of empty sections removed
    """
    result = deepcopy(mapping_dict)
    stats: Dict[str, int] = {
        "buttons_removed": 0,
        "axes_removed": 0,
        "sections_removed": 0,
    }

    # Step 1: Remove defaults if requested
    if remove_defaults:
        result, buttons_removed = remove_default_buttons(result)
        stats["buttons_removed"] = buttons_removed

        result, axes_removed = remove_default_axes(result)
        stats["axes_removed"] = axes_removed

    # Step 2: Remove empty sections if requested
    if remove_empty:
        result, removed_sections = remove_empty_sections(result)
        stats["sections_removed"] = len(removed_sections)

    return result, stats


def size_savings_estimate(mapping_dict: dict) -> int:
    """Estimate bytes saved by running full cleanup on a mapping.

    Computes the difference in JSON size (minified) between the original
    and cleaned versions.

    Args:
        mapping_dict: The mapping dict to estimate savings for.

    Returns:
        Estimated bytes saved (can be negative if cleanup increases size).
    """
    # Original size (minified JSON)
    original_json = json.dumps(mapping_dict, separators=(",", ":"), sort_keys=True)
    original_size = len(original_json.encode("utf-8"))

    # Cleaned size
    cleaned_dict, _ = cleanup(mapping_dict)
    cleaned_json = json.dumps(cleaned_dict, separators=(",", ":"), sort_keys=True)
    cleaned_size = len(cleaned_json.encode("utf-8"))

    # Savings (positive means bytes removed)
    return original_size - cleaned_size
