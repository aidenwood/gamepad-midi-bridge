"""Controller-family label mapping.

Regression: the Live and Visualise views hardcoded PlayStation names, so a
Windows user on an Xbox One Controller saw Cross / Circle / Square /
Triangle / Share / Options / PS — plus a touchpad their pad doesn't have.
"""
from __future__ import annotations

import pytest

from gamepad_midi_bridge import control_labels as cl


class TestFamilyDetection:

    @pytest.mark.parametrize("name,expected", [
        ("Xbox One Controller", cl.XBOX),
        ("Xbox Series X Controller", cl.XBOX),
        ("XInput Controller #1", cl.XBOX),
        ("DualSense Wireless Controller", cl.PLAYSTATION),
        ("Sony DualShock 4", cl.PLAYSTATION),
        ("Wireless Controller", cl.PLAYSTATION),
        ("Nintendo Switch Pro Controller", cl.SWITCH),
        ("Joy-Con (L)", cl.SWITCH),
        ("Generic USB Gamepad", cl.GENERIC),
    ])
    def test_classifies_known_controllers(self, name, expected):
        assert cl.family_for(name) == expected

    def test_handles_missing_name(self):
        assert cl.family_for(None) == cl.GENERIC
        assert cl.family_for("") == cl.GENERIC


class TestButtonLabels:

    def test_xbox_face_buttons(self):
        """Index 0 is the BOTTOM face button on every pad — 'A' on Xbox."""
        assert cl.button_label(0, cl.XBOX) == "A"
        assert cl.button_label(1, cl.XBOX) == "B"
        assert cl.button_label(2, cl.XBOX) == "X"
        assert cl.button_label(3, cl.XBOX) == "Y"

    def test_playstation_face_buttons(self):
        assert cl.button_label(0, cl.PLAYSTATION) == "Cross"
        assert cl.button_label(3, cl.PLAYSTATION) == "Triangle"

    def test_xbox_never_says_playstation_words(self):
        """The actual bug from the video, asserted directly."""
        banned = {"cross", "circle", "square", "triangle",
                  "share", "options", "ps", "l1", "r1", "l2", "r2"}
        for idx in range(11):
            assert cl.button_label(idx, cl.XBOX).lower() not in banned
        for side in ("L2", "R2"):
            assert cl.trigger_label(side, cl.XBOX).lower() not in banned

    def test_shoulders_and_triggers_per_family(self):
        assert cl.shoulder_label("L1", cl.XBOX) == "LB"
        assert cl.shoulder_label("R1", cl.XBOX) == "RB"
        assert cl.trigger_label("L2", cl.XBOX) == "LT"
        assert cl.trigger_label("R2", cl.XBOX) == "RT"
        assert cl.shoulder_label("L1", cl.PLAYSTATION) == "L1"
        assert cl.trigger_label("R2", cl.PLAYSTATION) == "R2"

    def test_every_family_labels_all_eleven_buttons(self):
        for family in (cl.PLAYSTATION, cl.XBOX, cl.SWITCH, cl.GENERIC):
            for idx in range(11):
                label = cl.button_label(idx, family)
                assert label and not label.startswith("Btn ") or family == cl.GENERIC

    def test_unknown_index_degrades_gracefully(self):
        assert cl.button_label(99, cl.XBOX) == "Btn 99"


class TestGlyphs:

    def test_playstation_uses_shape_glyphs(self):
        assert cl.button_glyph(0, cl.PLAYSTATION) == "✕"
        assert cl.button_glyph(3, cl.PLAYSTATION) == "△"

    def test_xbox_glyph_equals_its_label(self):
        """So the UI can skip rendering 'A   A'."""
        for idx in range(4):
            assert cl.button_glyph(idx, cl.XBOX) == cl.button_label(idx, cl.XBOX)

    def test_non_face_button_falls_back_to_label(self):
        assert cl.button_glyph(7, cl.PLAYSTATION) == "Options"


