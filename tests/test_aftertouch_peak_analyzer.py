"""Tests for aftertouch peak analyzer.

AftertouchPeakAnalyzer records aftertouch pressure samples per note/channel pair,
tracks peak/mean/min values, and provides statistical summaries. Pure stdlib, no Qt.
"""
from __future__ import annotations

import pytest


class TestAftertouchPeakAnalysis:
    """AftertouchPeakAnalysis dataclass — serialize/deserialize."""

    def test_analysis_construction(self):
        from gamepad_midi_bridge.aftertouch_peak_analyzer import (
            AftertouchPeakAnalysis,
        )

        analysis = AftertouchPeakAnalysis(
            note=60, channel=1, peak_value=100, mean_value=75.5, min_value=50, sample_count=5
        )
        assert analysis.note == 60
        assert analysis.channel == 1
        assert analysis.peak_value == 100
        assert analysis.mean_value == 75.5
        assert analysis.min_value == 50
        assert analysis.sample_count == 5

    def test_analysis_to_dict(self):
        from gamepad_midi_bridge.aftertouch_peak_analyzer import (
            AftertouchPeakAnalysis,
        )

        analysis = AftertouchPeakAnalysis(
            note=72, channel=5, peak_value=120, mean_value=90.0, min_value=60, sample_count=10
        )
        d = analysis.to_dict()
        assert d["note"] == 72
        assert d["channel"] == 5
        assert d["peak_value"] == 120
        assert d["mean_value"] == 90.0
        assert d["min_value"] == 60
        assert d["sample_count"] == 10

    def test_analysis_from_dict(self):
        from gamepad_midi_bridge.aftertouch_peak_analyzer import (
            AftertouchPeakAnalysis,
        )

        d = {
            "note": 48,
            "channel": 3,
            "peak_value": 110,
            "mean_value": 85.2,
            "min_value": 40,
            "sample_count": 8,
        }
        analysis = AftertouchPeakAnalysis.from_dict(d)
        assert analysis.note == 48
        assert analysis.channel == 3
        assert analysis.peak_value == 110
        assert analysis.mean_value == 85.2
        assert analysis.min_value == 40
        assert analysis.sample_count == 8

    def test_analysis_round_trip(self):
        from gamepad_midi_bridge.aftertouch_peak_analyzer import (
            AftertouchPeakAnalysis,
        )

        original = AftertouchPeakAnalysis(
            note=64,
            channel=2,
            peak_value=95,
            mean_value=77.3,
            min_value=55,
            sample_count=7,
        )
        d = original.to_dict()
        restored = AftertouchPeakAnalysis.from_dict(d)
        assert restored.note == original.note
        assert restored.channel == original.channel
        assert restored.peak_value == original.peak_value
        assert restored.mean_value == original.mean_value
        assert restored.min_value == original.min_value
        assert restored.sample_count == original.sample_count


class TestAftertouchPeakConfig:
    """AftertouchPeakConfig — clamp parameters on construction."""

    def test_config_defaults(self):
        from gamepad_midi_bridge.aftertouch_peak_analyzer import (
            AftertouchPeakConfig,
        )

        cfg = AftertouchPeakConfig()
        assert cfg.max_samples_per_note == 500

    def test_config_clamp_below_10(self):
        from gamepad_midi_bridge.aftertouch_peak_analyzer import (
            AftertouchPeakConfig,
        )

        cfg = AftertouchPeakConfig(max_samples_per_note=5)
        assert cfg.max_samples_per_note == 10
        cfg = AftertouchPeakConfig(max_samples_per_note=0)
        assert cfg.max_samples_per_note == 10

    def test_config_clamp_above_100000(self):
        from gamepad_midi_bridge.aftertouch_peak_analyzer import (
            AftertouchPeakConfig,
        )

        cfg = AftertouchPeakConfig(max_samples_per_note=100001)
        assert cfg.max_samples_per_note == 100000
        cfg = AftertouchPeakConfig(max_samples_per_note=999999)
        assert cfg.max_samples_per_note == 100000

    def test_config_no_clamp_in_range(self):
        from gamepad_midi_bridge.aftertouch_peak_analyzer import (
            AftertouchPeakConfig,
        )

        cfg = AftertouchPeakConfig(max_samples_per_note=5000)
        assert cfg.max_samples_per_note == 5000

    def test_config_to_dict(self):
        from gamepad_midi_bridge.aftertouch_peak_analyzer import (
            AftertouchPeakConfig,
        )

        cfg = AftertouchPeakConfig(max_samples_per_note=750)
        d = cfg.to_dict()
        assert d["max_samples_per_note"] == 750

    def test_config_from_dict(self):
        from gamepad_midi_bridge.aftertouch_peak_analyzer import (
            AftertouchPeakConfig,
        )

        d = {"max_samples_per_note": 1000}
        cfg = AftertouchPeakConfig.from_dict(d)
        assert cfg.max_samples_per_note == 1000

    def test_config_round_trip(self):
        from gamepad_midi_bridge.aftertouch_peak_analyzer import (
            AftertouchPeakConfig,
        )

        original = AftertouchPeakConfig(max_samples_per_note=600)
        d = original.to_dict()
        restored = AftertouchPeakConfig.from_dict(d)
        assert restored.max_samples_per_note == original.max_samples_per_note


