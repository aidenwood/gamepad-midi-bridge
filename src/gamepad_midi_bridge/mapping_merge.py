"""Pure dict-based helpers for merging and analyzing mapping dictionaries.

Provides tools to combine, inspect, and modify Mapping JSON/dict representations
without importing Qt, dataclasses, or the Mapping class itself. All functions are
non-mutating (return new dicts) and use only stdlib.
"""

from typing import Any, Dict, List, Tuple


def merge_dicts(
    base: dict,
    overlay: dict,
    strategy: str = "overlay"
) -> dict:
    """Recursively merge two dicts according to a merge strategy.

    Args:
        base: The base/left dict (baseline values).
        overlay: The overlay/right dict (new values to apply).
        strategy: One of "overlay", "prefer_base", "union", or unknown (treated as "overlay").

    Strategies:
        - "overlay": overlay wins on conflicts; nested dicts are deep-merged;
          lists from overlay replace base lists entirely.
        - "prefer_base": base wins on conflicts; only fills in keys absent in base;
          lists from base are kept unless missing, then overlay fills in.
        - "union": for lists, concat and deduplicate; for scalars, overlay wins.
        - Unknown: treat as "overlay".

    Returns:
        A new merged dict (non-mutating).
    """
    if strategy not in ("overlay", "prefer_base", "union"):
        strategy = "overlay"

    result: Dict[str, Any] = {}

    # Start with base
    for key, value in base.items():
        result[key] = value

    if strategy == "prefer_base":
        # Only fill in keys missing from base
        for key, value in overlay.items():
            if key not in result:
                result[key] = value
        return result

    # For "overlay" and "union", iterate overlay
    for key, overlay_val in overlay.items():
        if key not in result:
            # Key only in overlay
            result[key] = overlay_val
        else:
            # Key in both
            base_val = result[key]

            if isinstance(base_val, dict) and isinstance(overlay_val, dict):
                # Recurse into nested dicts
                result[key] = merge_dicts(base_val, overlay_val, strategy)
            elif isinstance(base_val, list) and isinstance(overlay_val, list):
                if strategy == "union":
                    # Concat and deduplicate (preserving order)
                    seen = set()
                    merged_list: List[Any] = []
                    for item in base_val:
                        # Use repr for hashability (works for scalars, dicts become str repr)
                        item_key = repr(item)
                        if item_key not in seen:
                            seen.add(item_key)
                            merged_list.append(item)
                    for item in overlay_val:
                        item_key = repr(item)
                        if item_key not in seen:
                            seen.add(item_key)
                            merged_list.append(item)
                    result[key] = merged_list
                else:
                    # "overlay": list from overlay replaces entirely
                    result[key] = overlay_val
            else:
                # Scalars: overlay wins (in both "overlay" and "union")
                result[key] = overlay_val

    return result


def find_conflicts(base: dict, overlay: dict) -> List[Tuple[str, Any, Any]]:
    """Find all leaf-key conflicts between two dicts.

    Returns a list of (dotted_path, base_value, overlay_value) tuples for keys
    that exist in both dicts but have different values at the leaf level.

    Args:
        base: The base dict.
        overlay: The overlay dict.

    Returns:
        List of (path, base_val, overlay_val) tuples.
    """
    conflicts: List[Tuple[str, Any, Any]] = []

    def recurse(base_obj: Any, overlay_obj: Any, path: str) -> None:
        if isinstance(base_obj, dict) and isinstance(overlay_obj, dict):
            for key in base_obj:
                if key in overlay_obj:
                    base_val = base_obj[key]
                    overlay_val = overlay_obj[key]
                    new_path = f"{path}.{key}" if path else key
                    recurse(base_val, overlay_val, new_path)
        else:
            # Leaf comparison (including lists, which we compare as whole objects)
            if base_obj != overlay_obj:
                conflicts.append((path, base_obj, overlay_obj))

    recurse(base, overlay, "")
    return conflicts


def pick_keys(source: dict, keys: List[str]) -> dict:
    """Extract a subset of a dict containing only the specified top-level keys.

    Args:
        source: The source dict.
        keys: List of top-level keys to include.

    Returns:
        A new dict with only the specified keys (missing keys are ignored).
    """
    result = {}
    for key in keys:
        if key in source:
            result[key] = source[key]
    return result


def omit_keys(source: dict, keys: List[str]) -> dict:
    """Create a new dict from source with specified top-level keys removed.

    Args:
        source: The source dict.
        keys: List of top-level keys to exclude.

    Returns:
        A new dict with the specified keys removed.
    """
    omit_set = set(keys)
    result = {}
    for key, value in source.items():
        if key not in omit_set:
            result[key] = value
    return result


def merge_mapping_subsection(
    base_mapping_dict: dict,
    section: str,
    overlay_section: dict,
    strategy: str = "overlay"
) -> dict:
    """Merge only one named subsection of a mapping dict, leaving others intact.

    Useful for updating just "buttons", "axes", "l2_trigger", etc. without
    touching the rest of the mapping.

    Args:
        base_mapping_dict: The full base mapping dict.
        section: The subsection key (e.g., "buttons", "axes", "l2_trigger").
        overlay_section: The new subsection dict to merge in.
        strategy: Merge strategy ("overlay", "prefer_base", "union").

    Returns:
        A new mapping dict with the subsection updated.
    """
    result = dict(base_mapping_dict)  # Shallow copy of top level

    if section in result:
        # Section exists in base; merge
        result[section] = merge_dicts(result[section], overlay_section, strategy)
    else:
        # Section doesn't exist in base; just add it
        result[section] = overlay_section

    return result
