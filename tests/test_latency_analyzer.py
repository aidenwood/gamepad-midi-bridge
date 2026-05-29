"""Latency analyzer — round-trip timing and statistics."""
from __future__ import annotations

import pytest

from gamepad_midi_bridge.latency_analyzer import (
    LatencyMeasurement,
    LatencyAnalyzerConfig,
    LatencyAnalyzer,
)


# ================================================================ LatencyMeasurement


def test_latency_measurement_round_trip_ms():
    """round_trip_ms = (received - sent) * 1000."""
    m = LatencyMeasurement(sent_at_s=0.0, received_at_s=0.005, label="test")
    assert m.round_trip_ms == 5.0


def test_latency_measurement_to_dict():
    """Serialization includes computed round_trip_ms."""
    m = LatencyMeasurement(sent_at_s=1.0, received_at_s=1.01, label="cc74")
    d = m.to_dict()
    assert d["sent_at_s"] == 1.0
    assert d["received_at_s"] == 1.01
    assert d["round_trip_ms"] == pytest.approx(10.0)
    assert d["label"] == "cc74"


def test_latency_measurement_from_dict():
    """Deserialization ignores computed round_trip_ms."""
    d = {
        "sent_at_s": 2.0,
        "received_at_s": 2.02,
        "round_trip_ms": 999.0,  # will be ignored
        "label": "L2",
    }
    m = LatencyMeasurement.from_dict(d)
    assert m.sent_at_s == 2.0
    assert m.received_at_s == 2.02
    assert m.round_trip_ms == pytest.approx(20.0)  # recomputed, not from dict
    assert m.label == "L2"


# ================================================================ LatencyAnalyzerConfig


def test_config_default_values():
    """Config defaults are max_measurements=1000, timeout_ms=500."""
    cfg = LatencyAnalyzerConfig()
    assert cfg.max_measurements == 1000
    assert cfg.timeout_ms == 500.0


def test_config_clamps_max_measurements_low():
    """max_measurements < 10 is clamped to 10."""
    cfg = LatencyAnalyzerConfig(max_measurements=5)
    assert cfg.max_measurements == 10


def test_config_clamps_max_measurements_high():
    """max_measurements > 100000 is clamped to 100000."""
    cfg = LatencyAnalyzerConfig(max_measurements=200000)
    assert cfg.max_measurements == 100000


def test_config_clamps_timeout_ms_low():
    """timeout_ms < 10 is clamped to 10."""
    cfg = LatencyAnalyzerConfig(timeout_ms=5.0)
    assert cfg.timeout_ms == 10.0


def test_config_clamps_timeout_ms_high():
    """timeout_ms > 10000 is clamped to 10000."""
    cfg = LatencyAnalyzerConfig(timeout_ms=15000.0)
    assert cfg.timeout_ms == 10000.0


def test_config_to_dict():
    """Serialization."""
    cfg = LatencyAnalyzerConfig(max_measurements=500, timeout_ms=250.0)
    d = cfg.to_dict()
    assert d["max_measurements"] == 500
    assert d["timeout_ms"] == 250.0


def test_config_from_dict():
    """Deserialization."""
    d = {"max_measurements": 750, "timeout_ms": 750.0}
    cfg = LatencyAnalyzerConfig.from_dict(d)
    assert cfg.max_measurements == 750
    assert cfg.timeout_ms == 750.0


# ================================================================ LatencyAnalyzer — empty state


def test_analyzer_empty_mean_is_none():
    """mean_ms() returns None if no measurements."""
    cfg = LatencyAnalyzerConfig()
    a = LatencyAnalyzer(cfg)
    assert a.mean_ms() is None


def test_analyzer_empty_median_is_none():
    """median_ms() returns None if no measurements."""
    cfg = LatencyAnalyzerConfig()
    a = LatencyAnalyzer(cfg)
    assert a.median_ms() is None


def test_analyzer_empty_min_is_none():
    """min_ms() returns None if no measurements."""
    cfg = LatencyAnalyzerConfig()
    a = LatencyAnalyzer(cfg)
    assert a.min_ms() is None


def test_analyzer_empty_max_is_none():
    """max_ms() returns None if no measurements."""
    cfg = LatencyAnalyzerConfig()
    a = LatencyAnalyzer(cfg)
    assert a.max_ms() is None


# ================================================================ LatencyAnalyzer — mark_sent / mark_received


def test_analyzer_mark_sent_and_received():
    """mark_sent + mark_received returns a measurement."""
    cfg = LatencyAnalyzerConfig()
    a = LatencyAnalyzer(cfg)
    a.mark_sent("t1", 0.0)
    m = a.mark_received("t1", 0.005, label="test")
    assert m is not None
    assert m.sent_at_s == 0.0
    assert m.received_at_s == 0.005
    assert m.round_trip_ms == 5.0
    assert m.label == "test"


