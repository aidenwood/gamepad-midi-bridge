"""Mapping conflict auto-resolver: fixes duplicate (note/CC + channel) assignments.

Walks conflicts and applies fixes: shift duplicate notes up an octave / pick next free CC /
move to different channel. Pure stdlib, no Qt. Non-mutating.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Tuple

from gamepad_midi_bridge.mapping_conflict_scanner import Conflict


@dataclass
class ResolveResult:
    """Result of a full conflict resolution pass.

    Attributes:
        conflicts_resolved: count of conflicts fully resolved
        conflicts_unresolved: count of conflicts that could not be resolved
        actions_taken: list of human-readable action strings (e.g. "Shifted buttons.5.note 60 → 72")
        new_mapping: the updated mapping dict with fixes applied
    """
    conflicts_resolved: int
    conflicts_unresolved: int
    actions_taken: List[str] = field(default_factory=list)
    new_mapping: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialize to dict."""
        return {
            "conflicts_resolved": self.conflicts_resolved,
            "conflicts_unresolved": self.conflicts_unresolved,
            "actions_taken": self.actions_taken,
            "new_mapping": self.new_mapping,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ResolveResult:
        """Deserialize from dict."""
        return cls(
            conflicts_resolved=data.get("conflicts_resolved", 0),
            conflicts_unresolved=data.get("conflicts_unresolved", 0),
            actions_taken=data.get("actions_taken", []),
            new_mapping=data.get("new_mapping", {}),
        )


@dataclass
class ResolverConfig:
    """Configuration for conflict resolution strategy.

    Attributes:
        strategy: "octave_shift" (shift notes up octave), "channel_shift" (cycle channels),
                  "skip" (leave unchanged), or unknown → "octave_shift"
        max_attempts: max tries per conflict (clamped 1..32), default 8
        prefer_keep_first: if True, keep first conflicting path unchanged and shift later ones
    """
    strategy: str = "octave_shift"
    max_attempts: int = 8
    prefer_keep_first: bool = True

    def __post_init__(self):
        """Clamp and validate on initialization."""
        if self.strategy not in ("octave_shift", "channel_shift", "skip"):
            self.strategy = "octave_shift"
        self.max_attempts = max(1, min(32, self.max_attempts))

    def to_dict(self) -> dict:
        """Serialize to dict."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> ResolverConfig:
        """Deserialize from dict."""
        return cls(
            strategy=data.get("strategy", "octave_shift"),
            max_attempts=data.get("max_attempts", 8),
            prefer_keep_first=data.get("prefer_keep_first", True),
        )


def resolve_note_collision(
    mapping_dict: dict, paths: List[str], cfg: ResolverConfig
) -> Tuple[dict, List[str], bool]:
    """Resolve a note collision by shifting notes.

    Args:
        mapping_dict: the mapping dict (will be deep-copied, not mutated)
        paths: list of dotted paths to conflicting note assignments (e.g. ["buttons[0]", "buttons[1]"])
        cfg: ResolverConfig with strategy and max_attempts

    Returns:
        (new_mapping, actions_taken, success) where:
        - new_mapping: copy of mapping with fixes applied
        - actions_taken: list of human-readable action strings
        - success: True if all conflicts in paths were resolved
    """
    if not paths:
        return copy.deepcopy(mapping_dict), [], True

    mapping = copy.deepcopy(mapping_dict)
    actions = []
    success = True

    if cfg.strategy == "skip":
        return mapping, actions, success

    if cfg.strategy not in ("octave_shift", "channel_shift"):
        cfg.strategy = "octave_shift"

    if cfg.strategy == "octave_shift":
        # Get original note value from first path for reference
        original_note = _get_value_from_path(mapping, paths[0])
        if original_note is None:
            return mapping, actions, False

        # Determine which paths to shift
        start_idx = 1 if cfg.prefer_keep_first else 0
        paths_to_shift = paths[start_idx:]

        for idx, path in enumerate(paths_to_shift):
            current_note = _get_value_from_path(mapping, path)
            if current_note is None:
                success = False
                continue

            # Try shifting up by octaves (12 semitones), offset by idx to avoid collisions
            shifted = False
            for attempt in range(cfg.max_attempts):
                shift_amount = 12 * (idx + attempt + 1)
                new_note = current_note + shift_amount
                if new_note <= 127:
                    _set_value_at_path(mapping, path, new_note)
                    actions.append(f"Shifted {path} {current_note} → {new_note} (octave up)")
                    shifted = True
                    break
                elif attempt == cfg.max_attempts - 1:
                    # Try shifting down
                    for down_attempt in range(1, cfg.max_attempts):
                        new_note = current_note - (12 * down_attempt)
                        if new_note >= 0:
                            _set_value_at_path(mapping, path, new_note)
                            actions.append(f"Shifted {path} {current_note} → {new_note} (octave down)")
                            shifted = True
                            break

            if not shifted:
                success = False

    elif cfg.strategy == "channel_shift":
        # Get original channel from first path
        original_path = paths[0]
        original_note = _get_value_from_path(mapping, original_path)
        original_channel = _get_channel_from_path(mapping, original_path)

        if original_channel is None:
            return mapping, actions, False

        # Shift later paths to different channels
        start_idx = 1 if cfg.prefer_keep_first else 0
        paths_to_shift = paths[start_idx:]

        for idx, path in enumerate(paths_to_shift):
            new_channel = (original_channel + idx + 1) % 16
            _set_channel_at_path(mapping, path, new_channel)
            actions.append(f"Shifted {path} to channel {new_channel}")

    return mapping, actions, success


def resolve_cc_collision(
    mapping_dict: dict, paths: List[str], cfg: ResolverConfig
) -> Tuple[dict, List[str], bool]:
    """Resolve a CC collision by picking next free CC.

    Args:
        mapping_dict: the mapping dict (will be deep-copied, not mutated)
        paths: list of dotted paths to conflicting CC assignments (e.g. ["axes[0]", "axes[1]"])
        cfg: ResolverConfig (strategy ignored for CC; always tries to find free CC)

    Returns:
        (new_mapping, actions_taken, success)
    """
    if not paths:
        return copy.deepcopy(mapping_dict), [], True

    mapping = copy.deepcopy(mapping_dict)
    actions = []
    success = True

    if cfg.strategy == "skip":
        return mapping, actions, success

    # Build set of used CCs (excluding 0)
    used_ccs = set()
    axes = mapping.get("axes", {})
    for cc in axes.values():
        if isinstance(cc, int) and cc > 0:
            used_ccs.add(cc)

    # Also check triggers
    l2_trigger = mapping.get("l2_trigger")
    if isinstance(l2_trigger, dict) and "cc" in l2_trigger:
        l2_cc = l2_trigger.get("cc")
        if isinstance(l2_cc, int) and l2_cc > 0:
            used_ccs.add(l2_cc)

    r2_trigger = mapping.get("r2_trigger")
    if isinstance(r2_trigger, dict) and "cc" in r2_trigger:
        r2_cc = r2_trigger.get("cc")
        if isinstance(r2_cc, int) and r2_cc > 0:
            used_ccs.add(r2_cc)

    # Keep first path unchanged if prefer_keep_first
    start_idx = 1 if cfg.prefer_keep_first else 0
    paths_to_shift = paths[start_idx:]

    for path in paths_to_shift:
        original_cc = _get_value_from_path(mapping, path)
        if original_cc is None:
            success = False
            continue

        # Find next free CC (skip 0 and the original)
        found = False
        for cc in range(1, 128):
            if cc not in used_ccs and cc != original_cc:
                _set_value_at_path(mapping, path, cc)
                used_ccs.add(cc)
                actions.append(f"Assigned {path} CC {original_cc} → {cc} (next free)")
                found = True
                break

        if not found:
            success = False

    return mapping, actions, success


def resolve_all(
    mapping_dict: dict, conflicts: List[Conflict], cfg: ResolverConfig
) -> ResolveResult:
    """Resolve all conflicts in a single pass.

    Walks conflicts in order, applying fixes and tracking success.

    Args:
        mapping_dict: the mapping dict
        conflicts: list of Conflict objects from scan()
        cfg: ResolverConfig

    Returns:
        ResolveResult with counts, actions, and new_mapping
    """
    mapping = copy.deepcopy(mapping_dict)
    all_actions = []
    resolved_count = 0
    unresolved_count = 0

    for conflict in conflicts:
        if conflict.kind == "note_collision":
            new_mapping, actions, success = resolve_note_collision(mapping, conflict.paths, cfg)
            mapping = new_mapping
            all_actions.extend(actions)
            if success:
                resolved_count += 1
            else:
                unresolved_count += 1

        elif conflict.kind == "cc_collision":
            new_mapping, actions, success = resolve_cc_collision(mapping, conflict.paths, cfg)
            mapping = new_mapping
            all_actions.extend(actions)
            if success:
                resolved_count += 1
            else:
                unresolved_count += 1

        else:
            # Unknown conflict kind; skip
            unresolved_count += 1

    return ResolveResult(
        conflicts_resolved=resolved_count,
        conflicts_unresolved=unresolved_count,
        actions_taken=all_actions,
        new_mapping=mapping,
    )


# --- Internal Helpers ---


def _get_value_from_path(mapping: dict, path: str) -> int | None:
    """Extract the value (note or CC) at a dotted path.

    Examples:
        "buttons[0]" → mapping["buttons"][0]
        "axes[2]" → mapping["axes"][2]

    Returns:
        The value at the path, or None if not found.
    """
    parts = path.split("[")
    if not parts:
        return None

    key = parts[0]
    container = mapping.get(key)
    if container is None:
        return None

    if len(parts) < 2:
        return None

    idx_str = parts[1].rstrip("]")
    try:
        idx = int(idx_str)
    except ValueError:
        return None

    value = container.get(idx)
    if isinstance(value, int):
        return value

    return None


def _set_value_at_path(mapping: dict, path: str, value: int) -> bool:
    """Set the value (note or CC) at a dotted path.

    Examples:
        "buttons[0]" → mapping["buttons"][0] = value
        "axes[2]" → mapping["axes"][2] = value

    Returns:
        True if successfully set, False otherwise.
    """
    parts = path.split("[")
    if not parts:
        return False

    key = parts[0]
    if key not in mapping:
        return False

    container = mapping[key]
    if not isinstance(container, dict):
        return False

    if len(parts) < 2:
        return False

    idx_str = parts[1].rstrip("]")
    try:
        idx = int(idx_str)
    except ValueError:
        return False

    container[idx] = value
    return True


def _get_channel_from_path(mapping: dict, path: str) -> int | None:
    """Extract the channel for a path (buttons[i] or axes[i]).

    Checks button_channels or axis_channels dict, falls back to midi_channel.

    Examples:
        "buttons[0]" → button_channels[0] or midi_channel
        "axes[2]" → axis_channels[2] or midi_channel
    """
    parts = path.split("[")
    if not parts:
        return None

    key = parts[0]
    if len(parts) < 2:
        return None

    idx_str = parts[1].rstrip("]")
    try:
        idx = int(idx_str)
    except ValueError:
        return None

    global_channel = mapping.get("midi_channel", 0)

    if key == "buttons":
        button_channels = mapping.get("button_channels", {})
        return button_channels.get(idx, global_channel)
    elif key == "axes":
        axis_channels = mapping.get("axis_channels", {})
        return axis_channels.get(idx, global_channel)

    return None


def _set_channel_at_path(mapping: dict, path: str, channel: int) -> bool:
    """Set the channel for a path (buttons[i] or axes[i]).

    Creates button_channels or axis_channels dict if needed.

    Returns:
        True if successfully set, False otherwise.
    """
    parts = path.split("[")
    if not parts:
        return False

    key = parts[0]
    if len(parts) < 2:
        return False

    idx_str = parts[1].rstrip("]")
    try:
        idx = int(idx_str)
    except ValueError:
        return False

    if key == "buttons":
        if "button_channels" not in mapping:
            mapping["button_channels"] = {}
        mapping["button_channels"][idx] = channel
        return True
    elif key == "axes":
        if "axis_channels" not in mapping:
            mapping["axis_channels"] = {}
        mapping["axis_channels"][idx] = channel
        return True

    return False
