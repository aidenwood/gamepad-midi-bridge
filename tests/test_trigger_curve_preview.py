"""Tests for trigger curve preview sampler.

Pure-function curve sampling for UI sparklines. No Qt, just pure math
for generating sample arrays of trigger response curves.
"""
from __future__ import annotations

import pytest

from gamepad_midi_bridge import trigger_curve_preview as tcp


# ─────────────────────────────────────────────────────────────────────
# sample_linear
# ─────────────────────────────────────────────────────────────────────


def test_sample_linear_returns_n_values():
    """sample_linear(32) returns exactly 32 values."""
    result = tcp.sample_linear(32)
    assert len(result) == 32


def test_sample_linear_first_is_min_last_is_max():
    """First value is min_value, last is max_value."""
    result = tcp.sample_linear(5, min_value=0, max_value=127)
    assert result[0] == 0
    assert result[-1] == 127


def test_sample_linear_monotonically_increasing():
    """Values increase monotonically from first to last."""
    result = tcp.sample_linear(10, min_value=0, max_value=127)
    for i in range(len(result) - 1):
        assert result[i] <= result[i + 1]


def test_sample_linear_with_single_sample():
    """sample_linear(1) returns a single-element list with max_value."""
    result = tcp.sample_linear(1, min_value=0, max_value=127)
    assert len(result) == 1
    assert result[0] == 127


def test_sample_linear_empty_samples():
    """sample_linear(0) returns empty list."""
    result = tcp.sample_linear(0)
    assert result == []


def test_sample_linear_custom_range():
    """Works with custom min and max values."""
    result = tcp.sample_linear(5, min_value=10, max_value=100)
    assert result[0] >= 10
    assert result[-1] <= 100


# ─────────────────────────────────────────────────────────────────────
# sample_with_ceiling
# ─────────────────────────────────────────────────────────────────────


def test_sample_with_ceiling_returns_n_values():
    """sample_with_ceiling(32) returns exactly 32 values."""
    result = tcp.sample_with_ceiling(32, ceiling=80)
    assert len(result) == 32


def test_sample_with_ceiling_clips_at_ceiling():
    """Full pressure reaches ceiling, not 127."""
    result = tcp.sample_with_ceiling(5, ceiling=80)
    assert result[-1] == 80


def test_sample_with_ceiling_zero_start():
    """Starts at zero."""
    result = tcp.sample_with_ceiling(5, ceiling=100)
    assert result[0] == 0


def test_sample_with_ceiling_monotonically_increasing():
    """Values increase monotonically."""
    result = tcp.sample_with_ceiling(10, ceiling=64)
    for i in range(len(result) - 1):
        assert result[i] <= result[i + 1]


def test_sample_with_ceiling_various_ceilings():
    """Works correctly with different ceiling values."""
    for ceiling in (32, 64, 100, 127):
        result = tcp.sample_with_ceiling(5, ceiling=ceiling)
        assert result[-1] <= ceiling


# ─────────────────────────────────────────────────────────────────────
# sample_inverted
# ─────────────────────────────────────────────────────────────────────


def test_sample_inverted_returns_n_values():
    """sample_inverted(32) returns exactly 32 values."""
    result = tcp.sample_inverted(32)
    assert len(result) == 32


def test_sample_inverted_descending():
    """Values descend from max to min (first > last)."""
    result = tcp.sample_inverted(10, min_value=0, max_value=127)
    assert result[0] > result[-1]
    assert result[0] == 127
    assert result[-1] == 0


def test_sample_inverted_first_is_max_last_is_min():
    """First is max_value, last is min_value."""
    result = tcp.sample_inverted(5, min_value=10, max_value=100)
    assert result[0] == 100
    assert result[-1] == 10


def test_sample_inverted_monotonically_decreasing():
    """Values decrease monotonically."""
    result = tcp.sample_inverted(10, min_value=0, max_value=127)
    for i in range(len(result) - 1):
        assert result[i] >= result[i + 1]


# ─────────────────────────────────────────────────────────────────────
# sample_latched
# ─────────────────────────────────────────────────────────────────────


