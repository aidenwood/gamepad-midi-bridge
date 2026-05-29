"""Setlist navigator — manage preset slugs with next/prev/jump/bookmark/history.

SetlistNavigator manages a list of SetlistEntry items (slug + metadata), with
navigation commands (next, prev, jump_to, back) and bookmark support. Tracks
navigation history for back() traversal.

Pure stdlib, no Qt dependencies.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class SetlistEntry:
    """A single entry in a setlist.

    Attributes:
        slug: Unique identifier for this preset (e.g., "lead", "pad", "bass").
        display_name: Optional human-readable name (defaults to slug if empty).
        notes: Optional notes or metadata about this entry.
        bookmarked: Whether this entry is bookmarked for quick navigation.
    """
    slug: str = ""
    display_name: str = ""
    notes: str = ""
    bookmarked: bool = False

    def to_dict(self) -> dict:
        """Serialize to JSON-friendly dict."""
        return {
            "slug": self.slug,
            "display_name": self.display_name,
            "notes": self.notes,
            "bookmarked": self.bookmarked,
        }

    @classmethod
    def from_dict(cls, d: dict) -> SetlistEntry:
        """Deserialize from JSON-friendly dict."""
        return cls(
            slug=str(d.get("slug", "")),
            display_name=str(d.get("display_name", "")),
            notes=str(d.get("notes", "")),
            bookmarked=bool(d.get("bookmarked", False)),
        )


@dataclass
class SetlistNavigatorConfig:
    """Configuration for SetlistNavigator.

    Attributes:
        loop: If True, next() at the end wraps to first; prev() at start wraps to last.
        max_history: Maximum number of history entries to retain (clamped 5..10000).
    """
    loop: bool = False
    max_history: int = 50

    def __post_init__(self) -> None:
        """Clamp max_history to valid range."""
        self.max_history = max(5, min(10000, self.max_history))

    def to_dict(self) -> dict:
        """Serialize to JSON-friendly dict."""
        return {
            "loop": self.loop,
            "max_history": self.max_history,
        }

    @classmethod
    def from_dict(cls, d: dict) -> SetlistNavigatorConfig:
        """Deserialize from JSON-friendly dict."""
        return cls(
            loop=bool(d.get("loop", False)),
            max_history=int(d.get("max_history", 50)),
        )


class SetlistNavigator:
    """Manages navigation through a setlist of preset slugs.

    Supports next/prev/jump/back/bookmark operations, with configurable loop
    and history retention.
    """

    def __init__(
        self,
        cfg: SetlistNavigatorConfig,
        entries: Optional[List[SetlistEntry]] = None,
    ) -> None:
        """Initialize navigator with config and optional entries.

        Args:
            cfg: SetlistNavigatorConfig instance.
            entries: Optional list of SetlistEntry items. If None, starts empty.
        """
        self.cfg = cfg
        self.entries = list(entries) if entries else []
        self._index: int = 0
        self._history: List[int] = []

    # ================================================================ navigation core

    def current(self) -> Optional[SetlistEntry]:
        """Return the currently selected entry, or None if list is empty."""
        if 0 <= self._index < len(self.entries):
            return self.entries[self._index]
        return None

    def next(self) -> Optional[SetlistEntry]:
        """Advance to next entry.

        If at the last entry:
          - If loop=False, stay at last entry.
          - If loop=True, wrap to first entry.

        Pushes prior index to history before advancing.

        Returns:
            The new current entry, or None if list is empty.
        """
        if not self.entries:
            return None

        # Record current index in history before moving
        if 0 <= self._index < len(self.entries):
            self._history.append(self._index)
            # Clamp history to max_history
            if len(self._history) > self.cfg.max_history:
                self._history.pop(0)

        # Advance or wrap
        if self._index >= len(self.entries) - 1:
            # At or beyond last entry
            if self.cfg.loop:
                self._index = 0
            # else stay at last
        else:
            self._index += 1

        return self.current()

    def prev(self) -> Optional[SetlistEntry]:
        """Decrement to previous entry.

        If at the first entry:
          - If loop=False, stay at first entry.
          - If loop=True, wrap to last entry.

        Pushes prior index to history before moving.

        Returns:
            The new current entry, or None if list is empty.
        """
        if not self.entries:
            return None

        # Record current index in history before moving
        if 0 <= self._index < len(self.entries):
            self._history.append(self._index)
            # Clamp history to max_history
            if len(self._history) > self.cfg.max_history:
                self._history.pop(0)

        # Decrement or wrap
        if self._index <= 0:
            # At or before first entry
            if self.cfg.loop:
                self._index = len(self.entries) - 1
            # else stay at first
        else:
            self._index -= 1

        return self.current()

    def jump_to(self, slug: str) -> Optional[SetlistEntry]:
        """Jump to the entry with the given slug.

        Pushes prior index to history before jumping.

        Args:
            slug: The slug to search for.

        Returns:
            The entry if found and set as current, None otherwise.
        """
        if not self.entries:
            return None

        # Search for slug
        for i, entry in enumerate(self.entries):
            if entry.slug == slug:
                # Record current index in history before moving
                if 0 <= self._index < len(self.entries):
                    self._history.append(self._index)
                    # Clamp history to max_history
                    if len(self._history) > self.cfg.max_history:
                        self._history.pop(0)

                self._index = i
                return self.current()

        return None

    def back(self) -> Optional[SetlistEntry]:
        """Return to the previous entry in history.

        Pops the most recent index from history and sets it as current.

        Returns:
            The entry at the restored index, or None if no history or empty list.
        """
        if not self._history:
            return None

        self._index = self._history.pop()
        return self.current()

    # ================================================================ bookmarks

    def bookmark_current(self) -> bool:
        """Toggle bookmark on the current entry.

        Returns:
            The new bookmarked state (True if now bookmarked, False if not).
            Returns False if no current entry.
        """
        current = self.current()
        if current is None:
            return False

        current.bookmarked = not current.bookmarked
        return current.bookmarked

    def bookmarks(self) -> List[SetlistEntry]:
        """Return all bookmarked entries (in order)."""
        return [e for e in self.entries if e.bookmarked]

    def goto_first_bookmark(self) -> Optional[SetlistEntry]:
        """Jump to the first bookmarked entry.

        Returns:
            The first bookmarked entry if one exists, None otherwise.
        """
        for entry in self.entries:
            if entry.bookmarked:
                return self.jump_to(entry.slug)
        return None

    # ================================================================ list management

    def progress(self) -> Tuple[int, int]:
        """Return (current_index_1based, total_entries) for UI display.

        Useful for showing "Song 3 of 12" style progress.

        Returns:
            Tuple of (1-based current position, total entries).
            Returns (0, 0) if list is empty.
        """
        if not self.entries:
            return (0, 0)
        return (self._index + 1, len(self.entries))

    def add(self, entry: SetlistEntry) -> None:
        """Append an entry to the setlist.

        Args:
            entry: SetlistEntry to append.
        """
        self.entries.append(entry)

    def remove(self, slug: str) -> bool:
        """Remove the entry with the given slug.

        If the removed entry was at or before current index, the index
        is decremented to keep the current position sensible.

        Args:
            slug: The slug to remove.

        Returns:
            True if an entry was removed, False if not found.
        """
        initial_len = len(self.entries)

        # Find and remove
        removed_index = None
        for i, entry in enumerate(self.entries):
            if entry.slug == slug:
                removed_index = i
                break

        if removed_index is None:
            return False

        self.entries.pop(removed_index)

        # Adjust index if needed
        if removed_index <= self._index and self._index > 0:
            self._index -= 1

        # Clamp index to valid range
        if self._index >= len(self.entries) and self.entries:
            self._index = len(self.entries) - 1
        elif not self.entries:
            self._index = 0

        return True

    def clear(self) -> None:
        """Clear all entries, reset index and history."""
        self.entries.clear()
        self._index = 0
        self._history.clear()
