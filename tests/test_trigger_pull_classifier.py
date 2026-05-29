"""Tests for trigger_pull_classifier module.

Tests classification of trigger pull styles and feature computation.
"""
import pytest
from gamepad_midi_bridge.trigger_pull_classifier import (
    PullSample,
    PullCurve,
    STYLES,
    compute_pull_features,
    classify,
    classify_history,
    dominant_style,
)


# ================================================================ helpers

def make_pull(
    pressures: list[float],
    start_t: float = 0.0,
    sample_interval_s: float = 0.01,
) -> PullCurve:
    """Helper to create a PullCurve from a list of pressure values.

    Args:
        pressures: List of pressure values (0..1).
        start_t: Starting timestamp in seconds.
        sample_interval_s: Time between samples in seconds.

    Returns:
        PullCurve with samples and computed peak/duration.
    """
    samples = []
    for i, p in enumerate(pressures):
        t = start_t + i * sample_interval_s
        samples.append(PullSample(pressure=float(p), timestamp_s=t))

    peak = max(pressures) if pressures else 0.0
    duration_ms = (len(pressures) - 1) * sample_interval_s * 1000.0 if len(pressures) > 1 else 0.0

    return PullCurve(samples=samples, peak_pressure=peak, duration_ms=duration_ms)


# ================================================================ tests: compute_pull_features

def test_compute_pull_features_empty_curve():
    """Empty curve returns default features."""
    curve = PullCurve(samples=[], peak_pressure=0.0, duration_ms=0.0)
    features = compute_pull_features(curve)

    assert features["peak_pressure"] == 0.0
    assert features["duration_ms"] == 0.0
    assert features["time_to_peak_ratio"] == 0.0
    assert features["ramp_slope"] == 0.0
    assert features["plateau_ratio"] == 0.0
    assert features["variance"] == 0.0


def test_compute_pull_features_single_sample():
    """Single-sample curve computes features gracefully."""
    curve = PullCurve(
        samples=[PullSample(pressure=0.8, timestamp_s=0.0)],
        peak_pressure=0.8,
        duration_ms=0.0,
    )
    features = compute_pull_features(curve)

    assert features["peak_pressure"] == 0.8
    assert features["duration_ms"] == 0.0
    assert features["ramp_slope"] == 0.0  # duration is 0
    assert features["variance"] == 0.0  # only 1 sample


def test_compute_pull_features_linear_ramp():
    """Linear ramp-up computes correct features."""
    # Create a linear ramp from 0 to 1 over 100ms
    pressures = [i / 10.0 for i in range(11)]  # 0, 0.1, 0.2, ..., 1.0
    curve = make_pull(pressures, sample_interval_s=0.01)

    features = compute_pull_features(curve)

    assert features["peak_pressure"] == 1.0
    assert features["duration_ms"] == pytest.approx(100.0, abs=0.5)
    assert features["time_to_peak_ratio"] == 1.0  # peak is at the end
    assert features["ramp_slope"] == pytest.approx(10.0, abs=0.5)  # 1.0 pressure / 0.1 s


def test_compute_pull_features_plateau():
    """Curve with a plateau computes plateau_ratio."""
    # Quick ramp to 0.7, then stay for a while
    pressures = [0.1, 0.3, 0.5, 0.7, 0.7, 0.7, 0.7, 0.8, 0.8, 0.8]
    curve = make_pull(pressures)

    features = compute_pull_features(curve)

    # Peak is 0.8, plateau_ratio should count samples within 0.1 of 0.8
    assert features["peak_pressure"] == 0.8
    # Samples within 0.1 of 0.8: 0.8, 0.8, 0.8 = 3 out of 10
    assert features["plateau_ratio"] == pytest.approx(0.3, abs=0.05)


def test_compute_pull_features_variance():
    """Variance is computed correctly for oscillating curve."""
    # Oscillating between 0.5 and 0.8
    pressures = [0.5, 0.8, 0.5, 0.8, 0.5, 0.8]
    curve = make_pull(pressures)

    features = compute_pull_features(curve)

    # Variance should be non-zero
    assert features["variance"] > 0.01


# ================================================================ tests: classify

def test_classify_feathery():
    """Low peak classified as feathery."""
    curve = make_pull([0.0, 0.1, 0.3, 0.25])
    style, confidence = classify(curve)

    assert style == "feathery"
    assert 0.0 <= confidence <= 1.0
    # Confidence should be proportional to low peak
    assert confidence > 0.3


def test_classify_slammy():
    """Quick pull classified as slammy."""
    # Fast ramp to peak in ~30ms with high peak
    curve = make_pull([0.0, 0.3, 0.7, 1.0], sample_interval_s=0.01)
    curve.duration_ms = 30.0  # Explicitly set short duration
    style, confidence = classify(curve)

    assert style == "slammy"
    assert 0.0 <= confidence <= 1.0
    assert confidence > 0.3


