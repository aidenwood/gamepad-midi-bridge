"""Tests for the CurveSparkline widget.

These tests run headless (no display required) — QApplication is created once
by the session fixture. We only verify that:
  1. The widget can be created without crashing.
  2. set_params() mutates internal state correctly.
  3. Sampled curve points respect endpoint constraints.
"""
from __future__ import annotations

import sys
import os
from pathlib import Path

import pytest

# Ensure src/ is importable.
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# Boot a minimal QApplication before importing any Qt widget.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

_app: QApplication | None = None


@pytest.fixture(scope="session", autouse=True)
def qt_app():
    global _app
    if QApplication.instance() is None:
        _app = QApplication(sys.argv[:1])
    yield QApplication.instance()


# ---------------------------------------------------------------------------


from gamepad_midi_bridge.ui.curve_sparkline import CurveSparkline  # noqa: E402


def test_curve_sparkline_creates_without_crash():
    """Instantiating CurveSparkline should not raise."""
    sparkline = CurveSparkline()
    assert sparkline is not None


def test_set_params_mutates_inner_deadzone():
    sparkline = CurveSparkline()
    sparkline.set_params(inner_deadzone=0.5)
    assert sparkline.inner_deadzone == pytest.approx(0.5, abs=1e-6)


def test_set_params_mutates_outer_clamp():
    sparkline = CurveSparkline()
    sparkline.set_params(outer_clamp=0.2)
    assert sparkline.outer_clamp == pytest.approx(0.2, abs=1e-6)


def test_set_params_mutates_curve():
    sparkline = CurveSparkline()
    sparkline.set_params(curve="exponential")
    assert sparkline.curve == "exponential"


def test_set_params_mutates_curve_amount():
    sparkline = CurveSparkline()
    sparkline.set_params(curve_amount=0.9)
    assert sparkline.curve_amount == pytest.approx(0.9, abs=1e-6)


def test_set_params_mutates_mode():
    sparkline = CurveSparkline()
    sparkline.set_params(mode="trigger")
    assert sparkline.mode == "trigger"


def test_set_params_multiple_at_once():
    sparkline = CurveSparkline()
    sparkline.set_params(inner_deadzone=0.1, curve="logarithmic", curve_amount=0.7)
    assert sparkline.inner_deadzone == pytest.approx(0.1, abs=1e-6)
    assert sparkline.curve == "logarithmic"
    assert sparkline.curve_amount == pytest.approx(0.7, abs=1e-6)


# ---------------------------------------------------------------------------
# Endpoint constraints — output[0] == 0, output[-1] == 1 for any valid config.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("curve", ["linear", "exponential", "logarithmic", "s-curve"])
def test_stick_mode_endpoint_zero(curve):
    """For stick mode, sampling at input=0 should produce output=0
    (assuming no outer_clamp that would shift the range)."""
    sparkline = CurveSparkline()
    sparkline.set_params(
        inner_deadzone=0.0,
        outer_clamp=0.0,
        curve=curve,
        curve_amount=0.5,
        mode="stick",
    )
    pts = sparkline._sample_curve()
    assert pts[0][1] == pytest.approx(0.0, abs=1e-3)


@pytest.mark.parametrize("curve", ["linear", "exponential", "logarithmic", "s-curve"])
def test_stick_mode_endpoint_one(curve):
    """For stick mode with no clamp, full input should produce output=1."""
    sparkline = CurveSparkline()
    sparkline.set_params(
        inner_deadzone=0.0,
        outer_clamp=0.0,
        curve=curve,
        curve_amount=0.5,
        mode="stick",
    )
    pts = sparkline._sample_curve()
    assert pts[-1][1] == pytest.approx(1.0, abs=1e-3)


@pytest.mark.parametrize("curve", ["linear", "exponential", "logarithmic", "s-curve"])
def test_trigger_mode_endpoints(curve):
    """For trigger mode, endpoints must be exactly 0 and 1."""
    sparkline = CurveSparkline()
    sparkline.set_params(curve=curve, curve_amount=0.8, mode="trigger")
    pts = sparkline._sample_curve()
    assert pts[0][1] == pytest.approx(0.0, abs=1e-3)
    assert pts[-1][1] == pytest.approx(1.0, abs=1e-3)


def test_sample_has_correct_length():
    """_sample_curve should return NUM_SAMPLES+1 points."""
    from gamepad_midi_bridge.ui.curve_sparkline import _NUM_SAMPLES
    sparkline = CurveSparkline()
    pts = sparkline._sample_curve()
    assert len(pts) == _NUM_SAMPLES + 1


def test_path_is_built_on_init():
    """The path cache should be populated after construction."""
    sparkline = CurveSparkline()
    assert sparkline._path is not None


def test_path_rebuilt_on_set_params():
    """Calling set_params with a changed value must rebuild the path."""
    sparkline = CurveSparkline()
    old_path_id = id(sparkline._path)
    sparkline.set_params(curve="exponential")
    assert id(sparkline._path) != old_path_id