def test_sample_latched_returns_n_values():
    """sample_latched(32) returns exactly 32 values."""
    result = tcp.sample_latched(32)
    assert len(result) == 32


def test_sample_latched_has_two_levels():
    """Result contains both low_value and high_value."""
    result = tcp.sample_latched(32, threshold=0.5, low_value=0, high_value=127)
    assert 0 in result
    assert 127 in result


def test_sample_latched_threshold_at_middle():
    """With threshold=0.5, transition is near middle."""
    result = tcp.sample_latched(10, threshold=0.5, low_value=0, high_value=127)
    # First half should be mostly low
    first_half = result[:5]
    # Second half should be mostly high
    second_half = result[5:]
    assert all(v == 0 for v in first_half)
    assert all(v == 127 for v in second_half)


def test_sample_latched_threshold_near_start():
    """With threshold=0.1, transition is near the start."""
    result = tcp.sample_latched(10, threshold=0.1, low_value=0, high_value=100)
    # Most should be high
    high_count = sum(1 for v in result if v == 100)
    assert high_count >= 8


def test_sample_latched_threshold_near_end():
    """With threshold=0.9, transition is near the end."""
    result = tcp.sample_latched(10, threshold=0.9, low_value=0, high_value=100)
    # Most should be low
    low_count = sum(1 for v in result if v == 0)
    assert low_count >= 8


# ─────────────────────────────────────────────────────────────────────
# sample_bow
# ─────────────────────────────────────────────────────────────────────


def test_sample_bow_returns_n_values():
    """sample_bow(32) returns exactly 32 values."""
    result = tcp.sample_bow(32)
    assert len(result) == 32


def test_sample_bow_peaks_near_middle():
    """Maximum value is near the middle of the array."""
    result = tcp.sample_bow(32)
    max_value = max(result)
    max_idx = result.index(max_value)
    # Peak should be within the middle third
    assert 8 <= max_idx <= 24


def test_sample_bow_small_at_edges():
    """First and last values are small (edges are quiet)."""
    result = tcp.sample_bow(32, min_velocity=0.1, max_velocity=5.0)
    # Edges should be much smaller than peak
    edge_avg = (result[0] + result[-1]) / 2
    peak = max(result)
    assert edge_avg < peak * 0.3


def test_sample_bow_symmetric():
    """Curve is roughly symmetric around the middle."""
    result = tcp.sample_bow(32)
    # Mirror comparison: first should be close to last, etc.
    mid = len(result) // 2
    for i in range(mid):
        left = result[i]
        right = result[-(i + 1)]
        assert abs(left - right) <= 2  # Within 2 MIDI units


# ─────────────────────────────────────────────────────────────────────
# sample_crossfade
# ─────────────────────────────────────────────────────────────────────


def test_sample_crossfade_returns_two_arrays():
    """sample_crossfade returns (a_curve, b_curve)."""
    a, b = tcp.sample_crossfade(32)
    assert isinstance(a, list)
    assert isinstance(b, list)
    assert len(a) == 32
    assert len(b) == 32


def test_sample_crossfade_same_length():
    """Both curves have the same number of samples."""
    a, b = tcp.sample_crossfade(16, curve=1.0)
    assert len(a) == len(b) == 16


def test_sample_crossfade_sum_to_127():
    """At each index, a[i] + b[i] ≈ 127 (within rounding)."""
    a, b = tcp.sample_crossfade(32, curve=1.0)
    for i in range(len(a)):
        total = a[i] + b[i]
        # Linear crossfade should sum exactly to 127 at each point
        assert total == 127


def test_sample_crossfade_a_rises():
    """Curve A rises from 0 to 127."""
    a, b = tcp.sample_crossfade(10, curve=1.0)
    assert a[0] == 0
    assert a[-1] == 127


def test_sample_crossfade_b_falls():
    """Curve B falls from 127 to 0."""
    a, b = tcp.sample_crossfade(10, curve=1.0)
    assert b[0] == 127
    assert b[-1] == 0


