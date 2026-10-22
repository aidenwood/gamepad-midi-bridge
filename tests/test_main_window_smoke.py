"""The main window must actually build and show.

7352 tests passed while the app refused to open. Not one of them ever
constructed MainWindow, so hiding the tab strip from outside —
ResponsiveTabWidget re-asserts that visibility on every resize — took the
whole window down and the suite stayed green.

This is the cheapest possible guard against that class of regression.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _has_qapp() -> bool:
    try:
        from PySide6.QtWidgets import QApplication  # noqa: F401
        return True
    except ImportError:
        return False


@pytest.mark.skipif("not _has_qapp()", reason="Qt not available")
class TestResponsiveTabWidgetChrome:
    """The shell header owns navigation, so the tab widget's own chrome is
    hidden through its OWN switch — an external hide is undone on resize."""

    def _widget(self):
        from PySide6.QtWidgets import QApplication, QLabel
        from gamepad_midi_bridge.ui.responsive_tab_widget import ResponsiveTabWidget
        QApplication.instance() or QApplication([])
        w = ResponsiveTabWidget()
        for name in ("Live", "Mapping", "Nodes"):
            w.addTab(QLabel(name), name)
        return w

    def test_chrome_starts_visible(self):
        w = self._widget()
        assert w._chrome_hidden is False

    def test_hiding_chrome_hides_both_the_bar_and_the_combo(self):
        w = self._widget()
        w.set_chrome_visible(False)
        assert w._tabs.tabBar().isVisible() is False
        assert w._combo.isVisible() is False

    def test_a_resize_cannot_bring_the_chrome_back(self):
        """The actual regression: _apply_mode re-asserted tab-bar
        visibility on every resize, fighting the external hide."""
        w = self._widget()
        w.set_chrome_visible(False)
        w._apply_mode(400)      # cross into compact
        assert w._tabs.tabBar().isVisible() is False
        assert w._combo.isVisible() is False
        w._apply_mode(1600)     # and back out of it
        assert w._tabs.tabBar().isVisible() is False
        assert w._combo.isVisible() is False

    def test_compact_state_is_still_tracked_while_hidden(self):
        w = self._widget()
        w.set_chrome_visible(False)
        w._apply_mode(400)
        assert w._compact is True

    def test_pages_still_switch_with_the_chrome_hidden(self):
        """Hiding the strip must not disable navigation — the header
        drives setCurrentIndex now."""
        w = self._widget()
        w.set_chrome_visible(False)
        w.setCurrentIndex(2)
        assert w.currentIndex() == 2
        assert w.tabText(2) == "Nodes"

    def test_chrome_can_be_restored(self):
        w = self._widget()
        w.set_chrome_visible(False)
        w.set_chrome_visible(True)
        assert w._chrome_hidden is False


@pytest.mark.skipif("not _has_qapp()", reason="Qt not available")
class TestControllerDiagramPaints:
    """A real paint pass. The diagram crashed the app with
    `'_ControllerDiagram' object has no attribute '_haptic_stamps'` because
    an edit inserted a method into the middle of __init__, orphaning every
    assignment after it. Constructing the widget was not enough to catch
    that — only painting it touches those attributes.
    """

    def _diagram(self, family=None):
        from PySide6.QtWidgets import QApplication
        from PySide6.QtGui import QPixmap, QColor
        from gamepad_midi_bridge.ui.visualise_tab import _ControllerDiagram
        QApplication.instance() or QApplication([])
        d = _ControllerDiagram()
        if family is not None:
            d.set_family(family)
        d.resize(700, 420)
        pm = QPixmap(700, 420)
        pm.fill(QColor("#0e0f12"))
        d.render(pm)          # forces paintEvent
        return d

    def test_init_completes_fully(self):
        """Every attribute paintEvent needs must survive __init__."""
        from gamepad_midi_bridge.ui.visualise_tab import _ControllerDiagram
        from PySide6.QtWidgets import QApplication
        QApplication.instance() or QApplication([])
        d = _ControllerDiagram()
        for attr in ("_axes", "_buttons", "_hats", "_touch_contact",
                     "_touch_x", "_touch_y", "_family", "_haptic_stamps"):
            assert hasattr(d, attr), f"__init__ never set {attr}"

    def test_paints_for_every_family(self):
        from gamepad_midi_bridge import control_labels as cl
        for family in (cl.PLAYSTATION, cl.XBOX, cl.SWITCH, cl.GENERIC):
            self._diagram(family)

    def test_paints_with_live_input_applied(self):
        d = self._diagram()
        d.on_axis(0, 0.7); d.on_button(3, True); d.on_hat("up", True)
        d.on_haptic("L", "rumble", 1.0)
        from PySide6.QtGui import QPixmap, QColor
        pm = QPixmap(700, 420); pm.fill(QColor("#0e0f12"))
        d.render(pm)

    def test_minimum_size_is_not_lost(self):
        """Also orphaned by the same edit — the floor exists so the tab
        never forces a horizontal scrollbar on narrow windows."""
        d = self._diagram()
        assert d.minimumSize().width() == 220
        assert d.minimumSize().height() == 160
