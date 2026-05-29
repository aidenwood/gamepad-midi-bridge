"""Tests for usage_stats module."""
from __future__ import annotations

import threading
import time

import pytest

from gamepad_midi_bridge.usage_stats import UsageTracker


def make_tracker() -> UsageTracker:
    """Fresh tracker for each test (avoids singleton cross-contamination)."""
    return UsageTracker()


# ---------------------------------------------------------------------------
# round-trip: record + snapshot
# ---------------------------------------------------------------------------

def test_record_and_snapshot_empty():
    t = make_tracker()
    assert t.snapshot() == []


def test_record_single():
    t = make_tracker()
    t.record("button", 0)
    records = t.snapshot()
    assert len(records) == 1
    r = records[0]
    assert r.kind == "button"
    assert r.index == 0
    assert r.count == 1
    assert r.last_used_ms > 0


def test_record_increments_count():
    t = make_tracker()
    for _ in range(5):
        t.record("axis", 2)
    records = t.snapshot()
    assert records[0].count == 5


def test_record_multiple_controls():
    t = make_tracker()
    t.record("button", 0)
    t.record("button", 1)
    t.record("axis", 4)
    records = t.snapshot()
    assert len(records) == 3


def test_snapshot_sorted_descending():
    t = make_tracker()
    t.record("button", 0)           # count=1
    for _ in range(3):
        t.record("hat", "up")       # count=3
    t.record("axis", 1)             # count=1
    t.record("axis", 1)             # count=2
    records = t.snapshot()
    counts = [r.count for r in records]
    assert counts == sorted(counts, reverse=True)


def test_snapshot_hat_direction_string_key():
    t = make_tracker()
    t.record("hat", "left")
    t.record("hat", "right")
    records = t.snapshot()
    indices = {r.index for r in records}
    assert "left" in indices
    assert "right" in indices


def test_last_used_ms_updates():
    t = make_tracker()
    t.record("button", 3)
    first_ms = t.snapshot()[0].last_used_ms
    time.sleep(0.01)
    t.record("button", 3)
    second_ms = t.snapshot()[0].last_used_ms
    assert second_ms >= first_ms


# ---------------------------------------------------------------------------
# top_n
# ---------------------------------------------------------------------------

def test_top_n_returns_n_most_used():
    t = make_tracker()
    for i in range(10):
        for _ in range(i + 1):
            t.record("button", i)
    top = t.top_n(5)
    assert len(top) == 5
    # All should be the 5 highest counts
    assert top[0].count >= top[-1].count


def test_top_n_when_fewer_than_n():
    t = make_tracker()
    t.record("button", 0)
    top = t.top_n(5)
    assert len(top) == 1


def test_top_n_default_is_five():
    t = make_tracker()
    for i in range(8):
        t.record("button", i)
    assert len(t.top_n()) == 5


def test_top_n_zero():
    t = make_tracker()
    t.record("button", 0)
    assert t.top_n(0) == []


# ---------------------------------------------------------------------------
# reset
# ---------------------------------------------------------------------------

def test_reset_clears_all():
    t = make_tracker()
    t.record("button", 0)
    t.record("axis", 1)
    t.reset()
    assert t.snapshot() == []


def test_reset_then_record_again():
    t = make_tracker()
    t.record("button", 0)
    t.reset()
    t.record("button", 0)
    records = t.snapshot()
    assert len(records) == 1
    assert records[0].count == 1


# ---------------------------------------------------------------------------
# thread safety
# ---------------------------------------------------------------------------

def test_concurrent_records_safe():
    """Multiple threads recording to the same key must not lose counts."""
    t = make_tracker()
    n_threads = 20
    records_per_thread = 100

    def worker():
        for _ in range(records_per_thread):
            t.record("button", 0)

    threads = [threading.Thread(target=worker) for _ in range(n_threads)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()

    records = t.snapshot()
    assert len(records) == 1
    assert records[0].count == n_threads * records_per_thread


def test_concurrent_mixed_keys():
    """Many threads recording different keys — total record count is correct."""
    t = make_tracker()
    n_threads = 10

    def worker(idx):
        for _ in range(50):
            t.record("button", idx % 3)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n_threads)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()

    total = sum(r.count for r in t.snapshot())
    assert total == n_threads * 50
