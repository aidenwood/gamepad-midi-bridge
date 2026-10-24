"""Responsive-layout regression tests.

The app is used on a second monitor, parked beside a DAW, and sometimes
squeezed into a phone-shaped strip. Before these tests the header laid out
once at build time and pinned every button's ``minimumWidth`` to its
FULL-LABEL ``sizeHint()`` — so compact mode changed the text but not the
width, and from ~740 px down the right-hand actions ran straight off the
edge of the window. ``CONNECT`` sat on top of ``OUTPUT`` and ``⬆ Update``
was half off-screen.

What is asserted here:
  * every header control stays inside the window at every width
  * no control is wider than the window it lives in
  * the window can genuinely be driven to its advertised 380 px floor
  * the richer presentations come back when the window is widened again
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("GMB_DEMO", "1")
os.environ.setdefault("GMB_UI_SMOKE", "1")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

# Widths worth pinning. 380 is the advertised floor, 735 is the width that
# produced the original overlap bug report, 1280 is a normal window.
WIDTHS = (380, 420, 520, 620, 735, 900, 1100, 1280)


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
    # Qt only delivers resizeEvent to a window that is actually mapped, and
    # the reflow hangs off resizeEvent. An unshown window would sit in its
    # build-time tier forever and every assertion below would be vacuous.
    win.show()
    yield win
    win.close()


def _settle(app, passes: int = 6) -> None:
    for _ in range(passes):
        app.processEvents()


def _header_controls(win):
    return [
        win._menu_btn, win._mode_live_btn, win._mode_setup_btn,
        win._nodeview_btn, win._connect_btn, win._output_btn,
        win._shell_status_btn,
    ]


@pytest.mark.parametrize("width", WIDTHS)
def test_header_controls_stay_inside_the_window(app, window, width):
    """No header button may extend past the right edge at any width."""
    window.resize(width, 760)
    _settle(app)
    overflow = []
    for btn in _header_controls(window):
        if not btn.isVisible():
            continue
        right = btn.mapTo(window, btn.rect().topRight()).x()
        if right > width:
            overflow.append((btn.accessibleName() or btn.text(), right))
    assert not overflow, f"at {width}px these ran off the edge: {overflow}"


@pytest.mark.parametrize("width", WIDTHS)
def test_header_controls_do_not_overlap(app, window, width):
    """Two buttons on the same row may not sit on top of each other.

    This is the exact symptom in the bug report: CONNECT painted over
    OUTPUT because the row demanded more width than it had.
    """
    window.resize(width, 760)
    _settle(app)
    rects = []
    for btn in _header_controls(window):
        if not btn.isVisible():
            continue
        top_left = btn.mapTo(window, btn.rect().topLeft())
        rects.append((btn.accessibleName() or btn.text(),
                      top_left.x(), top_left.y(),
                      btn.width(), btn.height()))
    for i, (name_a, ax, ay, aw, ah) in enumerate(rects):
        for name_b, bx, by, bw, bh in rects[i + 1:]:
            same_row = abs(ay - by) < max(ah, bh) / 2
            overlaps_x = ax < bx + bw and bx < ax + aw
            assert not (same_row and overlaps_x), (
                f"at {width}px {name_a!r} overlaps {name_b!r}")


@pytest.mark.parametrize("width", WIDTHS)
def test_no_widget_is_wider_than_the_window(app, window, width):
    """A child wider than its window is a child that cannot be reached."""
    window.resize(width, 760)
    _settle(app)
    too_wide = [
        (w.objectName() or type(w).__name__, w.width())
        for w in window.findChildren(type(window._menu_btn).__bases__[0])
        if w.isVisible() and w.width() > width
    ]
    assert not too_wide, f"at {width}px these are wider than the window: {too_wide}"


def test_window_reaches_its_advertised_minimum(app, window):
    """setMinimumSize(380, 280) has to be true, not aspirational.

    A single child with a 572 px floor (the MIDI header, before it learned
    to compact) silently raises the whole window's minimum and the user
    simply cannot drag it narrower.
    """
    window.resize(380, 400)
    _settle(app)
    assert window.minimumSizeHint().width() <= 380, (
        f"something inside pins the window to "
        f"{window.minimumSizeHint().width()}px wide")


def test_bottom_dock_stacks_when_narrow_and_unstacks_when_wide(app, window):
    """MIDI activity + Console sit side by side only when that fits."""
    from PySide6.QtCore import Qt
    window.resize(400, 760)
    _settle(app)
    assert window._bottom_splitter.orientation() == Qt.Vertical
    window.resize(1280, 760)
    _settle(app)
    assert window._bottom_splitter.orientation() == Qt.Horizontal


def test_header_tier_recovers_when_the_window_is_widened(app, window):
    """Narrowing must not be a one-way door — the labels come back."""
    window.resize(1280, 760)
    _settle(app)
    assert window._header_tier == "wide"
    assert window._connect_btn.text() == "CONNECT"
    window.resize(400, 760)
    _settle(app)
    assert window._header_tier in ("narrow", "micro")
    window.resize(1280, 760)
    _settle(app)
    assert window._header_tier == "wide"
    assert window._connect_btn.text() in ("CONNECT", "CONNECTED")


def test_status_text_keeps_its_full_value_when_elided(app, window):
    """The STATUS dropdown reads these labels back — it must not get "…"."""
    window.resize(380, 760)
    _settle(app)
    window._status_sub.setText("Plug in a controller, then open Connect.")
    _settle(app)
    assert window._status_sub.text() == "Plug in a controller, then open Connect."


def test_split_view_is_disabled_only_while_the_window_is_narrow(app, window):
    window.resize(400, 760)
    _settle(app)
    assert not window._split_btn.isEnabled()
    window.resize(1280, 760)
    _settle(app)
    assert window._split_btn.isEnabled()
