"""Regex-based mapping search — find values and keys matching a pattern.

Pure stdlib only. Provides utilities to search through a mapping dict for:
  - All values matching a regex pattern (across all leaves)
  - All keys matching a regex pattern (leaf key names only)
  - Values of a specific type matching a pattern (e.g., only strings)
  - Replacement of matching string values non-mutating

Useful for marketplace audits, user search, and bulk renaming operations.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from typing import Any, List, Optional, Tuple

from gamepad_midi_bridge.mapping_search import walk_paths


@dataclass
class RegexMatch:
    """Single match for a regex search within a mapping dict.

    Attributes:
      - path: dotted path to the matched value (e.g. "buttons.5", "description")
      - value: the actual value at that path
      - matched_text: the matched substring from the value's string representation
    """
    path: str
    value: Any
    matched_text: str

    def to_dict(self) -> dict:
        """Serialize to dict."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> RegexMatch:
        """Deserialize from dict."""
        return cls(**data)


def compile_safe(pattern: str) -> Optional[re.Pattern]:
    """Compile a regex pattern safely, returning None on error.

    Args:
      pattern: regex pattern string

    Returns:
      compiled Pattern object or None if pattern is invalid
    """
    try:
        return re.compile(pattern)
    except re.error:
        return None


def search(
    mapping_dict: dict,
    pattern: str,
    ignore_case: bool = True,
) -> List[RegexMatch]:
    """Find all values in the mapping matching a regex pattern.

    Walks all leaves (non-dict, non-list nodes) and tests their string
    representation against the regex. Returns matches with the matched text.

    Args:
      mapping_dict: the mapping dict (typically a Mapping.to_dict() result)
      pattern: regex pattern string
      ignore_case: if True, compile pattern with re.IGNORECASE flag

    Returns:
      list of RegexMatch objects with path, value, and matched_text

    Raises:
      re.error: if pattern is invalid
    """
    if not isinstance(mapping_dict, dict):
        return []

    flags = re.IGNORECASE if ignore_case else 0
    try:
        regex = re.compile(pattern, flags)
    except re.error:
        raise

    matches: List[RegexMatch] = []

    for path, value in walk_paths(mapping_dict):
        value_str = str(value)
        match_obj = regex.search(value_str)
        if match_obj:
            matches.append(RegexMatch(
                path=path,
                value=value,
                matched_text=match_obj.group(0)
            ))

    return matches


def search_keys(
    mapping_dict: dict,
    pattern: str,
    ignore_case: bool = True,
) -> List[str]:
    """Find all dotted paths whose leaf KEY name matches a regex pattern.

    Only tests the final key component (after the last . or [) against the pattern.

    Args:
      mapping_dict: the mapping dict
      pattern: regex pattern string
      ignore_case: if True, compile pattern with re.IGNORECASE flag

    Returns:
      list of dotted paths (strings) where the final key matches

    Raises:
      re.error: if pattern is invalid
    """
    if not isinstance(mapping_dict, dict):
        return []

    flags = re.IGNORECASE if ignore_case else 0
    try:
        regex = re.compile(pattern, flags)
    except re.error:
        raise

    matching_paths: List[str] = []

    for path, _ in walk_paths(mapping_dict):
        # Extract the final key component (after the last . or [)
        final_key = path.split(".")[-1].split("[")[0]
        if regex.search(final_key):
            matching_paths.append(path)

    return matching_paths


def search_values_only(
    mapping_dict: dict,
    pattern: str,
    value_type: Optional[type] = None,
    ignore_case: bool = True,
) -> List[RegexMatch]:
    """Find all values matching a pattern, optionally filtered by type.

    Only searches values, not keys. If value_type is specified, only tests
    values of that type (e.g., value_type=str filters to string values only).

    Args:
      mapping_dict: the mapping dict
      pattern: regex pattern string
      value_type: optional type filter (e.g., str, int). If provided, only
                  values of this type are tested
      ignore_case: if True, compile pattern with re.IGNORECASE flag

    Returns:
      list of RegexMatch objects

    Raises:
      re.error: if pattern is invalid
    """
    if not isinstance(mapping_dict, dict):
        return []

    flags = re.IGNORECASE if ignore_case else 0
    try:
        regex = re.compile(pattern, flags)
    except re.error:
        raise

    matches: List[RegexMatch] = []

    for path, value in walk_paths(mapping_dict):
        # Type filter
        if value_type is not None and not isinstance(value, value_type):
            continue

        value_str = str(value)
        match_obj = regex.search(value_str)
        if match_obj:
            matches.append(RegexMatch(
                path=path,
                value=value,
                matched_text=match_obj.group(0)
            ))

    return matches


def replace(
    mapping_dict: dict,
    pattern: str,
    replacement: str,
    ignore_case: bool = True,
) -> Tuple[dict, int]:
    """Replace all string values matching a pattern with a replacement string.

    Non-mutating: returns a new dict with replacements applied. Does not modify
    int/float/bool leaves or the original dict. Only replaces string values.

    Args:
      mapping_dict: the mapping dict
      pattern: regex pattern string
      replacement: replacement string (supports backreferences like \\1)
      ignore_case: if True, compile pattern with re.IGNORECASE flag

    Returns:
      tuple of (new_mapping_dict, replacement_count)

    Raises:
      re.error: if pattern is invalid
    """
    if not isinstance(mapping_dict, dict):
        return ({}, 0)

    flags = re.IGNORECASE if ignore_case else 0
    try:
        regex = re.compile(pattern, flags)
    except re.error:
        raise

    replacement_count = 0

    def _deep_copy_with_replace(obj: Any) -> Tuple[Any, int]:
        """Recursively copy obj, replacing string leaves."""
        count = 0
        if isinstance(obj, dict):
            new_dict = {}
            for key, val in obj.items():
                new_val, val_count = _deep_copy_with_replace(val)
                new_dict[key] = new_val
                count += val_count
            return new_dict, count
        elif isinstance(obj, list):
            new_list = []
            for item in obj:
                new_item, item_count = _deep_copy_with_replace(item)
                new_list.append(new_item)
                count += item_count
            return new_list, count
        elif isinstance(obj, str):
            # Try to replace
            new_val = regex.sub(replacement, obj)
            if new_val != obj:
                count = 1
            return new_val, count
        else:
            # Non-string leaf: return as-is
            return obj, count

    new_dict, replacement_count = _deep_copy_with_replace(mapping_dict)
    return new_dict, replacement_count