def test_sample_crossfade_curve_2_biases_a_low():
    """With curve=2.0, A is biased low at midpoint (exponential)."""
    a, b = tcp.sample_crossfade(10, curve=2.0)
    mid = len(a) // 2
    # At midpoint, A should be well below 64 due to exponential curve
    assert a[mid] < 50


def test_sample_crossfade_curve_0_5_biases_a_high():
    """With curve=0.5, A is biased high at midpoint (logarithmic)."""
    a, b = tcp.sample_crossfade(10, curve=0.5)
    mid = len(a) // 2
    # At midpoint, A should be well above 64 due to logarithmic curve
    assert a[mid] > 75


# ─────────────────────────────────────────────────────────────────────
# sample_from_mode (dispatcher)
# ─────────────────────────────────────────────────────────────────────


def test_sample_from_mode_linear():
    """sample_from_mode("linear") dispatches to sample_linear."""
    result = tcp.sample_from_mode("linear", samples=10)
    expected = tcp.sample_linear(10)
    assert result == expected


def test_sample_from_mode_ceiling():
    """sample_from_mode("ceiling") dispatches to sample_with_ceiling."""
    result = tcp.sample_from_mode("ceiling", samples=10, ceiling=80)
    expected = tcp.sample_with_ceiling(10, ceiling=80)
    assert result == expected


def test_sample_from_mode_inverted():
    """sample_from_mode("inverted") dispatches to sample_inverted."""
    result = tcp.sample_from_mode("inverted", samples=10)
    expected = tcp.sample_inverted(10)
    assert result == expected


def test_sample_from_mode_latch():
    """sample_from_mode("latch") dispatches to sample_latched."""
    result = tcp.sample_from_mode("latch", samples=10, threshold=0.5)
    expected = tcp.sample_latched(10, threshold=0.5)
    assert result == expected


def test_sample_from_mode_bow():
    """sample_from_mode("bow") dispatches to sample_bow."""
    result = tcp.sample_from_mode("bow", samples=10)
    expected = tcp.sample_bow(10)
    assert result == expected


def test_sample_from_mode_unknown_defaults_to_linear():
    """Unknown mode name defaults to linear."""
    result = tcp.sample_from_mode("unknown_mode", samples=10)
    expected = tcp.sample_linear(10)
    assert result == expected


def test_sample_from_mode_case_insensitive():
    """Mode name matching is case-insensitive."""
    linear_lower = tcp.sample_from_mode("linear", samples=10)
    linear_upper = tcp.sample_from_mode("LINEAR", samples=10)
    linear_mixed = tcp.sample_from_mode("LiNeAr", samples=10)
    assert linear_lower == linear_upper == linear_mixed


# ─────────────────────────────────────────────────────────────────────
# Value range validation
# ─────────────────────────────────────────────────────────────────────


def test_all_linear_values_in_midi_range():
    """sample_linear always returns values in 0..127."""
    result = tcp.sample_linear(100, min_value=0, max_value=127)
    assert all(0 <= v <= 127 for v in result)


def test_all_ceiling_values_in_midi_range():
    """sample_with_ceiling always returns values in 0..127."""
    result = tcp.sample_with_ceiling(100, ceiling=127)
    assert all(0 <= v <= 127 for v in result)


def test_all_inverted_values_in_midi_range():
    """sample_inverted always returns values in 0..127."""
    result = tcp.sample_inverted(100)
    assert all(0 <= v <= 127 for v in result)


def test_all_latched_values_in_midi_range():
    """sample_latched always returns values in 0..127."""
    result = tcp.sample_latched(100)
    assert all(0 <= v <= 127 for v in result)


def test_all_bow_values_in_midi_range():
    """sample_bow always returns values in 0..127."""
    result = tcp.sample_bow(100)
    assert all(0 <= v <= 127 for v in result)


def test_all_crossfade_values_in_midi_range():
    """sample_crossfade returns values in 0..127 for both curves."""
    a, b = tcp.sample_crossfade(100)
    assert all(0 <= v <= 127 for v in a)
    assert all(0 <= v <= 127 for v in b)
