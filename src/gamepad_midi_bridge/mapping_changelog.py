"""Append-only mutation changelog for mapping edits with rollback support.

MappingChangelog maintains a history of edits (path, old_value, new_value, timestamp)
and supports undo/redo operations without Qt dependencies. Pure stdlib implementation.

Example:
    >>> cfg = ChangelogConfig(max_entries=100)
    >>> changelog = MappingChangelog(cfg)
    >>> changelog.record('buttons.0.note', 60, 64, time.time())
    >>> changelog.record('buttons.1.note', 65, 67, time.time())
    >>> changelog.can_undo()
    True
    >>> entry = changelog.undo()
    >>> entry.path
    'buttons.1.note'
    >>> changelog.can_redo()
    True
"""
from __future__ import annotations

import copy
import time
from dataclasses import dataclass, asdict, field
from typing import Any, Dict, List, Optional


@dataclass
class MutationEntry:
    """One recorded mutation to a mapping value."""
    timestamp_s: float         # time.time() epoch seconds
    path: str                  # dotted path to the field (e.g. 'buttons.0.note')
    old_value: Any             # the previous value
    new_value: Any             # the new value after the mutation
    description: str = ""      # optional human-readable summary

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a JSON-serializable dict."""
        return asdict(self)

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> MutationEntry:
        """Reconstruct from a dict (e.g., from JSON)."""
        return MutationEntry(**d)


@dataclass
class ChangelogConfig:
    """Configuration for MappingChangelog."""
    max_entries: int = 200    # max entries to keep (FIFO eviction); clamped 10..100000

    def __post_init__(self) -> None:
        self.max_entries = max(10, min(100000, self.max_entries))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a JSON-serializable dict."""
        return asdict(self)

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> ChangelogConfig:
        """Reconstruct from a dict (e.g., from JSON)."""
        return ChangelogConfig(**d)


class MappingChangelog:
    """Append-only mutation changelog with undo/redo support."""

    def __init__(self, cfg: ChangelogConfig) -> None:
        """Initialize changelog with given config."""
        self._cfg = cfg
        self._entries: List[MutationEntry] = []
        self._undo_pointer = 0  # index of next entry to undo; if < len(_entries), redo is available

    # ---------------------------------------------------------------- public API

    def record(
        self,
        path: str,
        old_value: Any,
        new_value: Any,
        now_s: float,
        description: str = "",
    ) -> MutationEntry:
        """Record a new mutation.

        If user has undone entries and then records a new one, truncate the
        entries after the undo pointer (typical undo-then-edit behaviour).

        Trim FIFO if entries would exceed max_entries.

        Returns the created MutationEntry.
        """
        # If undo_pointer < len(_entries), user undone then re-recorded => trim future
        if self._undo_pointer < len(self._entries):
            self._entries = self._entries[: self._undo_pointer]

        entry = MutationEntry(
            timestamp_s=now_s,
            path=str(path),
            old_value=copy.deepcopy(old_value),
            new_value=copy.deepcopy(new_value),
            description=str(description),
        )

        # Trim FIFO if adding this entry would exceed max
        if len(self._entries) >= self._cfg.max_entries:
            self._entries.pop(0)
            self._undo_pointer = max(0, self._undo_pointer - 1)

        self._entries.append(entry)
        self._undo_pointer = len(self._entries)

        return entry

    def entries(self) -> List[MutationEntry]:
        """Return a copy of all entries."""
        return copy.deepcopy(self._entries)

    def recent(self, n: int = 20) -> List[MutationEntry]:
        """Return the last n entries."""
        return copy.deepcopy(self._entries[-n:])

    def undo(self) -> Optional[MutationEntry]:
        """Return the last recorded entry (the one to undo) and decrement pointer.

        Returns None if nothing to undo.
        """
        if self._undo_pointer <= 0:
            return None
        self._undo_pointer -= 1
        return self._entries[self._undo_pointer]

    def redo(self) -> Optional[MutationEntry]:
        """Return the next pending entry to re-apply and increment pointer.

        Returns None if nothing to redo.
        """
        if self._undo_pointer >= len(self._entries):
            return None
        entry = self._entries[self._undo_pointer]
        self._undo_pointer += 1
        return entry

    def can_undo(self) -> bool:
        """True if there are entries to undo."""
        return self._undo_pointer > 0

    def can_redo(self) -> bool:
        """True if there are entries to redo."""
        return self._undo_pointer < len(self._entries)

    def apply_undo(self, mapping_dict: dict) -> dict:
        """Return a NEW dict with the most recent recorded mutation reversed.

        Uses dotted-path walking to navigate and update nested dicts.
        Returns a deep copy of mapping_dict with the reversal applied.
        Idempotent: if can_undo() is False, returns an unmodified copy.
        """
        if not self.can_undo():
            return copy.deepcopy(mapping_dict)

        entry = self._entries[self._undo_pointer - 1]
        result = copy.deepcopy(mapping_dict)

        # Walk the dotted path and set old_value
        _set_nested_value(result, entry.path, entry.old_value)

        return result

    def apply_redo(self, mapping_dict: dict) -> dict:
        """Return a NEW dict with the next pending mutation re-applied.

        Uses dotted-path walking to navigate and update nested dicts.
        Returns a deep copy of mapping_dict with the re-application applied.
        Idempotent: if can_redo() is False, returns an unmodified copy.
        """
        if not self.can_redo():
            return copy.deepcopy(mapping_dict)

        entry = self._entries[self._undo_pointer]
        result = copy.deepcopy(mapping_dict)

        # Walk the dotted path and set new_value
        _set_nested_value(result, entry.path, entry.new_value)

        return result

    def clear(self) -> None:
        """Empty all entries and reset pointer."""
        self._entries.clear()
        self._undo_pointer = 0

    def summary(self) -> Dict[str, Any]:
        """Return a summary dict with stats.

        Keys: total, undone (number of entries that are undone),
        can_undo (0 or 1), can_redo (0 or 1).
        """
        undone_count = len(self._entries) - self._undo_pointer
        return {
            "total": len(self._entries),
            "undone": undone_count,
            "can_undo": 1 if self.can_undo() else 0,
            "can_redo": 1 if self.can_redo() else 0,
        }


