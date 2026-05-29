"""
Mapping Tags Central Registry

Stores tags applied to mapping slugs with support for tag filtering,
suggested-tag completion, and reverse lookup (which presets have tag X?).
Pure stdlib, no Qt dependencies.
"""

from dataclasses import dataclass, asdict
from typing import Dict, List, Set, Tuple


@dataclass
class TagsConfig:
    """Configuration for mapping tags registry."""

    max_tags_per_preset: int = 20
    max_total_tags: int = 5000

    def __post_init__(self):
        """Clamp config values."""
        self.max_tags_per_preset = max(1, min(256, self.max_tags_per_preset))
        self.max_total_tags = max(100, min(1000000, self.max_total_tags))

    def to_dict(self) -> dict:
        """Serialize to dict."""
        return asdict(self)

    @staticmethod
    def from_dict(data: dict) -> "TagsConfig":
        """Deserialize from dict."""
        return TagsConfig(**data)


class MappingTagRegistry:
    """Central registry for mapping tags."""

    def __init__(self, cfg: TagsConfig):
        """Initialize with config.

        Args:
            cfg: TagsConfig instance
        """
        self.cfg = cfg
        self._preset_tags: Dict[str, Set[str]] = {}  # preset_slug -> set of tags
        self._tag_index: Dict[str, Set[str]] = {}  # tag -> set of preset_slugs

    def add_tag(self, preset_slug: str, tag: str) -> bool:
        """Add a tag to a preset.

        Normalizes tag to lowercase and strips whitespace.
        Rejects empty/whitespace-only tags.
        Returns True if tag was added (not already present and under max).
        Returns False if tag already present, max tags exceeded, or tag invalid.

        Args:
            preset_slug: Preset identifier
            tag: Tag to add

        Returns:
            True if added, False otherwise
        """
        # Normalize
        tag = tag.lower().strip()

        # Reject empty
        if not tag:
            return False

        # Get or create preset tag set
        if preset_slug not in self._preset_tags:
            self._preset_tags[preset_slug] = set()

        # Already present
        if tag in self._preset_tags[preset_slug]:
            return False

        # Check preset-level max
        if len(self._preset_tags[preset_slug]) >= self.cfg.max_tags_per_preset:
            return False

        # Check registry-level max (only count unique tags)
        if len(self._tag_index) >= self.cfg.max_total_tags and tag not in self._tag_index:
            return False

        # Add to preset
        self._preset_tags[preset_slug].add(tag)

        # Add to index
        if tag not in self._tag_index:
            self._tag_index[tag] = set()
        self._tag_index[tag].add(preset_slug)

        return True

    def remove_tag(self, preset_slug: str, tag: str) -> bool:
        """Remove a tag from a preset.

        Returns True if tag was removed, False if tag not found.

        Args:
            preset_slug: Preset identifier
            tag: Tag to remove

        Returns:
            True if removed, False otherwise
        """
        tag = tag.lower().strip()

        if preset_slug not in self._preset_tags:
            return False

        if tag not in self._preset_tags[preset_slug]:
            return False

        # Remove from preset
        self._preset_tags[preset_slug].discard(tag)

        # Remove from index
        if tag in self._tag_index:
            self._tag_index[tag].discard(preset_slug)
            if not self._tag_index[tag]:
                del self._tag_index[tag]

        # Clean up empty preset entry
        if not self._preset_tags[preset_slug]:
            del self._preset_tags[preset_slug]

        return True

    def tags_for(self, preset_slug: str) -> List[str]:
        """Get all tags for a preset.

        Returns sorted list of tags.

        Args:
            preset_slug: Preset identifier

        Returns:
            Sorted list of tags
        """
        if preset_slug not in self._preset_tags:
            return []
        return sorted(self._preset_tags[preset_slug])

    def presets_with(self, tag: str) -> List[str]:
        """Get all presets with a given tag.

        Returns sorted list of preset slugs.

        Args:
            tag: Tag to search for

        Returns:
            Sorted list of preset slugs
        """
        tag = tag.lower().strip()
        if tag not in self._tag_index:
            return []
        return sorted(self._tag_index[tag])

    def find_any(self, tags: List[str]) -> List[str]:
        """Find presets with ANY of the given tags (union).

        Args:
            tags: List of tags to search for

        Returns:
            Sorted list of preset slugs
        """
        if not tags:
            return []

        result: Set[str] = set()
        for tag in tags:
            tag = tag.lower().strip()
            if tag in self._tag_index:
                result.update(self._tag_index[tag])

        return sorted(result)

    def find_all(self, tags: List[str]) -> List[str]:
        """Find presets with ALL of the given tags (intersection).

        Args:
            tags: List of tags to search for

        Returns:
            Sorted list of preset slugs
        """
        if not tags:
            return []

        # Normalize tags
        normalized = [tag.lower().strip() for tag in tags]

        # Get first tag's presets as starting set
        result: Set[str] = set(self._tag_index.get(normalized[0], []))

        # Intersect with remaining tags
        for tag in normalized[1:]:
            result &= self._tag_index.get(tag, set())

        return sorted(result)

    def all_tags(self) -> List[Tuple[str, int]]:
        """Get all unique tags with their counts.

        Returns list of (tag, count) tuples sorted by count descending.

        Returns:
            List of (tag, count) tuples
        """
        tags_with_counts = [
            (tag, len(presets)) for tag, presets in self._tag_index.items()
        ]
        return sorted(tags_with_counts, key=lambda x: x[1], reverse=True)

    def tag_count(self) -> int:
        """Get total unique tags.

        Returns:
            Count of unique tags
        """
        return len(self._tag_index)

    def preset_count(self) -> int:
        """Get total preset slugs with at least one tag.

        Returns:
            Count of presets with tags
        """
        return len(self._preset_tags)

    def suggest(self, prefix: str, limit: int = 10) -> List[str]:
        """Get tag suggestions by prefix (case-insensitive).

        Returns existing tags starting with prefix, sorted by frequency
        (count descending).

        Args:
            prefix: Prefix to search for
            limit: Maximum suggestions to return

        Returns:
            List of suggested tags
        """
        prefix = prefix.lower().strip()
        if not prefix:
            return []

        # Find all tags starting with prefix
        matching = [
            (tag, len(presets))
            for tag, presets in self._tag_index.items()
            if tag.startswith(prefix)
        ]

        # Sort by frequency (count) descending, then alphabetically
        matching.sort(key=lambda x: (-x[1], x[0]))

        # Return just the tag names, limited
        return [tag for tag, _ in matching[:limit]]

    def rename_tag(self, old: str, new: str) -> int:
        """Rename a tag globally.

        Rejects if new tag already exists.
        Returns count of affected presets.

        Args:
            old: Old tag name
            new: New tag name

        Returns:
            Count of affected presets, or 0 if rename failed
        """
        old = old.lower().strip()
        new = new.lower().strip()

        # Reject empty tags
        if not old or not new:
            return 0

        # Reject if old doesn't exist
        if old not in self._tag_index:
            return 0

        # Reject if new already exists and is different
        if new in self._tag_index and old != new:
            return 0

        # No-op if identical
        if old == new:
            return 0

        # Get all presets with old tag
        presets = list(self._tag_index[old])

        # Rename in all presets
        for preset_slug in presets:
            self._preset_tags[preset_slug].discard(old)
            self._preset_tags[preset_slug].add(new)

        # Update index
        self._tag_index[new] = set(presets)
        del self._tag_index[old]

        return len(presets)

    def clear(self) -> None:
        """Clear all tags."""
        self._preset_tags.clear()
        self._tag_index.clear()
