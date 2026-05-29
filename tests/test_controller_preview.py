"""Tests for ControllerPreview widget."""
from __future__ import annotations

import pytest


def _has_qt() -> bool:
    try:
        from PySide6.QtWidgets import QApplication  # noqa: F401
        return True
    except ImportError:
        return False


class TestControllerPreviewNoQt:
    """Import-level tests that don't need a QApplication."""

    def test_module_imports(self):
        """controller_preview module imports without error."""
        from gamepad_midi_bridge.ui import controller_preview  # noqa: F401
        assert hasattr(controller_preview, "ControllerPreview")

    def test_alias_tables_populated(self):
        """BUTTON_ALIASES and AXIS_ALIASES have entries."""
        from gamepad_midi_bridge.ui.controller_preview import BUTTON_ALIASES, AXIS_ALIASES
        assert len(BUTTON_ALIASES) > 0
        assert len(AXIS_ALIASES) > 0

    def test_known_button_aliases(self):
        """Common button keys resolve to expected shape names."""
        from gamepad_midi_bridge.ui.controller_preview import BUTTON_ALIASES
        assert BUTTON_ALIASES["cross"] == "cross"
        assert BUTTON_ALIASES["0"] == "cross"
        assert BUTTON_ALIASES["button_0"] == "cross"
        assert BUTTON_ALIASES["l1"] == "l1"
        assert BUTTON_ALIASES["touchpad"] == "touchpad"

    def test_known_axis_aliases(self):
        """Common axis keys resolve to expected shape names."""
        from gamepad_midi_bridge.ui.controller_preview import AXIS_ALIASES
        assert AXIS_ALIASES["0"] == "ls_x"
        assert AXIS_ALIASES["ls_x"] == "ls_x"
        assert AXIS_ALIASES["4"] == "l2"


@pytest.mark.skipif(not _has_qt(), reason="Qt not available")
class TestControllerPreviewWidget:
    """Widget tests (require QApplication)."""

    @pytest.fixture(autouse=True)
    def _app(self):
        from PySide6.QtWidgets import QApplication
        self.app = QApplication.instance() or QApplication([])

    def test_creation_does_not_crash(self):
        """ControllerPreview instantiates without error."""
        from gamepad_midi_bridge.ui.controller_preview import ControllerPreview
        widget = ControllerPreview()
        assert widget is not None
        widget.deleteLater()

    def test_fixed_size(self):
        """Widget reports 280×200 fixed size."""
        from gamepad_midi_bridge.ui.controller_preview import ControllerPreview
        widget = ControllerPreview()
        assert widget.width() == 280
        assert widget.height() == 200
        widget.deleteLater()

    def test_set_mapping_data_empty_dict(self):
        """set_mapping_data with empty dict renders without error."""
        from gamepad_midi_bridge.ui.controller_preview import ControllerPreview
        widget = ControllerPreview()
        widget.set_mapping_data({})
        assert widget._active == {}
        widget.deleteLater()

    def test_set_mapping_data_none_like(self):
        """set_mapping_data with non-dict value is safe."""
        from gamepad_midi_bridge.ui.controller_preview import ControllerPreview
        widget = ControllerPreview()
        widget.set_mapping_data(None)  # type: ignore[arg-type]
        assert widget._active == {}
        widget.deleteLater()

    def test_set_mapping_data_realistic_flat(self):
        """Flat preset blob highlights expected shapes."""
        from gamepad_midi_bridge.ui.controller_preview import ControllerPreview
        widget = ControllerPreview()
        blob = {
            "button_0": {"note": 60, "channel": 1},
            "button_1": {"note": 61, "channel": 1},
            "l1": {"note": 70, "channel": 1},
            "r2": {"note": 71, "channel": 1},
        }
        widget.set_mapping_data(blob)
        assert "cross" in widget._active
        assert "circle" in widget._active
        assert "l1" in widget._active
        assert "r2" in widget._active
        widget.deleteLater()

    def test_set_mapping_data_nested_buttons(self):
        """Nested 'buttons' sub-dict is parsed correctly."""
        from gamepad_midi_bridge.ui.controller_preview import ControllerPreview
        widget = ControllerPreview()
        blob = {
            "buttons": {
                "triangle": {"note": 80},
                "square": {"note": 81},
            }
        }
        widget.set_mapping_data(blob)
        assert "triangle" in widget._active
        assert "square" in widget._active
        widget.deleteLater()

    def test_set_mapping_data_mappings_list(self):
        """List-of-mappings layout is parsed."""
        from gamepad_midi_bridge.ui.controller_preview import ControllerPreview
        widget = ControllerPreview()
        blob = {
            "mappings": [
                {"input": {"kind": "button", "index": 3}, "output": {"note": 55, "channel": 1}},
                {"input": {"kind": "axis", "index": 0}, "output": {"cc": 1, "channel": 1}},
            ]
        }
        widget.set_mapping_data(blob)
        assert "triangle" in widget._active
        assert "ls_x" in widget._active
        widget.deleteLater()

    def test_labels_truncated_to_5_chars(self):
        """Long label values are truncated to 5 characters."""
        from gamepad_midi_bridge.ui.controller_preview import ControllerPreview
        widget = ControllerPreview()
        blob = {"cross": "TOOLONGVALUE"}
        widget.set_mapping_data(blob)
        assert len(widget._active.get("cross", "")) <= 5
        widget.deleteLater()

    def test_repaint_after_set_mapping(self):
        """Calling set_mapping_data twice doesn't crash."""
        from gamepad_midi_bridge.ui.controller_preview import ControllerPreview
        widget = ControllerPreview()
        widget.set_mapping_data({"l1": {"note": 60}})
        widget.set_mapping_data({})
        assert widget._active == {}
        widget.deleteLater()
