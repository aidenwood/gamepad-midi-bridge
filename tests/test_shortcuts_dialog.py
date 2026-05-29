"""Tests for ShortcutsDialog."""
from __future__ import annotations

import pytest

from gamepad_midi_bridge.ui.shortcuts_dialog import ShortcutsDialog


def _qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _has_pyside6() -> bool:
    try:
        from PySide6.QtWidgets import QApplication
        return True
    except ImportError:
        return False


skip_no_qt = pytest.mark.skipif(not _has_pyside6(), reason="PySide6 not available")


@skip_no_qt
def test_shortcuts_dialog_creation() -> None:
    """Test that ShortcutsDialog can be created without crashing."""
    _qapp()
    dialog = ShortcutsDialog()
    assert dialog is not None
    assert dialog.windowTitle() == "Keyboard Shortcuts"
    dialog.close()


@skip_no_qt
def test_shortcuts_dialog_lists_10_plus_shortcuts() -> None:
    """Test that ShortcutsDialog displays 10+ shortcuts."""
    _qapp()
    dialog = ShortcutsDialog()
    row_count = dialog._table.rowCount()
    assert row_count >= 10, f"Expected at least 10 shortcuts, got {row_count}"
    dialog.close()


@skip_no_qt
def test_shortcuts_dialog_filter_works() -> None:
    """Test that the filter input reduces visible shortcuts."""
    _qapp()
    dialog = ShortcutsDialog()
    initial_count = dialog._table.rowCount()

    # Filter for "bridge"
    dialog._filter.setText("bridge")
    filtered_count = dialog._table.rowCount()

    assert filtered_count < initial_count, "Filter should reduce visible rows"
    assert filtered_count > 0, "Filter should show at least one matching row"
    dialog.close()


@skip_no_qt
def test_shortcuts_dialog_filter_case_insensitive() -> None:
    """Test that filter is case-insensitive."""
    _qapp()
    dialog = ShortcutsDialog()

    # Filter with lowercase
    dialog._filter.setText("ctrl")
    count1 = dialog._table.rowCount()

    # Filter with uppercase
    dialog._filter.setText("CTRL")
    count2 = dialog._table.rowCount()

    assert count1 == count2, "Filter should be case-insensitive"
    assert count1 > 0, "Should find shortcuts with CTRL"
    dialog.close()


@skip_no_qt
def test_shortcuts_dialog_close_on_escape() -> None:
    """Test that dialog handles Escape key without crashing."""
    from PySide6.QtCore import Qt

    _qapp()
    dialog = ShortcutsDialog()
    dialog.show()

    from PySide6.QtGui import QKeyEvent
    escape_event = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier)
    # Should not raise an exception
    dialog.keyPressEvent(escape_event)
    dialog.close()


@skip_no_qt
def test_shortcuts_dialog_table_not_editable() -> None:
    """Test that shortcuts in the table are read-only."""
    _qapp()
    dialog = ShortcutsDialog()

    for row in range(dialog._table.rowCount()):
        for col in range(2):
            item = dialog._table.item(row, col)
            assert item is not None
            # Check that ItemIsEditable flag is NOT set
            from PySide6.QtCore import Qt
            assert not (item.flags() & Qt.ItemIsEditable), \
                f"Cell ({row}, {col}) should not be editable"

    dialog.close()
