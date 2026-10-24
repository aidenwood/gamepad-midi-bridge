"""The transport gap in sdl_profiles must stay visible, not become folklore.

``sdl_profiles`` keys its Microsoft layouts on PID alone, while SDL's own
database carries separate mappings for the same PID over USB and over
Bluetooth. That is a known, deliberate gap — but it is only safe while it
is *visible*, so these tests pin the two things that make it visible:

  * every shipped Microsoft profile was sourced from a USB GUID, so nothing
    in the table may silently claim Bluetooth provenance
  * the STATUS dropdown reports the decoded transport and the resolved axis
    map, so a mis-resolved profile is diagnosable from inside the app

The profile named ``XBOX_BT_0B20`` until 2026-10-24 asserted Bluetooth while
citing a GUID whose bus field is 0x0003 (USB). This is the test that would
have caught that.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("GMB_DEMO", "1")
os.environ.setdefault("GMB_UI_SMOKE", "1")

from gamepad_midi_bridge.control_labels import (
    BUS_BLUETOOTH,
    BUS_USB,
    bus_from_guid,
    vid_pid_from_guid,
)

# The GUID quoted in the XBOX_0B20 docstring as the source of that layout.
SDL_0B20_ENTRY = "030000005e040000200b000011050000"


def test_the_0b20_source_guid_is_usb_not_bluetooth():
    """The evidence behind XBOX_0B20 is a USB entry. Name it accurately."""
    assert bus_from_guid(SDL_0B20_ENTRY) == BUS_USB
    assert vid_pid_from_guid(SDL_0B20_ENTRY) == (0x045E, 0x0B20)


def test_profile_constant_does_not_claim_an_unverified_transport():
    from gamepad_midi_bridge import sdl_profiles
    assert not hasattr(sdl_profiles, "XBOX_BT_0B20"), (
        "XBOX_BT_0B20 claimed a Bluetooth provenance its own source GUID "
        "contradicts — it is XBOX_0B20 now")
    assert hasattr(sdl_profiles, "XBOX_0B20")


def test_bus_decoding_round_trips():
    """Guard the little-endian parse the whole disclosure rests on."""
    assert bus_from_guid("050000005e040000200b000013050000") == BUS_BLUETOOTH
    assert bus_from_guid("030000004c050000e60c000000006800") == BUS_USB
    assert bus_from_guid("") == 0
    assert bus_from_guid(None) == 0


def test_same_pid_resolves_identically_on_either_bus():
    """Documents today's behaviour so a future bus-aware change is deliberate.

    This is not an endorsement — it is the gap, pinned. When a Bluetooth
    layout is confirmed on hardware, this test should be UPDATED alongside
    the new (bus, pid) lookup, not deleted quietly.
    """
    from gamepad_midi_bridge.sdl_profiles import profile_for
    usb = profile_for("030000005e040000120b000001050000", 1, 15)
    bt = profile_for("050000005e040000120b000001050000", 1, 15)
    assert usb == bt


@pytest.fixture(scope="module")
def app():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_status_dropdown_reports_transport_and_axis_map(app, monkeypatch):
    """A mis-resolved profile has to be diagnosable without a terminal."""
    from PySide6.QtWidgets import QDialog, QMenu, QMessageBox
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k: QMessageBox.No))
    monkeypatch.setattr(QDialog, "exec", lambda self, *a, **k: 0)

    from gamepad_midi_bridge.controller import ControllerInfo
    from gamepad_midi_bridge.ui.main_window import MainWindow

    win = MainWindow()
    try:
        win._active_controller_info = ControllerInfo(
            name="Xbox Wireless Controller",
            num_axes=6, num_buttons=15, num_hats=1,
            guid="050000005e040000120b000001050000",   # 045e:0b12 over BT
            raw_name="Controller",
            axis_map=(0, 1, 3, 4, 2, 5),
        )
        captured = {}
        monkeypatch.setattr(MainWindow, "_popup",
                            lambda self, menu, anchor: captured.setdefault("menu", menu))
        win._open_status_dropdown()
        menu = captured.get("menu")
        assert isinstance(menu, QMenu)
        text = "\n".join(a.text() for a in menu.actions())
        assert "045e:0b12" in text
        assert "Bluetooth" in text
        # The remap itself, so "L2 moves the right stick" is one glance away.
        assert "L2→a2" in text
        assert "RX→a3" in text
    finally:
        win.close()


def test_status_dropdown_says_when_there_is_no_remap(app, monkeypatch):
    from PySide6.QtWidgets import QDialog, QMessageBox
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k: QMessageBox.No))
    monkeypatch.setattr(QDialog, "exec", lambda self, *a, **k: 0)

    from gamepad_midi_bridge.controller import ControllerInfo
    from gamepad_midi_bridge.ui.main_window import MainWindow

    win = MainWindow()
    try:
        win._active_controller_info = ControllerInfo(
            name="DualSense Wireless Controller",
            num_axes=6, num_buttons=13, num_hats=1,
            guid="030000004c050000e60c000000006800",
            raw_name="DualSense Wireless Controller",
            axis_map=(0, 1, 2, 3, 4, 5),
        )
        captured = {}
        monkeypatch.setattr(MainWindow, "_popup",
                            lambda self, menu, anchor: captured.setdefault("menu", menu))
        win._open_status_dropdown()
        text = "\n".join(a.text() for a in captured["menu"].actions())
        assert "no remap" in text
        assert "054c:0ce6" in text
        assert "USB" in text
    finally:
        win.close()
