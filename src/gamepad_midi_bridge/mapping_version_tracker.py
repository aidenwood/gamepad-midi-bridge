"""Mapping version tracker: snapshots, navigation, and diffing across versions.

Keeps a linear history of mapping snapshots and allows users to:
- commit() new versions with optional user notes
- rollback() / forward() through the history
- goto() a specific version by ID
- diff_to() compare current vs any other version

Pure stdlib only (hashlib for IDs, copy for deep copies). No Qt dependencies.
"""

from __future__ import annotations

import copy
import hashlib
import time
from dataclasses import dataclass, asdict, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class MappingVersion:
    """A single snapshot in the version history.

    Attributes:
        id: Unique short identifier (e.g., "v_abc123_1234567890")
        timestamp_s: Unix timestamp when this version was created
        mapping_snapshot: Deep copy of the mapping dict at this point
        note: Optional user comment (e.g., "added trigger haptics")
        parent_id: ID of the version this was created from (links to history)
    """

    id: str
    timestamp_s: float
    mapping_snapshot: Dict[str, Any]
    note: str = ""
    parent_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a plain dict for serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> MappingVersion:
        """Reconstruct from a plain dict."""
        return cls(**data)


@dataclass
class VersionTrackerConfig:
    """Configuration for the version tracker.

    Attributes:
        max_versions: Maximum number of versions to keep (clamped 5..10000, default 50)
        auto_prune_oldest: If True, delete oldest when exceeding max_versions (default True)
    """

    max_versions: int = 50
    auto_prune_oldest: bool = True

    def __post_init__(self) -> None:
        """Clamp max_versions to valid range."""
        self.max_versions = max(5, min(self.max_versions, 10000))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a plain dict for serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> VersionTrackerConfig:
        """Reconstruct from a plain dict."""
        return cls(**data)


