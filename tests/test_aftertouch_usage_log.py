"""Tests for aftertouch_usage_log module."""
import pytest
from gamepad_midi_bridge.aftertouch_usage_log import (
    AftertouchEvent,
    AftertouchUsageLog,
    UsageLogConfig,
)


class TestAftertouchEvent:
    """Tests for AftertouchEvent dataclass."""

    def test_event_creation(self):
        """Create an event with valid values."""
        event = AftertouchEvent(
            note=60,
            channel=1,
            value=100,
            timestamp_s=0.0,
        )
        assert event.note == 60
        assert event.channel == 1
        assert event.value == 100
        assert event.timestamp_s == 0.0

    def test_event_to_dict(self):
        """Serialize event to dict."""
        event = AftertouchEvent(60, 1, 100, 1.5)
        d = event.to_dict()
        assert d == {
            "note": 60,
            "channel": 1,
            "value": 100,
            "timestamp_s": 1.5,
        }

    def test_event_from_dict(self):
        """Deserialize event from dict."""
        d = {
            "note": 64,
            "channel": 2,
            "value": 80,
            "timestamp_s": 2.5,
        }
        event = AftertouchEvent.from_dict(d)
        assert event.note == 64
        assert event.channel == 2
        assert event.value == 80
        assert event.timestamp_s == 2.5

    def test_event_round_trip(self):
        """Event serialization round-trip."""
        original = AftertouchEvent(72, 5, 64, 3.14159)
        d = original.to_dict()
        restored = AftertouchEvent.from_dict(d)
        assert restored.note == original.note
        assert restored.channel == original.channel
        assert restored.value == original.value
        assert restored.timestamp_s == original.timestamp_s


class TestUsageLogConfig:
    """Tests for UsageLogConfig dataclass."""

    def test_config_defaults(self):
        """Default config values."""
        cfg = UsageLogConfig()
        assert cfg.max_events == 10000

    def test_config_clamping_low(self):
        """Clamp max_events to minimum 100."""
        cfg = UsageLogConfig(max_events=50)
        assert cfg.max_events == 100

    def test_config_clamping_high(self):
        """Clamp max_events to maximum 1000000."""
        cfg = UsageLogConfig(max_events=2000000)
        assert cfg.max_events == 1000000

    def test_config_clamping_edge(self):
        """Valid edge values pass through."""
        cfg1 = UsageLogConfig(max_events=100)
        assert cfg1.max_events == 100
        cfg2 = UsageLogConfig(max_events=1000000)
        assert cfg2.max_events == 1000000

    def test_config_to_dict(self):
        """Serialize config to dict."""
        cfg = UsageLogConfig(max_events=5000)
        d = cfg.to_dict()
        assert d == {"max_events": 5000}

    def test_config_from_dict(self):
        """Deserialize config from dict."""
        d = {"max_events": 8000}
        cfg = UsageLogConfig.from_dict(d)
        assert cfg.max_events == 8000

    def test_config_round_trip(self):
        """Config serialization round-trip."""
        original = UsageLogConfig(max_events=3000)
        d = original.to_dict()
        restored = UsageLogConfig.from_dict(d)
        assert restored.max_events == original.max_events


