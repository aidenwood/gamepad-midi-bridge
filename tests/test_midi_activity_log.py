"""Tests for midi_activity_log module."""
from __future__ import annotations

import time

import pytest

from gamepad_midi_bridge.midi_activity_log import (
    MidiEvent,
    MidiActivityLogConfig,
    classify_message,
    MidiActivityLog,
)


# ---------------------------------------------------------------------------
# classify_message tests
# ---------------------------------------------------------------------------


def test_classify_note_on():
    """0x90-0x9F are note_on."""
    kind, channel = classify_message([0x90, 60, 100])
    assert kind == "note_on"
    assert channel == 1

    kind, channel = classify_message([0x9F, 60, 100])
    assert kind == "note_on"
    assert channel == 16


def test_classify_note_off():
    """0x80-0x8F are note_off."""
    kind, channel = classify_message([0x80, 60, 100])
    assert kind == "note_off"
    assert channel == 1

    kind, channel = classify_message([0x8F, 60, 100])
    assert kind == "note_off"
    assert channel == 16


def test_classify_cc():
    """0xB0-0xBF are cc."""
    kind, channel = classify_message([0xB0, 7, 127])
    assert kind == "cc"
    assert channel == 1

    kind, channel = classify_message([0xBF, 1, 64])
    assert kind == "cc"
    assert channel == 16


def test_classify_program_change():
    """0xC0-0xCF are program_change."""
    kind, channel = classify_message([0xC0, 5])
    assert kind == "program_change"
    assert channel == 1

    kind, channel = classify_message([0xCF, 10])
    assert kind == "program_change"
    assert channel == 16


def test_classify_pitch_bend():
    """0xE0-0xEF are pitch_bend."""
    kind, channel = classify_message([0xE0, 0, 64])
    assert kind == "pitch_bend"
    assert channel == 1

    kind, channel = classify_message([0xEF, 0, 64])
    assert kind == "pitch_bend"
    assert channel == 16


def test_classify_sysex():
    """0xF0 is sysex."""
    kind, channel = classify_message([0xF0, 0x43, 0x12])
    assert kind == "sysex"
    assert channel is None


def test_classify_clock():
    """0xF8 is clock."""
    kind, channel = classify_message([0xF8])
    assert kind == "clock"
    assert channel is None


def test_classify_unknown():
    """Invalid status bytes are unknown."""
    kind, channel = classify_message([0xFF])
    assert kind == "unknown"
    assert channel is None

    kind, channel = classify_message([])
    assert kind == "unknown"
    assert channel is None


def test_classify_aftertouch_poly():
    """0xA0-0xAF are aftertouch."""
    kind, channel = classify_message([0xA0, 60, 100])
    assert kind == "aftertouch"
    assert channel == 1


def test_classify_aftertouch_channel():
    """0xD0-0xDF are channel aftertouch."""
    kind, channel = classify_message([0xD0, 100])
    assert kind == "aftertouch"
    assert channel == 1


# ---------------------------------------------------------------------------
# MidiEvent serialization
# ---------------------------------------------------------------------------


def test_midi_event_to_dict():
    """MidiEvent.to_dict() round-trips."""
    event = MidiEvent(
        timestamp_s=1.5,
        direction="in",
        message_bytes=[0x90, 60, 100],
        port_name="controller",
        tags=["note_on", "ch1"],
        kind="note_on",
        channel=1,
    )
    d = event.to_dict()
    assert d["timestamp_s"] == 1.5
    assert d["direction"] == "in"
    assert d["message_bytes"] == [0x90, 60, 100]
    assert d["port_name"] == "controller"
    assert d["tags"] == ["note_on", "ch1"]
    assert d["kind"] == "note_on"
    assert d["channel"] == 1


def test_midi_event_from_dict():
    """MidiEvent.from_dict() reconstructs event."""
    d = {
        "timestamp_s": 2.0,
        "direction": "out",
        "message_bytes": [0xB0, 7, 127],
        "port_name": "synth",
        "tags": ["volume"],
        "kind": "cc",
        "channel": 1,
    }
    event = MidiEvent.from_dict(d)
    assert event.timestamp_s == 2.0
    assert event.direction == "out"
    assert event.message_bytes == [0xB0, 7, 127]
    assert event.port_name == "synth"
    assert event.tags == ["volume"]
    assert event.kind == "cc"
    assert event.channel == 1


def test_midi_event_from_dict_with_extra_keys():
    """from_dict ignores extra keys."""
    d = {
        "timestamp_s": 1.0,
        "direction": "in",
        "message_bytes": [0x90, 60, 100],
        "extra_key": "ignored",
    }
    event = MidiEvent.from_dict(d)
    assert event.timestamp_s == 1.0
    assert event.direction == "in"


