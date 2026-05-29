"""Tests for trigger crossfade preview generator.

Pure-function curve preview and metadata for the dual-CC crossfade UI.
Tests cover curve labeling, pair computation, sampling, crossover detection,
and serialization.
"""
from __future__ import annotations

import pytest

from gamepad_midi_bridge import trigger_crossfade_preview as tcp


# ─────────────────────────────────────────────────────────────────────
# curve_label_for
# ─────────────────────────────────────────────────────────────────────


def test_curve_label_linear_at_1_0():
    """curve_label_for(1.0) == 'linear'."""
    assert tcp.curve_label_for(1.0) == "linear"


def test_curve_label_linear_in_range():
    """curve_label_for(0.99) and (1.01) return 'linear'."""
    assert tcp.curve_label_for(0.99) == "linear"
    assert tcp.curve_label_for(1.01) == "linear"


def test_curve_label_ease_in_below_0_95():
    """curve_label_for(0.5) == 'ease_in'."""
    assert tcp.curve_label_for(0.5) == "ease_in"


def test_curve_label_ease_out_above_1_05():
    """curve_label_for(2.0) == 'ease_out'."""
    assert tcp.curve_label_for(2.0) == "ease_out"


# ─────────────────────────────────────────────────────────────────────
# compute_pair
# ─────────────────────────────────────────────────────────────────────


def test_compute_pair_at_zero_pressure():
    """compute_pair(0, 1) == (0, 127)."""
    a, b = tcp.compute_pair(0.0, 1.0)
    assert a == 0
    assert b == 127


def test_compute_pair_at_full_pressure():
    """compute_pair(1, 1) == (127, 0)."""
    a, b = tcp.compute_pair(1.0, 1.0)
    assert a == 127
    assert b == 0


def test_compute_pair_at_half_pressure_linear():
    """compute_pair(0.5, 1.0) returns (~63 or ~64, ~63) for linear."""
    a, b = tcp.compute_pair(0.5, 1.0)
    assert a + b == 127
    assert 63 <= a <= 64


def test_compute_pair_clamps_pressure():
    """compute_pair clamps pressure to [0, 1]."""
    a1, b1 = tcp.compute_pair(-0.5, 1.0)
    a2, b2 = tcp.compute_pair(0.0, 1.0)
    assert (a1, b1) == (a2, b2)

    a3, b3 = tcp.compute_pair(1.5, 1.0)
    a4, b4 = tcp.compute_pair(1.0, 1.0)
    assert (a3, b3) == (a4, b4)


def test_compute_pair_clamps_curve():
    """compute_pair clamps curve to [0.1, 4.0]."""
    a1, b1 = tcp.compute_pair(0.5, 0.05)
    a2, b2 = tcp.compute_pair(0.5, 0.1)
    assert (a1, b1) == (a2, b2)

    a3, b3 = tcp.compute_pair(0.5, 5.0)
    a4, b4 = tcp.compute_pair(0.5, 4.0)
    assert (a3, b3) == (a4, b4)


def test_compute_pair_sum_is_127():
    """compute_pair always returns a + b == 127."""
    for pressure in [0.0, 0.25, 0.5, 0.75, 1.0]:
        for curve in [0.5, 1.0, 2.0]:
            a, b = tcp.compute_pair(pressure, curve)
            assert a + b == 127


# ─────────────────────────────────────────────────────────────────────
# sample_pair
# ─────────────────────────────────────────────────────────────────────


def test_sample_pair_returns_two_lists():
    """sample_pair returns a tuple of two lists."""
    a_curve, b_curve = tcp.sample_pair(32, 1.0)
    assert isinstance(a_curve, list)
    assert isinstance(b_curve, list)


def test_sample_pair_equal_lengths():
    """sample_pair returns two equal-length arrays."""
    a_curve, b_curve = tcp.sample_pair(32, 1.0)
    assert len(a_curve) == len(b_curve)
    assert len(a_curve) == 32


def test_sample_pair_clamps_samples_min():
    """sample_pair(1) returns 2 samples (minimum)."""
    a_curve, b_curve = tcp.sample_pair(1, 1.0)
    assert len(a_curve) == 2


def test_sample_pair_clamps_samples_max():
    """sample_pair(1000) returns 256 samples (maximum)."""
    a_curve, b_curve = tcp.sample_pair(1000, 1.0)
    assert len(a_curve) == 256


def test_sample_pair_sums_to_127():
    """sample_pair a[i] + b[i] == 127 at each index."""
    a_curve, b_curve = tcp.sample_pair(10, 1.0)
    for a, b in zip(a_curve, b_curve):
        assert a + b == 127


