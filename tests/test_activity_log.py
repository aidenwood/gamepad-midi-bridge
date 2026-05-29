"""Tests for ActivityLog — ring buffer, severity filter, clear, and round-trip."""
from __future__ import annotations

import time

import pytest


class TestActivityLogRecord:
    """record() + snapshot() round-trip."""

    def test_record_single_event(self):
        from gamepad_midi_bridge.activity_log import ActivityLog
        log = ActivityLog()
        log.record("bridge_start", "Bridge started")
        events = log.snapshot()
        assert len(events) == 1
        assert events[0].kind == "bridge_start"
        assert events[0].message == "Bridge started"
        assert events[0].severity == "info"

    def test_record_preserves_timestamp(self):
        from gamepad_midi_bridge.activity_log import ActivityLog
        log = ActivityLog()
        before = time.time()
        log.record("test", "msg")
        after = time.time()
        ts = log.snapshot()[0].timestamp
        assert before <= ts <= after

    def test_record_all_severities(self):
        from gamepad_midi_bridge.activity_log import ActivityLog
        log = ActivityLog()
        log.record("k", "info msg", severity="info")
        log.record("k", "warn msg", severity="warning")
        log.record("k", "err msg", severity="error")
        events = log.snapshot()
        assert [e.severity for e in events] == ["info", "warning", "error"]

    def test_record_invalid_severity_raises(self):
        from gamepad_midi_bridge.activity_log import ActivityLog
        log = ActivityLog()
        with pytest.raises(ValueError):
            log.record("k", "msg", severity="critical")

    def test_snapshot_is_copy(self):
        """Mutating snapshot does not affect internal buffer."""
        from gamepad_midi_bridge.activity_log import ActivityLog
        log = ActivityLog()
        log.record("k", "msg")
        snap = log.snapshot()
        snap.clear()
        assert len(log.snapshot()) == 1

    def test_snapshot_ordered_oldest_first(self):
        from gamepad_midi_bridge.activity_log import ActivityLog
        log = ActivityLog()
        for i in range(5):
            log.record("k", str(i))
        messages = [e.message for e in log.snapshot()]
        assert messages == ["0", "1", "2", "3", "4"]


class TestActivityLogRingBuffer:
    """Ring buffer caps at 200 and drops oldest."""

    def test_ring_buffer_caps_at_200(self):
        from gamepad_midi_bridge.activity_log import ActivityLog, RING_BUFFER_SIZE
        log = ActivityLog()
        for i in range(RING_BUFFER_SIZE + 50):
            log.record("k", str(i))
        assert len(log.snapshot()) == RING_BUFFER_SIZE

    def test_ring_buffer_drops_oldest(self):
        from gamepad_midi_bridge.activity_log import ActivityLog, RING_BUFFER_SIZE
        log = ActivityLog()
        for i in range(RING_BUFFER_SIZE + 10):
            log.record("k", str(i))
        events = log.snapshot()
        # The first surviving event should be the 11th (index 10)
        assert events[0].message == str(10)
        assert events[-1].message == str(RING_BUFFER_SIZE + 9)

    def test_len_matches_snapshot(self):
        from gamepad_midi_bridge.activity_log import ActivityLog
        log = ActivityLog()
        for i in range(7):
            log.record("k", str(i))
        assert len(log) == 7
        assert len(log.snapshot()) == 7


class TestActivityLogClear:
    """clear() empties the buffer."""

    def test_clear_empties(self):
        from gamepad_midi_bridge.activity_log import ActivityLog
        log = ActivityLog()
        log.record("k", "msg1")
        log.record("k", "msg2")
        log.clear()
        assert log.snapshot() == []
        assert len(log) == 0

    def test_record_after_clear(self):
        from gamepad_midi_bridge.activity_log import ActivityLog
        log = ActivityLog()
        log.record("k", "before")
        log.clear()
        log.record("k", "after")
        events = log.snapshot()
        assert len(events) == 1
        assert events[0].message == "after"


class TestActivityLogSeverityFilter:
    """snapshot_by_severity() filters correctly."""

    def test_filter_info_only(self):
        from gamepad_midi_bridge.activity_log import ActivityLog
        log = ActivityLog()
        log.record("k", "a", severity="info")
        log.record("k", "b", severity="warning")
        log.record("k", "c", severity="error")
        log.record("k", "d", severity="info")
        result = log.snapshot_by_severity("info")
        assert [e.message for e in result] == ["a", "d"]

    def test_filter_warning(self):
        from gamepad_midi_bridge.activity_log import ActivityLog
        log = ActivityLog()
        log.record("k", "a", severity="info")
        log.record("k", "b", severity="warning")
        log.record("k", "c", severity="warning")
        result = log.snapshot_by_severity("warning")
        assert len(result) == 2
        assert all(e.severity == "warning" for e in result)

    def test_filter_error(self):
        from gamepad_midi_bridge.activity_log import ActivityLog
        log = ActivityLog()
        log.record("k", "a", severity="info")
        log.record("k", "b", severity="error")
        result = log.snapshot_by_severity("error")
        assert len(result) == 1
        assert result[0].message == "b"

    def test_filter_empty_when_no_match(self):
        from gamepad_midi_bridge.activity_log import ActivityLog
        log = ActivityLog()
        log.record("k", "a", severity="info")
        assert log.snapshot_by_severity("error") == []


class TestActivityLogSingleton:
    """Module-level log() singleton behaves correctly."""

    def test_singleton_returns_same_instance(self):
        from gamepad_midi_bridge import activity_log
        # Reset singleton for clean test
        activity_log._instance = None
        a = activity_log.log()
        b = activity_log.log()
        assert a is b

    def test_singleton_accumulates_across_calls(self):
        from gamepad_midi_bridge import activity_log
        activity_log._instance = None
        activity_log.log().record("k", "first")
        activity_log.log().record("k", "second")
        events = activity_log.log().snapshot()
        assert len(events) == 2