def test_analyzer_mark_received_unknown_token_returns_none():
    """mark_received with unknown token returns None."""
    cfg = LatencyAnalyzerConfig()
    a = LatencyAnalyzer(cfg)
    m = a.mark_received("unknown", 1.0)
    assert m is None


def test_analyzer_measurement_appended_to_list():
    """Measurements are appended to internal list."""
    cfg = LatencyAnalyzerConfig()
    a = LatencyAnalyzer(cfg)
    a.mark_sent("t1", 0.0)
    a.mark_received("t1", 0.01)
    assert len(a._measurements) == 1


# ================================================================ LatencyAnalyzer — statistics


def test_analyzer_mean_simple():
    """mean_ms over [10, 20, 30] ms ≈ 20 ms."""
    cfg = LatencyAnalyzerConfig()
    a = LatencyAnalyzer(cfg)
    a.mark_sent("t1", 0.0)
    a.mark_received("t1", 0.010)
    a.mark_sent("t2", 0.02)
    a.mark_received("t2", 0.040)
    a.mark_sent("t3", 0.05)
    a.mark_received("t3", 0.080)
    assert a.mean_ms() == 20.0


def test_analyzer_median_even_length():
    """median of even-length sample = avg of two middle."""
    cfg = LatencyAnalyzerConfig()
    a = LatencyAnalyzer(cfg)
    for i, (sent, recv) in enumerate([(0.0, 0.010), (0.02, 0.040), (0.05, 0.070), (0.08, 0.120)]):
        a.mark_sent(f"t{i}", sent)
        a.mark_received(f"t{i}", recv)
    # round-trips: 10, 20, 20, 40 ms
    # sorted: 10, 20, 20, 40
    # median: (20 + 20) / 2 = 20
    assert a.median_ms() == 20.0


def test_analyzer_min_ms():
    """min_ms returns the lowest round-trip."""
    cfg = LatencyAnalyzerConfig()
    a = LatencyAnalyzer(cfg)
    a.mark_sent("t1", 0.0)
    a.mark_received("t1", 0.005)
    a.mark_sent("t2", 0.02)
    a.mark_received("t2", 0.050)
    assert a.min_ms() == 5.0


def test_analyzer_max_ms():
    """max_ms returns the highest round-trip."""
    cfg = LatencyAnalyzerConfig()
    a = LatencyAnalyzer(cfg)
    a.mark_sent("t1", 0.0)
    a.mark_received("t1", 0.005)
    a.mark_sent("t2", 0.02)
    a.mark_received("t2", 0.050)
    assert a.max_ms() == pytest.approx(30.0)


def test_analyzer_percentile_50():
    """percentile_ms(50) ≈ median."""
    cfg = LatencyAnalyzerConfig()
    a = LatencyAnalyzer(cfg)
    for i, (sent, recv) in enumerate([(0.0, 0.010), (0.02, 0.040), (0.05, 0.070), (0.08, 0.120)]):
        a.mark_sent(f"t{i}", sent)
        a.mark_received(f"t{i}", recv)
    # round-trips: 10, 20, 20, 40 ms
    # p50 should match median
    p50 = a.percentile_ms(50)
    assert p50 is not None
    assert p50 == pytest.approx(a.median_ms())


def test_analyzer_jitter_stddev():
    """jitter_ms returns stddev of round-trip times."""
    cfg = LatencyAnalyzerConfig()
    a = LatencyAnalyzer(cfg)
    # Add exactly 2 measurements for stddev
    a.mark_sent("t1", 0.0)
    a.mark_received("t1", 0.010)  # 10 ms
    a.mark_sent("t2", 0.02)
    a.mark_received("t2", 0.030)  # 10 ms
    # stddev([10, 10]) ≈ 0.0 (may have tiny float precision noise)
    assert a.jitter_ms() == pytest.approx(0.0, abs=1e-10)


def test_analyzer_jitter_none_with_one_sample():
    """jitter_ms returns None if < 2 samples."""
    cfg = LatencyAnalyzerConfig()
    a = LatencyAnalyzer(cfg)
    a.mark_sent("t1", 0.0)
    a.mark_received("t1", 0.010)
    assert a.jitter_ms() is None


def test_analyzer_jitter_none_with_zero_samples():
    """jitter_ms returns None if 0 samples."""
    cfg = LatencyAnalyzerConfig()
    a = LatencyAnalyzer(cfg)
    assert a.jitter_ms() is None


# ================================================================ LatencyAnalyzer — max_measurements