class TestTouchpad:

    def test_only_playstation_has_one(self):
        assert cl.has_touchpad(cl.PLAYSTATION) is True
        assert cl.has_touchpad(cl.XBOX) is False
        assert cl.has_touchpad(cl.SWITCH) is False
        assert cl.has_touchpad(cl.GENERIC) is False


def _has_qapp() -> bool:
    try:
        from PySide6.QtWidgets import QApplication  # noqa: F401
        return True
    except ImportError:
        return False


@pytest.mark.skipif("not _has_qapp()", reason="Qt not available")
class TestLiveViewAdaptsToController:
    """ControllerMeter must render the right family's controls."""

    def _meter(self, name):
        from PySide6.QtWidgets import QApplication
        from PySide6.QtGui import QColor, QPixmap
        from gamepad_midi_bridge.ui.controller_meter import ControllerMeter
        QApplication.instance() or QApplication([])
        m = ControllerMeter()
        m.resize(900, 560)
        m.set_connected(True, name)
        pm = QPixmap(900, 560)
        pm.fill(QColor("#0e0f12"))
        m.render(pm)          # force a real paint pass
        return m

    def test_touchpad_hitbox_only_for_playstation(self):
        assert self._meter("DualSense Wireless Controller")._touchpad_rect is not None
        assert self._meter("Xbox One Controller")._touchpad_rect is None

    def test_all_face_and_meta_buttons_are_hittable(self):
        """Every button index 0-10 gets a clickable rect, both families."""
        for name in ("Xbox One Controller", "DualSense Wireless Controller"):
            rects = self._meter(name)._button_rects
            for idx in range(11):
                assert idx in rects, f"{name}: button {idx} has no hitbox"

    def test_all_four_dpad_directions_are_hittable(self):
        rects = self._meter("Xbox One Controller")._dpad_rects
        for direction in ("up", "down", "left", "right"):
            assert direction in rects

    def test_both_triggers_are_hittable(self):
        rects = self._meter("Xbox One Controller")._trigger_rects
        assert "L2" in rects and "R2" in rects

    def test_both_sticks_are_hittable(self):
        rects = self._meter("Xbox One Controller")._stick_rects
        assert "left" in rects and "right" in rects


