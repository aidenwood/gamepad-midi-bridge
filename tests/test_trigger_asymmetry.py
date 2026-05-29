"""Tests for trigger asymmetry analyzer.

TriggerAsymmetryAnalyzer compares L2 vs R2 trigger usage across a session
to detect handedness / preference patterns. Pure stdlib, no Qt.
"""
from __future__ import annotations

import pytest


class TestAsymmetryReport:
    """AsymmetryReport dataclass — serialize/deserialize."""

    def test_report_construction(self):
        from gamepad_midi_bridge.trigger_asymmetry import AsymmetryReport

        report = AsymmetryReport(
            l2_total_uses=70,
            r2_total_uses=30,
            l2_mean_pressure=0.75,
            r2_mean_pressure=0.50,
            l2_peak_pressure=0.95,
            r2_peak_pressure=0.80,
            usage_ratio=0.7,
            dominant_trigger="L2",
            dominance_strength=0.4,
        )
        assert report.l2_total_uses == 70
        assert report.r2_total_uses == 30
        assert report.dominant_trigger == "L2"

    def test_report_to_dict(self):
        from gamepad_midi_bridge.trigger_asymmetry import AsymmetryReport

        report = AsymmetryReport(
            l2_total_uses=50,
            r2_total_uses=50,
            l2_mean_pressure=0.65,
            r2_mean_pressure=0.65,
            l2_peak_pressure=0.90,
            r2_peak_pressure=0.90,
            usage_ratio=0.5,
            dominant_trigger="balanced",
            dominance_strength=0.0,
        )
        d = report.to_dict()
        assert d["l2_total_uses"] == 50
        assert d["r2_total_uses"] == 50
        assert d["dominant_trigger"] == "balanced"

    def test_report_from_dict(self):
        from gamepad_midi_bridge.trigger_asymmetry import AsymmetryReport

        d = {
            "l2_total_uses": 100,
            "r2_total_uses": 50,
            "l2_mean_pressure": 0.8,
            "r2_mean_pressure": 0.6,
            "l2_peak_pressure": 1.0,
            "r2_peak_pressure": 0.9,
            "usage_ratio": 0.667,
            "dominant_trigger": "L2",
            "dominance_strength": 0.334,
        }
        report = AsymmetryReport.from_dict(d)
        assert report.l2_total_uses == 100
        assert report.r2_total_uses == 50
        assert report.dominant_trigger == "L2"

    def test_report_round_trip(self):
        from gamepad_midi_bridge.trigger_asymmetry import AsymmetryReport

        original = AsymmetryReport(
            l2_total_uses=60,
            r2_total_uses=40,
            l2_mean_pressure=0.7,
            r2_mean_pressure=0.55,
            l2_peak_pressure=0.92,
            r2_peak_pressure=0.85,
            usage_ratio=0.6,
            dominant_trigger="L2",
            dominance_strength=0.2,
        )
        d = original.to_dict()
        restored = AsymmetryReport.from_dict(d)
        assert restored.l2_total_uses == original.l2_total_uses
        assert restored.r2_total_uses == original.r2_total_uses
        assert restored.usage_ratio == original.usage_ratio
        assert restored.dominant_trigger == original.dominant_trigger


