"""Setlist shuffle helper — randomize setlist order with pinned positions and grouping constraints.

Randomizes a setlist (list of entries) with optional pinned positions (some entries stay in place)
and grouping constraints (avoid adjacent entries with matching tags).

Pure stdlib + random.Random, no Qt dependencies.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from random import Random
from typing import List, Optional


@dataclass
class ShuffleConfig:
    """Configuration for setlist shuffling.

    Attributes:
        seed: Optional seed for random.Random(). If None, random.Random() uses system entropy.
        pin_positions: List of 0-based indices that should remain in place during shuffle.
        avoid_adjacent_tags: List of tag strings. If non-empty, shuffle attempts to prevent
            two adjacent entries that both have a tag in this list.
        max_attempts: Maximum number of shuffle attempts when satisfying avoid_adjacent_tags.
            Clamped to 1..10000.
    """
    seed: Optional[int] = None
    pin_positions: List[int] = field(default_factory=list)
    avoid_adjacent_tags: List[str] = field(default_factory=list)
    max_attempts: int = 100

    def __post_init__(self) -> None:
        """Clamp max_attempts to valid range."""
        self.max_attempts = max(1, min(10000, self.max_attempts))

    def to_dict(self) -> dict:
        """Serialize to JSON-friendly dict."""
        return {
            "seed": self.seed,
            "pin_positions": list(self.pin_positions),
            "avoid_adjacent_tags": list(self.avoid_adjacent_tags),
            "max_attempts": self.max_attempts,
        }

    @classmethod
    def from_dict(cls, d: dict) -> ShuffleConfig:
        """Deserialize from JSON-friendly dict."""
        return cls(
            seed=d.get("seed"),
            pin_positions=list(d.get("pin_positions", [])),
            avoid_adjacent_tags=list(d.get("avoid_adjacent_tags", [])),
            max_attempts=int(d.get("max_attempts", 100)),
        )


def validate_pin_positions(entries: List[dict], pin_positions: List[int]) -> List[int]:
    """Sanitize pin_positions by removing out-of-range indices.

    Args:
        entries: List of entries to shuffle.
        pin_positions: Proposed list of pinned indices.

    Returns:
        New list with only valid (0-based) indices that exist in entries.
    """
    n = len(entries)
    return [idx for idx in pin_positions if 0 <= idx < n]


def has_adjacent_tag_conflict(entries: List[dict], avoid_tags: List[str]) -> bool:
    """Check if any adjacent entries share a tag in avoid_tags.

    Args:
        entries: List of entries (each with optional 'tags' key, list of strings).
        avoid_tags: List of tag strings to check for conflicts.

    Returns:
        True if any adjacent pair both have a tag in avoid_tags, False otherwise.
    """
    if not avoid_tags or len(entries) < 2:
        return False

    for i in range(len(entries) - 1):
        entry_i = entries[i]
        entry_j = entries[i + 1]

        tags_i = set(entry_i.get("tags", []))
        tags_j = set(entry_j.get("tags", []))
        avoid_set = set(avoid_tags)

        # If both entries have a tag in avoid_tags, conflict exists
        if tags_i & avoid_set and tags_j & avoid_set:
            return True

    return False


def safe_swap(
    entries: List[dict],
    i: int,
    j: int,
    pin_positions: List[int]
) -> List[dict]:
    """Swap entries at indices i and j, unless either is pinned.

    Args:
        entries: List of entries to mutate.
        i: First index to swap.
        j: Second index to swap.
        pin_positions: List of indices that cannot be swapped.

    Returns:
        New list with swap applied (if allowed), or copy of input (if either pinned).
    """
    pin_set = set(pin_positions)

    # If either position is pinned, return unchanged copy
    if i in pin_set or j in pin_set:
        return list(entries)

    # Perform swap
    result = list(entries)
    result[i], result[j] = result[j], result[i]
    return result


def reverse_unpinned(entries: List[dict], pin_positions: List[int]) -> List[dict]:
    """Reverse all unpinned entries while keeping pinned ones in place.

    Args:
        entries: List of entries.
        pin_positions: List of indices to keep in place.

    Returns:
        New list with unpinned entries reversed.
    """
    pin_set = set(pin_positions)

    # Extract unpinned entries and their original positions
    unpinned = []
    unpinned_indices = []
    for idx, entry in enumerate(entries):
        if idx not in pin_set:
            unpinned.append(entry)
            unpinned_indices.append(idx)

    # Reverse unpinned
    unpinned.reverse()

    # Build result with unpinned reversed and pinned in original positions
    result = list(entries)
    for new_idx, orig_idx in enumerate(unpinned_indices):
        result[orig_idx] = unpinned[new_idx]

    return result


def shuffle(entries: List[dict], cfg: ShuffleConfig) -> List[dict]:
    """Shuffle entries with pinned positions and optional tag-based grouping constraints.

    Returns a shuffled copy of entries. Entries at indices in cfg.pin_positions stay in place.
    Other entries are shuffled using a seeded random.Random(cfg.seed).

    If cfg.avoid_adjacent_tags is non-empty, shuffle repeats up to cfg.max_attempts until
    no two adjacent entries share a tag in the avoid list. If never satisfied, returns the
    last attempt.

    Args:
        entries: List of entries to shuffle (each entry is a dict).
        cfg: ShuffleConfig with seed, pin_positions, avoid_adjacent_tags, max_attempts.

    Returns:
        New shuffled list. If entries is empty or has one entry, returns a copy.
    """
    if len(entries) <= 1:
        return list(entries)

    # Sanitize pin_positions
    pin_positions = validate_pin_positions(entries, cfg.pin_positions)
    pin_set = set(pin_positions)

    # Create seeded RNG
    rng = Random(cfg.seed)

    # Extract unpinned entries
    unpinned = []
    unpinned_indices = []
    for idx, entry in enumerate(entries):
        if idx not in pin_set:
            unpinned.append(entry)
            unpinned_indices.append(idx)

    # If no unpinned entries, return copy as-is
    if not unpinned:
        return list(entries)

    # Attempt shuffle with constraint satisfaction
    best_attempt = None
    for attempt_num in range(cfg.max_attempts):
        # Shuffle unpinned entries
        rng.shuffle(unpinned)

        # Build full result with pinned entries in place
        result = list(entries)
        for new_idx, orig_idx in enumerate(unpinned_indices):
            result[orig_idx] = unpinned[new_idx]

        best_attempt = result

        # Check if constraint satisfied
        if not has_adjacent_tag_conflict(result, cfg.avoid_adjacent_tags):
            return result

    # Return last attempt (best effort)
    return best_attempt or list(entries)