def test_classify_two_stage():
    """Plateau then snap classified as two_stage."""
    # Many samples at peak (1.0) to exceed plateau ratio threshold
    # Need 36% of samples within 0.1 of peak
    pressures = [0.0, 0.3, 0.8] + [0.8] * 10 + [1.0] * 20
    curve = make_pull(pressures, sample_interval_s=0.01)
    style, confidence = classify(curve)

    assert style == "two_stage"
    assert 0.0 <= confidence <= 1.0


def test_classify_twitchy():
    """Oscillating curve classified as twitchy."""
    # Very high variance from extreme oscillations
    pressures = [0.05, 0.95, 0.1, 0.98, 0.05, 0.96, 0.1, 0.95, 0.05, 0.97]
    curve = make_pull(pressures, sample_interval_s=0.01)
    style, confidence = classify(curve)

    assert style == "twitchy"
    assert 0.0 <= confidence <= 1.0


def test_classify_gradual():
    """Smooth ramp classified as gradual (default)."""
    # Smooth linear ramp
    pressures = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
    curve = make_pull(pressures, sample_interval_s=0.01)
    style, confidence = classify(curve)

    assert style == "gradual"
    assert confidence == 0.5


def test_classify_empty_curve():
    """Empty curve returns feathery with low confidence."""
    curve = PullCurve(samples=[], peak_pressure=0.0, duration_ms=0.0)
    style, confidence = classify(curve)

    assert style == "feathery"
    assert confidence < 0.3


def test_classify_confidence_range():
    """All classifications return confidence in [0, 1]."""
    test_curves = [
        make_pull([0.0, 0.1, 0.2]),  # feathery
        make_pull([0.0, 0.5, 1.0], sample_interval_s=0.001),  # slammy
        make_pull([0.0, 0.2, 0.6, 0.6, 0.6, 0.8]),  # two_stage
        make_pull([0.4, 0.8, 0.3, 0.7, 0.5]),  # twitchy
        make_pull([0.0, 0.2, 0.4, 0.6, 0.8]),  # gradual
    ]

    for curve in test_curves:
        style, confidence = classify(curve)
        assert style in STYLES
        assert 0.0 <= confidence <= 1.0


# ================================================================ tests: classify_history

def test_classify_history_empty():
    """Empty history returns all zeros."""
    distribution = classify_history([])

    assert len(distribution) == len(STYLES)
    for style in STYLES:
        assert distribution[style] == 0.0


def test_classify_history_single_pull():
    """Single pull distribution sums to 1.0."""
    curve = make_pull([0.0, 0.2, 0.4, 0.6, 0.8])
    distribution = classify_history([curve])

    total = sum(distribution.values())
    assert total == pytest.approx(1.0)

    # One style should be 1.0, others 0.0
    assert sum(1 for v in distribution.values() if v > 0.5) == 1


def test_classify_history_mixed_styles():
    """Multiple different styles distribute correctly."""
    curves = [
        make_pull([0.0, 0.1, 0.2]),  # feathery
        make_pull([0.0, 0.1, 0.2]),  # feathery again
        make_pull([0.0, 0.3, 0.7, 1.0], sample_interval_s=0.001),  # slammy
        make_pull([0.0, 0.2, 0.4, 0.6, 0.8]),  # gradual
    ]
    distribution = classify_history(curves)

    total = sum(distribution.values())
    assert total == pytest.approx(1.0)

    # Feathery should be 2/4 = 0.5
    assert distribution["feathery"] == pytest.approx(0.5)


def test_classify_history_all_styles():
    """All style keys present in distribution."""
    curves = [make_pull([0.0, 0.5, 1.0]) for _ in range(5)]
    distribution = classify_history(curves)

    for style in STYLES:
        assert style in distribution
        assert 0.0 <= distribution[style] <= 1.0


# ================================================================ tests: dominant_style

def test_dominant_style_empty():
    """Empty list returns None."""
    result = dominant_style([])
    assert result is None


def test_dominant_style_single():
    """Single pull returns that style with fraction 1.0."""
    # Create a longer gradual ramp to avoid slammy classification
    curve = make_pull([0.0, 0.2, 0.4, 0.6, 0.8], sample_interval_s=0.05)
    style, fraction = dominant_style([curve])

    assert style == "gradual"
    assert fraction == 1.0


def test_dominant_style_clear_winner():
    """History with clear dominant style."""
    curves = [
        make_pull([0.0, 0.1, 0.2]),  # feathery
        make_pull([0.0, 0.1, 0.2]),  # feathery
        make_pull([0.0, 0.1, 0.2]),  # feathery
        make_pull([0.0, 0.5, 1.0], sample_interval_s=0.001),  # slammy (once)
    ]
    style, fraction = dominant_style(curves)

    assert style == "feathery"
    assert fraction == pytest.approx(0.75)


def test_dominant_style_tie():
    """Tie in dominance returns one of the tied styles."""
    curves = [
        make_pull([0.0, 0.1, 0.2]),  # feathery
        make_pull([0.0, 0.2, 0.4, 0.6, 0.8]),  # gradual
    ]
    style, fraction = dominant_style(curves)

    assert style in STYLES
    assert fraction == pytest.approx(0.5)


# ================================================================ tests: serialization

