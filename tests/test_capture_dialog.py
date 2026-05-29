"""Pure-state tests for the capture wizard and MappingEditor.set_worker.

CaptureDialog inherits QDialog and requires a QApplication to instantiate,
so the dialog tests are guarded with a pytest.importorskip + QApplication
fixture.  The MappingEditor.set_worker tests are pure-Python and run always.
"""
from __future__ import annotations

import sys
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_qapp():
    """Return (or create) the singleton QApplication for tests that need it."""
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv[:1])
    return app


# ---------------------------------------------------------------------------
# CaptureDialog tests — need QApplication
# ---------------------------------------------------------------------------

pyside6 = pytest.importorskip("PySide6", reason="PySide6 not installed")


def test_capture_dialog_none_worker_does_not_crash() -> None:
    """CaptureDialog(None, kind) must construct without raising."""
    _make_qapp()
    from gamepad_midi_bridge.ui.capture_dialog import CaptureDialog

    for kind in ("button", "axis", "hat"):
        dlg = CaptureDialog(worker=None, kind=kind)
        assert dlg.captured_index is None, (
            f"captured_index should start as None for kind={kind!r}"
        )
        dlg.deleteLater()


def test_capture_dialog_kind_stored() -> None:
    """_kind attribute is set from the constructor argument."""
    _make_qapp()
    from gamepad_midi_bridge.ui.capture_dialog import CaptureDialog

    dlg = CaptureDialog(worker=None, kind="axis")
    assert dlg._kind == "axis"
    dlg.deleteLater()


# ---------------------------------------------------------------------------
# MappingEditor.set_worker tests — pure state, no display needed
# ---------------------------------------------------------------------------

def test_mapping_editor_set_worker_stores_reference() -> None:
    """set_worker must update self._worker; starts as None."""
    _make_qapp()
    from gamepad_midi_bridge.ui.mapping_editor import MappingEditor
    from gamepad_midi_bridge.mapping import Mapping

    editor = MappingEditor(Mapping())
    assert editor._worker is None, "Worker should be None before set_worker()"

    sentinel = object()
    editor.set_worker(sentinel)
    assert editor._worker is sentinel, "set_worker should update _worker"
    editor.deleteLater()


def test_mapping_editor_set_worker_accepts_none() -> None:
    """set_worker(None) should not raise (graceful degradation)."""
    _make_qapp()
    from gamepad_midi_bridge.ui.mapping_editor import MappingEditor
    from gamepad_midi_bridge.mapping import Mapping

    editor = MappingEditor(Mapping())
    editor.set_worker(None)  # must not raise
    assert editor._worker is None
    editor.deleteLater()
