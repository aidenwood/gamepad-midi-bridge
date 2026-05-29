"""Timed-note scheduler — queue notes/events at future timestamps with cancellation.

TimedNoteScheduler provides a priority queue (heapq-based) for scheduling MIDI events
(note_on, note_off, CC) at future timestamps. Each scheduled event has a unique ID
allowing per-event cancellation without removing from the heap.

Used as a building block by tap_delay, arpeggio, quantize_grid, and similar modules.

Pure stdlib (heapq), no Qt dependencies.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import heapq


@dataclass
class ScheduledNote:
    """A MIDI event queued for future delivery.

    Attributes:
        id: Unique auto-incremented event ID (for cancellation).
        fire_at_s: Unix timestamp (seconds) when this event should fire.
        kind: Event type ("note_on", "note_off", "cc").
        note: MIDI note number (0..127), used for note_on/note_off.
        velocity: Note velocity (0..127), used for note_on/note_off.
        channel: MIDI channel (1..16).
        cc: CC number (0..127), used when kind=="cc".
        value: CC value (0..127), used when kind=="cc".
        cancelled: If True, pop_ready will skip this event.
    """
    id: int = 0
    fire_at_s: float = 0.0
    kind: str = "note_on"
    note: int = 0
    velocity: int = 0
    channel: int = 1
    cc: int = 0
    value: int = 0
    cancelled: bool = False

    def to_dict(self) -> dict:
        """Serialize to JSON-friendly dict."""
        return {
            "id": self.id,
            "fire_at_s": self.fire_at_s,
            "kind": self.kind,
            "note": self.note,
            "velocity": self.velocity,
            "channel": self.channel,
            "cc": self.cc,
            "value": self.value,
            "cancelled": self.cancelled,
        }

    @classmethod
    def from_dict(cls, d: dict) -> ScheduledNote:
        """Deserialize from JSON-friendly dict."""
        return cls(
            id=d.get("id", 0),
            fire_at_s=d.get("fire_at_s", 0.0),
            kind=d.get("kind", "note_on"),
            note=d.get("note", 0),
            velocity=d.get("velocity", 0),
            channel=d.get("channel", 1),
            cc=d.get("cc", 0),
            value=d.get("value", 0),
            cancelled=d.get("cancelled", False),
        )


class TimedNoteScheduler:
    """Priority queue for MIDI events scheduled at future timestamps.

    The scheduler uses a min-heap ordered by fire_at_s to efficiently retrieve
    events ready to fire. Cancellation marks events without removing from the heap
    (lazy deletion), so pop_ready skips cancelled events.

    Attributes:
        _heap: Min-heap of (fire_at_s, id, ScheduledNote) tuples.
        _index: Dict mapping event ID → ScheduledNote for O(1) cancellation lookup.
        _id_counter: Next unique ID to assign.
    """

    def __init__(self):
        """Initialize an empty scheduler."""
        self._heap: List[Tuple[float, int, ScheduledNote]] = []
        self._index: Dict[int, ScheduledNote] = {}
        self._id_counter: int = 0

    def schedule(
        self,
        fire_at_s: float,
        kind: str,
        note: int = 0,
        velocity: int = 0,
        channel: int = 1,
        cc: int = 0,
        value: int = 0,
    ) -> int:
        """Schedule a MIDI event for a future timestamp.

        Args:
            fire_at_s: Unix timestamp (seconds) when event should fire.
            kind: Event type ("note_on", "note_off", "cc").
            note: MIDI note (0..127) for note_on/note_off.
            velocity: Note velocity (0..127) for note_on/note_off.
            channel: MIDI channel (1..16).
            cc: CC number (0..127) for kind=="cc".
            value: CC value (0..127) for kind=="cc".

        Returns:
            Unique event ID (can be used with cancel()).
        """
        self._id_counter += 1
        event_id = self._id_counter

        event = ScheduledNote(
            id=event_id,
            fire_at_s=fire_at_s,
            kind=kind,
            note=note,
            velocity=velocity,
            channel=channel,
            cc=cc,
            value=value,
            cancelled=False,
        )

        self._index[event_id] = event
        heapq.heappush(self._heap, (fire_at_s, event_id, event))

        return event_id

    def cancel(self, event_id: int) -> bool:
        """Mark an event as cancelled (lazy deletion).

        The event remains in the heap but is skipped by pop_ready.

        Args:
            event_id: ID returned by schedule().

        Returns:
            True if the event was found and cancelled, False if ID not found.
        """
        if event_id not in self._index:
            return False

        event = self._index[event_id]
        event.cancelled = True
        return True

    def pop_ready(self, now_s: float) -> List[ScheduledNote]:
        """Pop all events ready to fire (fire_at_s <= now_s).

        Returns events in fire-time order (earliest first). Skips cancelled events.
        Cleans up the index for popped events.

        Args:
            now_s: Current timestamp (seconds).

        Returns:
            List of ScheduledNote events ready to fire, in fire-time order.
        """
        result = []

        while self._heap:
            fire_at_s, event_id, event = self._heap[0]

            if fire_at_s > now_s:
                break

            heapq.heappop(self._heap)

            # Skip cancelled events
            if event.cancelled:
                if event_id in self._index:
                    del self._index[event_id]
                continue

            result.append(event)
            if event_id in self._index:
                del self._index[event_id]

        return result

    def pending_count(self) -> int:
        """Count non-cancelled events waiting in the queue.

        Returns:
            Number of events that will fire in the future.
        """
        return sum(1 for event in self._index.values() if not event.cancelled)

    def next_fire_time(self) -> Optional[float]:
        """Get the earliest fire time of a non-cancelled event.

        Returns:
            Unix timestamp (seconds) of the next non-cancelled event, or None if empty.
        """
        while self._heap:
            fire_at_s, event_id, event = self._heap[0]

            if not event.cancelled:
                return fire_at_s

            # Skip cancelled event
            heapq.heappop(self._heap)
            if event_id in self._index:
                del self._index[event_id]

        return None

    def clear(self) -> None:
        """Empty the scheduler (heap, index, reset counter)."""
        self._heap.clear()
        self._index.clear()
        self._id_counter = 0
