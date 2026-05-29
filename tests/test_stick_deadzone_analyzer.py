"""Tests for stick deadzone analyzer module."""

import math

import pytest
from gamepad_midi_bridge.stick_deadzone_analyzer import (
    DeadzoneAnalysis,
    DeadzoneAnalyzerConfig,
    StickDeadzoneAnalyzer,
)


class TestDeadzoneAnalyzerConfig:
    """Tests for DeadzoneAnalyzerConfig dataclass."""

    def test_default_config(self):
        """Default config has standard values."""
        cfg = DeadzoneAnalyzerConfig()
        assert cfg.min_samples == 100
        assert cfg.stable_std_threshold == 0.03

    def test_custom_config(self):
        """Can construct with custom values."""
        cfg = DeadzoneAnalyzerConfig(
            min_samples=200,
            stable_std_threshold=0.05,
        )
        assert cfg.min_samples == 200
        assert cfg.stable_std_threshold == 0.05

    def test_clamp_min_samples_lower(self):
        """min_samples clamped to minimum of 10."""
        cfg = DeadzoneAnalyzerConfig(min_samples=5)
        assert cfg.min_samples == 10

    def test_clamp_min_samples_upper(self):
        """min_samples clamped to maximum of 10000."""
        cfg = DeadzoneAnalyzerConfig(min_samples=20000)
        assert cfg.min_samples == 10000

    def test_clamp_stable_std_threshold_lower(self):
        """stable_std_threshold clamped to minimum of 0."""
        cfg = DeadzoneAnalyzerConfig(stable_std_threshold=-0.1)
        assert cfg.stable_std_threshold == 0.0

    def test_clamp_stable_std_threshold_upper(self):
        """stable_std_threshold clamped to maximum of 0.5."""
        cfg = DeadzoneAnalyzerConfig(stable_std_threshold=0.6)
        assert cfg.stable_std_threshold == 0.5

    def test_config_to_dict(self):
        """Config serializes to dict."""
        cfg = DeadzoneAnalyzerConfig(min_samples=150, stable_std_threshold=0.04)
        d = cfg.to_dict()
        assert d["min_samples"] == 150
        assert d["stable_std_threshold"] == 0.04

    def test_config_from_dict(self):
        """Config deserializes from dict."""
        d = {"min_samples": 150, "stable_std_threshold": 0.04}
        cfg = DeadzoneAnalyzerConfig.from_dict(d)
        assert cfg.min_samples == 150
        assert cfg.stable_std_threshold == 0.04

    def test_config_round_trip(self):
        """Config survives to_dict/from_dict round-trip."""
        original = DeadzoneAnalyzerConfig(min_samples=250, stable_std_threshold=0.06)
        restored = DeadzoneAnalyzerConfig.from_dict(original.to_dict())
        assert restored.min_samples == original.min_samples
        assert restored.stable_std_threshold == original.stable_std_threshold


class TestDeadzoneAnalysis:
    """Tests for DeadzoneAnalysis dataclass."""

    def test_analysis_to_dict(self):
        """Analysis serializes to dict."""
        analysis = DeadzoneAnalysis(
            sample_count=100,
            mean_distance=0.02,
            max_distance=0.08,
            p50_distance=0.015,
            p90_distance=0.05,
            p99_distance=0.07,
            recommended_tight=0.06,
            recommended_balanced=0.09,
            recommended_loose=0.13,
            stable=True,
        )
        d = analysis.to_dict()
        assert d["sample_count"] == 100
        assert d["mean_distance"] == 0.02
        assert d["stable"] is True

    def test_analysis_from_dict(self):
        """Analysis deserializes from dict."""
        d = {
            "sample_count": 100,
            "mean_distance": 0.02,
            "max_distance": 0.08,
            "p50_distance": 0.015,
            "p90_distance": 0.05,
            "p99_distance": 0.07,
            "recommended_tight": 0.06,
            "recommended_balanced": 0.09,
            "recommended_loose": 0.13,
            "stable": True,
        }
        analysis = DeadzoneAnalysis.from_dict(d)
        assert analysis.sample_count == 100
        assert analysis.mean_distance == 0.02
        assert analysis.stable is True

    def test_analysis_round_trip(self):
        """Analysis survives to_dict/from_dict round-trip."""
        original = DeadzoneAnalysis(
            sample_count=150,
            mean_distance=0.025,
            max_distance=0.1,
            p50_distance=0.02,
            p90_distance=0.06,
            p99_distance=0.08,
            recommended_tight=0.07,
            recommended_balanced=0.1,
            recommended_loose=0.15,
            stable=False,
        )
        restored = DeadzoneAnalysis.from_dict(original.to_dict())
        assert restored.sample_count == original.sample_count
        assert restored.mean_distance == original.mean_distance
        assert restored.max_distance == original.max_distance
        assert restored.stable == original.stable