# ---------------------------------------------------------------------------
# MidiActivityLogConfig
# ---------------------------------------------------------------------------


def test_config_defaults():
    """Default config has max_events=1000."""
    cfg = MidiActivityLogConfig()
    assert cfg.max_events == 1000


def test_config_clamp_min():
    """max_events < 100 is clamped to 100."""
    cfg = MidiActivityLogConfig(max_events=50)
    assert cfg.max_events == 100


def test_config_clamp_max():
    """max_events > 100000 is clamped to 100000."""
    cfg = MidiActivityLogConfig(max_events=200000)
    assert cfg.max_events == 100000


def test_config_valid_range():
    """max_events in valid range stays unchanged."""
    cfg = MidiActivityLogConfig(max_events=5000)
    assert cfg.max_events == 5000


def test_config_to_dict():
    """Config.to_dict() round-trips."""
    cfg = MidiActivityLogConfig(max_events=500)
    d = cfg.to_dict()
    assert d["max_events"] == 500


def test_config_from_dict():
    """Config.from_dict() reconstructs."""
    d = {"max_events": 2000}
    cfg = MidiActivityLogConfig.from_dict(d)
    assert cfg.max_events == 2000


# ---------------------------------------------------------------------------
# MidiActivityLog: record + events
# ---------------------------------------------------------------------------


def test_log_empty():
    """Fresh log is empty."""
    cfg = MidiActivityLogConfig(max_events=100)
    log = MidiActivityLog(cfg)
    assert log.total() == 0
    assert log.events() == []


def test_log_record_single():
    """Recording a single event."""
    cfg = MidiActivityLogConfig(max_events=100)
    log = MidiActivityLog(cfg)
    ts = time.time()
    event = log.record("out", [0x90, 60, 100], ts, port_name="ctrl")
    assert log.total() == 1
    assert event.direction == "out"
    assert event.kind == "note_on"
    assert event.channel == 1
    assert event.port_name == "ctrl"


def test_log_record_returns_event():
    """record() returns the created event."""
    cfg = MidiActivityLogConfig(max_events=100)
    log = MidiActivityLog(cfg)
    ts = time.time()
    returned = log.record("in", [0xB0, 7, 64], ts)
    assert returned.direction == "in"
    assert returned.kind == "cc"
    assert returned.timestamp_s == ts


def test_log_record_multiple():
    """Recording multiple events preserves order."""
    cfg = MidiActivityLogConfig(max_events=100)
    log = MidiActivityLog(cfg)
    log.record("in", [0x90, 60, 100], 1.0)
    log.record("out", [0xB0, 7, 127], 2.0)
    log.record("in", [0x80, 60, 0], 3.0)
    events = log.events()
    assert len(events) == 3
    assert events[0].timestamp_s == 1.0
    assert events[1].timestamp_s == 2.0
    assert events[2].timestamp_s == 3.0


# ---------------------------------------------------------------------------
# recent()
# ---------------------------------------------------------------------------


def test_recent_returns_last_n():
    """recent(n) returns the last n events."""
    cfg = MidiActivityLogConfig(max_events=100)
    log = MidiActivityLog(cfg)
    for i in range(10):
        log.record("in", [0x90, 60 + i, 100], float(i))
    recent = log.recent(3)
    assert len(recent) == 3
    assert recent[0].timestamp_s == 7.0
    assert recent[1].timestamp_s == 8.0
    assert recent[2].timestamp_s == 9.0


def test_recent_when_fewer_than_n():
    """recent(n) when total < n returns all."""
    cfg = MidiActivityLogConfig(max_events=100)
    log = MidiActivityLog(cfg)
    for i in range(2):
        log.record("in", [0x90, 60, 100], float(i))
    recent = log.recent(10)
    assert len(recent) == 2


def test_recent_zero():
    """recent(0) returns empty list."""
    cfg = MidiActivityLogConfig(max_events=100)
    log = MidiActivityLog(cfg)
    log.record("in", [0x90, 60, 100], 1.0)
    assert log.recent(0) == []


def test_recent_negative():
    """recent(negative) returns empty list."""
    cfg = MidiActivityLogConfig(max_events=100)
    log = MidiActivityLog(cfg)
    log.record("in", [0x90, 60, 100], 1.0)
    assert log.recent(-5) == []


# ---------------------------------------------------------------------------
# filter_by_kind()
# ---------------------------------------------------------------------------