class TestAsymmetryConfig:
    """AsymmetryConfig — clamp parameters on construction."""

    def test_config_defaults(self):
        from gamepad_midi_bridge.trigger_asymmetry import AsymmetryConfig

        cfg = AsymmetryConfig()
        assert cfg.max_samples == 10000
        assert cfg.balanced_threshold == 0.1

    def test_config_clamp_max_samples_below_100(self):
        from gamepad_midi_bridge.trigger_asymmetry import AsymmetryConfig

        cfg = AsymmetryConfig(max_samples=50)
        assert cfg.max_samples == 100

    def test_config_clamp_max_samples_above_1000000(self):
        from gamepad_midi_bridge.trigger_asymmetry import AsymmetryConfig

        cfg = AsymmetryConfig(max_samples=2000000)
        assert cfg.max_samples == 1000000

    def test_config_clamp_balanced_threshold_below_0(self):
        from gamepad_midi_bridge.trigger_asymmetry import AsymmetryConfig

        cfg = AsymmetryConfig(balanced_threshold=-0.1)
        assert cfg.balanced_threshold == 0.0

    def test_config_clamp_balanced_threshold_above_0_5(self):
        from gamepad_midi_bridge.trigger_asymmetry import AsymmetryConfig

        cfg = AsymmetryConfig(balanced_threshold=0.7)
        assert cfg.balanced_threshold == 0.5

    def test_config_to_dict(self):
        from gamepad_midi_bridge.trigger_asymmetry import AsymmetryConfig

        cfg = AsymmetryConfig(max_samples=5000, balanced_threshold=0.15)
        d = cfg.to_dict()
        assert d["max_samples"] == 5000
        assert d["balanced_threshold"] == 0.15

    def test_config_from_dict(self):
        from gamepad_midi_bridge.trigger_asymmetry import AsymmetryConfig

        d = {"max_samples": 8000, "balanced_threshold": 0.2}
        cfg = AsymmetryConfig.from_dict(d)
        assert cfg.max_samples == 8000
        assert cfg.balanced_threshold == 0.2

    def test_config_round_trip(self):
        from gamepad_midi_bridge.trigger_asymmetry import AsymmetryConfig

        original = AsymmetryConfig(max_samples=15000, balanced_threshold=0.12)
        d = original.to_dict()
        restored = AsymmetryConfig.from_dict(d)
        assert restored.max_samples == original.max_samples
        assert restored.balanced_threshold == original.balanced_threshold