class TestAftertouchPeakAnalyzer:
    """AftertouchPeakAnalyzer — record, query, analyze pressure."""

    def test_empty_analyze_note_returns_none(self):
        from gamepad_midi_bridge.aftertouch_peak_analyzer import (
            AftertouchPeakAnalyzer,
            AftertouchPeakConfig,
        )

        cfg = AftertouchPeakConfig()
        analyzer = AftertouchPeakAnalyzer(cfg)
        assert analyzer.analyze_note(60, 1) is None

    def test_record_single_sample(self):
        from gamepad_midi_bridge.aftertouch_peak_analyzer import (
            AftertouchPeakAnalyzer,
            AftertouchPeakConfig,
        )

        cfg = AftertouchPeakConfig()
        analyzer = AftertouchPeakAnalyzer(cfg)
        analyzer.record(60, 1, 80)
        analysis = analyzer.analyze_note(60, 1)
        assert analysis is not None
        assert analysis.note == 60
        assert analysis.channel == 1
        assert analysis.peak_value == 80
        assert analysis.mean_value == 80.0
        assert analysis.min_value == 80
        assert analysis.sample_count == 1

    def test_record_multiple_samples_peak_value(self):
        from gamepad_midi_bridge.aftertouch_peak_analyzer import (
            AftertouchPeakAnalyzer,
            AftertouchPeakConfig,
        )

        cfg = AftertouchPeakConfig()
        analyzer = AftertouchPeakAnalyzer(cfg)
        values = [50, 80, 100, 90, 70]
        for v in values:
            analyzer.record(60, 1, v)
        analysis = analyzer.analyze_note(60, 1)
        assert analysis.peak_value == 100

    def test_record_multiple_samples_min_value(self):
        from gamepad_midi_bridge.aftertouch_peak_analyzer import (
            AftertouchPeakAnalyzer,
            AftertouchPeakConfig,
        )

        cfg = AftertouchPeakConfig()
        analyzer = AftertouchPeakAnalyzer(cfg)
        values = [50, 80, 100, 90, 70]
        for v in values:
            analyzer.record(60, 1, v)
        analysis = analyzer.analyze_note(60, 1)
        assert analysis.min_value == 50

    def test_record_multiple_samples_mean_value(self):
        from gamepad_midi_bridge.aftertouch_peak_analyzer import (
            AftertouchPeakAnalyzer,
            AftertouchPeakConfig,
        )

        cfg = AftertouchPeakConfig()
        analyzer = AftertouchPeakAnalyzer(cfg)
        values = [50, 80, 100, 90, 70]
        for v in values:
            analyzer.record(60, 1, v)
        analysis = analyzer.analyze_note(60, 1)
        # (50 + 80 + 100 + 90 + 70) / 5 = 390 / 5 = 78.0
        assert round(analysis.mean_value, 1) == 78.0

    def test_record_clamps_note_below_zero(self):
        from gamepad_midi_bridge.aftertouch_peak_analyzer import (
            AftertouchPeakAnalyzer,
            AftertouchPeakConfig,
        )

        cfg = AftertouchPeakConfig()
        analyzer = AftertouchPeakAnalyzer(cfg)
        analyzer.record(-10, 1, 80)
        analysis = analyzer.analyze_note(0, 1)
        assert analysis is not None
        assert analysis.note == 0

    def test_record_clamps_note_above_127(self):
        from gamepad_midi_bridge.aftertouch_peak_analyzer import (
            AftertouchPeakAnalyzer,
            AftertouchPeakConfig,
        )

        cfg = AftertouchPeakConfig()
        analyzer = AftertouchPeakAnalyzer(cfg)
        analyzer.record(150, 1, 80)
        analysis = analyzer.analyze_note(127, 1)
        assert analysis is not None
        assert analysis.note == 127

    def test_record_clamps_channel_below_1(self):
        from gamepad_midi_bridge.aftertouch_peak_analyzer import (
            AftertouchPeakAnalyzer,
            AftertouchPeakConfig,
        )

        cfg = AftertouchPeakConfig()
        analyzer = AftertouchPeakAnalyzer(cfg)
        analyzer.record(60, 0, 80)
        analysis = analyzer.analyze_note(60, 1)
        assert analysis is not None
        assert analysis.channel == 1

    def test_record_clamps_channel_above_16(self):
        from gamepad_midi_bridge.aftertouch_peak_analyzer import (
            AftertouchPeakAnalyzer,
            AftertouchPeakConfig,
        )

        cfg = AftertouchPeakConfig()
        analyzer = AftertouchPeakAnalyzer(cfg)
        analyzer.record(60, 20, 80)
        analysis = analyzer.analyze_note(60, 16)
        assert analysis is not None
        assert analysis.channel == 16

    def test_record_clamps_value_below_zero(self):
        from gamepad_midi_bridge.aftertouch_peak_analyzer import (
            AftertouchPeakAnalyzer,
            AftertouchPeakConfig,
        )

        cfg = AftertouchPeakConfig()
        analyzer = AftertouchPeakAnalyzer(cfg)
        analyzer.record(60, 1, -10)
        analysis = analyzer.analyze_note(60, 1)
        assert analysis.peak_value == 0
        assert analysis.min_value == 0

    def test_record_clamps_value_above_127(self):
        from gamepad_midi_bridge.aftertouch_peak_analyzer import (
            AftertouchPeakAnalyzer,
            AftertouchPeakConfig,
        )

        cfg = AftertouchPeakConfig()
        analyzer = AftertouchPeakAnalyzer(cfg)
        analyzer.record(60, 1, 150)
        analysis = analyzer.analyze_note(60, 1)
        assert analysis.peak_value == 127
        assert analysis.min_value == 127

    def test_analyze_all_sorts_by_peak_desc(self):
        from gamepad_midi_bridge.aftertouch_peak_analyzer import (
            AftertouchPeakAnalyzer,
            AftertouchPeakConfig,
        )

        cfg = AftertouchPeakConfig()
        analyzer = AftertouchPeakAnalyzer(cfg)
        analyzer.record(60, 1, 50)
        analyzer.record(62, 1, 100)
        analyzer.record(64, 1, 80)
        analyses = analyzer.analyze_all()
        assert len(analyses) == 3
        assert analyses[0].peak_value == 100
        assert analyses[1].peak_value == 80
        assert analyses[2].peak_value == 50

    def test_top_notes_returns_top_n(self):
        from gamepad_midi_bridge.aftertouch_peak_analyzer import (
            AftertouchPeakAnalyzer,
            AftertouchPeakConfig,
        )

        cfg = AftertouchPeakConfig()
        analyzer = AftertouchPeakAnalyzer(cfg)
        for i, v in enumerate([40, 60, 80, 100, 120, 50]):
            analyzer.record(60 + i, 1, v)
        top_3 = analyzer.top_notes(3)
        assert len(top_3) == 3
        assert top_3[0].peak_value == 120
        assert top_3[1].peak_value == 100
        assert top_3[2].peak_value == 80

    def test_max_samples_per_note_fifo_eviction(self):
        from gamepad_midi_bridge.aftertouch_peak_analyzer import (
            AftertouchPeakAnalyzer,
            AftertouchPeakConfig,
        )

        cfg = AftertouchPeakConfig(max_samples_per_note=20)
        analyzer = AftertouchPeakAnalyzer(cfg)
        # Add 22 samples to trigger eviction (will keep last 20)
        for i in range(22):
            analyzer.record(60, 1, 50 + i * 2)
        analysis = analyzer.analyze_note(60, 1)
        # values: 50, 52, 54, ..., 92 (22 values total)
        # After eviction to 20: 54, 56, 58, ..., 92
        assert analysis.sample_count == 20
        assert analysis.peak_value == 92
        assert analysis.min_value == 54

    def test_note_count_tracks_unique_pairs(self):
        from gamepad_midi_bridge.aftertouch_peak_analyzer import (
            AftertouchPeakAnalyzer,
            AftertouchPeakConfig,
        )

        cfg = AftertouchPeakConfig()
        analyzer = AftertouchPeakAnalyzer(cfg)
        analyzer.record(60, 1, 80)
        analyzer.record(60, 1, 90)  # Same pair
        analyzer.record(62, 1, 100)
        analyzer.record(60, 2, 85)  # Different channel
        assert analyzer.note_count() == 3

    def test_total_records_sums_samples(self):
        from gamepad_midi_bridge.aftertouch_peak_analyzer import (
            AftertouchPeakAnalyzer,
            AftertouchPeakConfig,
        )

        cfg = AftertouchPeakConfig()
        analyzer = AftertouchPeakAnalyzer(cfg)
        analyzer.record(60, 1, 80)
        analyzer.record(60, 1, 90)
        analyzer.record(62, 1, 100)
        analyzer.record(60, 2, 85)
        analyzer.record(60, 2, 75)
        assert analyzer.total_records() == 5

    def test_clear_empties_all_data(self):
        from gamepad_midi_bridge.aftertouch_peak_analyzer import (
            AftertouchPeakAnalyzer,
            AftertouchPeakConfig,
        )

        cfg = AftertouchPeakConfig()
        analyzer = AftertouchPeakAnalyzer(cfg)
        analyzer.record(60, 1, 80)
        analyzer.record(62, 1, 100)
        assert analyzer.note_count() > 0
        analyzer.clear()
        assert analyzer.note_count() == 0
        assert analyzer.total_records() == 0
        assert analyzer.analyze_note(60, 1) is None

    def test_different_channels_tracked_separately(self):
        from gamepad_midi_bridge.aftertouch_peak_analyzer import (
            AftertouchPeakAnalyzer,
            AftertouchPeakConfig,
        )

        cfg = AftertouchPeakConfig()
        analyzer = AftertouchPeakAnalyzer(cfg)
        analyzer.record(60, 1, 50)
        analyzer.record(60, 2, 100)
        analysis_ch1 = analyzer.analyze_note(60, 1)
        analysis_ch2 = analyzer.analyze_note(60, 2)
        assert analysis_ch1.peak_value == 50
        assert analysis_ch2.peak_value == 100
        assert analyzer.note_count() == 2

    def test_summary_empty(self):
        from gamepad_midi_bridge.aftertouch_peak_analyzer import (
            AftertouchPeakAnalyzer,
            AftertouchPeakConfig,
        )

        cfg = AftertouchPeakConfig()
        analyzer = AftertouchPeakAnalyzer(cfg)
        summary = analyzer.summary()
        assert summary["note_count"] == 0
        assert summary["total_records"] == 0
        assert summary["overall_peak"] is None
        assert summary["overall_mean"] is None

    def test_summary_with_data(self):
        from gamepad_midi_bridge.aftertouch_peak_analyzer import (
            AftertouchPeakAnalyzer,
            AftertouchPeakConfig,
        )

        cfg = AftertouchPeakConfig()
        analyzer = AftertouchPeakAnalyzer(cfg)
        analyzer.record(60, 1, 50)
        analyzer.record(60, 1, 80)
        analyzer.record(62, 1, 100)
        summary = analyzer.summary()
        assert summary["note_count"] == 2
        assert summary["total_records"] == 3
        assert summary["overall_peak"] == 100
        # (50 + 80 + 100) / 3 = 230 / 3 ≈ 76.67
        assert round(summary["overall_mean"], 2) == 76.67

    def test_summary_all_keys_present(self):
        from gamepad_midi_bridge.aftertouch_peak_analyzer import (
            AftertouchPeakAnalyzer,
            AftertouchPeakConfig,
        )

        cfg = AftertouchPeakConfig()
        analyzer = AftertouchPeakAnalyzer(cfg)
        analyzer.record(60, 1, 80)
        summary = analyzer.summary()
        assert "note_count" in summary
        assert "total_records" in summary
        assert "overall_peak" in summary
        assert "overall_mean" in summary
