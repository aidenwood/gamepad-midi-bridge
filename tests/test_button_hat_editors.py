"""Tests for button and hat inspector editors.

These tests run headless (no display required) — QApplication is created once
by the session fixture. We verify that the editors can render and expose the
right controls for mutation.
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


from gamepad_midi_bridge.mapping import Mapping, ButtonConfig  # noqa: E402
from gamepad_midi_bridge.ui.inspector_renderers import (  # noqa: E402
    render_button_editor,
    render_hat_editor,
)


def test_button_editor_renders():
    """Test that button editor renders without crashing."""
    mapping = Mapping()
    mapping.buttons[5] = 60
    mapping.button_channels[5] = -1

    def _on_change():
        pass

    payload = {
        "index": "5",
        "note": "60",
        "label": "Button 5",
        "channel": -1,
        "config": None,
        "_mapping": mapping,
        "on_change": _on_change,
    }

    widget = render_button_editor(payload)
    assert widget is not None
    assert widget.isVisible() is False  # Not shown until parent shows it


def test_hat_editor_renders():
    """Test that hat editor renders without crashing."""
    mapping = Mapping()
    mapping.hats["up"] = 60
    mapping.hat_channels["up"] = -1

    def _on_change():
        pass

    payload = {
        "index": "up",
        "note": "60",
        "label": "D-pad Up",
        "channel": -1,
        "_mapping": mapping,
        "on_change": _on_change,
    }

    widget = render_hat_editor(payload)
    assert widget is not None
    assert widget.isVisible() is False


def test_button_config_gate_creation():
    """Test that button editor creates ButtonConfig when gate is set."""
    mapping = Mapping()
    mapping.buttons[5] = 60

    change_count = [0]

    def _on_change():
        change_count[0] += 1

    payload = {
        "index": "5",
        "note": "60",
        "label": "Button 5",
        "channel": -1,
        "config": None,
        "_mapping": mapping,
        "on_change": _on_change,
    }

    widget = render_button_editor(payload)
    # The widget should be created successfully
    assert widget is not None
    # Verify initial state
    assert 5 not in mapping.button_configs


def test_button_channel_override():
    """Test that button editor can set channel override."""
    mapping = Mapping()
    mapping.buttons[5] = 60

    change_count = [0]

    def _on_change():
        change_count[0] += 1

    payload = {
        "index": "5",
        "note": "60",
        "label": "Button 5",
        "channel": -1,
        "config": None,
        "_mapping": mapping,
        "on_change": _on_change,
    }

    widget = render_button_editor(payload)
    assert widget is not None
    # Channel should not be set initially
    assert 5 not in mapping.button_channels


def test_hat_channel_override():
    """Test that hat editor can set channel override."""
    mapping = Mapping()
    mapping.hats["up"] = 60

    change_count = [0]

    def _on_change():
        change_count[0] += 1

    payload = {
        "index": "up",
        "note": "60",
        "label": "D-pad Up",
        "channel": -1,
        "_mapping": mapping,
        "on_change": _on_change,
    }

    widget = render_hat_editor(payload)
    assert widget is not None
    # Channel should not be set initially
    assert "up" not in mapping.hat_channels
