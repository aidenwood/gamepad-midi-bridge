"""Mapping conflict scanner: detects duplicate (note/CC + channel) assignments.

Walks a mapping dictionary searching for note collisions (multiple buttons on
same note + channel) and CC collisions (multiple axes/triggers on same CC + channel).

Pure stdlib, no Qt. Defensive throughout.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, List, Optional


@dataclass
class Conflict:
    """A single collision in the mapping.

    Attributes:
        kind: "note_collision", "cc_collision", or "channel_overlap"
        key: human-readable collision key (e.g. "note 60 ch 1" or "cc 1 ch 1")
        paths: list of dotted paths to all assignments sharing this key
        severity: "warning" or "error"
    """
    kind: str
    key: str
    paths: List[str]
    severity: str = "warning"

    def to_dict(self) -> dict:
        """Serialize to dict."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> Conflict:
        """Deserialize from dict."""
        return cls(**data)


def scan(mapping_dict: dict) -> List[Conflict]:
    """Scan a mapping dictionary for all types of conflicts.

    Args:
        mapping_dict: the raw mapping dict (e.g. from JSON, before Mapping unpacking)

    Returns:
        list of all Conflict objects found (notes + CCs + others)
    """
    conflicts = []
    conflicts.extend(_scan_notes(mapping_dict))
    conflicts.extend(_scan_ccs(mapping_dict))
    return conflicts


def scan_notes_only(mapping_dict: dict) -> List[Conflict]:
    """Scan for note_collision conflicts only."""
    return _scan_notes(mapping_dict)


def scan_ccs_only(mapping_dict: dict) -> List[Conflict]:
    """Scan for cc_collision conflicts only."""
    return _scan_ccs(mapping_dict)


def _scan_notes(mapping_dict: dict) -> List[Conflict]:
    """Internal: scan buttons for note collisions.

    Builds a map of (note, channel) → [paths] and returns any with 2+ paths.
    """
    collisions: Dict[tuple, List[str]] = {}
    buttons = mapping_dict.get("buttons") or {}
    button_channels = mapping_dict.get("button_channels") or {}
    global_channel = mapping_dict.get("midi_channel", 0)

    for button_idx, note in buttons.items():
        if not isinstance(note, int) or note == 0:
            continue
        channel = button_channels.get(button_idx, global_channel)
        key = (note, channel)
        path = f"buttons[{button_idx}]"
        if key not in collisions:
            collisions[key] = []
        collisions[key].append(path)

    # Extract conflicts (2+ paths for same key)
    result = []
    for (note, channel), paths in collisions.items():
        if len(paths) > 1:
            paths_sorted = sorted(paths)
            key_str = f"note {note} ch {channel}"
            conflict = Conflict(
                kind="note_collision",
                key=key_str,
                paths=paths_sorted,
                severity="error"
            )
            result.append(conflict)

    return result


def _scan_ccs(mapping_dict: dict) -> List[Conflict]:
    """Internal: scan axes and triggers for CC collisions.

    A CC collision occurs when:
    - Multiple axes share the same (CC, channel)
    - An axis and trigger share the same (CC, channel) when trigger is explicitly configured
    - Multiple triggers (L2, R2) share the same (CC, channel)

    Note: Axes 4 and 5 naturally map to L2/R2 via the default axes dict.
    We only flag a collision if the trigger has an EXPLICIT override or config.
    """
    collisions: Dict[tuple, List[str]] = {}
    axes = mapping_dict.get("axes") or {}
    axis_channels = mapping_dict.get("axis_channels") or {}
    global_channel = mapping_dict.get("midi_channel", 0)

    # Add axes (including 4=L2, 5=R2)
    for axis_idx, cc in axes.items():
        if not isinstance(cc, int) or cc == 0:
            continue
        channel = axis_channels.get(axis_idx, global_channel)
        key = (cc, channel)
        path = f"axes[{axis_idx}]"
        if key not in collisions:
            collisions[key] = []
        collisions[key].append(path)

    # Add L2 trigger ONLY if it has explicit config with a CC override
    # or if it defines a crossfade that uses a different channel
    l2_trigger = mapping_dict.get("l2_trigger")
    if isinstance(l2_trigger, dict) and l2_trigger:
        # Only add if this trigger config explicitly sets a CC (not using axis default)
        if "cc" in l2_trigger:
            l2_cc = l2_trigger.get("cc")
            if isinstance(l2_cc, int) and l2_cc > 0:
                l2_channel = l2_trigger.get("channel_override")
                if l2_channel is None or l2_channel < 0:
                    l2_channel = global_channel
                key = (l2_cc, l2_channel)
                path = "l2_trigger"
                if key not in collisions:
                    collisions[key] = []
                collisions[key].append(path)

    # Add R2 trigger ONLY if it has explicit config with a CC override
    r2_trigger = mapping_dict.get("r2_trigger")
    if isinstance(r2_trigger, dict) and r2_trigger:
        # Only add if this trigger config explicitly sets a CC (not using axis default)
        if "cc" in r2_trigger:
            r2_cc = r2_trigger.get("cc")
            if isinstance(r2_cc, int) and r2_cc > 0:
                r2_channel = r2_trigger.get("channel_override")
                if r2_channel is None or r2_channel < 0:
                    r2_channel = global_channel
                key = (r2_cc, r2_channel)
                path = "r2_trigger"
                if key not in collisions:
                    collisions[key] = []
                collisions[key].append(path)

    # Extract conflicts
    result = []
    for (cc, channel), paths in collisions.items():
        if len(paths) > 1:
            paths_sorted = sorted(paths)
            key_str = f"cc {cc} ch {channel}"
            conflict = Conflict(
                kind="cc_collision",
                key=key_str,
                paths=paths_sorted,
                severity="error"
            )
            result.append(conflict)

    return result


def count_by_kind(conflicts: List[Conflict]) -> Dict[str, int]:
    """Count conflicts by kind.

    Args:
        conflicts: list of Conflict objects

    Returns:
        dict like {"note_collision": 2, "cc_collision": 1}
    """
    counts: Dict[str, int] = {}
    for conflict in conflicts:
        counts[conflict.kind] = counts.get(conflict.kind, 0) + 1
    return counts


def format_report(conflicts: List[Conflict]) -> str:
    """Format conflicts as a human-readable multi-line report.

    Args:
        conflicts: list of Conflict objects

    Returns:
        multi-line string report, or empty string if no conflicts
    """
    if not conflicts:
        return ""

    lines = ["Mapping Conflicts:"]
    for conflict in sorted(conflicts, key=lambda c: (c.kind, c.key)):
        paths_str = ", ".join(conflict.paths)
        line = f"  [{conflict.severity.upper()}] {conflict.kind}: {conflict.key} → {paths_str}"
        lines.append(line)

    return "\n".join(lines)
