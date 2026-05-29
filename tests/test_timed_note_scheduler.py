"""Timed-note scheduler — queue and fire MIDI events at future timestamps."""
from __future__ import annotations

import pytest

from gamepad_midi_bridge.timed_note_scheduler import (
    ScheduledNote,
    TimedNoteScheduler,
)


class TestScheduledNote:
    """ScheduledNote dataclass — serialization and basic structure."""

    def test_scheduled_note_defaults(self):
        """ScheduledNote has sensible defaults."""
        note = ScheduledNote()
        assert note.id == 0
        assert note.fire_at_s == 0.0
        assert note.kind == "note_on"
        assert note.note == 0
        assert note.velocity == 0
        assert note.channel == 1
        assert note.cc == 0
        assert note.value == 0
        assert note.cancelled is False

    def test_scheduled_note_to_dict(self):
        """ScheduledNote.to_dict() serializes correctly."""
        note = ScheduledNote(
            id=5,
            fire_at_s=1.5,
            kind="note_on",
            note=60,
            velocity=80,
            channel=2,
        )
        d = note.to_dict()

        assert d["id"] == 5
        assert d["fire_at_s"] == 1.5
        assert d["kind"] == "note_on"
        assert d["note"] == 60
        assert d["velocity"] == 80
        assert d["channel"] == 2

    def test_scheduled_note_from_dict(self):
        """ScheduledNote.from_dict() deserializes correctly."""
        d = {
            "id": 5,
            "fire_at_s": 1.5,
            "kind": "note_on",
            "note": 60,
            "velocity": 80,
            "channel": 2,
            "cc": 0,
            "value": 0,
            "cancelled": False,
        }
        note = ScheduledNote.from_dict(d)

        assert note.id == 5
        assert note.fire_at_s == 1.5
        assert note.kind == "note_on"
        assert note.note == 60
        assert note.velocity == 80
        assert note.channel == 2

    def test_scheduled_note_round_trip(self):
        """ScheduledNote round-trip serialization preserves all fields."""
        original = ScheduledNote(
            id=10,
            fire_at_s=2.75,
            kind="cc",
            note=0,
            velocity=0,
            channel=3,
            cc=7,
            value=100,
            cancelled=False,
        )
        d = original.to_dict()
        restored = ScheduledNote.from_dict(d)

        assert restored.id == original.id
        assert restored.fire_at_s == original.fire_at_s
        assert restored.kind == original.kind
        assert restored.note == original.note
        assert restored.velocity == original.velocity
        assert restored.channel == original.channel
        assert restored.cc == original.cc
        assert restored.value == original.value
        assert restored.cancelled == original.cancelled