# --------------------------------------------------------------------------- helpers

def _set_nested_value(d: dict, dotted_path: str, value: Any) -> None:
    """Mutate dict d by setting a nested key via dotted path.

    Example: _set_nested_value(d, 'buttons.0.note', 64)
    will do d['buttons'][0]['note'] = 64 (mutating in-place).

    Creates intermediate dicts if they don't exist.
    """
    parts = dotted_path.split(".")
    current = d

    # Navigate to the parent of the final key
    for part in parts[:-1]:
        # Try to interpret as int index
        try:
            idx = int(part)
            # If current is a list, extend if needed
            if isinstance(current, list):
                while len(current) <= idx:
                    current.append({})
                if not isinstance(current[idx], dict):
                    current[idx] = {}
                current = current[idx]
            else:
                # Current is a dict; treat part as a string key
                if part not in current:
                    current[part] = {}
                current = current[part]
        except ValueError:
            # part is not an int, treat as string key
            if part not in current:
                current[part] = {}
            current = current[part]

    # Set the final key
    final_key = parts[-1]
    try:
        idx = int(final_key)
        if isinstance(current, list):
            while len(current) <= idx:
                current.append(None)
            current[idx] = value
        else:
            current[final_key] = value
    except ValueError:
        current[final_key] = value


def _get_nested_value(d: dict, dotted_path: str) -> Any:
    """Retrieve a nested value from dict d via dotted path.

    Example: _get_nested_value(d, 'buttons.0.note')
    returns d['buttons'][0]['note'].

    Returns None if path doesn't exist.
    """
    parts = dotted_path.split(".")
    current = d

    for part in parts:
        if current is None:
            return None

        try:
            idx = int(part)
            if isinstance(current, (list, tuple)):
                if 0 <= idx < len(current):
                    current = current[idx]
                else:
                    return None
            else:
                current = current.get(part)
        except ValueError:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None

    return current