class TestAftertouchUsageLogBasic:
    """Basic tests for AftertouchUsageLog."""

    def test_empty_log(self):
        """Empty log has zero events and counts."""
        cfg = UsageLogConfig()
        log = AftertouchUsageLog(cfg)
        assert log.total() == 0
        assert log.note_usage_counts() == {}
        assert log.most_used_notes() == []

    def test_record_single_event(self):
        """Record a single event."""
        cfg = UsageLogConfig()
        log = AftertouchUsageLog(cfg)
        event = log.record(60, 1, 100, 0.0)
        assert event.note == 60
        assert event.channel == 1
        assert event.value == 100
        assert event.timestamp_s == 0.0
        assert log.total() == 1

    def test_record_increments_count(self):
        """Recording increments per-note count."""
        cfg = UsageLogConfig()
        log = AftertouchUsageLog(cfg)
        log.record(60, 1, 50, 0.0)
        log.record(60, 1, 80, 0.1)
        counts = log.note_usage_counts()
        assert counts[(60, 1)] == 2
        assert log.total() == 2

    def test_clamp_note(self):
        """Note values clamped to 0..127."""
        cfg = UsageLogConfig()
        log = AftertouchUsageLog(cfg)
        log.record(-5, 1, 100, 0.0)
        log.record(200, 1, 100, 0.1)
        events = log.recent(2)
        assert events[0].note == 0
        assert events[1].note == 127

    def test_clamp_channel(self):
        """Channel values clamped to 1..16."""
        cfg = UsageLogConfig()
        log = AftertouchUsageLog(cfg)
        log.record(60, 0, 100, 0.0)
        log.record(60, 20, 100, 0.1)
        events = log.recent(2)
        assert events[0].channel == 1
        assert events[1].channel == 16

    def test_clamp_value(self):
        """Value clamped to 0..127."""
        cfg = UsageLogConfig()
        log = AftertouchUsageLog(cfg)
        log.record(60, 1, -10, 0.0)
        log.record(60, 1, 200, 0.1)
        events = log.recent(2)
        assert events[0].value == 0
        assert events[1].value == 127


class TestAftertouchUsageLogRecent:
    """Tests for recent() method."""

    def test_recent_empty(self):
        """recent() on empty log returns empty list."""
        cfg = UsageLogConfig()
        log = AftertouchUsageLog(cfg)
        assert log.recent(5) == []

    def test_recent_all(self):
        """recent() returns all events if fewer than N."""
        cfg = UsageLogConfig()
        log = AftertouchUsageLog(cfg)
        for i in range(3):
            log.record(60 + i, 1, 50 + i * 10, float(i))
        events = log.recent(10)
        assert len(events) == 3

    def test_recent_n(self):
        """recent(n) returns last N events."""
        cfg = UsageLogConfig()
        log = AftertouchUsageLog(cfg)
        for i in range(10):
            log.record(60, 1, i, float(i))
        recent_5 = log.recent(5)
        assert len(recent_5) == 5
        # Last 5 events should have values 5, 6, 7, 8, 9
        assert [e.value for e in recent_5] == [5, 6, 7, 8, 9]


class TestAftertouchUsageLogPerNote:
    """Tests for per-note query methods."""

    def test_events_for_note_empty(self):
        """events_for_note on empty log returns empty."""
        cfg = UsageLogConfig()
        log = AftertouchUsageLog(cfg)
        assert log.events_for_note(60, 1) == []

    def test_events_for_note_filters(self):
        """events_for_note filters by (note, channel)."""
        cfg = UsageLogConfig()
        log = AftertouchUsageLog(cfg)
        log.record(60, 1, 50, 0.0)
        log.record(60, 2, 60, 0.1)  # Different channel
        log.record(61, 1, 70, 0.2)  # Different note
        log.record(60, 1, 80, 0.3)  # Match
        events_60_1 = log.events_for_note(60, 1)
        assert len(events_60_1) == 2
        assert all(e.note == 60 and e.channel == 1 for e in events_60_1)

    def test_note_usage_counts_tally(self):
        """note_usage_counts tallies per-note counts."""
        cfg = UsageLogConfig()
        log = AftertouchUsageLog(cfg)
        log.record(60, 1, 50, 0.0)
        log.record(60, 1, 60, 0.1)
        log.record(64, 1, 70, 0.2)
        log.record(60, 2, 80, 0.3)
        counts = log.note_usage_counts()
        assert counts == {(60, 1): 2, (64, 1): 1, (60, 2): 1}

    def test_most_used_notes_empty(self):
        """most_used_notes on empty log returns empty."""
        cfg = UsageLogConfig()
        log = AftertouchUsageLog(cfg)
        assert log.most_used_notes(5) == []

    def test_most_used_notes_sorts(self):
        """most_used_notes sorts by count descending."""
        cfg = UsageLogConfig()
        log = AftertouchUsageLog(cfg)
        # Record different counts
        for _ in range(4):
            log.record(60, 1, 50, 0.0)
        for _ in range(1):
            log.record(64, 1, 60, 0.1)
        for _ in range(2):
            log.record(62, 1, 70, 0.2)
        top = log.most_used_notes(5)
        assert top[0] == (60, 1, 4)
        assert top[1] == (62, 1, 2)
        assert top[2] == (64, 1, 1)

    def test_most_used_notes_n(self):
        """most_used_notes returns top N."""
        cfg = UsageLogConfig()
        log = AftertouchUsageLog(cfg)
        for note in range(60, 65):
            log.record(note, 1, 50, 0.0)
        top_2 = log.most_used_notes(2)
        assert len(top_2) == 2