def test_filter_by_kind_note_on():
    """filter_by_kind(['note_on']) returns only note_on events."""
    cfg = MidiActivityLogConfig(max_events=100)
    log = MidiActivityLog(cfg)
    log.record("in", [0x90, 60, 100], 1.0)
    log.record("out", [0xB0, 7, 127], 2.0)
    log.record("in", [0x90, 62, 100], 3.0)
    result = log.filter_by_kind(["note_on"])
    assert len(result) == 2
    assert all(e.kind == "note_on" for e in result)


def test_filter_by_kind_multiple():
    """filter_by_kind accepts multiple kinds."""
    cfg = MidiActivityLogConfig(max_events=100)
    log = MidiActivityLog(cfg)
    log.record("in", [0x90, 60, 100], 1.0)  # note_on
    log.record("out", [0xB0, 7, 127], 2.0)  # cc
    log.record("in", [0x80, 60, 0], 3.0)    # note_off
    result = log.filter_by_kind(["note_on", "note_off"])
    assert len(result) == 2
    assert {e.kind for e in result} == {"note_on", "note_off"}


def test_filter_by_kind_empty():
    """filter_by_kind([]) returns empty."""
    cfg = MidiActivityLogConfig(max_events=100)
    log = MidiActivityLog(cfg)
    log.record("in", [0x90, 60, 100], 1.0)
    result = log.filter_by_kind([])
    assert result == []


# ---------------------------------------------------------------------------
# filter_by_direction()
# ---------------------------------------------------------------------------


def test_filter_by_direction_in():
    """filter_by_direction('in') returns only input events."""
    cfg = MidiActivityLogConfig(max_events=100)
    log = MidiActivityLog(cfg)
    log.record("in", [0x90, 60, 100], 1.0)
    log.record("out", [0xB0, 7, 127], 2.0)
    log.record("in", [0x80, 60, 0], 3.0)
    result = log.filter_by_direction("in")
    assert len(result) == 2
    assert all(e.direction == "in" for e in result)


def test_filter_by_direction_out():
    """filter_by_direction('out') returns only output events."""
    cfg = MidiActivityLogConfig(max_events=100)
    log = MidiActivityLog(cfg)
    log.record("in", [0x90, 60, 100], 1.0)
    log.record("out", [0xB0, 7, 127], 2.0)
    result = log.filter_by_direction("out")
    assert len(result) == 1
    assert result[0].direction == "out"


# ---------------------------------------------------------------------------
# filter_by_channel()
# ---------------------------------------------------------------------------


def test_filter_by_channel():
    """filter_by_channel(n) returns events on channel n."""
    cfg = MidiActivityLogConfig(max_events=100)
    log = MidiActivityLog(cfg)
    log.record("in", [0x90, 60, 100], 1.0)  # channel 1
    log.record("in", [0x91, 60, 100], 2.0)  # channel 2
    log.record("in", [0x90, 60, 100], 3.0)  # channel 1
    result = log.filter_by_channel(1)
    assert len(result) == 2
    assert all(e.channel == 1 for e in result)


def test_filter_by_channel_no_match():
    """filter_by_channel for a channel with no events."""
    cfg = MidiActivityLogConfig(max_events=100)
    log = MidiActivityLog(cfg)
    log.record("in", [0x90, 60, 100], 1.0)  # channel 1
    result = log.filter_by_channel(5)
    assert result == []


# ---------------------------------------------------------------------------
# filter_by_timerange()
# ---------------------------------------------------------------------------


def test_filter_by_timerange_inclusive():
    """filter_by_timerange includes both boundaries."""
    cfg = MidiActivityLogConfig(max_events=100)
    log = MidiActivityLog(cfg)
    log.record("in", [0x90, 60, 100], 1.0)
    log.record("in", [0x90, 60, 100], 2.0)
    log.record("in", [0x90, 60, 100], 3.0)
    log.record("in", [0x90, 60, 100], 4.0)
    result = log.filter_by_timerange(2.0, 3.0)
    assert len(result) == 2
    assert result[0].timestamp_s == 2.0
    assert result[1].timestamp_s == 3.0


def test_filter_by_timerange_no_match():
    """filter_by_timerange with no events in range."""
    cfg = MidiActivityLogConfig(max_events=100)
    log = MidiActivityLog(cfg)
    log.record("in", [0x90, 60, 100], 1.0)
    log.record("in", [0x90, 60, 100], 5.0)
    result = log.filter_by_timerange(2.0, 3.0)
    assert result == []


# ---------------------------------------------------------------------------
# count_by_kind()
# ---------------------------------------------------------------------------


