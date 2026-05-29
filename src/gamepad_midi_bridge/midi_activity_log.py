"""MIDI activity log — ring buffer of recent MIDI events (in + out) with filtering.

Provides a pure-stdlib ring buffer for recording and filtering MIDI messages.
Supports classification of message types, channel detection, and flexible querying.
No Qt dependencies — suitable for headless or UI contexts.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict, fields
from typing import List, Optional, Tuple, Dict


@dataclass
class MidiEvent:
    """One recorded MIDI event with metadata."""
    timestamp_s: float
    direction: str  # "in" or "out"
    message_bytes: List[int]
    port_name: str = ""
    tags: List[str] = field(default_factory=list)
    kind: str = "unknown"  # note_on, note_off, cc, pitch_bend, program_change, aftertouch, sysex, clock, unknown
    channel: Optional[int] = None  # 1-16 or None

    def __post_init__(self) -> None:
        """Validate fields."""
        if self.direction not in ("in", "out"):
            raise ValueError(f"direction must be 'in' or 'out', got {self.direction!r}")
        if not isinstance(self.message_bytes, list):
            raise TypeError(f"message_bytes must be a list, got {type(self.message_bytes)}")

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> MidiEvent:
        """Construct from dictionary (round-trip)."""
        # Filter to only fields that exist in the dataclass
        field_names = {f.name for f in fields(cls)}
        filtered = {k: v for k, v in d.items() if k in field_names}
        return cls(**filtered)


@dataclass
class MidiActivityLogConfig:
    """Configuration for MidiActivityLog."""
    max_events: int = 1000

    def __post_init__(self) -> None:
        """Clamp max_events to valid range."""
        if self.max_events < 100:
            self.max_events = 100
        elif self.max_events > 100000:
            self.max_events = 100000

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> MidiActivityLogConfig:
        """Construct from dictionary (round-trip)."""
        return cls(**d)


def classify_message(msg_bytes: List[int]) -> Tuple[str, Optional[int]]:
    """Classify a MIDI message by status byte.

    Returns:
        Tuple of (kind, channel) where:
        - kind: "note_off", "note_on", "aftertouch", "cc", "program_change",
                "pitch_bend", "sysex", "clock", "unknown"
        - channel: 1-16 for channel messages, None for system messages
    """
    if not msg_bytes:
        return ("unknown", None)

    status = msg_bytes[0]

    # Channel messages (0x80-0xEF)
    if 0x80 <= status <= 0x8F:
        return ("note_off", (status & 0x0F) + 1)
    elif 0x90 <= status <= 0x9F:
        return ("note_on", (status & 0x0F) + 1)
    elif 0xA0 <= status <= 0xAF:
        return ("aftertouch", (status & 0x0F) + 1)
    elif 0xB0 <= status <= 0xBF:
        return ("cc", (status & 0x0F) + 1)
    elif 0xC0 <= status <= 0xCF:
        return ("program_change", (status & 0x0F) + 1)
    elif 0xD0 <= status <= 0xDF:
        return ("aftertouch", (status & 0x0F) + 1)
    elif 0xE0 <= status <= 0xEF:
        return ("pitch_bend", (status & 0x0F) + 1)

    # System messages (0xF0-0xFF)
    elif status == 0xF0:
        return ("sysex", None)
    elif status == 0xF8:
        return ("clock", None)
    else:
        return ("unknown", None)


class MidiActivityLog:
    """Ring buffer for MIDI activity with filtering and statistics."""

    def __init__(self, cfg: MidiActivityLogConfig) -> None:
        """Initialize the log with configuration."""
        self.cfg = cfg
        self._events: List[MidiEvent] = []

    def record(
        self,
        direction: str,
        message_bytes: List[int],
        timestamp_s: float,
        port_name: str = "",
        tags: Optional[List[str]] = None,
    ) -> MidiEvent:
        """Record a MIDI event.

        Args:
            direction: "in" or "out"
            message_bytes: raw MIDI bytes
            timestamp_s: event timestamp in seconds
            port_name: source/destination port name
            tags: optional list of tags (e.g., ["cc", "ch1"])

        Returns:
            The created MidiEvent.
        """
        if tags is None:
            tags = []

        kind, channel = classify_message(message_bytes)

        event = MidiEvent(
            timestamp_s=timestamp_s,
            direction=direction,
            message_bytes=message_bytes,
            port_name=port_name,
            tags=tags,
            kind=kind,
            channel=channel,
        )

        self._events.append(event)

        # FIFO eviction: remove oldest while at/exceeds max
        while len(self._events) > self.cfg.max_events:
            self._events.pop(0)

        return event

    def events(self) -> List[MidiEvent]:
        """Return a copy of all events (oldest-first)."""
        return list(self._events)

    def recent(self, n: int = 50) -> List[MidiEvent]:
        """Return the last n events."""
        if n <= 0:
            return []
        return list(self._events[-n:])

    def filter_by_kind(self, kinds: List[str]) -> List[MidiEvent]:
        """Return events whose kind is in the provided list."""
        return [e for e in self._events if e.kind in kinds]

    def filter_by_direction(self, direction: str) -> List[MidiEvent]:
        """Return events filtered by direction ('in' or 'out')."""
        return [e for e in self._events if e.direction == direction]

    def filter_by_channel(self, channel: int) -> List[MidiEvent]:
        """Return events on the specified channel (1-16)."""
        return [e for e in self._events if e.channel == channel]

    def filter_by_timerange(self, start_s: float, end_s: float) -> List[MidiEvent]:
        """Return events in the time range [start_s, end_s] (inclusive)."""
        return [e for e in self._events if start_s <= e.timestamp_s <= end_s]

    def count_by_kind(self) -> Dict[str, int]:
        """Return a dictionary of counts per message kind."""
        counts: Dict[str, int] = {}
        for event in self._events:
            counts[event.kind] = counts.get(event.kind, 0) + 1
        return counts

    def clear(self) -> None:
        """Empty the log."""
        self._events.clear()

    def total(self) -> int:
        """Return the total number of events."""
        return len(self._events)
