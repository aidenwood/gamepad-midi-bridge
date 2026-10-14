"""Console severity signalling + the status-bar attention pulse.

Why this exists: a Windows user hit several bugs and sent a screen recording
instead of the log, because nothing on screen indicated the console had
anything worth reading. The console button now tints green / amber / red and
pulses when an unseen message lands.
"""
from __future__ import annotations

import pytest

from gamepad_midi_bridge.ui.log_console import (
    SEVERITY_RANK, TAG_SEVERITY, LogConsole,
)


def _has_qapp() -> bool:
    try:
        from PySide6.QtWidgets import QApplication  # noqa: F401
        return True
    except ImportError:
        return False


class TestSeverityMapping:
    """Pure lookup tables — no Qt needed."""

    def test_every_level_tag_has_a_severity(self):
        from gamepad_midi_bridge.ui.log_console import LEVEL_TAG
        for tag in LEVEL_TAG.values():
            assert tag in TAG_SEVERITY, f"tag {tag!r} has no severity bucket"

    def test_severity_rank_orders_error_highest(self):
        assert SEVERITY_RANK["error"] > SEVERITY_RANK["warning"]
        assert SEVERITY_RANK["warning"] > SEVERITY_RANK["info"]


@pytest.mark.skipif("not _has_qapp()", reason="Qt not available")
class TestUnseenSeverity:
    """High-water mark of unread severity while the console is collapsed."""

    def _console(self):
        from PySide6.QtWidgets import QApplication
        QApplication.instance() or QApplication([])
        c = LogConsole()
        c.set_collapsed_silent(True)
        c.clear_unseen()
        return c

    def test_starts_with_nothing_unseen(self):
        assert self._console().highest_unseen_severity() is None

    def test_tracks_worst_severity(self):
        c = self._console()
        c._append_line(" ", "info line")
        assert c.highest_unseen_severity() == "info"
        c._append_line("!", "warning line")
        assert c.highest_unseen_severity() == "warning"
        c._append_line("✕", "error line")
        assert c.highest_unseen_severity() == "error"

    def test_lower_severity_does_not_downgrade(self):
        """A chatty INFO stream must not bury a prior error."""
        c = self._console()
        c._append_line("✕", "the important one")
        for _ in range(20):
            c._append_line(" ", "noise")
        assert c.highest_unseen_severity() == "error"

    def test_opening_the_console_clears_it(self):
        c = self._console()
        c._append_line("✕", "error line")
        c.set_collapsed(False)
        assert c.highest_unseen_severity() is None

    def test_nothing_tracked_while_open(self):
        """If the panel is open the user can already see the line."""
        c = self._console()
        c.set_collapsed_silent(False)
        c.clear_unseen()
        c._append_line("✕", "error line")
        assert c.highest_unseen_severity() is None

    def test_activity_signal_carries_severity(self):
        c = self._console()
        seen = []
        c.activity.connect(seen.append)
        c._append_line("!", "warning line")
        c._append_line("✕", "error line")
        assert seen == ["warning", "error"]


@pytest.mark.skipif("not _has_qapp()", reason="Qt not available")
class TestConsoleAttentionColours:
    """MainWindow's tinting logic, exercised without booting the whole window."""

    def _stub(self):
        from PySide6.QtCore import QObject
        from PySide6.QtWidgets import QApplication, QPushButton
        from gamepad_midi_bridge.ui.main_window import MainWindow

        QApplication.instance() or QApplication([])
        console = LogConsole()
        console.set_collapsed_silent(True)
        console.clear_unseen()

        class Stub(QObject):
            _CONSOLE_SEVERITY_COLOURS = MainWindow._CONSOLE_SEVERITY_COLOURS
            _CONSOLE_PULSE_FLASHES = MainWindow._CONSOLE_PULSE_FLASHES
            _CONSOLE_PULSE_MS = MainWindow._CONSOLE_PULSE_MS
            _on_console_activity = MainWindow._on_console_activity
            _start_console_pulse = MainWindow._start_console_pulse
            _tick_console_pulse = MainWindow._tick_console_pulse
            _clear_console_attention = MainWindow._clear_console_attention

            def __init__(self):
                super().__init__()
                self._console_btn = QPushButton("Console")
                self._console_btn.setObjectName("LayoutToggle")
                self._log_console = console

        s = Stub()
        console.activity.connect(s._on_console_activity)
        return s, console

    @pytest.mark.parametrize("tag,colour", [
        (" ", "#2dd4bf"),   # info    -> green/teal
        ("!", "#f0b429"),   # warning -> amber
        ("✕", "#ef4444"),   # error   -> red
    ])
    def test_tint_per_severity(self, tag, colour):
        s, console = self._stub()
        console._append_line(tag, "a line")
        assert colour in s._console_btn.styleSheet()

    def test_error_tint_survives_later_info_lines(self):
        s, console = self._stub()
        console._append_line("✕", "the important one")
        console._append_line(" ", "noise")
        assert "#ef4444" in s._console_btn.styleSheet()

    def test_clearing_removes_the_tint(self):
        s, console = self._stub()
        console._append_line("✕", "error")
        s._clear_console_attention()
        assert s._console_btn.styleSheet() == ""
        assert console.highest_unseen_severity() is None

    def test_no_tint_while_console_is_open(self):
        s, console = self._stub()
        console.set_collapsed_silent(False)
        console._append_line("✕", "error")
        assert s._console_btn.styleSheet() == ""