def test_count_by_kind():
    """count_by_kind() returns correct counts per kind."""
    cfg = MidiActivityLogConfig(max_events=100)
    log = MidiActivityLog(cfg)
    log.record("in", [0x90, 60, 100], 1.0)  # note_on
    log.record("out", [0xB0, 7, 127], 2.0)  # cc
    log.record("in", [0x90, 62, 100], 3.0)  # note_on
    log.record("in", [0xB0, 1, 64], 4.0)    # cc
    counts = log.count_by_kind()
    assert counts["note_on"] == 2
    assert counts["cc"] == 2


def test_count_by_kind_empty_log():
    """count_by_kind() on empty log returns empty dict."""
    cfg = MidiActivityLogConfig(max_events=100)
    log = MidiActivityLog(cfg)
    counts = log.count_by_kind()
    assert counts == {}


# ---------------------------------------------------------------------------
# clear()
# ---------------------------------------------------------------------------


def test_clear_empties_log():
    """clear() removes all events."""
    cfg = MidiActivityLogConfig(max_events=100)
    log = MidiActivityLog(cfg)
    log.record("in", [0x90, 60, 100], 1.0)
    log.record("in", [0xB0, 7, 127], 2.0)
    log.clear()
    assert log.total() == 0
    assert log.events() == []


def test_clear_then_record():
    """Recording after clear() works normally."""
    cfg = MidiActivityLogConfig(max_events=100)
    log = MidiActivityLog(cfg)
    log.record("in", [0x90, 60, 100], 1.0)
    log.clear()
    log.record("in", [0xB0, 7, 127], 2.0)
    assert log.total() == 1
    assert log.events()[0].kind == "cc"


# ---------------------------------------------------------------------------
# max_events FIFO eviction
# ---------------------------------------------------------------------------


def test_fifo_eviction_when_max_exceeded():
    """When total > max_events, oldest event is removed."""
    cfg = MidiActivityLogConfig(max_events=105)  # Use 105 to test eviction
    log = MidiActivityLog(cfg)
    for i in range(110):
        log.record("in", [0x90, 60, 100], float(i))
    events = log.events()
    assert len(events) == 105
    assert events[0].timestamp_s == 5.0  # First 5 were evicted
    assert events[-1].timestamp_s == 109.0


def test_fifo_eviction_preserves_order():
    """FIFO eviction preserves event order."""
    cfg = MidiActivityLogConfig(max_events=103)
    log = MidiActivityLog(cfg)
    for i in range(108):
        log.record("in", [0x90, 60 + i, 100], float(i))
    events = log.events()
    assert [e.timestamp_s for e in events] == [float(i) for i in range(5, 108)]


# ---------------------------------------------------------------------------
# Integration: complex scenario
# ---------------------------------------------------------------------------


def test_complex_scenario():
    """Record multiple events, filter, count, verify."""
    cfg = MidiActivityLogConfig(max_events=100)
    log = MidiActivityLog(cfg)

    # Record mixed events
    log.record("in", [0x90, 60, 100], 1.0, port_name="ctrl")  # note_on ch1
    log.record("out", [0x91, 62, 100], 2.0, port_name="synth")  # note_on ch2
    log.record("out", [0xB0, 7, 127], 3.0, port_name="synth")  # cc ch1
    log.record("in", [0xB1, 1, 64], 4.0, port_name="ctrl")  # cc ch2
    log.record("in", [0x80, 60, 0], 5.0, port_name="ctrl")  # note_off ch1

    # Verify total
    assert log.total() == 5

    # Filter by kind
    note_ons = log.filter_by_kind(["note_on"])
    assert len(note_ons) == 2

    # Filter by direction
    inputs = log.filter_by_direction("in")
    assert len(inputs) == 3

    # Filter by channel
    ch1_events = log.filter_by_channel(1)
    assert len(ch1_events) == 3

    # Count by kind
    counts = log.count_by_kind()
    assert counts["note_on"] == 2
    assert counts["cc"] == 2
    assert counts["note_off"] == 1

    # Recent
    recent_3 = log.recent(3)
    assert len(recent_3) == 3
    assert recent_3[0].timestamp_s == 3.0


# ---------------------------------------------------------------------------
# Tags and port_name
# ---------------------------------------------------------------------------


def test_record_with_tags():
    """record() preserves tags."""
    cfg = MidiActivityLogConfig(max_events=100)
    log = MidiActivityLog(cfg)
    event = log.record(
        "in",
        [0x90, 60, 100],
        1.0,
        port_name="ctrl",
        tags=["pedal", "kick"],
    )
    assert event.tags == ["pedal", "kick"]
    assert event.port_name == "ctrl"


def test_record_without_tags():
    """record() defaults tags to empty list."""
    cfg = MidiActivityLogConfig(max_events=100)
    log = MidiActivityLog(cfg)
    event = log.record("in", [0x90, 60, 100], 1.0)
    assert event.tags == []
    assert event.port_name == ""