class TestTriggerAsymmetryAnalyzer:
    """TriggerAsymmetryAnalyzer — record and analyze trigger usage."""

    def test_empty_analyzer(self):
        from gamepad_midi_bridge.trigger_asymmetry import (
            AsymmetryConfig,
            TriggerAsymmetryAnalyzer,
        )

        cfg = AsymmetryConfig()
        analyzer = TriggerAsymmetryAnalyzer(cfg)
        report = analyzer.analyze()

        assert report.l2_total_uses == 0
        assert report.r2_total_uses == 0
        assert report.usage_ratio == 0.5
        assert report.dominant_trigger == "balanced"
        assert report.dominance_strength == 0.0

    def test_all_l2(self):
        from gamepad_midi_bridge.trigger_asymmetry import (
            AsymmetryConfig,
            TriggerAsymmetryAnalyzer,
        )

        cfg = AsymmetryConfig()
        analyzer = TriggerAsymmetryAnalyzer(cfg)

        for _ in range(100):
            analyzer.record("L2", 0.8)

        report = analyzer.analyze()
        assert report.l2_total_uses == 100
        assert report.r2_total_uses == 0
        assert report.dominant_trigger == "L2"
        assert report.l2_peak_pressure == 0.8
        assert report.l2_mean_pressure == 0.8

    def test_all_r2(self):
        from gamepad_midi_bridge.trigger_asymmetry import (
            AsymmetryConfig,
            TriggerAsymmetryAnalyzer,
        )

        cfg = AsymmetryConfig()
        analyzer = TriggerAsymmetryAnalyzer(cfg)

        for _ in range(100):
            analyzer.record("R2", 0.6)

        report = analyzer.analyze()
        assert report.l2_total_uses == 0
        assert report.r2_total_uses == 100
        assert report.dominant_trigger == "R2"
        assert report.r2_peak_pressure == 0.6
        assert report.r2_mean_pressure == 0.6

    def test_50_50_split_balanced(self):
        from gamepad_midi_bridge.trigger_asymmetry import (
            AsymmetryConfig,
            TriggerAsymmetryAnalyzer,
        )

        cfg = AsymmetryConfig(balanced_threshold=0.1)
        analyzer = TriggerAsymmetryAnalyzer(cfg)

        for _ in range(50):
            analyzer.record("L2", 0.7)
            analyzer.record("R2", 0.5)

        report = analyzer.analyze()
        assert report.l2_total_uses == 50
        assert report.r2_total_uses == 50
        assert report.usage_ratio == 0.5
        assert report.dominant_trigger == "balanced"

    def test_70_30_split_l2_dominant(self):
        from gamepad_midi_bridge.trigger_asymmetry import (
            AsymmetryConfig,
            TriggerAsymmetryAnalyzer,
        )

        cfg = AsymmetryConfig(balanced_threshold=0.05)
        analyzer = TriggerAsymmetryAnalyzer(cfg)

        for _ in range(70):
            analyzer.record("L2", 0.8)
        for _ in range(30):
            analyzer.record("R2", 0.4)

        report = analyzer.analyze()
        assert report.l2_total_uses == 70
        assert report.r2_total_uses == 30
        assert abs(report.usage_ratio - 0.7) < 0.01
        assert report.dominant_trigger == "L2"
        assert abs(report.dominance_strength - 0.4) < 0.01  # (0.7 - 0.5) * 2 = 0.4

    def test_pressure_clamping(self):
        from gamepad_midi_bridge.trigger_asymmetry import (
            AsymmetryConfig,
            TriggerAsymmetryAnalyzer,
        )

        cfg = AsymmetryConfig()
        analyzer = TriggerAsymmetryAnalyzer(cfg)

        analyzer.record("L2", -0.5)  # Should clamp to 0.0
        analyzer.record("L2", 1.5)   # Should clamp to 1.0
        analyzer.record("L2", 0.5)

        report = analyzer.analyze()
        assert report.l2_peak_pressure == 1.0
        assert report.l2_mean_pressure == (0.0 + 1.0 + 0.5) / 3

    def test_unknown_trigger_ignored(self):
        from gamepad_midi_bridge.trigger_asymmetry import (
            AsymmetryConfig,
            TriggerAsymmetryAnalyzer,
        )

        cfg = AsymmetryConfig()
        analyzer = TriggerAsymmetryAnalyzer(cfg)

        analyzer.record("L2", 0.5)
        analyzer.record("Unknown", 0.8)  # Should be ignored
        analyzer.record("R2", 0.6)

        report = analyzer.analyze()
        assert report.l2_total_uses == 1
        assert report.r2_total_uses == 1
        assert analyzer.total_records() == 2

    def test_max_samples_fifo_l2(self):
        from gamepad_midi_bridge.trigger_asymmetry import (
            AsymmetryConfig,
            TriggerAsymmetryAnalyzer,
        )

        cfg = AsymmetryConfig(max_samples=100)
        analyzer = TriggerAsymmetryAnalyzer(cfg)

        for i in range(200):
            analyzer.record("L2", float(i) / 200.0)

        report = analyzer.analyze()
        assert report.l2_total_uses == 100
        # Last 100 samples: 100/200 to 199/200 (0.5 to 0.995)
        assert report.l2_peak_pressure == 0.995
        assert report.l2_mean_pressure > 0.7

    def test_max_samples_fifo_r2(self):
        from gamepad_midi_bridge.trigger_asymmetry import (
            AsymmetryConfig,
            TriggerAsymmetryAnalyzer,
        )

        cfg = AsymmetryConfig(max_samples=100)
        analyzer = TriggerAsymmetryAnalyzer(cfg)

        for i in range(150):
            analyzer.record("R2", float(i) / 150.0)

        report = analyzer.analyze()
        assert report.r2_total_uses == 100

    def test_dominance_strength_range(self):
        from gamepad_midi_bridge.trigger_asymmetry import (
            AsymmetryConfig,
            TriggerAsymmetryAnalyzer,
        )

        cfg = AsymmetryConfig(balanced_threshold=0.0)
        analyzer = TriggerAsymmetryAnalyzer(cfg)

        # Test that dominance_strength is always 0..1
        test_cases = [
            (1, 99),   # 0.99 ratio
            (10, 90),  # 0.9 ratio
            (25, 75),  # 0.75 ratio
            (50, 50),  # 0.5 ratio
        ]

        for l2_count, r2_count in test_cases:
            analyzer.clear()
            for _ in range(l2_count):
                analyzer.record("L2", 0.5)
            for _ in range(r2_count):
                analyzer.record("R2", 0.5)

            report = analyzer.analyze()
            assert 0.0 <= report.dominance_strength <= 1.0

    def test_mean_pressure_calculation(self):
        from gamepad_midi_bridge.trigger_asymmetry import (
            AsymmetryConfig,
            TriggerAsymmetryAnalyzer,
        )

        cfg = AsymmetryConfig()
        analyzer = TriggerAsymmetryAnalyzer(cfg)

        analyzer.record("L2", 0.2)
        analyzer.record("L2", 0.4)
        analyzer.record("L2", 0.6)

        report = analyzer.analyze()
        assert abs(report.l2_mean_pressure - 0.4) < 0.01

    def test_peak_pressure_calculation(self):
        from gamepad_midi_bridge.trigger_asymmetry import (
            AsymmetryConfig,
            TriggerAsymmetryAnalyzer,
        )

        cfg = AsymmetryConfig()
        analyzer = TriggerAsymmetryAnalyzer(cfg)

        analyzer.record("L2", 0.3)
        analyzer.record("L2", 0.9)
        analyzer.record("L2", 0.5)

        report = analyzer.analyze()
        assert report.l2_peak_pressure == 0.9

    def test_clear(self):
        from gamepad_midi_bridge.trigger_asymmetry import (
            AsymmetryConfig,
            TriggerAsymmetryAnalyzer,
        )

        cfg = AsymmetryConfig()
        analyzer = TriggerAsymmetryAnalyzer(cfg)

        analyzer.record("L2", 0.5)
        analyzer.record("R2", 0.6)
        assert analyzer.total_records() == 2

        analyzer.clear()
        assert analyzer.total_records() == 0
        report = analyzer.analyze()
        assert report.dominant_trigger == "balanced"

    def test_total_records(self):
        from gamepad_midi_bridge.trigger_asymmetry import (
            AsymmetryConfig,
            TriggerAsymmetryAnalyzer,
        )

        cfg = AsymmetryConfig()
        analyzer = TriggerAsymmetryAnalyzer(cfg)

        analyzer.record("L2", 0.5)
        assert analyzer.total_records() == 1

        analyzer.record("L2", 0.6)
        analyzer.record("R2", 0.7)
        assert analyzer.total_records() == 3

    def test_l2_count_r2_count(self):
        from gamepad_midi_bridge.trigger_asymmetry import (
            AsymmetryConfig,
            TriggerAsymmetryAnalyzer,
        )

        cfg = AsymmetryConfig()
        analyzer = TriggerAsymmetryAnalyzer(cfg)

        for _ in range(25):
            analyzer.record("L2", 0.5)
        for _ in range(35):
            analyzer.record("R2", 0.6)

        assert analyzer.l2_count() == 25
        assert analyzer.r2_count() == 35

    def test_summary_dict(self):
        from gamepad_midi_bridge.trigger_asymmetry import (
            AsymmetryConfig,
            TriggerAsymmetryAnalyzer,
        )

        cfg = AsymmetryConfig()
        analyzer = TriggerAsymmetryAnalyzer(cfg)

        for _ in range(70):
            analyzer.record("L2", 0.8)
        for _ in range(30):
            analyzer.record("R2", 0.4)

        summary = analyzer.summary()
        assert summary["l2_count"] == 70
        assert summary["r2_count"] == 30
        assert summary["total_records"] == 100
        assert summary["dominant_trigger"] == "L2"
        assert 0.0 <= summary["dominance_strength"] <= 1.0
