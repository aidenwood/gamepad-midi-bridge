"""Tests for setlist_time_tracker module."""
from __future__ import annotations

import pytest

from gamepad_midi_bridge.setlist_time_tracker import (
    PresetTimeRecord,
    SetlistTimeTracker,
)


# ---------------------------------------------------------------------------
# PresetTimeRecord: empty and serialization
# ---------------------------------------------------------------------------


def test_preset_record_init():
    rec = PresetTimeRecord(preset_slug="ambient-pad")
    assert rec.preset_slug == "ambient-pad"
    assert rec.total_seconds == 0.0
    assert rec.switch_count == 0
    assert rec.last_active_at is None


def test_preset_record_to_dict():
    rec = PresetTimeRecord(
        preset_slug="drums",
        total_seconds=15.5,
        switch_count=3,
        last_active_at=1000.0,
    )
    d = rec.to_dict()
    assert d["preset_slug"] == "drums"
    assert d["total_seconds"] == 15.5
    assert d["switch_count"] == 3
    assert d["last_active_at"] == 1000.0


def test_preset_record_from_dict():
    d = {
        "preset_slug": "synth-lead",
        "total_seconds": 42.1,
        "switch_count": 2,
        "last_active_at": 2000.5,
    }
    rec = PresetTimeRecord.from_dict(d)
    assert rec.preset_slug == "synth-lead"
    assert rec.total_seconds == 42.1
    assert rec.switch_count == 2
    assert rec.last_active_at == 2000.5


def test_preset_record_round_trip():
    orig = PresetTimeRecord(
        preset_slug="test",
        total_seconds=99.9,
        switch_count=5,
        last_active_at=9999.0,
    )
    d = orig.to_dict()
    restored = PresetTimeRecord.from_dict(d)
    assert restored.preset_slug == orig.preset_slug
    assert restored.total_seconds == orig.total_seconds
    assert restored.switch_count == orig.switch_count
    assert restored.last_active_at == orig.last_active_at


def test_preset_record_from_dict_with_defaults():
    """Missing optional fields should get default values."""
    d = {"preset_slug": "minimal"}
    rec = PresetTimeRecord.from_dict(d)
    assert rec.preset_slug == "minimal"
    assert rec.total_seconds == 0.0
    assert rec.switch_count == 0
    assert rec.last_active_at is None


# ---------------------------------------------------------------------------
# SetlistTimeTracker: basic operations
# ---------------------------------------------------------------------------


def test_tracker_init_empty():
    t = SetlistTimeTracker()
    assert t.get_record("anything") is None
    assert t.all_records() == {}


def test_start_session():
    t = SetlistTimeTracker()
    t.start_session(0.0)
    # No records yet; session just started
    assert t.total_session_seconds() == 0.0


def test_set_active_creates_record():
    t = SetlistTimeTracker()
    t.start_session(0.0)
    t.set_active("preset-a", 0.0)
    rec = t.get_record("preset-a")
    assert rec is not None
    assert rec.preset_slug == "preset-a"
    assert rec.switch_count == 1


def test_set_active_accumulates_duration():
    """Switch from a to b: a's time is flushed and accumulated."""
    t = SetlistTimeTracker()
    t.start_session(0.0)
    t.set_active("a", 0.0)
    t.set_active("b", 5.0)  # 5 seconds on "a"

    rec_a = t.get_record("a")
    assert rec_a is not None
    assert rec_a.total_seconds == 5.0
    assert rec_a.switch_count == 1


def test_set_active_multiple_switches():
    """Switch a → b → a → end: check durations and switch counts."""
    t = SetlistTimeTracker()
    t.start_session(0.0)
    t.set_active("a", 0.0)
    t.set_active("b", 5.0)  # a gets 5s
    t.set_active("a", 8.0)  # b gets 3s
    t.end_session(10.0)      # a gets +2s more = 7s total

    rec_a = t.get_record("a")
    rec_b = t.get_record("b")
    assert rec_a.total_seconds == 7.0
    assert rec_a.switch_count == 2
    assert rec_b.total_seconds == 3.0
    assert rec_b.switch_count == 1


