"""LazyTab defers construction until the tab is first shown."""
from __future__ import annotations

import pytest


def _has_qapp() -> bool:
    try:
        from PySide6.QtWidgets import QApplication  # noqa: F401
        return True
    except ImportError:
        return False


@pytest.mark.skipif("not _has_qapp()", reason="Qt not available")
class TestLazyTab:

    def _make(self):
        from PySide6.QtWidgets import QApplication, QLabel
        from gamepad_midi_bridge.ui.lazy_tab import LazyTab
        QApplication.instance() or QApplication([])
        calls = []

        def factory():
            calls.append(1)
            return QLabel("real content")

        return LazyTab(factory), calls

    def test_factory_not_called_on_construction(self):
        """The whole point — building the tab must cost nothing up front."""
        _tab, calls = self._make()
        assert calls == []

    def test_factory_runs_on_first_show(self):
        tab, calls = self._make()
        tab.show()
        assert calls == [1]
        assert tab.is_built()

    def test_factory_runs_only_once(self):
        tab, calls = self._make()
        tab.show()
        tab.hide()
        tab.show()
        assert calls == [1]

    def test_inner_forces_the_build(self):
        """Callers can reach the content without waiting for a click."""
        tab, calls = self._make()
        inner = tab.inner()
        assert calls == [1]
        assert inner.text() == "real content"

    def test_inner_is_stable_across_calls(self):
        tab, _ = self._make()
        assert tab.inner() is tab.inner()

    def test_loaded_signal_carries_the_widget(self):
        tab, _ = self._make()
        got = []
        tab.loaded.connect(got.append)
        tab.show()
        assert len(got) == 1
        assert got[0].text() == "real content"

    def test_placeholder_is_replaced_by_content(self):
        from PySide6.QtWidgets import QLabel
        tab, _ = self._make()
        tab.show()
        labels = [w for w in tab.findChildren(QLabel)
                  if w.text() == "real content"]
        assert labels, "real content should be parented into the tab"
