"""
Mapping Favourites Manager

Tracks user-starred mappings with ratings, recently-played list, and pinned-to-top list.
Pure stdlib, no Qt dependencies.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional


@dataclass
class FavouriteEntry:
    """A single favourite mapping entry."""

    preset_slug: str
    stars: int = 0
    pinned: bool = False
    last_played_at: Optional[float] = None
    play_count: int = 0
    tags: List[str] = field(default_factory=list)
    notes: str = ""

    def __post_init__(self):
        """Clamp stars to 0..5."""
        self.stars = max(0, min(5, self.stars))

    def to_dict(self) -> dict:
        """Serialize to dict."""
        return asdict(self)

    @staticmethod
    def from_dict(data: dict) -> "FavouriteEntry":
        """Deserialize from dict."""
        return FavouriteEntry(**data)


@dataclass
class FavouritesConfig:
    """Configuration for favourites manager."""

    max_entries: int = 500
    max_recently_played: int = 20

    def __post_init__(self):
        """Clamp config values."""
        self.max_entries = max(10, min(100000, self.max_entries))
        self.max_recently_played = max(1, min(1000, self.max_recently_played))

    def to_dict(self) -> dict:
        """Serialize to dict."""
        return asdict(self)

    @staticmethod
    def from_dict(data: dict) -> "FavouritesConfig":
        """Deserialize from dict."""
        return FavouritesConfig(**data)


class MappingFavourites:
    """Manages favourites for MIDI mappings."""

    def __init__(self, cfg: FavouritesConfig):
        """Initialize with config.

        Args:
            cfg: FavouritesConfig instance
        """
        self.cfg = cfg
        self._entries: Dict[str, FavouriteEntry] = {}

    def set_stars(self, preset_slug: str, stars: int) -> FavouriteEntry:
        """Set star rating (0..5) for a mapping.

        Creates entry if missing. Returns the entry.

        Args:
            preset_slug: Preset identifier
            stars: Rating 0..5 (will be clamped)

        Returns:
            FavouriteEntry with updated stars
        """
        if preset_slug not in self._entries:
            self._entries[preset_slug] = FavouriteEntry(preset_slug=preset_slug)

        entry = self._entries[preset_slug]
        entry.stars = max(0, min(5, stars))
        return entry

    def pin(self, preset_slug: str) -> FavouriteEntry:
        """Pin a mapping to top.

        Creates entry if missing. Returns the entry.

        Args:
            preset_slug: Preset identifier

        Returns:
            FavouriteEntry with pinned=True
        """
        if preset_slug not in self._entries:
            self._entries[preset_slug] = FavouriteEntry(preset_slug=preset_slug)

        self._entries[preset_slug].pinned = True
        return self._entries[preset_slug]

    def unpin(self, preset_slug: str) -> FavouriteEntry:
        """Unpin a mapping.

        Creates entry if missing. Returns the entry.

        Args:
            preset_slug: Preset identifier

        Returns:
            FavouriteEntry with pinned=False
        """
        if preset_slug not in self._entries:
            self._entries[preset_slug] = FavouriteEntry(preset_slug=preset_slug)

        self._entries[preset_slug].pinned = False
        return self._entries[preset_slug]

    def mark_played(self, preset_slug: str, now_s: float) -> FavouriteEntry:
        """Mark a mapping as played and increment counters.

        Creates entry if missing. Returns the entry.

        Args:
            preset_slug: Preset identifier
            now_s: Current timestamp in seconds

        Returns:
            FavouriteEntry with updated play_count and last_played_at
        """
        if preset_slug not in self._entries:
            self._entries[preset_slug] = FavouriteEntry(preset_slug=preset_slug)

        entry = self._entries[preset_slug]
        entry.play_count += 1
        entry.last_played_at = now_s
        return entry

    def get(self, preset_slug: str) -> Optional[FavouriteEntry]:
        """Get entry by preset_slug.

        Args:
            preset_slug: Preset identifier

        Returns:
            FavouriteEntry or None if not found
        """
        return self._entries.get(preset_slug)

    def pinned_list(self) -> List[FavouriteEntry]:
        """Get all pinned entries.

        Returns:
            List of pinned FavouriteEntry objects (unsorted)
        """
        return [e for e in self._entries.values() if e.pinned]

    def top_starred(self, min_stars: int = 4) -> List[FavouriteEntry]:
        """Get high-rated mappings.

        Args:
            min_stars: Minimum stars to include (default 4)

        Returns:
            List of entries with stars >= min_stars, sorted by stars descending
        """
        filtered = [e for e in self._entries.values() if e.stars >= min_stars]
        return sorted(filtered, key=lambda e: e.stars, reverse=True)

    def recently_played(self, n: int = 10) -> List[FavouriteEntry]:
        """Get recently played mappings.

        Args:
            n: How many to return

        Returns:
            List of entries sorted by last_played_at descending,
            capped at min(n, max_recently_played)
        """
        limit = min(n, self.cfg.max_recently_played)
        with_played = [
            e for e in self._entries.values() if e.last_played_at is not None
        ]
        return sorted(with_played, key=lambda e: e.last_played_at, reverse=True)[
            :limit
        ]

    def most_played(self, n: int = 10) -> List[FavouriteEntry]:
        """Get most frequently played mappings.

        Args:
            n: How many to return

        Returns:
            List of entries sorted by play_count descending
        """
        with_count = [e for e in self._entries.values() if e.play_count > 0]
        return sorted(with_count, key=lambda e: e.play_count, reverse=True)[:n]

    def remove(self, preset_slug: str) -> bool:
        """Delete a favourite entry.

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
        """Clear all favourite entries."""
        self._entries.clear()

    def add_tag(self, preset_slug: str, tag: str) -> bool:
        """Add a tag to a mapping (deduped).

        Creates entry if missing.

        Args:
            preset_slug: Preset identifier
            tag: Tag string

        Returns:
            True if tag was added, False if it already existed
        """
        if preset_slug not in self._entries:
            self._entries[preset_slug] = FavouriteEntry(preset_slug=preset_slug)

        entry = self._entries[preset_slug]
        if tag not in entry.tags:
            entry.tags.append(tag)
            return True
        return False

    def remove_tag(self, preset_slug: str, tag: str) -> bool:
        """Remove a tag from a mapping.

        Args:
            preset_slug: Preset identifier
            tag: Tag string

        Returns:
            True if tag was removed, False if it didn't exist
        """
        entry = self.get(preset_slug)
        if entry and tag in entry.tags:
            entry.tags.remove(tag)
            return True
        return False

    def find_by_tag(self, tag: str) -> List[FavouriteEntry]:
        """Find all entries with a given tag.

        Args:
            tag: Tag string

        Returns:
            List of matching FavouriteEntry objects (unsorted)
        """
        return [e for e in self._entries.values() if tag in e.tags]