class TestGuidIdentity:
    """Naming a pad from its GUID rather than its USB product string.

    Microsoft's Xbox descriptor sets the product string to the literal word
    "Controller". SDL passes that through, so LIVE STATS read
    "CONTROLLER: Controller" and — worse — `family_for("Controller")`
    returned GENERIC, costing the pad the A/B/X/Y labels this module exists
    to provide. The VID:PID was sitting unused in ControllerInfo.guid.
    """

    DUALSENSE_USB = "030000004c050000e60c000000006800"
    DUALSENSE_BT = "050000004c050000e60c000000006800"
    XBOX_SERIES = "030000005e040000120b000000006800"

    def test_decodes_vid_pid_from_a_real_dualsense_guid(self):
        assert cl.vid_pid_from_guid(self.DUALSENSE_USB) == (0x054C, 0x0CE6)

    def test_decodes_vid_pid_from_a_real_xbox_guid(self):
        assert cl.vid_pid_from_guid(self.XBOX_SERIES) == (0x045E, 0x0B12)

    def test_decodes_bus_type(self):
        assert cl.bus_from_guid(self.DUALSENSE_USB) == cl.BUS_USB
        assert cl.bus_from_guid(self.DUALSENSE_BT) == cl.BUS_BLUETOOTH

    @pytest.mark.parametrize("guid", ["", None, "xyz", "zzzzzzzzzzzzzzzzzzzz"])
    def test_garbage_guids_do_not_raise(self, guid):
        assert cl.vid_pid_from_guid(guid) == (0, 0)
        assert cl.bus_from_guid(guid) == 0

    def test_xbox_useless_name_is_replaced_from_guid(self):
        """The actual bug: SDL says "Controller", the GUID says Xbox."""
        assert cl.display_name("Controller", self.XBOX_SERIES) == \
            "Xbox Wireless Controller"

    def test_replaced_name_now_classifies_as_xbox(self):
        """Why the name mattered — family_for reads the same string, so a
        blank name also cost the pad its A/B/X/Y labels."""
        assert cl.family_for(cl.display_name("Controller", self.XBOX_SERIES)) \
            == cl.XBOX

    def test_raw_controller_string_still_classifies_as_generic(self):
        """Guards the reason display_name has to run FIRST."""
        assert cl.family_for("Controller") == cl.GENERIC

    def test_dualsense_name_is_preserved(self):
        assert cl.display_name("DualSense Wireless Controller",
                               self.DUALSENSE_USB) == \
            "DualSense Wireless Controller"

    def test_known_vid_pid_beats_a_vague_sdl_name(self):
        assert cl.display_name("Wireless Controller", self.DUALSENSE_USB) == \
            "DualSense Wireless Controller"

    def test_unknown_pid_from_known_vendor_falls_back_to_brand(self):
        unknown_sony = "03000000" + "4c05" + "0000" + "ffff" + "000000006800"
        assert cl.display_name("Controller", unknown_sony) == \
            "PlayStation Controller"

    def test_unknown_hardware_keeps_its_own_name(self):
        assert cl.display_name("8BitDo SN30 Pro", "") == "8BitDo SN30 Pro"

    def test_nothing_useful_anywhere_is_still_a_string(self):
        assert cl.display_name("", "") == "Unknown Controller"
        assert cl.display_name(None, None) == "Unknown Controller"

    def test_unknown_vendor_reports_the_ids_it_found(self):
        logitech = "03000000" + "6d04" + "0000" + "1dc2" + "000000006800"
        assert cl.display_name("Controller", logitech) == \
            "Unknown Controller (046d:c21d)"


@pytest.mark.skipif("not _has_qapp()", reason="Qt not available")
class TestVisualiseTabAdaptsToController:
    """The Visualise tab was PlayStation-only while the Live tab wasn't, so
    one session showed A/B/X/Y and Cross/Circle/Square/Triangle for the same
    pad on two different tabs."""

    def test_heatmap_cells_follow_the_family(self):
        from gamepad_midi_bridge.ui.visualise_tab import button_cells
        xbox = dict((label, key) for label, key in button_cells(cl.XBOX))
        assert "A" in xbox and "B" in xbox and "X" in xbox and "Y" in xbox
        assert "Cross" not in xbox and "Triangle" not in xbox

    def test_playstation_cells_are_unchanged(self):
        from gamepad_midi_bridge.ui.visualise_tab import button_cells
        ps = dict((label, key) for label, key in button_cells(cl.PLAYSTATION))
        assert ps["Cross"] == 0 and ps["Triangle"] == 3

    def test_dpad_cells_are_present_for_every_family(self):
        from gamepad_midi_bridge.ui.visualise_tab import button_cells
        for family in (cl.PLAYSTATION, cl.XBOX, cl.SWITCH, cl.GENERIC):
            keys = [key for _label, key in button_cells(family)]
            for d in ("up", "down", "left", "right"):
                assert d in keys, f"{family} lost the {d} d-pad cell"

    def test_cell_count_still_fits_the_three_by_five_grid(self):
        """paintEvent lays out exactly 15 cells."""
        from gamepad_midi_bridge.ui.visualise_tab import button_cells
        for family in (cl.PLAYSTATION, cl.XBOX, cl.SWITCH, cl.GENERIC):
            assert len(button_cells(family)) == 15

    def test_face_glyphs_differ_between_xbox_and_playstation(self):
        assert cl.button_glyph(0, cl.XBOX) != cl.button_glyph(0, cl.PLAYSTATION)

    def test_only_playstation_draws_a_touchpad(self):
        assert cl.has_touchpad(cl.PLAYSTATION) is True
        assert cl.has_touchpad(cl.XBOX) is False
