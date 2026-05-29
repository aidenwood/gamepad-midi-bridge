"""Guitar-style hammer-on and pull-off detection.

Detects when a note B is pressed while note A is still held, where B is higher
than A (hammer-on), and when a held note is released while a higher note is
still held (pull-off). Pure stdlib, no Qt.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set


@dataclass
class HammerEvent:
    """Represents a detected hammer-on or pull-off event.

    Attributes:
        kind: "hammer_on" or "pull_off".
        first_note: The note that was held first (lower in hammer-on).
        second_note: The note that triggered the event (higher in hammer-on).
        channel: MIDI channel (0..15).
        time_s: Timestamp in seconds when the event was detected.
    """

    kind: str  # "hammer_on" or "pull_off"
    first_note: int  # Note held first
    second_note: int  # Note that triggered the event
    channel: int  # MIDI channel
    time_s: float  # Timestamp in seconds

    def to_dict(self) -> dict:
        """Serialize to dict."""
        return {
            "kind": self.kind,
            "first_note": self.first_note,
            "second_note": self.second_note,
            "channel": self.channel,
            "time_s": self.time_s,
        }

    @staticmethod
    def from_dict(data: dict) -> HammerEvent:
        """Deserialize from dict."""
        return HammerEvent(
            kind=data.get("kind", "hammer_on"),
            first_note=data.get("first_note", 0),
            second_note=data.get("second_note", 0),
            channel=data.get("channel", 0),
            time_s=data.get("time_s", 0.0),
        )


@dataclass
class HammerOnConfig:
    """Configuration for hammer-on/pull-off detection.

    Attributes:
        enabled: Whether detection is active.
        max_history: Maximum number of events to keep (clamped 10..100000).
        min_interval_semitones: Minimum semitone distance to trigger (clamped 1..24).
        max_interval_semitones: Maximum semitone distance to trigger (clamped 1..36).
    """

    enabled: bool = False
    max_history: int = 200
    min_interval_semitones: int = 1
    max_interval_semitones: int = 12

    def __post_init__(self):
        """Clamp all numeric fields to valid ranges."""
        self.max_history = max(10, min(100000, self.max_history))
        self.min_interval_semitones = max(1, min(24, self.min_interval_semitones))
        self.max_interval_semitones = max(1, min(36, self.max_interval_semitones))

    def to_dict(self) -> dict:
        """Serialize to dict."""
        return {
            "enabled": self.enabled,
            "max_history": self.max_history,
            "min_interval_semitones": self.min_interval_semitones,
            "max_interval_semitones": self.max_interval_semitones,
        }

    @staticmethod
    def from_dict(data: dict) -> HammerOnConfig:
        """Deserialize from dict."""
        return HammerOnConfig(
            enabled=data.get("enabled", False),
            max_history=data.get("max_history", 200),
            min_interval_semitones=data.get("min_interval_semitones", 1),
            max_interval_semitones=data.get("max_interval_semitones", 12),
        )


class HammerOnDetector:
    """Detects hammer-on and pull-off events in real time.

    Tracks held notes per channel and emits HammerEvent when guitar-style
    techniques are detected (note B pressed while note A is held and B > A,
    or note A released while higher note B is still held).
    """

    def __init__(self, cfg: HammerOnConfig):
        """Initialize detector with config.

        Args:
            cfg: HammerOnConfig.
        """
        self.cfg = cfg
        # _held: channel -> set of currently held notes
        self._held: Dict[int, Set[int]] = {}
        # _events: list of detected HammerEvent
        self._events: List[HammerEvent] = []

    def on_note_on(self, note: int, channel: int, now_s: float) -> Optional[HammerEvent]:
        """Handle note-on event.

        If a note is held on the same channel where the new note is higher
        and the interval is within [min, max] semitones, emit a hammer-on event.

        Args:
            note: MIDI note (0..127).
            channel: MIDI channel (0..15).
            now_s: Current time in seconds.

        Returns:
            HammerEvent if hammer-on detected, else None.
        """
        if not self.cfg.enabled:
            if channel not in self._held:
                self._held[channel] = set()
            self._held[channel].add(note)
            return None

        # Ensure channel exists in tracking dict
        if channel not in self._held:
            self._held[channel] = set()

        # Check if any held note is lower and within interval range
        event = None
        for held_note in self._held[channel]:
            if note > held_note:  # New note is higher
                interval = note - held_note
                if (
                    self.cfg.min_interval_semitones
                    <= interval
                    <= self.cfg.max_interval_semitones
                ):
                    event = HammerEvent(
                        kind="hammer_on",
                        first_note=held_note,
                        second_note=note,
                        channel=channel,
                        time_s=now_s,
                    )
                    break

        # Add note to held set
        self._held[channel].add(note)

        # Append event and truncate history if needed
        if event:
            self._events.append(event)
            if len(self._events) > self.cfg.max_history:
                self._events = self._events[-self.cfg.max_history :]

        return event

    def on_note_off(self, note: int, channel: int, now_s: float) -> Optional[HammerEvent]:
        """Handle note-off event.

        If the released note is held and a higher note is still held,
        emit a pull-off event using the highest remaining note.

        Args:
            note: MIDI note being released.
            channel: MIDI channel.
            now_s: Current time in seconds.

        Returns:
            HammerEvent if pull-off detected, else None.
        """
        if channel not in self._held:
            return None

        # Remove note from held set
        self._held[channel].discard(note)

        if not self.cfg.enabled:
            return None

        # Check if a higher note is still held
        higher_notes = [n for n in self._held[channel] if n > note]
        if higher_notes:
            highest = max(higher_notes)
            event = HammerEvent(
                kind="pull_off",
                first_note=note,
                second_note=highest,
                channel=channel,
                time_s=now_s,
            )
            self._events.append(event)
            if len(self._events) > self.cfg.max_history:
                self._events = self._events[-self.cfg.max_history :]
            return event

        return None

    def recent(self, n: int = 20) -> List[HammerEvent]:
        """Get the most recent n events.

        Args:
            n: Number of events to return (default 20).

        Returns:
            List of the most recent n HammerEvent objects.
        """
        return self._events[-n:]

    def count(self, kind: Optional[str] = None) -> int:
        """Count events, optionally filtered by kind.

        Args:
            kind: Optional filter ("hammer_on" or "pull_off").
                  If None, count all events.

        Returns:
            Number of matching events.
        """
        if kind is None:
            return len(self._events)
        return sum(1 for e in self._events if e.kind == kind)

    def clear(self) -> None:
        """Clear all tracked events and held notes."""
        self._events.clear()
        self._held.clear()