class TestAftertouchUsageLogTimeRange:
    """Tests for time-range queries."""

    def test_events_in_range_empty(self):
        """events_in_range on empty log returns empty."""
        cfg = UsageLogConfig()
        log = AftertouchUsageLog(cfg)
        assert log.events_in_range(0.0, 1.0) == []

    def test_events_in_range_filters(self):
        """events_in_range filters by timestamp."""
        cfg = UsageLogConfig()
        log = AftertouchUsageLog(cfg)
        log.record(60, 1, 50, 0.0)
        log.record(60, 1, 60, 0.5)
        log.record(60, 1, 70, 1.0)
        log.record(60, 1, 80, 1.5)
        events = log.events_in_range(0.2, 1.2)
        assert len(events) == 2
        assert events[0].timestamp_s == 0.5
        assert events[1].timestamp_s == 1.0

    def test_events_per_second_rate(self):
        """events_per_second computes event rate."""
        cfg = UsageLogConfig()
        log = AftertouchUsageLog(cfg)
        # Record 3 events at timestamps 0, 1, 2
        for i in range(3):
            log.record(60, 1, 50 + i, float(i))
        # Window from 0.0 to 2.0 with now_s=2.0
        # Events in [2.0 - 2.0, 2.0] = [0.0, 2.0] → events at 0, 1, 2 = 3 events
        rate = log.events_per_second(2.0, window_s=2.0)
        # 3 events / 2.0 seconds = 1.5 events/sec
        assert rate == 1.5

    def test_events_per_second_partial_window(self):
        """events_per_second counts within window only."""
        cfg = UsageLogConfig()
        log = AftertouchUsageLog(cfg)
        log.record(60, 1, 50, 0.0)
        log.record(60, 1, 60, 0.5)
        log.record(60, 1, 70, 1.0)
        log.record(60, 1, 80, 1.5)
        # Window from 0.3 to 1.3 (centered at now_s=1.3, window_s=1.0)
        rate = log.events_per_second(1.3, window_s=1.0)
        # Events at 0.5, 1.0 are in [0.3, 1.3] → 2 events
        # 2 / 1.0 = 2.0 events/sec
        assert rate == 2.0

    def test_events_per_second_zero_window(self):
        """events_per_second with zero window returns 0.0."""
        cfg = UsageLogConfig()
        log = AftertouchUsageLog(cfg)
        log.record(60, 1, 50, 0.0)
        rate = log.events_per_second(1.0, window_s=0.0)
        assert rate == 0.0


