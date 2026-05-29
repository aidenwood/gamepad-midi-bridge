"""Pretty, UI-friendly diff renderer for mapping dicts.

Produces multi-line diffs with color-friendly markers and structured output.
Pure stdlib only; no Qt dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, Iterator, List, Tuple


@dataclass
class DiffLine:
    """A single line in a formatted diff output.

    Attributes:
        kind: One of "added", "removed", "changed", "unchanged", "section"
        path: Dotted path to the key (e.g. "buttons.0.note")
        old_value: Value in the old/left dict (None if added or section)
        new_value: Value in the new/right dict (None if removed or section)
    """
    kind: str
    path: str
    old_value: Any = None
    new_value: Any = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a plain dict for serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> DiffLine:
        """Reconstruct from a plain dict."""
        return cls(**data)


def walk_keys(d: Any, prefix: str = "") -> Iterator[Tuple[str, Any]]:
    """Yield (dotted_path, leaf_value) for every leaf in a nested dict.

    Recursively descends into nested dicts, yielding only leaf values
    (scalars, lists, or non-dict objects). Intermediate dicts are skipped.

    Args:
        d: The value to walk (typically a dict, but handles any type).
        prefix: The dotted path prefix (used internally during recursion).

    Yields:
        Tuples of (dotted_path, leaf_value).
    """
    if isinstance(d, dict):
        if not d:  # Empty dict is a leaf
            yield (prefix, d)
        else:
            for key, value in sorted(d.items()):
                new_prefix = f"{prefix}.{key}" if prefix else key
                if isinstance(value, dict):
                    # Recurse into nested dicts
                    yield from walk_keys(value, new_prefix)
                else:
                    # Leaf value (scalar, list, or non-dict)
                    yield (new_prefix, value)
    else:
        # Not a dict; it's a leaf
        if prefix:
            yield (prefix, d)


def diff(a: Dict[str, Any], b: Dict[str, Any]) -> List[DiffLine]:
    """Compare two dicts and return a list of DiffLine entries.

    Recursively compares a (old) and b (new), yielding DiffLine objects
    for each difference. Identical values are skipped.

    Args:
        a: The old/left dict.
        b: The new/right dict.

    Returns:
        List of DiffLine entries for all differences.
    """
    lines: List[DiffLine] = []

    # Collect all paths from both dicts
    paths_a = {path: value for path, value in walk_keys(a)}
    paths_b = {path: value for path, value in walk_keys(b)}

    all_paths = sorted(set(paths_a.keys()) | set(paths_b.keys()))

    for path in all_paths:
        val_a = paths_a.get(path)
        val_b = paths_b.get(path)

        if path not in paths_a:
            # Added in b
            lines.append(DiffLine(kind="added", path=path, old_value=None, new_value=val_b))
        elif path not in paths_b:
            # Removed from a
            lines.append(DiffLine(kind="removed", path=path, old_value=val_a, new_value=None))
        elif val_a != val_b:
            # Changed
            lines.append(DiffLine(kind="changed", path=path, old_value=val_a, new_value=val_b))
        else:
            # Unchanged
            lines.append(DiffLine(kind="unchanged", path=path, old_value=val_a, new_value=val_b))

    return lines


def summary(diff_lines: List[DiffLine]) -> Dict[str, int]:
    """Count diff lines by kind.

    Args:
        diff_lines: A list of DiffLine entries.

    Returns:
        A dict with counts per kind: {"added": 5, "removed": 2, ...}
    """
    counts: Dict[str, int] = {}
    for line in diff_lines:
        counts[line.kind] = counts.get(line.kind, 0) + 1
    return counts


def format_line(
    line: DiffLine,
    color: bool = False,
    markers: bool = True
) -> str:
    """Format a DiffLine as a readable string.

    Args:
        line: The DiffLine to format.
        color: If True, wrap with ANSI color codes (green for +, red for -, yellow for ~).
        markers: If True, prefix with "+ " (added), "- " (removed), "~ " (changed), "  " (unchanged).

    Returns:
        A formatted string.
    """
    # Determine marker
    if markers:
        if line.kind == "added":
            marker = "+ "
        elif line.kind == "removed":
            marker = "- "
        elif line.kind == "changed":
            marker = "~ "
        else:
            marker = "  "
    else:
        marker = ""

    # Build value part
    if line.kind == "removed":
        value_part = f"{line.path} = {line.old_value!r}"
    elif line.kind == "added":
        value_part = f"{line.path} = {line.new_value!r}"
    elif line.kind == "changed":
        value_part = f"{line.path}: {line.old_value!r} → {line.new_value!r}"
    else:  # unchanged
        value_part = f"{line.path} = {line.old_value!r}"

    text = marker + value_part

    # Apply color if requested
    if color:
        if line.kind == "added":
            # Green
            text = f"\033[32m{text}\033[0m"
        elif line.kind == "removed":
            # Red
            text = f"\033[31m{text}\033[0m"
        elif line.kind == "changed":
            # Yellow
            text = f"\033[33m{text}\033[0m"

    return text


def render(
    a: Dict[str, Any],
    b: Dict[str, Any],
    include_unchanged: bool = False,
    color: bool = False
) -> str:
    """Render a multi-line diff string comparing two dicts.

    Args:
        a: The old/left dict.
        b: The new/right dict.
        include_unchanged: If True, include unchanged lines (default False).
        color: If True, use ANSI color codes (default False).

    Returns:
        A multi-line string with formatted diff output.
    """
    lines = diff(a, b)

    # Filter to changes only (unless include_unchanged)
    if not include_unchanged:
        lines = [line for line in lines if line.kind != "unchanged"]

    # Format and join
    formatted = [format_line(line, color=color, markers=True) for line in lines]
    return "\n".join(formatted)


def group_by_section(lines: List[DiffLine]) -> Dict[str, List[DiffLine]]:
    """Group DiffLine entries by top-level section name.

    Extracts the first component of the dotted path (e.g., "buttons" from
    "buttons.0.note") and groups lines accordingly.

    Args:
        lines: A list of DiffLine entries.

    Returns:
        A dict mapping section names to lists of DiffLine entries.
    """
    grouped: Dict[str, List[DiffLine]] = {}
    for line in lines:
        # Extract first component of path
        section = line.path.split(".")[0] if line.path else "root"
        if section not in grouped:
            grouped[section] = []
        grouped[section].append(line)
    return grouped