def test_end_session_flushes_current():
    """end_session should accumulate the current preset's elapsed time."""
    t = SetlistTimeTracker()
    t.start_session(0.0)
    t.set_active("preset-x", 0.0)
    t.end_session(10.0)

    rec = t.get_record("preset-x")
    assert rec.total_seconds == 10.0


def test_all_records_returns_copy():
    """all_records() should return a copy, not the internal dict."""
    t = SetlistTimeTracker()
    t.start_session(0.0)
    t.set_active("a", 0.0)

    records1 = t.all_records()
    records2 = t.all_records()
    assert records1 is not records2  # Different dict objects
    assert records1 == records2  # But same content


def test_get_record_returns_none_for_nonexistent():
    t = SetlistTimeTracker()
    assert t.get_record("never-seen") is None


# ---------------------------------------------------------------------------
# SetlistTimeTracker: total_session_seconds and duration tracking
# ---------------------------------------------------------------------------


def test_total_session_seconds_not_started():
    t = SetlistTimeTracker()
    assert t.total_session_seconds() == 0.0


def test_total_session_seconds_during_session():
    t = SetlistTimeTracker()
    t.start_session(0.0)
    t.set_active("a", 0.0)
    t.set_active("b", 3.5)
    t.set_active("c", 7.2)
    # Total time recorded: 3.5 + 3.7 = 7.2 seconds
    assert t.total_session_seconds() == pytest.approx(7.2, abs=0.01)


def test_total_session_seconds_after_end():
    t = SetlistTimeTracker()
    t.start_session(0.0)
    t.set_active("a", 0.0)
    t.set_active("b", 5.0)
    t.end_session(8.0)
    # a=5s, b=3s, total=8s
    assert t.total_session_seconds() == pytest.approx(8.0, abs=0.01)


# ---------------------------------------------------------------------------
# SetlistTimeTracker: most_used and least_used
# ---------------------------------------------------------------------------


def test_most_used_empty():
    t = SetlistTimeTracker()
    assert t.most_used() == []


def test_most_used_single():
    t = SetlistTimeTracker()
    t.start_session(0.0)
    t.set_active("only-one", 0.0)
    t.end_session(5.0)

    most = t.most_used(1)
    assert len(most) == 1
    assert most[0].preset_slug == "only-one"


def test_most_used_sorts_descending():
    t = SetlistTimeTracker()
    t.start_session(0.0)
    t.set_active("a", 0.0)    # a will get 2s
    t.set_active("b", 2.0)    # b will get 5s
    t.set_active("c", 7.0)    # c will get 3s
    t.end_session(10.0)

    most = t.most_used(3)
    times = [r.total_seconds for r in most]
    assert times == sorted(times, reverse=True)
    # Most used should be b (5s), c (3s), a (2s)
    assert most[0].preset_slug == "b"


def test_most_used_limits_n():
    t = SetlistTimeTracker()
    t.start_session(0.0)
    for i in range(10):
        t.set_active(f"preset-{i}", float(i))
    t.end_session(10.0)

    top3 = t.most_used(3)
    assert len(top3) == 3


def test_most_used_fewer_than_n():
    t = SetlistTimeTracker()
    t.start_session(0.0)
    t.set_active("a", 0.0)
    t.set_active("b", 1.0)
    t.end_session(2.0)

    top5 = t.most_used(5)
    assert len(top5) == 2  # Only 2 presets exist


def test_least_used_excludes_zero():
    """least_used should exclude presets with 0 total_seconds."""
    t = SetlistTimeTracker()
    t.start_session(0.0)
    # Create a record with 0 seconds by starting but never switching
    t.set_active("zero-sec", 0.0)
    t.set_active("a", 0.0)  # This flushes "zero-sec" with 0 duration
    t.set_active("b", 5.0)
    t.end_session(8.0)

    least = t.least_used(5)
    # Should have a (5s) and b (3s), but not "zero-sec" (0s)
    for rec in least:
        assert rec.total_seconds > 0


