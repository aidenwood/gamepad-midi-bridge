"""Per-channel press lamps on the MIDI activity panel.

The panel was a scrolling text log. Confirming "my button press actually
reached MIDI" meant expanding it and reading timestamps, which is not
something you can do mid-performance. The lamps live in the header so they
work while the log is collapsed.
"""
from __future__ import annotations

import time

import pytest


def _has_qapp() -> bool:
    try:
        from PySide6.QtWidgets import QApplication  # noqa: F401
        return True
    except ImportError:
        return False


def _blinkers():
    from PySide6.QtWidgets import QApplication
    from gamepad_midi_bridge.ui.midi_log_panel import ChannelBlinkers
    QApplication.instance() or QApplication([])
    return ChannelBlinkers()


@pytest.mark.skipif("not _has_qapp()", reason="Qt not available")
class TestChannelBlinkers:

    def test_a_sent_note_lights_its_channel(self):
        b = _blinkers()
        b.blink(3, True)
        assert 3 in b._stamps

    def test_notes_and_ccs_are_distinguished(self):
        """A stick sweep would otherwise hold every lamp lit and drown out
        the button presses the lamps exist to show."""
        b = _blinkers()
        b.blink(0, True)
        b.blink(1, False)
        assert b._stamps[0][1] is True
        assert b._stamps[1][1] is False

    def test_out_of_range_channels_are_ignored(self):
        b = _blinkers()
        b.blink(-1, True)
        b.blink(16, True)
        b.blink(99, True)
        assert b._stamps == {}

    def test_lamps_decay_and_the_timer_stops(self):
        """Idle must cost nothing — the repaint timer only runs while
        something is actually fading."""
        b = _blinkers()
        b.blink(5, True)
        assert b._timer.isActive()
        b._stamps[5] = (time.perf_counter() - 10.0, True)
        b._tick()
        assert b._stamps == {}
        assert not b._timer.isActive()

    def test_clear_resets_everything(self):
        b = _blinkers()
        b.blink(2, True)
        b.clear()
        assert b._stamps == {}
        assert not b._timer.isActive()

    def test_sixteen_lamps_are_sized_for_sixteen_channels(self):
        b = _blinkers()
        expected = 16 * b.CELL_W + 15 * b.GAP
        assert b.width() == expected


@pytest.mark.skipif("not _has_qapp()", reason="Qt not available")
class TestPanelWiring:

    def _panel(self):
        from PySide6.QtWidgets import QApplication
        from gamepad_midi_bridge.ui.midi_log_panel import MidiLogPanel
        QApplication.instance() or QApplication([])
        return MidiLogPanel()

    def test_sending_a_note_lights_the_lamp(self):
        p = self._panel()
        p.append_sent(4, "NOTE-ON #60", 60, 100)
        assert 4 in p._blinkers._stamps
        assert p._blinkers._stamps[4][1] is True

    def test_sending_a_cc_lights_dim(self):
        p = self._panel()
        p.append_sent(0, "CC#7", 7, 64)
        assert p._blinkers._stamps[0][1] is False

    def test_clearing_the_log_clears_the_lamps(self):
        p = self._panel()
        p.append_sent(1, "NOTE-ON #60", 60, 100)
        p._clear_all()
        assert p._blinkers._stamps == {}
