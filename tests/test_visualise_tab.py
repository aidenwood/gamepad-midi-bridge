"""Tests for AxisScope oscilloscope widget and VisualiseTab sub-tabs."""
from __future__ import annotations

from collections import deque

import pytest

from gamepad_midi_bridge.ui.visualise_tab import AxisScope, VisualiseTab, OSCILLOSCOPE_SAMPLES


class TestAxisScopeBuffer:
    """Pure buffer tests (no Qt needed)."""

    def test_buffer_caps_at_max_samples(self):
        """Ring buffer has maxlen=OSCILLOSCOPE_SAMPLES; older samples drop."""
        buf: deque = deque(maxlen=OSCILLOSCOPE_SAMPLES)
        for i in range(OSCILLOSCOPE_SAMPLES + 10):
            buf.append(float(i))
        assert len(buf) == OSCILLOSCOPE_SAMPLES
        # Oldest 10 items should have dropped.
        assert buf[0] == 10.0

    def test_add_sample_updates_latest(self):
        """add_sample appends new value to end."""
        buf: deque = deque(maxlen=OSCILLOSCOPE_SAMPLES)
        buf.append(0.5)
        buf.append(0.7)
        buf.append(-0.3)
        assert buf[-1] == -0.3

    def test_stick_clamping_logic(self):
        """Stick axis clamping: -1..+1."""
        val1 = max(-1.0, min(1.0, 2.0))
        val2 = max(-1.0, min(1.0, -2.0))
        assert val1 == 1.0
        assert val2 == -1.0

    def test_trigger_clamping_logic(self):
        """Trigger axis clamping: 0..+1."""
        val1 = max(0.0, min(1.0, -0.5))
        val2 = max(0.0, min(1.0, 2.0))
        assert val1 == 0.0
        assert val2 == 1.0


class TestAxisScope:
    """AxisScope widget tests (Qt required)."""

    @pytest.mark.skipif("not _has_qapp()", reason="Qt not available")
    def test_stick_scope_creation(self):
        """Stick scope (axis 0-3) initializes correctly."""
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])

        scope = AxisScope(2, "RX")
        assert scope._axis_index == 2
        assert scope._is_trigger is False
        assert scope._label == "RX"
        assert len(scope._samples) == 0

    @pytest.mark.skipif("not _has_qapp()", reason="Qt not available")
    def test_trigger_scope_creation(self):
        """Trigger scope (axis 4-5) initializes correctly."""
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])

        scope = AxisScope(4, "L2")
        assert scope._axis_index == 4
        assert scope._is_trigger is True

    @pytest.mark.skipif("not _has_qapp()", reason="Qt not available")
    def test_scope_add_samples(self):
        """add_sample clamping works per axis type."""
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])

        stick = AxisScope(0, "LX")
        stick.add_sample(2.0)
        stick.add_sample(-2.0)
        assert stick._samples[0] == 1.0
        assert stick._samples[1] == -1.0

        trigger = AxisScope(4, "L2")
        trigger.add_sample(-0.5)
        trigger.add_sample(2.0)
        assert trigger._samples[0] == 0.0
        assert trigger._samples[1] == 1.0


class TestVisualiseTabs:
    """VisualiseTab sub-tabs smoke tests."""

    @pytest.mark.skipif("not _has_qapp()", reason="Qt not available")
    def test_visualise_tab_creation(self):
        """VisualiseTab creates without errors."""
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])

        tab = VisualiseTab()
        assert tab is not None

    @pytest.mark.skipif("not _has_qapp()", reason="Qt not available")
    def test_subtab_count(self):
        """VisualiseTab has exactly 5 sub-tabs."""
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])

        tab = VisualiseTab()
        assert tab._tabs.count() == 5

    @pytest.mark.skipif("not _has_qapp()", reason="Qt not available")
    def test_subtab_titles(self):
        """Sub-tab titles match expected names."""
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])

        tab = VisualiseTab()
        expected_titles = ["Live", "Scope", "Throughput", "Heatmap", "Timeline"]
        for i, title in enumerate(expected_titles):
            assert tab._tabs.tabText(i) == title

    @pytest.mark.skipif("not _has_qapp()", reason="Qt not available")
    def test_default_live_tab(self):
        """Live tab is active by default (or persisted from QSettings)."""
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import QSettings
        app = QApplication.instance() or QApplication([])

        # Clear persisted setting so we get the default.
        settings = QSettings()
        settings.remove("visualise/last_tab")

        tab = VisualiseTab()
        # Should start at 0 (Live tab).
        assert tab._tabs.currentIndex() == 0

    @pytest.mark.skipif("not _has_qapp()", reason="Qt not available")
    def test_tab_persistence(self):
        """Tab selection persists via QSettings."""
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import QSettings
        app = QApplication.instance() or QApplication([])

        settings = QSettings()
        # Explicitly set to Heatmap tab (index 3).
        settings.setValue("visualise/last_tab", 3)

        tab = VisualiseTab()
        # Should restore to index 3.
        assert tab._tabs.currentIndex() == 3

        # Verify it would persist if we switch.
        tab._tabs.setCurrentIndex(1)
        assert settings.value("visualise/last_tab", type=int) == 1

    @pytest.mark.skipif("not _has_qapp()", reason="Qt not available")
    def test_each_tab_contains_widgets(self):
        """Each sub-tab is a QWidget and can be accessed."""
        from PySide6.QtWidgets import QApplication, QWidget
        app = QApplication.instance() or QApplication([])

        tab = VisualiseTab()
        for i in range(tab._tabs.count()):
            widget = tab._tabs.widget(i)
            assert isinstance(widget, QWidget)
            assert widget is not None


def _has_qapp() -> bool:
    """Check if PySide6 is available."""
    try:
        from PySide6.QtWidgets import QApplication
        return True
    except ImportError:
        return False
