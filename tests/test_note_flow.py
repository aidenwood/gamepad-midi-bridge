"""Tests for note-flow timeline bucketing.

NoteFlow bins note event timestamps into fixed-size time buckets, enabling
activity-timeline visualization. Pure stdlib, no Qt.
"""
from __future__ import annotations

import pytest


class TestNoteFlowConfig:
    """NoteFlowConfig — clamp parameters on construction."""

    def test_config_defaults(self):
        from gamepad_midi_bridge.note_flow import NoteFlowConfig
        cfg = NoteFlowConfig()
        assert cfg.bucket_seconds == 1.0
        assert cfg.max_buckets == 600

    def test_config_clamp_bucket_seconds_below_0_05(self):
        from gamepad_midi_bridge.note_flow import NoteFlowConfig
        cfg = NoteFlowConfig(bucket_seconds=0.01)
        assert cfg.bucket_seconds == 0.05
        cfg = NoteFlowConfig(bucket_seconds=0.0)
        assert cfg.bucket_seconds == 0.05

    def test_config_clamp_bucket_seconds_above_3600(self):
        from gamepad_midi_bridge.note_flow import NoteFlowConfig
        cfg = NoteFlowConfig(bucket_seconds=3601.0)
        assert cfg.bucket_seconds == 3600.0
        cfg = NoteFlowConfig(bucket_seconds=9999.0)
        assert cfg.bucket_seconds == 3600.0

    def test_config_no_clamp_bucket_seconds_in_range(self):
        from gamepad_midi_bridge.note_flow import NoteFlowConfig
        cfg = NoteFlowConfig(bucket_seconds=0.5)
        assert cfg.bucket_seconds == 0.5
        cfg = NoteFlowConfig(bucket_seconds=2.0)
        assert cfg.bucket_seconds == 2.0
        cfg = NoteFlowConfig(bucket_seconds=1800.0)
        assert cfg.bucket_seconds == 1800.0

    def test_config_clamp_max_buckets_below_10(self):
        from gamepad_midi_bridge.note_flow import NoteFlowConfig
        cfg = NoteFlowConfig(max_buckets=5)
        assert cfg.max_buckets == 10
        cfg = NoteFlowConfig(max_buckets=0)
        assert cfg.max_buckets == 10

    def test_config_clamp_max_buckets_above_100000(self):
        from gamepad_midi_bridge.note_flow import NoteFlowConfig
        cfg = NoteFlowConfig(max_buckets=100001)
        assert cfg.max_buckets == 100000
        cfg = NoteFlowConfig(max_buckets=999999)
        assert cfg.max_buckets == 100000

    def test_config_no_clamp_max_buckets_in_range(self):
        from gamepad_midi_bridge.note_flow import NoteFlowConfig
        cfg = NoteFlowConfig(max_buckets=1000)
        assert cfg.max_buckets == 1000
        cfg = NoteFlowConfig(max_buckets=50000)
        assert cfg.max_buckets == 50000

    def test_config_to_dict(self):
        from gamepad_midi_bridge.note_flow import NoteFlowConfig
        cfg = NoteFlowConfig(bucket_seconds=0.5, max_buckets=500)
        d = cfg.to_dict()
        assert d["bucket_seconds"] == 0.5
        assert d["max_buckets"] == 500

    def test_config_from_dict(self):
        from gamepad_midi_bridge.note_flow import NoteFlowConfig
        d = {"bucket_seconds": 2.0, "max_buckets": 1000}
        cfg = NoteFlowConfig.from_dict(d)
        assert cfg.bucket_seconds == 2.0
        assert cfg.max_buckets == 1000

    def test_config_round_trip(self):
        from gamepad_midi_bridge.note_flow import NoteFlowConfig
        original = NoteFlowConfig(bucket_seconds=0.25, max_buckets=800)
        d = original.to_dict()
        restored = NoteFlowConfig.from_dict(d)
        assert restored.bucket_seconds == original.bucket_seconds
        assert restored.max_buckets == original.max_buckets

    def test_config_from_dict_with_missing_keys(self):
        from gamepad_midi_bridge.note_flow import NoteFlowConfig
        d = {}  # Empty dict
        cfg = NoteFlowConfig.from_dict(d)
        assert cfg.bucket_seconds == 1.0  # Default
        assert cfg.max_buckets == 600  # Default