def test_sample_pair_a_is_monotonic_increasing():
    """sample_pair a_curve is monotonically increasing."""
    a_curve, _ = tcp.sample_pair(32, 1.0)
    for i in range(len(a_curve) - 1):
        assert a_curve[i] <= a_curve[i + 1]


def test_sample_pair_b_is_monotonic_decreasing():
    """sample_pair b_curve is monotonically decreasing."""
    _, b_curve = tcp.sample_pair(32, 1.0)
    for i in range(len(b_curve) - 1):
        assert b_curve[i] >= b_curve[i + 1]


# ─────────────────────────────────────────────────────────────────────
# build_preview
# ─────────────────────────────────────────────────────────────────────


def test_build_preview_returns_dataclass():
    """build_preview returns a CrossfadePreview."""
    preview = tcp.build_preview(32, 1.0)
    assert isinstance(preview, tcp.CrossfadePreview)


def test_build_preview_has_correct_curve_label():
    """build_preview assigns the correct curve_label."""
    linear = tcp.build_preview(32, 1.0)
    assert linear.curve_label == "linear"

    ease_in = tcp.build_preview(32, 0.5)
    assert ease_in.curve_label == "ease_in"

    ease_out = tcp.build_preview(32, 2.0)
    assert ease_out.curve_label == "ease_out"


def test_build_preview_samples_match_input():
    """build_preview.samples matches the input samples count (after clamping)."""
    preview = tcp.build_preview(32, 1.0)
    assert preview.samples == 32


def test_build_preview_curves_have_correct_length():
    """build_preview.a_curve and b_curve have the correct length."""
    preview = tcp.build_preview(16, 1.0)
    assert len(preview.a_curve) == 16
    assert len(preview.b_curve) == 16


def test_build_preview_midpoints():
    """build_preview.midpoint_a + midpoint_b == 127."""
    preview = tcp.build_preview(32, 1.0)
    assert preview.midpoint_a + preview.midpoint_b == 127
    assert 63 <= preview.midpoint_a <= 64


# ─────────────────────────────────────────────────────────────────────
# crossover_point
# ─────────────────────────────────────────────────────────────────────


def test_crossover_point_linear_near_half():
    """crossover_point(curve=1.0) returns ~0.5."""
    crossover = tcp.crossover_point(1.0, 256)
    assert 0.48 < crossover < 0.52


def test_crossover_point_ease_in_below_half():
    """crossover_point(curve=0.5) returns < 0.5 (ease_in crossover earlier)."""
    crossover = tcp.crossover_point(0.5, 256)
    assert crossover < 0.5


def test_crossover_point_ease_out_above_half():
    """crossover_point(curve=2.0) returns > 0.5 (ease_out crossover later)."""
    crossover = tcp.crossover_point(2.0, 256)
    assert crossover > 0.5


# ─────────────────────────────────────────────────────────────────────
# compare_curves
# ─────────────────────────────────────────────────────────────────────


def test_compare_curves_returns_list():
    """compare_curves returns a list of CrossfadePreview."""
    curves = [0.5, 1.0, 2.0]
    result = tcp.compare_curves(curves, 32)
    assert isinstance(result, list)
    assert len(result) == 3


def test_compare_curves_matching_count():
    """compare_curves returns one preview per input curve."""
    curves = [0.5, 1.0, 1.5, 2.0]
    result = tcp.compare_curves(curves, 32)
    assert len(result) == len(curves)


def test_compare_curves_order_preserved():
    """compare_curves preserves the order of input curves."""
    curves = [0.5, 1.0, 2.0]
    result = tcp.compare_curves(curves, 32)
    for i, preview in enumerate(result):
        assert preview.curve == curves[i]


# ─────────────────────────────────────────────────────────────────────
# Serialization
# ─────────────────────────────────────────────────────────────────────


def test_crossfade_preview_to_dict():
    """CrossfadePreview.to_dict() returns a plain dict."""
    preview = tcp.build_preview(5, 1.0)
    d = preview.to_dict()
    assert isinstance(d, dict)
    assert "samples" in d
    assert "curve" in d
    assert "curve_label" in d
    assert "a_curve" in d
    assert "b_curve" in d
    assert "midpoint_a" in d
    assert "midpoint_b" in d


def test_crossfade_preview_roundtrip_serialization():
    """CrossfadePreview round-trips through to_dict / from_dict."""
    preview1 = tcp.build_preview(8, 1.5)
    d = preview1.to_dict()
    preview2 = tcp.CrossfadePreview.from_dict(d)

    assert preview2.samples == preview1.samples
    assert preview2.curve == preview1.curve
    assert preview2.curve_label == preview1.curve_label
    assert preview2.a_curve == preview1.a_curve
    assert preview2.b_curve == preview1.b_curve
    assert preview2.midpoint_a == preview1.midpoint_a
    assert preview2.midpoint_b == preview1.midpoint_b