def test_least_used_sorts_ascending():
    t = SetlistTimeTracker()
    t.start_session(0.0)
    t.set_active("a", 0.0)    # a: 2s
    t.set_active("b", 2.0)    # b: 5s
    t.set_active("c", 7.0)    # c: 3s
    t.end_session(10.0)

    least = t.least_used(3)
    times = [r.total_seconds for r in least]
    assert times == sorted(times)


def test_least_used_empty():
    t = SetlistTimeTracker()
    assert t.least_used() == []


# ---------------------------------------------------------------------------
# SetlistTimeTracker: summary
# ---------------------------------------------------------------------------


def test_summary_keys():
    t = SetlistTimeTracker()
    t.start_session(0.0)
    t.set_active("a", 0.0)
    t.end_session(5.0)

    summary = t.summary()
    assert "session_seconds" in summary
    assert "preset_count" in summary
    assert "most_used_slug" in summary
    assert "total_switches" in summary


def test_summary_values():
    t = SetlistTimeTracker()
    t.start_session(0.0)
    t.set_active("a", 0.0)
    t.set_active("b", 3.0)
    t.set_active("a", 5.0)
    t.end_session(10.0)

    summary = t.summary()
    assert summary["session_seconds"] == pytest.approx(10.0, abs=0.01)
    assert summary["preset_count"] == 2
    assert summary["most_used_slug"] == "a"  # a has 8s, b has 2s
    assert summary["total_switches"] == 3


def test_summary_most_used_slug_none_if_empty():
    t = SetlistTimeTracker()
    summary = t.summary()
    assert summary["most_used_slug"] is None
    assert summary["preset_count"] == 0


# ---------------------------------------------------------------------------
# SetlistTimeTracker: tick
# ---------------------------------------------------------------------------


def test_tick_updates_last_active_at():
    t = SetlistTimeTracker()
    t.start_session(0.0)
    t.set_active("a", 0.0)
    initial_last = t.get_record("a").last_active_at
    t.tick(5.0)
    updated_last = t.get_record("a").last_active_at
    assert updated_last == 5.0
    assert updated_last > initial_last


def test_tick_no_current_preset():
    """tick should do nothing if no preset is active."""
    t = SetlistTimeTracker()
    t.start_session(0.0)
    # No set_active called; should not crash
    t.tick(1.0)


# ---------------------------------------------------------------------------
# SetlistTimeTracker: reset
# ---------------------------------------------------------------------------


def test_reset_clears_all():
    t = SetlistTimeTracker()
    t.start_session(0.0)
    t.set_active("a", 0.0)
    t.set_active("b", 5.0)
    t.reset()

    assert t.all_records() == {}
    assert t.total_session_seconds() == 0.0


def test_reset_clears_session_state():
    t = SetlistTimeTracker()
    t.start_session(0.0)
    t.set_active("a", 0.0)
    t.reset()

    # After reset, session is not started
    assert t._current_preset is None
    assert t._session_start_at is None
    assert t._current_start_at is None


def test_reset_then_start_new_session():
    t = SetlistTimeTracker()
    t.start_session(0.0)
    t.set_active("a", 0.0)
    t.set_active("b", 5.0)
    t.reset()

    # Start a fresh session
    t.start_session(100.0)
    t.set_active("new-preset", 100.0)
    t.end_session(105.0)

    records = t.all_records()
    assert "a" not in records
    assert "b" not in records
    assert "new-preset" in records
    assert records["new-preset"].total_seconds == pytest.approx(5.0, abs=0.01)


# ---------------------------------------------------------------------------
# Integration: complex scenario from spec
# ---------------------------------------------------------------------------


def test_spec_example_a_b_a_end():
    """Spec example: a → b → a → end; expect a=7s (2+2), b=3s"""
    t = SetlistTimeTracker()
    t.start_session(0.0)
    t.set_active("a", 0.0)
    t.set_active("b", 5.0)
    t.set_active("a", 8.0)
    t.end_session(10.0)

    rec_a = t.get_record("a")
    rec_b = t.get_record("b")
    assert rec_a.total_seconds == pytest.approx(7.0, abs=0.01)
    assert rec_a.switch_count == 2
    assert rec_b.total_seconds == pytest.approx(3.0, abs=0.01)
    assert rec_b.switch_count == 1