class TestTimedNoteScheduler:
    """TimedNoteScheduler — event scheduling and cancellation."""

    def test_empty_scheduler(self):
        """New scheduler is empty."""
        sched = TimedNoteScheduler()
        assert sched.pending_count() == 0
        assert sched.next_fire_time() is None
        assert sched.pop_ready(10.0) == []

    def test_schedule_returns_id(self):
        """schedule() returns a unique integer ID."""
        sched = TimedNoteScheduler()
        id1 = sched.schedule(1.0, "note_on", note=60)
        id2 = sched.schedule(2.0, "note_on", note=64)

        assert isinstance(id1, int)
        assert isinstance(id2, int)
        assert id1 != id2
        assert id1 == 1
        assert id2 == 2

    def test_schedule_increments_counter(self):
        """schedule() auto-increments IDs starting from 1."""
        sched = TimedNoteScheduler()
        ids = [sched.schedule(i, "note_on", note=60 + i) for i in range(5)]

        assert ids == [1, 2, 3, 4, 5]

    def test_pending_count_after_schedule(self):
        """pending_count() reflects scheduled events."""
        sched = TimedNoteScheduler()
        sched.schedule(1.0, "note_on", note=60)
        sched.schedule(2.0, "note_on", note=64)
        sched.schedule(3.0, "note_on", note=67)

        assert sched.pending_count() == 3

    def test_pop_ready_before_fire_time(self):
        """pop_ready() before fire time returns empty list."""
        sched = TimedNoteScheduler()
        sched.schedule(1.0, "note_on", note=60)

        assert sched.pop_ready(0.5) == []
        assert sched.pending_count() == 1

    def test_pop_ready_at_exact_fire_time(self):
        """pop_ready() at exact fire time returns event."""
        sched = TimedNoteScheduler()
        sched.schedule(1.0, "note_on", note=60)

        result = sched.pop_ready(1.0)
        assert len(result) == 1
        assert result[0].note == 60
        assert result[0].fire_at_s == 1.0

    def test_pop_ready_after_fire_time(self):
        """pop_ready() after fire time returns event."""
        sched = TimedNoteScheduler()
        sched.schedule(1.0, "note_on", note=60)

        result = sched.pop_ready(2.0)
        assert len(result) == 1
        assert result[0].note == 60

    def test_pop_ready_in_fire_time_order(self):
        """pop_ready() returns events in fire-time order (not insertion order)."""
        sched = TimedNoteScheduler()
        sched.schedule(3.0, "note_on", note=60)
        sched.schedule(1.0, "note_on", note=64)
        sched.schedule(2.0, "note_on", note=67)

        result = sched.pop_ready(4.0)
        assert len(result) == 3
        assert result[0].note == 64  # 1.0
        assert result[1].note == 67  # 2.0
        assert result[2].note == 60  # 3.0

    def test_pop_ready_cleans_index(self):
        """pop_ready() removes popped events from index."""
        sched = TimedNoteScheduler()
        sched.schedule(1.0, "note_on", note=60)

        assert sched.pending_count() == 1
        sched.pop_ready(2.0)
        assert sched.pending_count() == 0

    def test_cancel_marks_event_cancelled(self):
        """cancel() marks event as cancelled."""
        sched = TimedNoteScheduler()
        event_id = sched.schedule(1.0, "note_on", note=60)

        assert sched.cancel(event_id) is True
        result = sched.pop_ready(2.0)
        assert len(result) == 0

    def test_cancel_returns_false_for_unknown_id(self):
        """cancel() returns False for unknown event ID."""
        sched = TimedNoteScheduler()
        assert sched.cancel(999) is False

    def test_cancel_returns_true_for_valid_id(self):
        """cancel() returns True when event is found."""
        sched = TimedNoteScheduler()
        event_id = sched.schedule(1.0, "note_on", note=60)
        assert sched.cancel(event_id) is True

    def test_cancel_skips_in_pop_ready(self):
        """Cancelled events are skipped by pop_ready()."""
        sched = TimedNoteScheduler()
        id1 = sched.schedule(1.0, "note_on", note=60)
        id2 = sched.schedule(1.5, "note_on", note=64)
        id3 = sched.schedule(2.0, "note_on", note=67)

        sched.cancel(id2)

        result = sched.pop_ready(3.0)
        assert len(result) == 2
        assert result[0].note == 60
        assert result[1].note == 67

    def test_next_fire_time_when_empty(self):
        """next_fire_time() returns None when scheduler is empty."""
        sched = TimedNoteScheduler()
        assert sched.next_fire_time() is None

    def test_next_fire_time_single_event(self):
        """next_fire_time() returns fire time of only event."""
        sched = TimedNoteScheduler()
        sched.schedule(1.5, "note_on", note=60)

        assert sched.next_fire_time() == 1.5

    def test_next_fire_time_earliest(self):
        """next_fire_time() returns earliest event time."""
        sched = TimedNoteScheduler()
        sched.schedule(3.0, "note_on", note=60)
        sched.schedule(1.0, "note_on", note=64)
        sched.schedule(2.0, "note_on", note=67)

        assert sched.next_fire_time() == 1.0

    def test_next_fire_time_skips_cancelled(self):
        """next_fire_time() skips cancelled events and returns next valid."""
        sched = TimedNoteScheduler()
        id1 = sched.schedule(1.0, "note_on", note=60)
        id2 = sched.schedule(2.0, "note_on", note=64)

        sched.cancel(id1)

        assert sched.next_fire_time() == 2.0

    def test_pending_count_after_pop_ready(self):
        """pending_count() reflects remaining events after pop_ready()."""
        sched = TimedNoteScheduler()
        sched.schedule(1.0, "note_on", note=60)
        sched.schedule(3.0, "note_on", note=64)

        assert sched.pending_count() == 2
        sched.pop_ready(2.0)
        assert sched.pending_count() == 1

    def test_clear_empties_scheduler(self):
        """clear() empties heap and index."""
        sched = TimedNoteScheduler()
        sched.schedule(1.0, "note_on", note=60)
        sched.schedule(2.0, "note_on", note=64)

        assert sched.pending_count() == 2
        sched.clear()
        assert sched.pending_count() == 0
        assert sched.next_fire_time() is None
        assert sched.pop_ready(10.0) == []

    def test_clear_resets_counter(self):
        """clear() resets the ID counter."""
        sched = TimedNoteScheduler()
        sched.schedule(1.0, "note_on", note=60)
        sched.schedule(2.0, "note_on", note=64)
        sched.clear()

        id1 = sched.schedule(1.0, "note_on", note=60)
        assert id1 == 1

    def test_schedule_kind_note_off(self):
        """schedule() with kind="note_off" works."""
        sched = TimedNoteScheduler()
        event_id = sched.schedule(1.0, "note_off", note=60, velocity=0, channel=1)

        result = sched.pop_ready(2.0)
        assert len(result) == 1
        assert result[0].kind == "note_off"
        assert result[0].note == 60

    def test_schedule_kind_cc(self):
        """schedule() with kind="cc" stores CC and value."""
        sched = TimedNoteScheduler()
        event_id = sched.schedule(1.0, "cc", cc=7, value=100, channel=1)

        result = sched.pop_ready(2.0)
        assert len(result) == 1
        assert result[0].kind == "cc"
        assert result[0].cc == 7
        assert result[0].value == 100

    def test_schedule_with_channel(self):
        """schedule() respects channel parameter."""
        sched = TimedNoteScheduler()
        event_id = sched.schedule(1.0, "note_on", note=60, channel=5)

        result = sched.pop_ready(2.0)
        assert result[0].channel == 5

    def test_many_events_efficiency(self):
        """Scheduler handles many events efficiently."""
        sched = TimedNoteScheduler()
        n = 1000

        # Schedule in random order
        for i in range(n):
            sched.schedule(float(n - i), "note_on", note=60 + (i % 12))

        assert sched.pending_count() == n
        assert sched.next_fire_time() == 1.0

        # Pop all
        result = sched.pop_ready(float(n + 1))
        assert len(result) == n

        # Should be in fire-time order
        for i, event in enumerate(result):
            assert event.fire_at_s == float(i + 1)

    def test_many_events_with_cancellation(self):
        """Scheduler efficiently handles many cancellations."""
        sched = TimedNoteScheduler()
        n = 1000

        # Schedule and get IDs
        ids = [
            sched.schedule(float(i), "note_on", note=60 + (i % 12))
            for i in range(1, n + 1)
        ]

        # Cancel every other event
        for i in range(0, n, 2):
            sched.cancel(ids[i])

        assert sched.pending_count() == n // 2

        # Pop all
        result = sched.pop_ready(float(n + 1))
        assert len(result) == n // 2

    def test_pop_ready_multiple_calls(self):
        """pop_ready() can be called multiple times as time advances."""
        sched = TimedNoteScheduler()
        sched.schedule(1.0, "note_on", note=60)
        sched.schedule(2.0, "note_on", note=64)
        sched.schedule(3.0, "note_on", note=67)

        result1 = sched.pop_ready(1.5)
        assert len(result1) == 1
        assert result1[0].note == 60

        result2 = sched.pop_ready(2.5)
        assert len(result2) == 1
        assert result2[0].note == 64

        result3 = sched.pop_ready(4.0)
        assert len(result3) == 1
        assert result3[0].note == 67

        assert sched.pending_count() == 0