class MappingVersionTracker:
    """Tracks mapping versions, enabling rollback/forward navigation and diffing."""

    def __init__(self, cfg: VersionTrackerConfig) -> None:
        """Initialize the tracker with a config.

        Args:
            cfg: VersionTrackerConfig instance
        """
        self.cfg = cfg
        self._versions: List[MappingVersion] = []
        self._current_index: int = -1

    def commit(
        self, mapping_dict: Dict[str, Any], now_s: float, note: str = ""
    ) -> MappingVersion:
        """Commit a new version snapshot.

        Creates a new MappingVersion with a unique ID, deep-copies the mapping,
        and appends it to the history. Sets the parent_id to the current version
        (if one exists). If exceeding max_versions and auto_prune is enabled,
        removes the oldest version.

        Args:
            mapping_dict: The mapping dictionary to snapshot
            now_s: Unix timestamp for the commit
            note: Optional user comment

        Returns:
            The newly created MappingVersion
        """
        # Generate unique ID: short hash of mapping content + timestamp
        snapshot = copy.deepcopy(mapping_dict)
        import hashlib

        content_hash = hashlib.sha256(
            str(sorted(snapshot.items())).encode("utf-8")
        ).hexdigest()[:6]
        version_id = f"v_{content_hash}_{int(now_s * 1000000) % 1000000:06d}"

        parent_id = None
        if 0 <= self._current_index < len(self._versions):
            parent_id = self._versions[self._current_index].id

        version = MappingVersion(
            id=version_id,
            timestamp_s=now_s,
            mapping_snapshot=snapshot,
            note=note,
            parent_id=parent_id,
        )

        self._versions.append(version)
        self._current_index = len(self._versions) - 1

        # Auto-prune oldest if exceeding max
        while self.cfg.auto_prune_oldest and len(self._versions) > self.cfg.max_versions:
            self._versions.pop(0)
            self._current_index = max(0, self._current_index - 1)

        return version

    def current(self) -> Optional[MappingVersion]:
        """Return the currently selected version, or None if empty."""
        if 0 <= self._current_index < len(self._versions):
            return self._versions[self._current_index]
        return None

    def previous(self) -> Optional[MappingVersion]:
        """Return the version before current without advancing the index."""
        prev_index = self._current_index - 1
        if 0 <= prev_index < len(self._versions):
            return self._versions[prev_index]
        return None

    def next_version(self) -> Optional[MappingVersion]:
        """Return the version after current without advancing the index."""
        next_index = self._current_index + 1
        if 0 <= next_index < len(self._versions):
            return self._versions[next_index]
        return None

    def rollback(self) -> Optional[MappingVersion]:
        """Move current index back by 1 and return the new current version.

        Returns None if already at the start.
        """
        if self._current_index > 0:
            self._current_index -= 1
            return self.current()
        return None

    def forward(self) -> Optional[MappingVersion]:
        """Move current index forward by 1 and return the new current version.

        Returns None if already at the end.
        """
        if self._current_index < len(self._versions) - 1:
            self._current_index += 1
            return self.current()
        return None

    def goto(self, version_id: str) -> Optional[MappingVersion]:
        """Jump to a specific version by ID.

        Args:
            version_id: The ID to search for

        Returns:
            The version if found, None otherwise (index unchanged on miss)
        """
        for i, version in enumerate(self._versions):
            if version.id == version_id:
                self._current_index = i
                return version
        return None

    def find(self, version_id: str) -> Optional[MappingVersion]:
        """Find a version by ID without changing the current index.

        Args:
            version_id: The ID to search for

        Returns:
            The version if found, None otherwise
        """
        for version in self._versions:
            if version.id == version_id:
                return version
        return None

    def versions(self) -> List[MappingVersion]:
        """Return a copy of all versions."""
        return copy.deepcopy(self._versions)

    def version_count(self) -> int:
        """Return the total number of versions."""
        return len(self._versions)

    def diff_to(self, other_version_id: str) -> Optional[List[Tuple[str, Any, Any]]]:
        """Diff current version against another by ID.

        Returns simple (path, old_value, new_value) tuples.
        Attempts to use mapping_diff_pretty if available, else inline diff.

        Args:
            other_version_id: The ID of the version to diff against

        Returns:
            List of (path, old, new) tuples, or None if other version not found
        """
        current = self.current()
        other = self.find(other_version_id)

        if not current or not other:
            return None

        # Try to use mapping_diff_pretty for structured output, fall back to inline
        try:
            from .mapping_diff_pretty import diff as diff_pretty

            diff_lines = diff_pretty(current.mapping_snapshot, other.mapping_snapshot)
            # Convert DiffLine to (path, old, new) tuples
            result = []
            for line in diff_lines:
                result.append((line.path, line.old_value, line.new_value))
            return result
        except ImportError:
            # Fallback: simple inline diff
            return self._inline_diff(
                current.mapping_snapshot, other.mapping_snapshot
            )

    @staticmethod
    def _inline_diff(
        a: Dict[str, Any], b: Dict[str, Any]
    ) -> List[Tuple[str, Any, Any]]:
        """Simple inline diff fallback (pure stdlib).

        Args:
            a: Old mapping dict
            b: New mapping dict

        Returns:
            List of (path, old, new) tuples
        """
        result: List[Tuple[str, Any, Any]] = []

        def walk(a_val: Any, b_val: Any, prefix: str = "") -> None:
            """Recursively walk and record differences."""
            if isinstance(a_val, dict) and isinstance(b_val, dict):
                all_keys = set(a_val.keys()) | set(b_val.keys())
                for key in sorted(all_keys):
                    new_prefix = f"{prefix}.{key}" if prefix else key
                    a_nested = a_val.get(key)
                    b_nested = b_val.get(key)
                    walk(a_nested, b_nested, new_prefix)
            elif a_val != b_val:
                result.append((prefix, a_val, b_val))

        walk(a, b)
        return result

    def clear(self) -> None:
        """Clear all versions and reset the current index."""
        self._versions = []
        self._current_index = -1
