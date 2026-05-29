"""Note overlap detector — flags MIDI note collisions on same channel."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass
class NoteOverlapConfig:
    """Configuration for note overlap detection."""

    enabled: bool = False
    max_overlaps: int = 100

    def __post_init__(self) -> None:
        """Clamp max_overlaps to valid range."""
        self.max_overlaps = max(10, min(10000, self.max_overlaps))

    def to_dict(self) -> dict:
        """Round-trip to dict (for JSON serialization)."""
        return {
            "enabled": self.enabled,
            "max_overlaps": self.max_overlaps,
        }

    @classmethod
    def from_dict(cls, data: dict) -> NoteOverlapConfig:
        """Deserialize from dict, clamping values."""
        enabled = data.get("enabled", False)
        max_overlaps = max(10, min(10000, int(data.get("max_overlaps", 100))))

        return cls(
            enabled=enabled,
            max_overlaps=max_overlaps,
        )


@dataclass
class OverlapEvent:
    """Record of a detected note overlap (same note + channel pressed twice)."""

    note: int
    channel: int
    first_press_at_s: float
    second_press_at_s: float

    def to_dict(self) -> dict:
        """Round-trip to dict (for JSON serialization)."""
        return {
            "note": self.note,
            "channel": self.channel,
            "first_press_at_s": self.first_press_at_s,
            "second_press_at_s": self.second_press_at_s,
        }

    @classmethod
    def from_dict(cls, data: dict) -> OverlapEvent:
        """Deserialize from dict."""
        return cls(
            note=int(data.get("note", 0)),
            channel=int(data.get("channel", 0)),
            first_press_at_s=float(data.get("first_press_at_s", 0.0)),
            second_press_at_s=float(data.get("second_press_at_s", 0.0)),
        )


class NoteOverlapDetector:
    """Detect simultaneous MIDI note presses on the same note + channel."""

    def __init__(self, cfg: NoteOverlapConfig):
        """Initialize with config."""
        self.cfg = cfg
        # Track open notes: (note, channel) -> first_press_time_s
        self._open: Dict[Tuple[int, int], float] = {}
        # History of overlap events (FIFO, capped at max_overlaps)
        self._overlaps: List[OverlapEvent] = []

    def on_note_on(
        self, note: int, channel: int, now_s: float
    ) -> Optional[OverlapEvent]:
        """
        Record note_on event. Returns OverlapEvent if collision detected, else None.

        If (note, channel) is already being held, create and return an OverlapEvent.
        Otherwise, record the press time and return None.
        """
        if not self.cfg.enabled:
            return None

        key = (note, channel)

        if key in self._open:
            # Collision: same note+channel pressed while already held
            first_press = self._open[key]
            event = OverlapEvent(
                note=note,
                channel=channel,
                first_press_at_s=first_press,
                second_press_at_s=now_s,
            )
            self._overlaps.append(event)

            # FIFO eviction: keep only the most recent max_overlaps
            if len(self._overlaps) > self.cfg.max_overlaps:
                self._overlaps.pop(0)

            # Update the open time to the latest press (for multi-tap detection)
            self._open[key] = now_s

            return event
        else:
            # No collision: record this press
            self._open[key] = now_s
            return None

    def on_note_off(self, note: int, channel: int) -> None:
        """Record note_off event (clears the hold)."""
        key = (note, channel)
        self._open.pop(key, None)

    def recent(self, n: int = 20) -> List[OverlapEvent]:
        """Return the last n overlap events."""
        return self._overlaps[-n:]

    def count(self) -> int:
        """Return total number of overlap events recorded."""
        return len(self._overlaps)

    def count_per_note(self) -> Dict[int, int]:
        """Return a tally of overlaps per note number."""
        tally: Dict[int, int] = {}
        for event in self._overlaps:
            tally[event.note] = tally.get(event.note, 0) + 1
        return tally

    def clear(self) -> None:
        """Clear all overlap history and open holds."""
        self._overlaps = []
        self._open = {}

    def currently_overlapping(self) -> List[Tuple[int, int]]:
        """Return list of (note, channel) tuples currently being held."""
        return list(self._open.keys())
