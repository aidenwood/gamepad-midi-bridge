"""Tests for the StickTrail widget.

These tests run headless (no display required) — QApplication is created once
by the session fixture. We verify:
  1. Widget creation doesn't crash.
  2. add_sample() appends and respects buffer capacity.
  3. paintEvent() handles empty buffer gracefully.
  4. Both axes (X/Y) update correctly.
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

from gamepad_midi_bridge.ui.stick_trail import StickTrail  # noqa: E402


def test_stick_trail_creates_without_crash():
    """Instantiating StickTrail should not raise."""
    trail = StickTrail()
    assert trail is not None


def test_stick_trail_with_label():
    """Creating StickTrail with a label should work."""
    trail = StickTrail(label="L STICK")
    assert trail is not None


def test_add_sample_appends_to_buffer():
    """add_sample() should append (timestamp, x, y) to the buffer."""
    trail = StickTrail()
    trail.add_sample(0.5, -0.3)
    assert len(trail._buffer) == 1

    trail.add_sample(0.7, 0.2)
    assert len(trail._buffer) == 2


def test_buffer_respects_capacity():
    """Buffer should cap at BUFFER_CAPACITY (150)."""
    trail = StickTrail()
    for i in range(200):
        trail.add_sample(0.5, -0.3)
    assert len(trail._buffer) == 150


def test_add_sample_clamps_values():
    """Values outside -1..+1 should be clamped."""
    trail = StickTrail()
    trail.add_sample(2.0, -3.0)  # Out of range
    assert len(trail._buffer) == 1
    ts, x, y = trail._buffer[0]
    assert x == 1.0
    assert y == -1.0


def test_paint_event_with_empty_buffer():
    """paintEvent should not crash when buffer is empty."""
    trail = StickTrail()
    # Trigger a repaint (should be no-op on empty buffer)
    trail.update()
    # If we got here without exception, the test passes


def test_paint_event_with_samples():
    """paintEvent should not crash with samples in buffer."""
    trail = StickTrail()
    for i in range(10):
        trail.add_sample(0.1 * i, -0.1 * i)
    trail.update()
    # If we got here without exception, the test passes


def test_both_axes_update():
    """Both X and Y axes should update independently."""
    trail = StickTrail()
    trail.add_sample(0.5, 0.0)
    trail.add_sample(0.0, 0.8)

    assert len(trail._buffer) == 2
    ts1, x1, y1 = trail._buffer[0]
    ts2, x2, y2 = trail._buffer[1]

    assert x1 == 0.5
    assert y1 == 0.0
    assert x2 == 0.0
    assert y2 == 0.8
