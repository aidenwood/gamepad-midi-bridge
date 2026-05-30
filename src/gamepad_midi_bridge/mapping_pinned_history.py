"""Mapping Pinned History Manager

Tracks recently-opened presets (with timestamps) and a separate pinned-to-top list.
Distinct from mapping_favourites (stars + tags) and mapping_banks (groups).
Pure stdlib only, no Qt dependencies.
"""

from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any


@dataclass
class HistoryEntry:
    """A single history entry for a preset."""

    preset_slug: str
    opened_at_s: float
    pinned: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict."""
        return asdict(self)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "HistoryEntry":
        """Deserialize from dict."""
        return HistoryEntry(
            preset_slug=data["preset_slug"],
            opened_at_s=data["opened_at_s"],
            pinned=data.get("pinned", False),
        )


@dataclass
class PinnedHistoryConfig:
    """Configuration for pinned history manager."""

    max_recent: int = 20
    max_pinned: int = 10

    def __post_init__(self):
        """Clamp config values."""
        self.max_recent = max(1, min(1000, self.max_recent))
        self.max_pinned = max(1, min(100, self.max_pinned))

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict."""
        return asdict(self)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "PinnedHistoryConfig":
        """Deserialize from dict."""
        return PinnedHistoryConfig(
            max_recent=data.get("max_recent", 20),
            max_pinned=data.get("max_pinned", 10),
        )


class MappingPinnedHistory:
    """Manages pinned and recently-opened presets."""

    def __init__(self, cfg: PinnedHistoryConfig):
        """Initialize with config.

        Args:
            cfg: PinnedHistoryConfig instance
        """
        self.cfg = cfg
        self._entries: Dict[str, HistoryEntry] = {}

    def record_open(self, preset_slug: str, now_s: float) -> HistoryEntry:
        """Record a preset as opened (or update its timestamp).

        If entry doesn't exist, creates it. Updates opened_at_s to now_s.
        Enforces max_recent cap by removing oldest unpinned entries when needed.

        Args:
            preset_slug: Preset identifier
            now_s: Current timestamp in seconds

        Returns:
            HistoryEntry with updated opened_at_s
        """
        if preset_slug not in self._entries:
            self._entries[preset_slug] = HistoryEntry(
                preset_slug=preset_slug, opened_at_s=now_s
            )
        else:
            self._entries[preset_slug].opened_at_s = now_s

        # Enforce max_recent cap (pinned entries don't count against the limit)
        self._enforce_max_recent()

        return self._entries[preset_slug]

    def _enforce_max_recent(self) -> None:
        """Remove oldest unpinned entries if total exceeds max_recent."""
        unpinned = [
            e for e in self._entries.values() if not e.pinned
        ]
        if len(unpinned) > self.cfg.max_recent:
            # Sort by opened_at_s ascending (oldest first)
            unpinned.sort(key=lambda e: e.opened_at_s)
            # Remove oldest until we're at max_recent
            to_remove_count = len(unpinned) - self.cfg.max_recent
            for entry in unpinned[:to_remove_count]:
                del self._entries[entry.preset_slug]

    def pin(self, preset_slug: str) -> bool:
        """Pin a preset to top.

        Only succeeds if entry exists, not already pinned, and total pinned < max_pinned.

        Args:
            preset_slug: Preset identifier

        Returns:
            True if newly pinned, False if not found, already pinned, or at max
        """
        if preset_slug not in self._entries:
            return False

        entry = self._entries[preset_slug]
        if entry.pinned:
            return False

        pinned_count = sum(1 for e in self._entries.values() if e.pinned)
        if pinned_count >= self.cfg.max_pinned:
            return False

        entry.pinned = True
        return True

    def unpin(self, preset_slug: str) -> bool:
        """Unpin a preset.

        Args:
            preset_slug: Preset identifier

        Returns:
            True if was pinned and now unpinned, False if not found or wasn't pinned
        """
        if preset_slug not in self._entries:
            return False

        entry = self._entries[preset_slug]
        if not entry.pinned:
            return False

        entry.pinned = False
        return True

    def recent(self, n: Optional[int] = None) -> List[HistoryEntry]:
        """Get most recently opened presets (unpinned only).

        Args:
            n: How many to return (uses max_recent if None)

        Returns:
            List of HistoryEntry sorted by opened_at_s descending
        """
        limit = n if n is not None else self.cfg.max_recent
        unpinned = [e for e in self._entries.values() if not e.pinned]
        return sorted(unpinned, key=lambda e: e.opened_at_s, reverse=True)[:limit]

    def pinned_list(self) -> List[HistoryEntry]:
        """Get all pinned entries.

        Returns:
            List of pinned HistoryEntry sorted by opened_at_s descending
        """
        pinned = [e for e in self._entries.values() if e.pinned]
        return sorted(pinned, key=lambda e: e.opened_at_s, reverse=True)

    def combined_view(self) -> List[HistoryEntry]:
        """Get pinned entries followed by recent (deduplicated).

        Pinned entries appear first, then unpinned recent entries.
        No entry appears twice.

        Returns:
            Combined list with pinned first, then recent
        """
        pinned = self.pinned_list()
        recent = self.recent()
        # Combine: pinned first, then recent (no duplicates by construction)
        return pinned + recent

    def pin_count(self) -> int:
        """Get number of currently pinned entries.

        Returns:
            Count of pinned entries
        """
        return sum(1 for e in self._entries.values() if e.pinned)

    def recent_count(self) -> int:
        """Get total number of entries (pinned + unpinned).

        Returns:
            Total entry count
        """
        return len(self._entries)

    def remove(self, preset_slug: str) -> bool:
        """Delete an entry.

        Args:
            preset_slug: Preset identifier

        Returns:
            True if entry existed and was deleted, False otherwise
        """
        if preset_slug in self._entries:
            del self._entries[preset_slug]
            return True
        return False

    def clear(self) -> None:
        """Clear all entries."""
        self._entries.clear()