def test_analyzer_fifo_eviction_on_overflow():
    """Oldest measurement is removed when count > max_measurements."""
    cfg = LatencyAnalyzerConfig(max_measurements=10)
    a = LatencyAnalyzer(cfg)
    # Add 11 measurements to trigger eviction (max is 10)
    for i in range(11):
        a.mark_sent(f"t{i}", float(i) * 0.01)
        a.mark_received(f"t{i}", float(i) * 0.01 + 0.005)
    # Should keep only last 10 (t1-t10; t0 should be evicted)
    assert len(a._measurements) == 10
    # First measurement should be from t1 (t0 was evicted)
    assert a._measurements[0].sent_at_s == pytest.approx(0.01)  # t1's sent time
    # Last measurement should be from t10
    assert a._measurements[9].sent_at_s == pytest.approx(0.10)  # t10's sent time


# ================================================================ LatencyAnalyzer — prune_timed_out


def test_analyzer_prune_timed_out_removes_stale():
    """prune_timed_out removes pending entries older than timeout_ms."""
    cfg = LatencyAnalyzerConfig(timeout_ms=100.0)  # 0.1 s
    a = LatencyAnalyzer(cfg)
    a.mark_sent("t1", 0.0)
    a.mark_sent("t2", 0.05)
    a.mark_sent("t3", 0.15)
    # At time 0.2s, t1 (0.2s old) and t2 (0.15s old) exceed 0.1s timeout
    # t3 (0.05s old) is still pending
    pruned = a.prune_timed_out(0.2)
    assert pruned == 2
    assert a.pending_count() == 1


def test_analyzer_prune_timed_out_returns_count():
    """prune_timed_out returns count of removed entries."""
    cfg = LatencyAnalyzerConfig(timeout_ms=50.0)
    a = LatencyAnalyzer(cfg)
    for i in range(5):
        a.mark_sent(f"t{i}", float(i) * 0.01)
    pruned = a.prune_timed_out(0.2)
    assert pruned == 5


# ================================================================ LatencyAnalyzer — summary


def test_analyzer_summary_keys():
    """summary() returns dict with expected keys."""
    cfg = LatencyAnalyzerConfig()
    a = LatencyAnalyzer(cfg)
    # Need at least 2 measurements for percentile
    a.mark_sent("t1", 0.0)
    a.mark_received("t1", 0.010)
    a.mark_sent("t2", 0.02)
    a.mark_received("t2", 0.030)
    s = a.summary()
    assert "count" in s
    assert "mean_ms" in s
    assert "median_ms" in s
    assert "min_ms" in s
    assert "max_ms" in s
    assert "jitter_ms" in s
    assert "p95_ms" in s


def test_analyzer_summary_empty():
    """summary() on empty analyzer has count=0, others None."""
    cfg = LatencyAnalyzerConfig()
    a = LatencyAnalyzer(cfg)
    s = a.summary()
    assert s["count"] == 0
    assert s["mean_ms"] is None
    assert s["median_ms"] is None
    assert s["jitter_ms"] is None


# ================================================================ LatencyAnalyzer — clear / pending_count


def test_analyzer_clear_empties_both():
    """clear() removes both pending and measurements."""
    cfg = LatencyAnalyzerConfig()
    a = LatencyAnalyzer(cfg)
    a.mark_sent("t1", 0.0)
    a.mark_sent("t2", 0.01)
    a.mark_received("t1", 0.005)
    assert a.pending_count() == 1
    assert len(a._measurements) == 1
    a.clear()
    assert a.pending_count() == 0
    assert len(a._measurements) == 0


def test_analyzer_pending_count():
    """pending_count returns count of in-flight measurements."""
    cfg = LatencyAnalyzerConfig()
    a = LatencyAnalyzer(cfg)
    a.mark_sent("t1", 0.0)
    a.mark_sent("t2", 0.01)
    a.mark_sent("t3", 0.02)
    a.mark_received("t1", 0.005)
    assert a.pending_count() == 2


# ================================================================ Integration


def test_analyzer_realistic_workflow():
    """Realistic workflow: send multiple, receive some, prune, check stats."""
    cfg = LatencyAnalyzerConfig(max_measurements=100, timeout_ms=500.0)
    a = LatencyAnalyzer(cfg)

    # Send batch
    for i in range(5):
        a.mark_sent(f"msg{i}", 0.0 + i * 0.001)

    # Receive 3 of 5
    a.mark_received("msg0", 0.010)  # 10 ms
    a.mark_received("msg1", 0.012)  # 11 ms
    a.mark_received("msg2", 0.015)  # 14 ms

    # Check state
    assert a.pending_count() == 2
    assert len(a._measurements) == 3

    # Prune old pending (none yet, as we're still at ~0.015s)
    pruned = a.prune_timed_out(0.020)
    assert pruned == 0

    # Receive remaining
    a.mark_received("msg3", 0.020)  # 19 ms
    a.mark_received("msg4", 0.025)  # 24 ms

    # All received
    assert a.pending_count() == 0
    assert len(a._measurements) == 5

    # Check stats
    assert a.mean_ms() is not None
    assert a.median_ms() is not None
    assert a.jitter_ms() is not None
    summary = a.summary()
    assert summary["count"] == 5
