"""The four repeated button treatments from the Setup wireframe.

UI-HANDOVER.md is explicit that these are four treatments of ONE component,
not four components: "Do not create separate styles for every feature or an
independent compact component with its own event wiring." These tests pin
that down, because a second compact button class is the easy wrong turn.
"""
from __future__ import annotations

import pytest

from gamepad_midi_bridge.ui import tokens as T


def _has_qapp() -> bool:
    try:
        from PySide6.QtWidgets import QApplication  # noqa: F401
        return True
    except ImportError:
        return False


def _btn(text="ACTION", variant="header"):
    from gamepad_midi_bridge.ui.primitives.button import UIButton
    return UIButton(text, variant=variant)


@pytest.mark.skipif("not _has_qapp()", reason="Qt not available")
class TestTreatments:

    @pytest.mark.parametrize("variant", [
        "primary", "secondary", "ghost", "danger",
        "mode", "header", "utility", "utility_round",
    ])
    def test_every_variant_builds_a_stylesheet(self, variant):
        assert _btn(variant=variant).styleSheet().strip()

    def test_mode_uses_the_wireframe_teal_when_selected(self):
        css = _btn(variant="mode").styleSheet()
        assert T.SHELL_TEAL in css
        assert "QPushButton:checked" in css

    def test_mode_label_on_teal_is_the_readable_pair(self):
        """White on #2DD4BF is ~1.86:1 and fails at small sizes."""
        assert T.SHELL_TEAL_FG in _btn(variant="mode").styleSheet()

    def test_mode_is_checkable_so_selection_is_state_not_text(self):
        assert _btn(variant="mode").isCheckable() is True

    def test_header_uses_the_secondary_blue(self):
        assert T.SHELL_BLUE in _btn(variant="header").styleSheet()

    def test_utilities_use_the_dark_teal(self):
        for v in ("utility", "utility_round"):
            assert T.SHELL_TEAL_UTIL in _btn(variant=v).styleSheet()

    def test_round_utility_is_actually_round(self):
        assert "999px" in _btn(variant="utility_round").styleSheet()

    def test_rect_utility_is_not_round(self):
        assert "999px" not in _btn(variant="utility").styleSheet()


@pytest.mark.skipif("not _has_qapp()", reason="Qt not available")
class TestCompactPresentation:

    def test_compact_hides_the_label(self):
        b = _btn("CONNECT")
        b.set_compact(True)
        assert b.text() == ""

    def test_compact_keeps_the_control_identifiable(self):
        """Losing the label must not lose the name — icon-only buttons still
        need an accessible name and a tooltip."""
        b = _btn("CONNECT")
        b.set_compact(True)
        assert b.accessibleName() == "CONNECT"
        assert b.toolTip() == "CONNECT"

    def test_restoring_brings_the_same_label_back(self):
        b = _btn("NODE VIEW")
        b.set_compact(True)
        b.set_compact(False)
        assert b.text() == "NODE VIEW"

    def test_compact_does_not_change_state(self):
        """Narrow mode changes presentation, not the command or its state."""
        b = _btn("SETUP", variant="mode")
        b.setChecked(True)
        b.set_compact(True)
        assert b.isChecked() is True
        assert b.isCheckable() is True

    def test_compact_does_not_disturb_the_signal(self):
        b = _btn("CONNECT")
        fired = []
        b.clicked.connect(lambda: fired.append(1))
        b.set_compact(True)
        b.click()
        assert fired == [1]

    def test_a_preset_tooltip_is_not_overwritten(self):
        b = _btn("STATUS")
        b.setToolTip("Readiness and diagnostics")
        b.set_compact(True)
        assert b.toolTip() == "Readiness and diagnostics"

    def test_toggling_twice_is_idempotent(self):
        b = _btn("OUTPUT")
        b.set_compact(True)
        b.set_compact(True)
        b.set_compact(False)
        assert b.text() == "OUTPUT"
        assert b.is_compact() is False
