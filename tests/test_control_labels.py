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
