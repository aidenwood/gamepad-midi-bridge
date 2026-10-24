"""The bottom dock hugs its content until the user drags it.

Before this, MIDI activity + Console reserved a fixed 200 px (400 px once
stacked on a narrow window) whether or not either had anything in it. On a
phone-shaped window that was half the screen given over to two empty black
rectangles.

Now the dock asks for exactly what its panels contain — two headers when
they are empty, more as messages land — and stops asking the moment the
user drags the splitter to a height of their own.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("GMB_DEMO", "1")
os.environ.setdefault("GMB_UI_SMOKE", "1")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app, monkeypatch):
    from PySide6.QtWidgets import QDialog, QMessageBox
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k: QMessageBox.No))
    monkeypatch.setattr(QDialog, "exec", lambda self, *a, **k: 0)
    from gamepad_midi_bridge.ui.main_window import MainWindow
    win = MainWindow()
    win.show()
    yield win
    win.close()


def _settle(app, passes: int = 8) -> None:
    for _ in range(passes):
        app.processEvents()


# --------------------------------------------------------------- the panels

def test_empty_panel_asks_for_its_header_only(app):
    from gamepad_midi_bridge.ui.log_console import LogConsole
    from gamepad_midi_bridge.ui.midi_log_panel import MidiLogPanel
    for panel in (MidiLogPanel(), LogConsole()):
        panel.set_collapsed(False)
        _settle(app)
        assert panel.content_height() == panel.header_height(), (
            f"{type(panel).__name__} reserves space for content it has none of")


def test_empty_panel_hides_its_body(app):
    """An empty body laid out at a tight height paints over the header.

    ``isHidden()``, not ``isVisible()`` — these panels are built standalone
    here, and every child of an unshown widget reports isVisible() False,
    which would make the assertion pass without testing anything.
    """
    from gamepad_midi_bridge.ui.log_console import LogConsole
    from gamepad_midi_bridge.ui.midi_log_panel import MidiLogPanel
    for panel in (MidiLogPanel(), LogConsole()):
        panel.set_collapsed(False)
        _settle(app)
        assert panel._body.isHidden()


def test_panel_grows_with_its_content(app):
    from gamepad_midi_bridge.ui.midi_log_panel import MidiLogPanel
    panel = MidiLogPanel()
    panel.set_collapsed(False)
    _settle(app)
    empty = panel.content_height()
    for note in range(60, 66):
        panel.append_sent(0, "NOTE-ON", note, 100)
    _settle(app)
    assert panel.content_height() > empty
    assert not panel._body.isHidden()


def test_clearing_shrinks_the_panel_back(app):
    from gamepad_midi_bridge.ui.midi_log_panel import MidiLogPanel
    panel = MidiLogPanel()
    panel.set_collapsed(False)
    _settle(app)
    for note in range(60, 66):
        panel.append_sent(0, "NOTE-ON", note, 100)
    _settle(app)
    panel._clear_all()
    _settle(app)
    assert panel.content_height() == panel.header_height()
    assert panel._body.isHidden()


def test_panel_can_always_shrink_to_its_header(app):
    """A QListWidget's own ~120px floor would beat the dock's request."""
    from gamepad_midi_bridge.ui.log_console import LogConsole
    from gamepad_midi_bridge.ui.midi_log_panel import MidiLogPanel
    for panel in (MidiLogPanel(), LogConsole()):
        panel.set_collapsed(False)
        _settle(app)
        assert panel.minimumSizeHint().height() <= panel.header_height()


# ----------------------------------------------------------------- the dock

def test_dock_hugs_two_empty_headers(app, window):
    window.resize(380, 820)
    _settle(app)
    window._log_console.set_collapsed(False)
    window._midi_log_panel.set_collapsed(False)
    _settle(app)
    wanted = window._bottom_wanted_height()
    both_headers = (window._log_console.header_height()
                    + window._midi_log_panel.header_height())
    # Headers plus the splitter handle and a few px of breathing room —
    # nowhere near the old flat 400.
    assert wanted < both_headers + 24, (
        f"empty dock wants {wanted}px for {both_headers}px of headers")


def test_dock_grows_when_midi_arrives(app, window):
    window.resize(380, 820)
    _settle(app)
    window._midi_log_panel.set_collapsed(False)
    _settle(app)
    before = window._bottom_wanted_height()
    for note in range(60, 70):
        window._midi_log_panel.append_sent(0, "NOTE-ON", note, 100)
    _settle(app)
    assert window._bottom_wanted_height() > before


def test_dock_never_exceeds_half_the_window(app, window):
    window.resize(380, 820)
    _settle(app)
    window._midi_log_panel.set_collapsed(False)
    for note in range(200):
        window._midi_log_panel.append_sent(0, "NOTE-ON", 60 + note % 12, 100)
    _settle(app)
    window._apply_bottom_panel_sizes()
    _settle(app)
    assert window._body_splitter.sizes()[1] <= window._bottom_height_limit()


def test_a_manual_drag_wins_over_autosize(app, window):
    """Auto-sizing that silently undoes a deliberate drag is infuriating."""
    window.resize(900, 820)
    _settle(app)
    window._midi_log_panel.set_collapsed(False)
    _settle(app)
    # Simulate the user dragging the handle to a tall dock.
    total = sum(window._body_splitter.sizes())
    window._body_splitter.setSizes([total - 300, 300])
    window._on_body_splitter_moved(0, 1)
    _settle(app)
    assert window._bottom_user_height is not None
    pinned = window._bottom_wanted_height()
    # Content arriving must not move it.
    for note in range(30):
        window._midi_log_panel.append_sent(0, "NOTE-ON", 60 + note % 12, 100)
    _settle(app)
    assert window._bottom_wanted_height() == pinned


def test_dragging_down_to_the_headers_hands_sizing_back_to_auto(app, window):
    window.resize(900, 820)
    _settle(app)
    total = sum(window._body_splitter.sizes())
    window._body_splitter.setSizes([total - 300, 300])
    window._on_body_splitter_moved(0, 1)
    _settle(app)
    assert window._bottom_user_height is not None
    header = max(window._log_console.header_height(),
                 window._midi_log_panel.header_height())
    window._body_splitter.setSizes([total - header, header])
    window._on_body_splitter_moved(0, 1)
    _settle(app)
    assert window._bottom_user_height is None


# ----------------------------------------------------- wrapped-row surfaces

def test_wrapped_header_row_is_transparent(app, window):
    """Row 2 is the same bar continued, not a black strip bolted under it."""
    window.resize(380, 820)
    _settle(app)
    assert window._status_row2_widget.isVisible()
    assert "transparent" in window._status_row2_widget.styleSheet()


def test_wrapped_banner_row_is_transparent(app, window):
    window.resize(380, 820)
    _settle(app)
    assert "transparent" in window._banner_row2_widget.styleSheet()