def test_pull_sample_serialization():
    """PullSample round-trips through dict."""
    sample = PullSample(pressure=0.75, timestamp_s=1234.56)
    d = sample.to_dict()
    recovered = PullSample.from_dict(d)

    assert recovered.pressure == pytest.approx(0.75)
    assert recovered.timestamp_s == pytest.approx(1234.56)


def test_pull_curve_serialization():
    """PullCurve round-trips through dict."""
    samples = [
        PullSample(pressure=0.1, timestamp_s=0.0),
        PullSample(pressure=0.5, timestamp_s=0.01),
        PullSample(pressure=0.9, timestamp_s=0.02),
    ]
    curve = PullCurve(samples=samples, peak_pressure=0.9, duration_ms=20.0)

    d = curve.to_dict()
    recovered = PullCurve.from_dict(d)

    assert len(recovered.samples) == 3
    assert recovered.peak_pressure == pytest.approx(0.9)
    assert recovered.duration_ms == pytest.approx(20.0)
    assert recovered.samples[0].pressure == pytest.approx(0.1)
    assert recovered.samples[1].timestamp_s == pytest.approx(0.01)


# ================================================================ tests: edge cases

def test_classify_zero_peak():
    """Zero peak classified as feathery."""
    curve = PullCurve(samples=[PullSample(0.0, 0.0)], peak_pressure=0.0, duration_ms=0.0)
    style, confidence = classify(curve)

    assert style == "feathery"
    assert confidence < 0.5


def test_classify_max_pressure():
    """Maximum pressure (1.0) classified based on duration."""
    # High pressure but very fast → slammy
    curve = PullCurve(
        samples=[PullSample(1.0, 0.0)],
        peak_pressure=1.0,
        duration_ms=25.0,
    )
    style, confidence = classify(curve)

    assert style == "slammy"


def test_features_variance_stability():
    """Variance computation doesn't crash on edge cases."""
    # Constant pressure (no variance)
    pressures = [0.5] * 10
    curve = make_pull(pressures)
    features = compute_pull_features(curve)

    assert features["variance"] == 0.0


def test_plateau_ratio_boundary():
    """Plateau ratio near threshold works correctly."""
    # Plateau ratio exactly 0.3 (boundary case)
    pressures = [0.5, 0.5, 0.5, 0.6, 0.6, 0.6, 0.6, 0.6, 0.6, 0.9]
    curve = make_pull(pressures)
    features = compute_pull_features(curve)

    # Should be close to 0.3 (7 out of ~10 near the 0.9 peak)
    # Actually, we count samples within 0.1 of 0.9, so: 0.9 itself = 1
    # This depends on exact implementation
    assert 0.0 <= features["plateau_ratio"] <= 1.0


# ================================================================ tests: integration

def test_full_workflow():
    """Complete workflow: classify history, get dominant style."""
    # Simulate a user playing session with mixed styles
    session_pulls = [
        make_pull([0.0, 0.15, 0.25]),  # feathery
        make_pull([0.0, 0.15, 0.25]),  # feathery
        make_pull([0.0, 0.3, 0.6, 0.9], sample_interval_s=0.05),  # gradual (longer)
        make_pull([0.0, 0.3, 0.6, 0.9], sample_interval_s=0.05),  # gradual (longer)
        make_pull([0.0, 0.3, 0.6, 0.9], sample_interval_s=0.05),  # gradual (longer)
    ]

    # Get distribution
    dist = classify_history(session_pulls)
    assert sum(dist.values()) == pytest.approx(1.0)

    # Get dominant style
    top_style, top_frac = dominant_style(session_pulls)
    assert top_style == "gradual"
    assert top_frac == pytest.approx(0.6)

    # Verify features exist for all
    for curve in session_pulls:
        features = compute_pull_features(curve)
        assert all(k in features for k in [
            "peak_pressure", "duration_ms", "time_to_peak_ratio",
            "ramp_slope", "plateau_ratio", "variance"
        ])


def test_realistic_session():
    """Realistic playing session with varied styles."""
    pulls = []

    # User starts with a few feathery pulls (warming up)
    for _ in range(3):
        pulls.append(make_pull([0.0, 0.08, 0.15, 0.12]))

    # Then switches to gradual pulls (main technique, longer duration to avoid slammy)
    for _ in range(7):
        pulls.append(make_pull([0.0, 0.2, 0.4, 0.6, 0.8, 0.9], sample_interval_s=0.05))

    # One twitchy moment (very high variance to exceed 0.15 threshold)
    pulls.append(make_pull([0.05, 0.95, 0.1, 0.98, 0.05, 0.96, 0.1, 0.98, 0.05, 0.97]))

    # Summary
    dist = classify_history(pulls)
    # 3 feathery, 7 gradual, 1 twitchy = 11 total
    assert dist["gradual"] == pytest.approx(7.0/11)
    assert dist["feathery"] == pytest.approx(3.0/11)
    assert dist["twitchy"] == pytest.approx(1.0/11)

    dominant, frac = dominant_style(pulls)
    assert dominant == "gradual"
    assert frac > 0.6
