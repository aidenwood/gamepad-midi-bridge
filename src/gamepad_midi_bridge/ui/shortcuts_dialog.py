"""ShortcutsDialog — searchable keyboard shortcuts reference."""
from __future__ import annotations

from typing import List, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QHeaderView, QLineEdit, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)


# Shortcuts registered in the app. Each tuple is (shortcut_keys, action_description).
_SHORTCUTS: List[Tuple[str, str]] = [
    ("Ctrl+Return", "Toggle bridge start/stop"),
    ("Ctrl+K", "Open command palette"),
    ("Ctrl+Shift+P", "Panic (all notes off)"),
    ("Cmd+O / Ctrl+O", "Open preset"),
    ("Cmd+S / Ctrl+S", "Save preset"),
    ("Cmd+Shift+S / Ctrl+Shift+S", "Save preset as"),
    ("Cmd+, / Ctrl+,", "Preferences"),
    ("Cmd+Q / Ctrl+Q", "Quit"),
    ("Cmd+Alt+S / Ctrl+Alt+S", "Toggle Split view"),
    ("Cmd+Alt+C / Ctrl+Alt+C", "Toggle Console"),
    ("Cmd+Alt+I / Ctrl+Alt+I", "Toggle Inspector"),
    ("Cmd+Alt+3 / Ctrl+Alt+3", "Toggle 3D view"),
]


class ShortcutsDialog(QDialog):
    """Searchable keyboard shortcuts reference dialog.

    Displays all registered shortcuts in a two-column table (Shortcut + Action)
    with a filter input at the top. Close on Escape.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Keyboard Shortcuts")
        self.setModal(True)
        self.setWindowFlags(
            Qt.Dialog | Qt.WindowTitleHint | Qt.WindowCloseButtonHint
        )
        self.setMinimumSize(500, 400)

        v = QVBoxLayout(self)
        v.setContentsMargins(20, 20, 20, 20)
        v.setSpacing(12)

        # Filter input
        self._filter = QLineEdit()
        self._filter.setPlaceholderText("Search shortcuts…")
        self._filter.textChanged.connect(self._on_filter_changed)
        v.addWidget(self._filter)

        # Table
        self._table = QTableWidget()
        self._table.setColumnCount(2)
        self._table.setHorizontalHeaderLabels(["Shortcut", "Action"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setSelectionMode(QTableWidget.NoSelection)
        v.addWidget(self._table, 1)

        # Populate table with all shortcuts
        self._populate_table(_SHORTCUTS)

    def _populate_table(self, shortcuts: List[Tuple[str, str]]) -> None:
        """Fill the table with the given shortcuts."""
        self._table.setRowCount(len(shortcuts))
        for row, (shortcut, action) in enumerate(shortcuts):
            shortcut_item = QTableWidgetItem(shortcut)
            shortcut_item.setFlags(shortcut_item.flags() & ~Qt.ItemIsEditable)
            action_item = QTableWidgetItem(action)
            action_item.setFlags(action_item.flags() & ~Qt.ItemIsEditable)
            self._table.setItem(row, 0, shortcut_item)
            self._table.setItem(row, 1, action_item)

    def _on_filter_changed(self) -> None:
        """Filter shortcuts based on search text."""
        query = self._filter.text().lower()
        if not query:
            self._populate_table(_SHORTCUTS)
            return

        filtered = [
            (shortcut, action)
            for shortcut, action in _SHORTCUTS
            if query in shortcut.lower() or query in action.lower()
        ]
        self._populate_table(filtered)

    def keyPressEvent(self, event) -> None:
        """Close on Escape."""
        if event.key() == Qt.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)
