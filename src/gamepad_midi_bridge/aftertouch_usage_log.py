"""Aftertouch usage log — records aftertouch events with timestamp + note + channel + value.

Records every aftertouch event (timestamp, note, channel, value) in a time-series log.
Exposes activity per note, usage rate, and time-series queries.
Different from aftertouch_peak_analyzer (which gives summary stats) — this provides
a recent-history log with FIFO eviction and per-note activity counts.

Pure stdlib, no Qt dependencies.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class AftertouchEvent:
    """One aftertouch event in the usage log.

    Attributes:
        note: MIDI note number 0..127.
        channel: MIDI channel 1..16.
        value: Aftertouch pressure 0..127.
        timestamp_s: Unix epoch timestamp in seconds (float).
    """
    note: int
    channel: int
    value: int
    timestamp_s: float

    def to_dict(self) -> dict:
        """Serialize to JSON-friendly dict."""
        return {
            "note": self.note,
            "channel": self.channel,
            "value": self.value,
            "timestamp_s": self.timestamp_s,
        }

    @classmethod
    def from_dict(cls, d: dict) -> AftertouchEvent:
        """Deserialize from JSON-friendly dict."""
        return cls(
            note=int(d.get("note", 0)),
            channel=int(d.get("channel", 1)),
            value=int(d.get("value", 0)),
            timestamp_s=float(d.get("timestamp_s", 0.0)),
        )


@dataclass
class UsageLogConfig:
    """Configuration for AftertouchUsageLog.

    Attributes:
        max_events: Maximum number of events to retain in the log
                    (clamped 100..1000000).
    """
    max_events: int = 10000

    def __post_init__(self) -> None:
        """Clamp parameters to valid ranges."""
        self.max_events = max(100, min(1000000, self.max_events))

    def to_dict(self) -> dict:
        """Serialize to JSON-friendly dict."""
        return {
            "max_events": self.max_events,
        }

    @classmethod
    def from_dict(cls, d: dict) -> UsageLogConfig:
        """Deserialize from JSON-friendly dict."""
        return cls(
            max_events=int(d.get("max_events", 10000)),
        )


class AftertouchUsageLog:
    """Records aftertouch events in a time-series log with per-note activity counts.

    Maintains a FIFO ring buffer of AftertouchEvent with configurable max size.
    Tracks usage count per (note, channel) pair with proper FIFO eviction and
    per-note decrement on eviction. Exposes recent events, per-note queries,
    activity counts, and time-range filtering.
    """

    def __init__(self, cfg: UsageLogConfig) -> None:
        """Initialize with config.

        Args:
            cfg: UsageLogConfig instance.
        """
        self.cfg = cfg
        self._events: List[AftertouchEvent] = []
        self._per_note_count: Dict[Tuple[int, int], int] = {}

    # ---------------------------------------------------------------- record

    def record(
        self, note: int, channel: int, value: int, timestamp_s: float
    ) -> AftertouchEvent:
        """Record an aftertouch event.

        Clamps note to 0..127, channel to 1..16, value to 0..127.
        If total events exceed max_events, removes oldest event (FIFO)
        and decrements its per-note count.

        Args:
            note: MIDI note number (clamped to 0..127).
            channel: MIDI channel (clamped to 1..16).
            value: Aftertouch pressure (clamped to 0..127).
            timestamp_s: Unix epoch timestamp in seconds.

        Returns:
            The recorded AftertouchEvent.
        """
        note = max(0, min(127, note))
        channel = max(1, min(16, channel))
        value = max(0, min(127, value))

        event = AftertouchEvent(
            note=note,
            channel=channel,
            value=value,
            timestamp_s=timestamp_s,
        )
        self._events.append(event)

        # Increment per-note count
        key = (note, channel)
        self._per_note_count[key] = self._per_note_count.get(key, 0) + 1

        # FIFO eviction if we exceeded max
        while len(self._events) > self.cfg.max_events:
            oldest = self._events.pop(0)
            oldest_key = (oldest.note, oldest.channel)
            self._per_note_count[oldest_key] -= 1
            if self._per_note_count[oldest_key] <= 0:
                del self._per_note_count[oldest_key]

        return event

    # ---------------------------------------------------------------- query

    def recent(self, n: int = 50) -> List[AftertouchEvent]:
        """Return the last N events (newest last in the list).

        Args:
            n: Number of recent events to return (default 50).

        Returns:
            List of up to N most recent AftertouchEvent objects.
        """
        return self._events[-n:] if self._events else []

    def events_for_note(self, note: int, channel: int) -> List[AftertouchEvent]:
        """Return all events for a specific (note, channel) pair.

        Args:
            note: MIDI note number.
            channel: MIDI channel.

        Returns:
            List of AftertouchEvent matching the pair.
        """
        return [
            e for e in self._events
            if e.note == note and e.channel == channel
        ]

    def note_usage_counts(self) -> Dict[Tuple[int, int], int]:
        """Return a copy of the per-note usage counts.

        Returns:
            Dict mapping (note, channel) to event count.
        """
        return dict(self._per_note_count)

    def most_used_notes(self, n: int = 5) -> List[Tuple[int, int, int]]:
        """Return top N most-used (note, channel) pairs.

        Args:
            n: Number of top pairs to return (default 5).

        Returns:
            List of (note, channel, count) tuples, sorted by count descending.
        """
        sorted_pairs = sorted(
            self._per_note_count.items(),
            key=lambda x: x[1],
            reverse=True,
        )
        return [
            (note, channel, count)
            for (note, channel), count in sorted_pairs[:n]
        ]

    def events_in_range(
        self, start_s: float, end_s: float
    ) -> List[AftertouchEvent]:
        """Return events in a time window.

        Args:
            start_s: Start of time window (Unix epoch seconds).
            end_s: End of time window (Unix epoch seconds).

        Returns:
            List of AftertouchEvent with timestamp_s in [start_s, end_s].
        """
        return [
            e for e in self._events
            if start_s <= e.timestamp_s <= end_s
        ]

    def events_per_second(
        self, now_s: float, window_s: float = 1.0
    ) -> float:
        """Calculate the aftertouch event rate over a time window.

        Args:
            now_s: Current time (Unix epoch seconds).
            window_s: Window size in seconds (default 1.0).

        Returns:
            Events per second: (count in [now_s - window_s, now_s]) / window_s.
        """
        start_s = now_s - window_s
        count = len(self.events_in_range(start_s, now_s))
        return count / window_s if window_s > 0 else 0.0

    # ---------------------------------------------------------------- stats

    def total(self) -> int:
        """Return total number of recorded events.

        Returns:
            Count of all events currently in the log.
        """
        return len(self._events)

    # ---------------------------------------------------------------- clear

    def clear(self) -> None:
        """Delete all recorded events and counts."""
        self._events.clear()
        self._per_note_count.clear()