class TestStickDeadzoneAnalyzer:
    """Tests for StickDeadzoneAnalyzer class."""

    def test_empty_analyze_returns_none(self):
        """analyze returns None with no samples."""
        cfg = DeadzoneAnalyzerConfig(min_samples=10)
        analyzer = StickDeadzoneAnalyzer(cfg)
        assert analyzer.analyze() is None

    def test_too_few_samples_returns_none(self):
        """analyze returns None if fewer than min_samples."""
        cfg = DeadzoneAnalyzerConfig(min_samples=10)
        analyzer = StickDeadzoneAnalyzer(cfg)
        for _ in range(5):
            analyzer.add_sample(0.01, 0.01)
        assert analyzer.analyze() is None

    def test_clamp_x_y_in_add_sample(self):
        """add_sample clamps x,y to -1..1."""
        cfg = DeadzoneAnalyzerConfig(min_samples=1)
        analyzer = StickDeadzoneAnalyzer(cfg)
        analyzer.add_sample(2.0, -2.0)
        analyzer.add_sample(-1.5, 1.5)
        assert analyzer._samples[0] == (1.0, -1.0)
        assert analyzer._samples[1] == (-1.0, 1.0)

    def test_clear_empties_samples(self):
        """clear removes all samples."""
        cfg = DeadzoneAnalyzerConfig(min_samples=10)
        analyzer = StickDeadzoneAnalyzer(cfg)
        for _ in range(10):
            analyzer.add_sample(0.01, 0.01)
        assert len(analyzer._samples) == 10
        analyzer.clear()
        assert len(analyzer._samples) == 0

    def test_samples_near_origin(self):
        """Samples near origin give small mean_distance."""
        cfg = DeadzoneAnalyzerConfig(min_samples=10)
        analyzer = StickDeadzoneAnalyzer(cfg)
        for _ in range(20):
            analyzer.add_sample(0.01, 0.01)
        analysis = analyzer.analyze()
        assert analysis is not None
        assert analysis.sample_count == 20
        assert analysis.mean_distance < 0.02

    def test_distance_ordering(self):
        """max >= p99 >= p90 >= p50."""
        cfg = DeadzoneAnalyzerConfig(min_samples=10)
        analyzer = StickDeadzoneAnalyzer(cfg)
        for i in range(100):
            dist = i / 100.0
            analyzer.add_sample(dist, 0.0)
        analysis = analyzer.analyze()
        assert analysis is not None
        assert analysis.max_distance >= analysis.p99_distance
        assert analysis.p99_distance >= analysis.p90_distance
        assert analysis.p90_distance >= analysis.p50_distance

    def test_recommendation_ordering(self):
        """recommended_tight < balanced < loose."""
        cfg = DeadzoneAnalyzerConfig(min_samples=10)
        analyzer = StickDeadzoneAnalyzer(cfg)
        for i in range(100):
            dist = i / 1000.0
            analyzer.add_sample(dist, 0.0)
        analysis = analyzer.analyze()
        assert analysis is not None
        assert analysis.recommended_tight < analysis.recommended_balanced
        assert analysis.recommended_balanced < analysis.recommended_loose

    def test_stable_true_when_samples_close_together(self):
        """stable=True when all samples are close together."""
        cfg = DeadzoneAnalyzerConfig(min_samples=10, stable_std_threshold=0.05)
        analyzer = StickDeadzoneAnalyzer(cfg)
        for _ in range(20):
            analyzer.add_sample(0.001, 0.001)
        analysis = analyzer.analyze()
        assert analysis is not None
        assert analysis.stable is True

    def test_stable_false_with_wild_samples(self):
        """stable=False when samples are scattered."""
        cfg = DeadzoneAnalyzerConfig(min_samples=10, stable_std_threshold=0.001)
        analyzer = StickDeadzoneAnalyzer(cfg)
        for i in range(20):
            analyzer.add_sample(i / 20.0, 0.0)
        analysis = analyzer.analyze()
        assert analysis is not None
        assert analysis.stable is False

    def test_recommend_tight(self):
        """recommend('tight') returns recommended_tight."""
        cfg = DeadzoneAnalyzerConfig(min_samples=10)
        analyzer = StickDeadzoneAnalyzer(cfg)
        for _ in range(20):
            analyzer.add_sample(0.01, 0.01)
        tight = analyzer.recommend("tight")
        assert tight is not None
        analysis = analyzer.analyze()
        assert abs(tight - analysis.recommended_tight) < 1e-6

    def test_recommend_balanced(self):
        """recommend('balanced') returns recommended_balanced."""
        cfg = DeadzoneAnalyzerConfig(min_samples=10)
        analyzer = StickDeadzoneAnalyzer(cfg)
        for _ in range(20):
            analyzer.add_sample(0.01, 0.01)
        balanced = analyzer.recommend("balanced")
        assert balanced is not None
        analysis = analyzer.analyze()
        assert abs(balanced - analysis.recommended_balanced) < 1e-6

    def test_recommend_loose(self):
        """recommend('loose') returns recommended_loose."""
        cfg = DeadzoneAnalyzerConfig(min_samples=10)
        analyzer = StickDeadzoneAnalyzer(cfg)
        for _ in range(20):
            analyzer.add_sample(0.01, 0.01)
        loose = analyzer.recommend("loose")
        assert loose is not None
        analysis = analyzer.analyze()
        assert abs(loose - analysis.recommended_loose) < 1e-6

    def test_recommend_unknown_profile_returns_none(self):
        """recommend with unknown profile returns None."""
        cfg = DeadzoneAnalyzerConfig(min_samples=10)
        analyzer = StickDeadzoneAnalyzer(cfg)
        for _ in range(20):
            analyzer.add_sample(0.01, 0.01)
        result = analyzer.recommend("unknown")
        assert result is None

    def test_recommend_with_insufficient_samples_returns_none(self):
        """recommend returns None if not enough samples."""
        cfg = DeadzoneAnalyzerConfig(min_samples=100)
        analyzer = StickDeadzoneAnalyzer(cfg)
        for _ in range(10):
            analyzer.add_sample(0.01, 0.01)
        result = analyzer.recommend("balanced")
        assert result is None

    def test_multiple_analyze_calls_consistent(self):
        """Multiple analyze calls return same result."""
        cfg = DeadzoneAnalyzerConfig(min_samples=10)
        analyzer = StickDeadzoneAnalyzer(cfg)
        for _ in range(20):
            analyzer.add_sample(0.02, 0.02)
        analysis1 = analyzer.analyze()
        analysis2 = analyzer.analyze()
        assert analysis1 is not None
        assert analysis2 is not None
        assert analysis1.mean_distance == analysis2.mean_distance
        assert analysis1.max_distance == analysis2.max_distance