class TestNoteFlow:
    """NoteFlow — record, query, and analyze note activity buckets."""

    def test_empty_buckets_list(self):
        from gamepad_midi_bridge.note_flow import NoteFlow, NoteFlowConfig
        cfg = NoteFlowConfig()
        nf = NoteFlow(cfg)
        assert nf.buckets() == []

    def test_empty_total_is_zero(self):
        from gamepad_midi_bridge.note_flow import NoteFlow, NoteFlowConfig
        cfg = NoteFlowConfig()
        nf = NoteFlow(cfg)
        assert nf.total() == 0

    def test_empty_peak_is_zero(self):
        from gamepad_midi_bridge.note_flow import NoteFlow, NoteFlowConfig
        cfg = NoteFlowConfig()
        nf = NoteFlow(cfg)
        assert nf.peak() == 0

    def test_empty_peak_index_is_none(self):
        from gamepad_midi_bridge.note_flow import NoteFlow, NoteFlowConfig
        cfg = NoteFlowConfig()
        nf = NoteFlow(cfg)
        assert nf.peak_index() is None

    def test_first_record_creates_bucket_zero(self):
        from gamepad_midi_bridge.note_flow import NoteFlow, NoteFlowConfig
        cfg = NoteFlowConfig(bucket_seconds=1.0)
        nf = NoteFlow(cfg)
        nf.record(0.0)
        assert nf.buckets() == [1]
        assert nf.total() == 1
        assert nf.peak() == 1
        assert nf.peak_index() == 0

    def test_multiple_records_within_same_bucket(self):
        from gamepad_midi_bridge.note_flow import NoteFlow, NoteFlowConfig
        cfg = NoteFlowConfig(bucket_seconds=1.0)
        nf = NoteFlow(cfg)
        nf.record(0.0)
        nf.record(0.2)
        nf.record(0.5)
        nf.record(0.9)
        nf.record(0.99)
        assert nf.buckets() == [5]
        assert nf.total() == 5
        assert nf.peak() == 5

    def test_records_spanning_multiple_buckets(self):
        from gamepad_midi_bridge.note_flow import NoteFlow, NoteFlowConfig
        cfg = NoteFlowConfig(bucket_seconds=1.0)
        nf = NoteFlow(cfg)
        nf.record(0.0)      # Bucket 0
        nf.record(0.5)      # Bucket 0
        nf.record(0.8)      # Bucket 0
        nf.record(2.5)      # Bucket 2
        nf.record(3.1)      # Bucket 3
        assert nf.buckets() == [3, 0, 1, 1]
        assert nf.total() == 5
        assert nf.peak() == 3
        assert nf.peak_index() == 0

    def test_records_fill_gaps_with_zeros(self):
        from gamepad_midi_bridge.note_flow import NoteFlow, NoteFlowConfig
        cfg = NoteFlowConfig(bucket_seconds=1.0)
        nf = NoteFlow(cfg)
        nf.record(0.0)      # Bucket 0
        nf.record(5.5)      # Bucket 5 (creates buckets 1, 2, 3, 4 with 0s)
        assert nf.buckets() == [1, 0, 0, 0, 0, 1]
        assert nf.total() == 2

    def test_peak_with_multiple_buckets(self):
        from gamepad_midi_bridge.note_flow import NoteFlow, NoteFlowConfig
        cfg = NoteFlowConfig(bucket_seconds=1.0)
        nf = NoteFlow(cfg)
        # Use clean integer starting point to avoid floating-point issues
        nf.record(0.0)
        nf.record(0.5)  # Bucket 0
        nf.record(1.0)  # Bucket 1
        nf.record(1.1)  # Bucket 1
        nf.record(1.2)  # Bucket 1
        nf.record(1.3)  # Bucket 1
        nf.record(2.0)  # Bucket 2
        assert nf.buckets() == [2, 4, 1]
        assert nf.peak() == 4
        assert nf.peak_index() == 1

    def test_recent_returns_last_n(self):
        from gamepad_midi_bridge.note_flow import NoteFlow, NoteFlowConfig
        cfg = NoteFlowConfig(bucket_seconds=1.0)
        nf = NoteFlow(cfg)
        # Use integer timestamps to avoid floating-point precision issues
        for t in [0, 1, 2, 3, 4]:
            nf.record(float(t))
        recent_3 = nf.recent(3)
        assert recent_3 == [1, 1, 1]
        recent_5 = nf.recent(5)
        assert recent_5 == [1, 1, 1, 1, 1]

    def test_recent_fewer_buckets_than_n(self):
        from gamepad_midi_bridge.note_flow import NoteFlow, NoteFlowConfig
        cfg = NoteFlowConfig(bucket_seconds=1.0)
        nf = NoteFlow(cfg)
        nf.record(0.1)
        nf.record(1.1)
        nf.record(2.1)
        # Only 3 buckets, but ask for 10
        recent_10 = nf.recent(10)
        assert recent_10 == [1, 1, 1]

    def test_recent_zero_or_negative(self):
        from gamepad_midi_bridge.note_flow import NoteFlow, NoteFlowConfig
        cfg = NoteFlowConfig(bucket_seconds=1.0)
        nf = NoteFlow(cfg)
        nf.record(0.1)
        nf.record(1.1)
        assert nf.recent(0) == []
        assert nf.recent(-5) == []

    def test_normalize_all_ones(self):
        from gamepad_midi_bridge.note_flow import NoteFlow, NoteFlowConfig
        cfg = NoteFlowConfig(bucket_seconds=1.0)
        nf = NoteFlow(cfg)
        nf.record(0.1)
        nf.record(1.1)
        nf.record(2.1)
        normalized = nf.normalize()
        assert normalized == [1.0, 1.0, 1.0]

    def test_normalize_varied_counts(self):
        from gamepad_midi_bridge.note_flow import NoteFlow, NoteFlowConfig
        cfg = NoteFlowConfig(bucket_seconds=1.0)
        nf = NoteFlow(cfg)
        nf.record(0.1)
        nf.record(0.2)  # Bucket 0: 2
        nf.record(1.1)  # Bucket 1: 1
        nf.record(2.1)
        nf.record(2.2)
        nf.record(2.3)
        nf.record(2.4)  # Bucket 2: 4
        normalized = nf.normalize()
        assert len(normalized) == 3
        assert normalized[0] == 0.5  # 2/4
        assert normalized[1] == 0.25  # 1/4
        assert normalized[2] == 1.0  # 4/4 (peak)

    def test_normalize_empty(self):
        from gamepad_midi_bridge.note_flow import NoteFlow, NoteFlowConfig
        cfg = NoteFlowConfig()
        nf = NoteFlow(cfg)
        assert nf.normalize() == []

    def test_normalize_all_zeros(self):
        from gamepad_midi_bridge.note_flow import NoteFlow, NoteFlowConfig
        cfg = NoteFlowConfig(bucket_seconds=1.0)
        nf = NoteFlow(cfg)
        # Manually set buckets to all zeros (normally impossible through record())
        nf._buckets = [0, 0, 0]
        nf._bucket_start_at = 0.0
        assert nf.normalize() == []

    def test_duration_s_empty(self):
        from gamepad_midi_bridge.note_flow import NoteFlow, NoteFlowConfig
        cfg = NoteFlowConfig(bucket_seconds=1.0)
        nf = NoteFlow(cfg)
        assert nf.duration_s() == 0.0

    def test_duration_s_single_bucket(self):
        from gamepad_midi_bridge.note_flow import NoteFlow, NoteFlowConfig
        cfg = NoteFlowConfig(bucket_seconds=1.0)
        nf = NoteFlow(cfg)
        nf.record(0.0)
        assert nf.duration_s() == 1.0

    def test_duration_s_multiple_buckets(self):
        from gamepad_midi_bridge.note_flow import NoteFlow, NoteFlowConfig
        cfg = NoteFlowConfig(bucket_seconds=0.5)
        nf = NoteFlow(cfg)
        nf.record(0.0)
        nf.record(2.5)  # Creates 6 buckets (0, 0.5, 1.0, 1.5, 2.0, 2.5)
        assert nf.buckets() == [1, 0, 0, 0, 0, 1]
        assert len(nf.buckets()) == 6
        assert nf.duration_s() == 6 * 0.5
        assert nf.duration_s() == 3.0

    def test_max_buckets_truncates_from_start(self):
        from gamepad_midi_bridge.note_flow import NoteFlow, NoteFlowConfig
        cfg = NoteFlowConfig(bucket_seconds=1.0, max_buckets=15)
        nf = NoteFlow(cfg)
        # Add 18 records: 0.0 through 17.0
        # This creates 18 buckets; when we exceed max_buckets=15, truncate
        for i in range(18):
            nf.record(float(i))
        # Should have 15 buckets (newest), oldest 3 removed
        assert len(nf.buckets()) == 15
        # We keep buckets 3-17 (15 total)
        assert nf.buckets() == [1] * 15

    def test_max_buckets_shifts_bucket_start_at(self):
        from gamepad_midi_bridge.note_flow import NoteFlow, NoteFlowConfig
        cfg = NoteFlowConfig(bucket_seconds=1.0, max_buckets=10)
        nf = NoteFlow(cfg)
        # Record timestamps 0 through 11 (12 records = 12 buckets)
        for i in range(12):
            nf.record(float(i))
        # When we exceed max_buckets=10, the oldest 2 buckets are truncated
        # and _bucket_start_at is shifted forward by 2 * bucket_seconds = 2.0
        assert len(nf.buckets()) == 10
        assert nf._bucket_start_at == 2.0
        # Verify the buckets are the newest 10 (from timestamp 2 onwards)
        assert nf.buckets() == [1] * 10

    def test_clear(self):
        from gamepad_midi_bridge.note_flow import NoteFlow, NoteFlowConfig
        cfg = NoteFlowConfig()
        nf = NoteFlow(cfg)
        nf.record(0.0)
        nf.record(1.0)
        assert nf.total() > 0
        nf.clear()
        assert nf.buckets() == []
        assert nf.total() == 0
        assert nf._bucket_start_at is None

    def test_summary_empty(self):
        from gamepad_midi_bridge.note_flow import NoteFlow, NoteFlowConfig
        cfg = NoteFlowConfig()
        nf = NoteFlow(cfg)
        summary = nf.summary()
        assert summary["buckets"] == []
        assert summary["total"] == 0
        assert summary["peak"] == 0
        assert summary["peak_index"] is None
        assert summary["duration_s"] == 0.0
        assert summary["num_buckets"] == 0

    def test_summary_with_data(self):
        from gamepad_midi_bridge.note_flow import NoteFlow, NoteFlowConfig
        cfg = NoteFlowConfig(bucket_seconds=1.0)
        nf = NoteFlow(cfg)
        nf.record(0.1)
        nf.record(0.2)
        nf.record(1.1)
        nf.record(2.1)
        nf.record(2.2)
        summary = nf.summary()
        assert summary["buckets"] == [2, 1, 2]
        assert summary["total"] == 5
        assert summary["peak"] == 2
        assert summary["peak_index"] in [0, 2]  # Two buckets tied at peak
        assert summary["duration_s"] == 3.0
        assert summary["num_buckets"] == 3

    def test_summary_all_keys_present(self):
        from gamepad_midi_bridge.note_flow import NoteFlow, NoteFlowConfig
        cfg = NoteFlowConfig()
        nf = NoteFlow(cfg)
        nf.record(0.0)
        summary = nf.summary()
        assert "buckets" in summary
        assert "total" in summary
        assert "peak" in summary
        assert "peak_index" in summary
        assert "duration_s" in summary
        assert "num_buckets" in summary

    def test_record_with_fractional_bucket_seconds(self):
        from gamepad_midi_bridge.note_flow import NoteFlow, NoteFlowConfig
        cfg = NoteFlowConfig(bucket_seconds=0.5)
        nf = NoteFlow(cfg)
        nf.record(0.0)      # Bucket 0
        nf.record(0.2)      # Bucket 0 (0.2 / 0.5 = 0)
        nf.record(0.7)      # Bucket 1 (0.7 / 0.5 = 1)
        nf.record(1.1)      # Bucket 2 (1.1 / 0.5 = 2)
        assert nf.buckets() == [2, 1, 1]
        assert nf.total() == 4