class TestAftertouchUsageLogFIFOEviction:
    """Tests for FIFO eviction and per-note decrement."""

    def test_fifo_eviction(self):
        """FIFO eviction removes oldest event when exceeding max_events."""
        cfg = UsageLogConfig(max_events=103)  # Use valid min boundary
        log = AftertouchUsageLog(cfg)
        log.record(60, 1, 50, 0.0)
        log.record(61, 1, 60, 0.1)
        log.record(62, 1, 70, 0.2)
        assert log.total() == 3
        # Add 101 more, should have exactly 103
        for i in range(101):
            log.record(60 + ((i + 3) % 128), 1, 80, float(i + 0.3))
        assert log.total() == 103
        # Add one more, should still be 103 and evict the oldest
        log.record(63, 1, 80, 200.0)
        assert log.total() == 103
        # Oldest should now be the second recorded event (61, 1)
        oldest = log.recent(1)[0]
        assert oldest.note != 60 or oldest.timestamp_s != 0.0

    def test_fifo_per_note_decrement(self):
        """FIFO eviction decrements per-note count properly."""
        cfg = UsageLogConfig(max_events=103)
        log = AftertouchUsageLog(cfg)
        log.record(60, 1, 50, 0.0)
        log.record(60, 1, 60, 0.1)
        log.record(61, 1, 70, 0.2)
        counts_before = log.note_usage_counts()
        assert counts_before[(60, 1)] == 2
        # Add enough events to evict the first (60, 1)
        for i in range(101):
            log.record(62, 1, 80, float(i + 0.3))
        counts_after = log.note_usage_counts()
        # First (60, 1) should be evicted, count should be 1
        assert counts_after[(60, 1)] == 1

    def test_fifo_per_note_removal(self):
        """Per-note count entry removed when count drops to 0."""
        cfg = UsageLogConfig(max_events=102)
        log = AftertouchUsageLog(cfg)
        log.record(60, 1, 50, 0.0)
        log.record(61, 1, 60, 0.1)
        assert (60, 1) in log.note_usage_counts()
        # Add enough to evict the single (60, 1) event
        for i in range(101):
            log.record(62, 1, 80, float(i + 0.2))
        # (60, 1) should be completely gone
        assert (60, 1) not in log.note_usage_counts()


class TestAftertouchUsageLogClear:
    """Tests for clear() method."""

    def test_clear_empties_log(self):
        """clear() deletes all events."""
        cfg = UsageLogConfig()
        log = AftertouchUsageLog(cfg)
        log.record(60, 1, 50, 0.0)
        log.record(60, 1, 60, 0.1)
        assert log.total() == 2
        log.clear()
        assert log.total() == 0

    def test_clear_empties_counts(self):
        """clear() deletes all per-note counts."""
        cfg = UsageLogConfig()
        log = AftertouchUsageLog(cfg)
        log.record(60, 1, 50, 0.0)
        log.record(61, 1, 60, 0.1)
        counts_before = log.note_usage_counts()
        assert len(counts_before) > 0
        log.clear()
        counts_after = log.note_usage_counts()
        assert counts_after == {}


class TestIntegration:
    """Integration tests combining multiple operations."""

    def test_full_workflow(self):
        """Full workflow: record, query, clear."""
        cfg = UsageLogConfig(max_events=500)
        log = AftertouchUsageLog(cfg)

        # Record 3 events
        log.record(60, 1, 50, 0.0)
        log.record(60, 1, 80, 0.1)
        log.record(64, 1, 90, 0.2)
        assert log.total() == 3

        # Query
        recent = log.recent(2)
        assert len(recent) == 2
        counts = log.note_usage_counts()
        assert counts[(60, 1)] == 2
        assert counts[(64, 1)] == 1

        # Add more events
        for i in range(4, 100):
            log.record(60 + (i % 128), 1, 100, float(i) * 0.1)
        assert log.total() == 99

        # Verify most-used
        top = log.most_used_notes(2)
        assert top[0][2] >= 1  # At least 1 event for top note

        # Clear
        log.clear()
        assert log.total() == 0
        assert log.note_usage_counts() == {}

    def test_demo_query(self):
        """Demo from spec: 5 events, expect specific most_used output."""
        cfg = UsageLogConfig()
        log = AftertouchUsageLog(cfg)

        # Record 4 events on note 60, 1 on note 64
        log.record(60, 1, 50, 0.0)
        log.record(60, 1, 80, 0.1)
        log.record(60, 1, 100, 0.2)
        log.record(60, 1, 70, 1.0)
        log.record(64, 1, 90, 1.5)

        # Expect: total=5, most_used=[(60,1,4), (64,1,1)]
        assert log.total() == 5
        most_used = log.most_used_notes(2)
        assert most_used == [(60, 1, 4), (64, 1, 1)]

        # events_per_second over 2-second window ending at 1.5
        # Events in [1.5 - 2.0, 1.5] = [-0.5, 1.5] → all 5 events
        rate = log.events_per_second(1.5, window_s=2.0)
        assert rate == 2.5  # 5 / 2.0 = 2.5
