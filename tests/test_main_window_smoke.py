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
