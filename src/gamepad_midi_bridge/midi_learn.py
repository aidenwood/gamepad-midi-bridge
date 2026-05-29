"""MIDI Learn: bind incoming CCs to parameter updates.

Pure data + scaling layer. No Qt imports, no global state, no bridge integration yet.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional


@dataclass
class MidiLearnBinding:
    """One incoming MIDI CC → local mapping parameter binding.

    Fields:
      - `cc`           : CC number (0..127)
      - `channel`      : MIDI channel (1..16)
      - `target_path`  : dotted path like "triggers.L2.cc_value_max" or
                         "stick.curve_amount"
      - `min_value`    : lowest value in the target range (float)
      - `max_value`    : highest value in the target range (float)
      - `enabled`      : if False, this binding is skipped (default True)
    """
    cc: int
    channel: int
    target_path: str
    min_value: float
    max_value: float
    enabled: bool = True

    def __post_init__(self) -> None:
        """Clamp CC and channel to valid ranges."""
        self.cc = max(0, min(127, self.cc))
        self.channel = max(1, min(16, self.channel))


@dataclass
class MidiLearnConfig:
    """Collection of MIDI Learn bindings.

    Fields:
      - `bindings` : list of MidiLearnBinding objects
    """
    bindings: List[MidiLearnBinding] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Round-trip to JSON-serializable dict."""
        return {
            "bindings": [asdict(b) for b in self.bindings]
        }

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> "MidiLearnConfig":
        """Hydrate from JSON dict. Missing/None → empty config."""
        if not data:
            return cls()

        raw_bindings = data.get("bindings") or []
        bindings: List[MidiLearnBinding] = []

        for entry in raw_bindings:
            if not isinstance(entry, dict):
                continue
            try:
                bindings.append(MidiLearnBinding(
                    cc=max(0, min(127, int(entry.get("cc", 0)))),
                    channel=max(1, min(16, int(entry.get("channel", 1)))),
                    target_path=str(entry.get("target_path", "")),
                    min_value=float(entry.get("min_value", 0.0)),
                    max_value=float(entry.get("max_value", 1.0)),
                    enabled=bool(entry.get("enabled", True)),
                ))
            except (TypeError, ValueError):
                continue

        return cls(bindings=bindings)


def apply_learn_to_mapping(
    mapping_dict: dict,
    cc: int,
    channel: int,
    raw_value: int,
    bindings: List[MidiLearnBinding],
) -> dict:
    """Apply matching MIDI Learn bindings to mapping dict.

    Returns a NEW dict (deep clone of mapping_dict) with target paths updated.
    Walks dotted paths through nested dicts AND lists (indexed by string keys).

    Args:
      mapping_dict  : current mapping as dict (from mapping.to_dict())
      cc            : incoming CC number (0..127)
      channel       : incoming channel (1..16)
      raw_value     : incoming CC value (0..127)
      bindings      : list of MidiLearnBinding to apply

    Returns:
      A new dict with matching bindings applied. Unchanged dict if no matches.
    """
    # Deep clone the input
    result = _deep_clone(mapping_dict)

    # Filter bindings: only enabled, CC/channel match
    for binding in bindings:
        if not binding.enabled:
            continue
        if binding.cc != cc or binding.channel != channel:
            continue

        # Scale raw_value (0..127) to [min_value, max_value]
        scaled = _scale_value(raw_value, binding.min_value, binding.max_value)

        # Walk the dotted path and update
        _set_nested_value(result, binding.target_path, scaled)

    return result


def _scale_value(raw: int, min_val: float, max_val: float) -> float:
    """Scale a 0..127 CC value to [min_val, max_val]."""
    normalized = raw / 127.0
    return min_val + normalized * (max_val - min_val)


def _deep_clone(obj: object) -> object:
    """Recursively clone dicts and lists. Leaf values pass through."""
    if isinstance(obj, dict):
        return {k: _deep_clone(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_deep_clone(item) for item in obj]
    else:
        return obj


def _set_nested_value(obj: dict, path: str, value: object) -> None:
    """Walk a dotted path and set the final key to value.

    Path like "a.b.c" walks obj["a"]["b"] and sets ["c"] = value.
    Handles both nested dicts and lists indexed by string keys.
    Silent no-op if path doesn't exist.

    Args:
      obj   : the dict to modify in-place
      path  : dotted path string (e.g. "triggers.L2.cc_value_max")
      value : the value to set
    """
    parts = path.split(".")
    if not parts:
        return

    current = obj
    # Walk all but the last part
    for part in parts[:-1]:
        if isinstance(current, dict):
            if part not in current:
                return  # Path doesn't exist, silent no-op
            current = current[part]
        else:
            return  # Hit a non-dict, can't continue

    # Set the final key
    final_key = parts[-1]
    if isinstance(current, dict):
        current[final_key] = value
