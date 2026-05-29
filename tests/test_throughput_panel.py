"""Tests for the ThroughputPanel MIDI throughput dashboard widget."""
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


def test_throughput_panel_creation(qt_app) -> None:
    """ThroughputPanel creation doesn't crash."""
    from gamepad_midi_bridge.ui.throughput_panel import ThroughputPanel

    panel = ThroughputPanel()
    assert panel is not None
    assert panel.width() > 0


def test_tick_adds_entries(qt_app) -> None:
    """tick() appends entries to the ring buffer."""
    from gamepad_midi_bridge.ui.throughput_panel import ThroughputPanel

    panel = ThroughputPanel()
    assert len(panel._history) == 0

    panel.tick(10, 5)
    assert len(panel._history) == 1

    panel.tick(15, 8)
    assert len(panel._history) == 2


def test_ring_buffer_capacity(qt_app) -> None:
    """Ring buffer caps at 60 entries."""
    from gamepad_midi_bridge.ui.throughput_panel import ThroughputPanel

    panel = ThroughputPanel()

    # Add 70 entries
    for i in range(70):
        panel.tick(i, i * 2)

    # Should only have 60 (maxlen)
    assert len(panel._history) == 60


def test_peak_tracking(qt_app) -> None:
    """Peak tracking returns correct max over history."""
    from gamepad_midi_bridge.ui.throughput_panel import ThroughputPanel

    panel = ThroughputPanel()

    panel.tick(10, 5)
    assert panel._peak_out == 10
    assert panel._peak_in == 5

    panel.tick(25, 3)
    assert panel._peak_out == 25  # Updated
    assert panel._peak_in == 5    # Not updated

    panel.tick(20, 15)
    assert panel._peak_out == 25  # Still 25
    assert panel._peak_in == 15   # Updated


def test_current_values(qt_app) -> None:
    """Current values reflect the most recent tick."""
    from gamepad_midi_bridge.ui.throughput_panel import ThroughputPanel

    panel = ThroughputPanel()

    panel.tick(42, 13)
    assert panel._current_out == 42
    assert panel._current_in == 13

    panel.tick(5, 99)
    assert panel._current_out == 5
    assert panel._current_in == 99


def test_reset_clears_history(qt_app) -> None:
    """reset() clears the buffer and peak tracking."""
    from gamepad_midi_bridge.ui.throughput_panel import ThroughputPanel

    panel = ThroughputPanel()

    # Add some data
    panel.tick(50, 25)
    panel.tick(100, 200)
    assert len(panel._history) == 2
    assert panel._peak_out == 100
    assert panel._peak_in == 200

    # Reset
    panel.reset()

    assert len(panel._history) == 0
    assert panel._peak_out == 0
    assert panel._peak_in == 0
    assert panel._current_out == 0
    assert panel._current_in == 0


def test_paint_event_no_crash(qt_app) -> None:
    """paintEvent doesn't crash with empty or sparse history."""
    from gamepad_midi_bridge.ui.throughput_panel import ThroughputPanel

    panel = ThroughputPanel()
    panel.show()

    # Paint with no history
    panel.paintEvent(None)

    # Paint with 1 entry (sparse)
    panel.tick(5, 3)
    panel.paintEvent(None)

    # Paint with normal history
    for i in range(10):
        panel.tick(i * 2, i * 3)
    panel.paintEvent(None)
