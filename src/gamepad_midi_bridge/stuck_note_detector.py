"""Stuck note detector — flags notes held too long, optionally auto-releases. Pure stdlib."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class StuckNoteConfig:
    """Configuration for stuck note detection."""

    enabled: bool = False
    stuck_after_s: float = 10.0
    auto_release: bool = False

    def __post_init__(self) -> None:
        """Clamp stuck_after_s to 0.5..3600 seconds."""
        if self.stuck_after_s < 0.5:
            self.stuck_after_s = 0.5
        elif self.stuck_after_s > 3600.0:
            self.stuck_after_s = 3600.0

    def to_dict(self) -> dict:
        """Round-trip to dict (for JSON serialization)."""
        return {
            "enabled": self.enabled,
            "stuck_after_s": self.stuck_after_s,
            "auto_release": self.auto_release,
        }

    @classmethod
    def from_dict(cls, data: dict) -> StuckNoteConfig:
        """Deserialize from dict, clamping values."""
        enabled = data.get("enabled", False)
        stuck_after_s = float(data.get("stuck_after_s", 10.0))
        auto_release = data.get("auto_release", False)

        return cls(
            enabled=enabled,
            stuck_after_s=stuck_after_s,
            auto_release=auto_release,
        )


class StuckNoteDetector:
    """Detect MIDI notes held past a threshold, optionally auto-release them."""

    def __init__(self, cfg: StuckNoteConfig):
        """Initialize with config."""
        self.cfg = cfg
        # Dict: (note, channel) -> start_time_s
        self._open: dict[tuple[int, int], float] = {}

    def on_note_on(self, note: int, channel: int, now_s: float) -> None:
        """Record a note-on. If already open, replace start time."""
        self._open[(note, channel)] = now_s

    def on_note_off(self, note: int, channel: int, now_s: float) -> None:
        """Remove a note-off from tracking (remove from _open)."""
        self._open.pop((note, channel), None)

    def stuck_notes(self, now_s: float) -> list[tuple[int, int, float]]:
        """
        Return list of (note, channel, age_s) for notes held longer than stuck_after_s.
        Sorted by age descending (oldest first).
        """
        if not self.cfg.enabled:
            return []

        result = []
        for (note, channel), start_time_s in self._open.items():
            age_s = now_s - start_time_s
            if age_s >= self.cfg.stuck_after_s:
                result.append((note, channel, age_s))

        # Sort by age descending
        result.sort(key=lambda x: x[2], reverse=True)
        return result

    def tick(self, now_s: float) -> list[tuple[int, int]]:
        """
        If auto_release is True, return (and remove from _open) stuck notes.
        Otherwise return empty list.
        """
        if not self.cfg.auto_release:
            return []

        stuck = self.stuck_notes(now_s)
        # Remove from _open and return (note, channel) tuples
        result = [(note, channel) for note, channel, _ in stuck]
        for note, channel in result:
            self._open.pop((note, channel), None)
        return result

    def panic(self) -> list[tuple[int, int]]:
        """Release all open notes and clear _open."""
        result = list(self._open.keys())
        self._open.clear()
        return result

    def open_count(self) -> int:
        """Return count of currently open notes."""
        return len(self._open)

    def oldest_age(self, now_s: float) -> Optional[float]:
        """Return age of oldest held note, or None if no notes open."""
        if not self._open:
            return None
        ages = [now_s - start_time_s for start_time_s in self._open.values()]
        return max(ages) if ages else None
