"""Pure-function note retrigger detector for chatter / rapid re-pressing detection.

This module detects rapid same-note repeats, useful for identifying accidental
double-presses, electrical chattering, or unintended quick re-presses of a button
mapped to a MIDI note.

Features:
  - Retrigger detection: Track note_on events and detect when the same note
                         on the same channel occurs within a threshold time window.
  - Configurable gap threshold: min_gap_ms defines the boundary (default 50 ms).
  - Per-note tracking: Different notes and channels tracked independently.
  - Event history: Maintains circular buffer of detected retriggers up to max_history.
  - Statistics: Count, mean gap, per-note tally, summary snapshot.
  - Pure stdlib: No Qt, no external deps, deterministic and testable.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class RetriggerEvent:
    """A detected retrigger event: rapid same-note re-press.

    Attributes:
        note: MIDI note number (0..127).
        channel: MIDI channel (0..15).
        first_at_s: Timestamp of the first note_on in seconds.
        second_at_s: Timestamp of the second note_on (the retrigger) in seconds.
        gap_ms: Gap between first and second, in milliseconds.
    """
    note: int
    channel: int
    first_at_s: float
    second_at_s: float
    gap_ms: float

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "note": self.note,
            "channel": self.channel,
            "first_at_s": self.first_at_s,
            "second_at_s": self.second_at_s,
            "gap_ms": self.gap_ms,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RetriggerEvent:
        """Deserialize from a dict (e.g. from JSON)."""
        return cls(
            note=data["note"],
            channel=data["channel"],
            first_at_s=data["first_at_s"],
            second_at_s=data["second_at_s"],
            gap_ms=data["gap_ms"],
        )


@dataclass
class RetriggerConfig:
    """Configuration for note retrigger detection.

    Attributes:
        enabled: Whether retrigger detection is active.
        min_gap_ms: Threshold gap in milliseconds. Gaps shorter than this
                   are considered retrigggers. Clamped to 1..2000 on construction.
                   Default: 50 ms (typical double-tap / contact bounce window).
        max_history: Maximum number of retrigger events to keep in history.
                    Older events are evicted in FIFO order. Clamped to 10..100000
                    on construction. Default: 200.
    """
    enabled: bool = False
    min_gap_ms: float = 50.0
    max_history: int = 200

    def __post_init__(self) -> None:
        """Normalize and clamp all values after construction."""
        # Clamp min_gap_ms to 1..2000.
        self.min_gap_ms = max(1.0, min(2000.0, self.min_gap_ms))

        # Clamp max_history to 10..100000.
        self.max_history = max(10, min(100000, self.max_history))

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "enabled": self.enabled,
            "min_gap_ms": self.min_gap_ms,
            "max_history": self.max_history,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RetriggerConfig:
        """Deserialize from a dict (e.g. from JSON).

        Missing keys fall back to dataclass defaults. __post_init__ handles
        clamping.
        """
        return cls(
            enabled=data.get("enabled", False),
            min_gap_ms=data.get("min_gap_ms", 50.0),
            max_history=data.get("max_history", 200),
        )


class NoteRetriggerDetector:
    """Stateful detector for rapid same-note repeats.

    Maintains per-(note, channel) timing state to detect retriggerings
    and accumulates a history of detected events with statistics.
    """

    def __init__(self, cfg: RetriggerConfig) -> None:
        """Initialize detector with config.

        Args:
            cfg: RetriggerConfig describing detection thresholds and history limits.
        """
        self.cfg = cfg
        self._last_at: Dict[Tuple[int, int], float] = {}  # (note, channel) → timestamp
        self._retriggers: List[RetriggerEvent] = []

    def on_note_on(
        self, note: int, channel: int, now_s: float
    ) -> Optional[RetriggerEvent]:
        """Process a note_on event and detect retriggers.

        If the same (note, channel) pair has a recent history (within min_gap_ms),
        emit a RetriggerEvent. Otherwise, update the tracking state for next check.

        Args:
            note: MIDI note number (0..127).
            channel: MIDI channel (0..15).
            now_s: Current time in seconds.

        Returns:
            RetriggerEvent if a retrigger is detected, else None.
        """
        key = (note, channel)

        # Check if we have a prior note_on for this (note, channel).
        if key in self._last_at:
            first_at = self._last_at[key]
            gap_s = now_s - first_at
            gap_ms = gap_s * 1000.0

            # Is this a retrigger (gap too short)?
            if gap_ms < self.cfg.min_gap_ms:
                # Emit event.
                event = RetriggerEvent(
                    note=note,
                    channel=channel,
                    first_at_s=first_at,
                    second_at_s=now_s,
                    gap_ms=gap_ms,
                )
                self._retriggers.append(event)

                # Enforce max_history (FIFO eviction).
                while len(self._retriggers) > self.cfg.max_history:
                    self._retriggers.pop(0)

                return event
            else:
                # Gap is large enough; this is a new legitimate press. Update the timestamp.
                self._last_at[key] = now_s
        else:
            # First note_on for this (note, channel). Record the timestamp.
            self._last_at[key] = now_s

        return None

    def recent(self, n: int = 20) -> List[RetriggerEvent]:
        """Return the last n retrigger events.

        Args:
            n: Number of events to return (defaults to 20).

        Returns:
            List of the last n RetriggerEvent objects, newest first.
        """
        return list(reversed(self._retriggers[-n:]))

    def count(self) -> int:
        """Total number of detected retrigger events."""
        return len(self._retriggers)

    def count_per_note(self) -> Dict[int, int]:
        """Tally retrigger count grouped by MIDI note number.

        Returns:
            Dict mapping note → count.
        """
        tally: Dict[int, int] = {}
        for event in self._retriggers:
            tally[event.note] = tally.get(event.note, 0) + 1
        return tally

    def mean_gap_ms(self) -> Optional[float]:
        """Average gap (in ms) of all detected retriggers.

        Returns:
            Mean gap_ms, or None if no retriggers have been detected.
        """
        if not self._retriggers:
            return None
        total = sum(event.gap_ms for event in self._retriggers)
        return total / len(self._retriggers)

    def clear(self) -> None:
        """Reset all state: clear history and last-note tracking."""
        self._retriggers.clear()
        self._last_at.clear()

    def summary(self) -> Dict[str, Any]:
        """Return a snapshot of detection statistics.

        Returns:
            Dict with keys:
              - "count": Total retrigger events detected.
              - "mean_gap_ms": Average gap (None if no events).
              - "min_gap_ms": Minimum gap (None if no events).
              - "max_gap_ms": Maximum gap (None if no events).
        """
        if not self._retriggers:
            return {
                "count": 0,
                "mean_gap_ms": None,
                "min_gap_ms": None,
                "max_gap_ms": None,
            }

        gaps = [event.gap_ms for event in self._retriggers]
        return {
            "count": len(self._retriggers),
            "mean_gap_ms": self.mean_gap_ms(),
            "min_gap_ms": min(gaps),
            "max_gap_ms": max(gaps),
        }
