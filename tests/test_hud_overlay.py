"""Tests for HudOverlay widget."""
from __future__ import annotations

import pytest


def _has_qt() -> bool:
    try:
        from PySide6.QtWidgets import QApplication  # noqa: F401
        return True
    except ImportError:
        return False


class TestHudOverlayModule:
    """Import-level tests — no QApplication needed."""

    def test_module_imports(self):
        """hud_overlay module imports without error."""
        from gamepad_midi_bridge.ui import hud_overlay  # noqa: F401
        assert hasattr(hud_overlay, "HudOverlay")

    def test_class_exists(self):
        """HudOverlay class is exported at module level."""
        from gamepad_midi_bridge.ui.hud_overlay import HudOverlay
        assert HudOverlay is not None


@pytest.mark.skipif(not _has_qt(), reason="Qt not available")
class TestHudOverlayWidget:
    """Widget-level tests (require a QApplication)."""

    @pytest.fixture(autouse=True)
    def _app(self):
        from PySide6.QtWidgets import QApplication
        self.app = QApplication.instance() or QApplication([])

    # ------------------------------------------------------------------ creation

    def test_creation_does_not_crash(self):
        """HudOverlay instantiates without error."""
        from gamepad_midi_bridge.ui.hud_overlay import HudOverlay
        hud = HudOverlay()
        assert hud is not None
        hud.deleteLater()

    def test_fixed_size(self):
        """Widget reports 240×70 fixed size."""
        from gamepad_midi_bridge.ui.hud_overlay import HudOverlay
        hud = HudOverlay()
        assert hud.width() == 240
        assert hud.height() == 70
        hud.deleteLater()

    def test_window_flags_include_tool(self):
        """Qt.Tool flag is set so the overlay is hidden from the taskbar."""
        from PySide6.QtCore import Qt
        from gamepad_midi_bridge.ui.hud_overlay import HudOverlay
        hud = HudOverlay()
        assert bool(hud.windowFlags() & Qt.Tool)
        hud.deleteLater()

    def test_window_flags_include_stays_on_top(self):
        """Qt.WindowStaysOnTopHint is set."""
        from PySide6.QtCore import Qt
        from gamepad_midi_bridge.ui.hud_overlay import HudOverlay
        hud = HudOverlay()
        assert bool(hud.windowFlags() & Qt.WindowStaysOnTopHint)
        hud.deleteLater()

    def test_window_flags_frameless(self):
        """Qt.FramelessWindowHint is set."""
        from PySide6.QtCore import Qt
        from gamepad_midi_bridge.ui.hud_overlay import HudOverlay
        hud = HudOverlay()
        assert bool(hud.windowFlags() & Qt.FramelessWindowHint)
        hud.deleteLater()

    # ------------------------------------------------------------------ state API

    def test_set_preset_updates_label(self):
        """set_preset changes the internal name and label text."""
        from gamepad_midi_bridge.ui.hud_overlay import HudOverlay
        hud = HudOverlay()
        hud.set_preset("Kick Drum")
        assert hud._preset_name == "Kick Drum"
        assert hud._preset_label.text() == "Kick Drum"
        hud.deleteLater()

    def test_set_preset_empty_string_shows_dash(self):
        """Empty preset name falls back to '—'."""
        from gamepad_midi_bridge.ui.hud_overlay import HudOverlay
        hud = HudOverlay()
        hud.set_preset("")
        assert hud._preset_name == "—"
        hud.deleteLater()

    def test_set_throughput_updates_label(self):
        """set_throughput stores rates and refreshes the throughput label."""
        from gamepad_midi_bridge.ui.hud_overlay import HudOverlay
        hud = HudOverlay()
        hud.set_throughput(142, 0)
        assert hud._out_rate == 142
        assert hud._in_rate == 0
        assert "142" in hud._throughput_label.text()
        hud.deleteLater()

    def test_set_throughput_in_rate(self):
        """Incoming rate appears in the label."""
        from gamepad_midi_bridge.ui.hud_overlay import HudOverlay
        hud = HudOverlay()
        hud.set_throughput(10, 5)
        assert hud._in_rate == 5
        assert "5" in hud._throughput_label.text()
        hud.deleteLater()

    def test_set_status_running_true(self):
        """set_status(True) sets _running and updates the dot colour."""
        from gamepad_midi_bridge.ui.hud_overlay import HudOverlay
        hud = HudOverlay()
        hud.set_status(True)
        assert hud._running is True
        # Colour should contain the teal accent.
        assert "2dd4bf" in hud._status_dot.styleSheet()
        hud.deleteLater()

    def test_set_status_running_false(self):
        """set_status(False) marks stopped and dims the dot."""
        from gamepad_midi_bridge.ui.hud_overlay import HudOverlay
        hud = HudOverlay()
        hud.set_status(True)
        hud.set_status(False)
        assert hud._running is False
        assert "2c313b" in hud._status_dot.styleSheet()
        hud.deleteLater()

    # ------------------------------------------------------------------ QSettings round-trip

    def test_position_roundtrip(self, tmp_path, monkeypatch):
        """Widget position survives a save/restore cycle via QSettings."""
        from PySide6.QtCore import QSettings, QPoint
        from gamepad_midi_bridge.ui import hud_overlay as hud_mod

        # Redirect QSettings to an isolated ini file so we don't pollute the
        # real user settings during tests.
        ini_path = str(tmp_path / "hud_test.ini")
        monkeypatch.setattr(
            "gamepad_midi_bridge.ui.hud_overlay._SETTINGS_ORG",
            "TestOrg",
        )
        monkeypatch.setattr(
            "gamepad_midi_bridge.ui.hud_overlay._SETTINGS_APP",
            "TestApp",
        )
        from gamepad_midi_bridge.ui.hud_overlay import HudOverlay

        hud = HudOverlay()
        hud.move(123, 456)
        hud._save_position()

        hud2 = HudOverlay()
        # Position restored from QSettings (same org/app within this process).
        assert hud2.x() == 123
        assert hud2.y() == 456
        hud.deleteLater()
        hud2.deleteLater()

    def test_write_read_visible(self, monkeypatch):
        """write_visible / read_visible round-trip returns the stored value."""
        monkeypatch.setattr(
            "gamepad_midi_bridge.ui.hud_overlay._SETTINGS_ORG",
            "TestOrg2",
        )
        monkeypatch.setattr(
            "gamepad_midi_bridge.ui.hud_overlay._SETTINGS_APP",
            "TestApp2",
        )
        from gamepad_midi_bridge.ui.hud_overlay import HudOverlay
        HudOverlay.write_visible(True)
        assert HudOverlay.read_visible() is True
        HudOverlay.write_visible(False)
        assert HudOverlay.read_visible() is False
