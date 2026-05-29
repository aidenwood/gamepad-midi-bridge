"""SnapshotDialog — browse, save, restore, and delete named mapping snapshots."""
from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .. import snapshots as snap_io
from ..mapping import Mapping


class SnapshotDialog(QDialog):
    """Named-snapshot manager dialog.

    Signals
    -------
    restore_requested(slug)  — emitted when the user clicks Restore on a row.
    dialog_done              — emitted when the dialog is closing.
    """

    restore_requested: Signal = Signal(str)
    dialog_done: Signal = Signal()

    # Table column indices
    _COL_NAME = 0
    _COL_MODIFIED = 1
    _COL_SIZE = 2
    _COL_RESTORE = 3
    _COL_DELETE = 4

    def __init__(
        self,
        current_mapping_provider,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._get_current = current_mapping_provider
        self.setWindowTitle("Snapshots")
        self.resize(600, 400)

        v = QVBoxLayout(self)
        v.setContentsMargins(16, 16, 16, 16)
        v.setSpacing(10)

        # Top action bar
        top_row = QHBoxLayout()
        self._save_btn = QPushButton("Save current as…")
        self._save_btn.clicked.connect(self._on_save)
        top_row.addWidget(self._save_btn)
        top_row.addStretch(1)
        v.addLayout(top_row)

        # Table
        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(["Name", "Last modified", "Size", "", ""])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        v.addWidget(self._table, 1)

        # Bottom close button
        bottom_row = QHBoxLayout()
        bottom_row.addStretch(1)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        bottom_row.addWidget(close_btn)
        v.addLayout(bottom_row)

        self._refresh()

    # ------------------------------------------------------------------ private

    def _refresh(self) -> None:
        """Reload the snapshot list and rebuild the table."""
        snapshots = snap_io.list_snapshots()
        self._table.setRowCount(len(snapshots))
        for row, info in enumerate(snapshots):
            # Name
            name_item = QTableWidgetItem(info.name)
            name_item.setData(Qt.UserRole, info.slug)
            self._table.setItem(row, self._COL_NAME, name_item)

            # Modified — friendly datetime
            dt = datetime.fromtimestamp(info.mtime).strftime("%Y-%m-%d %H:%M")
            self._table.setItem(row, self._COL_MODIFIED, QTableWidgetItem(dt))

            # Size
            size_str = f"{info.size / 1024:.1f} KB" if info.size >= 1024 else f"{info.size} B"
            self._table.setItem(row, self._COL_SIZE, QTableWidgetItem(size_str))

            # Restore button
            restore_btn = QPushButton("Restore")
            restore_btn.setProperty("slug", info.slug)
            restore_btn.clicked.connect(self._on_restore)
            self._table.setCellWidget(row, self._COL_RESTORE, restore_btn)

            # Delete button
            delete_btn = QPushButton("Delete")
            delete_btn.setProperty("slug", info.slug)
            delete_btn.clicked.connect(self._on_delete)
            self._table.setCellWidget(row, self._COL_DELETE, delete_btn)

        if not snapshots:
            self._table.setRowCount(1)
            placeholder = QTableWidgetItem("No snapshots yet — save the current mapping above.")
            placeholder.setFlags(Qt.ItemIsEnabled)
            placeholder.setTextAlignment(Qt.AlignCenter)
            self._table.setItem(0, self._COL_NAME, placeholder)
            self._table.setSpan(0, 0, 1, 5)

    def _on_save(self) -> None:
        name, ok = QInputDialog.getText(self, "Save snapshot", "Snapshot name:")
        if not ok or not name.strip():
            return
        mapping = self._get_current()
        snap_io.save_snapshot(mapping, name.strip())
        self._refresh()

    def _on_restore(self) -> None:
        btn = self.sender()
        if btn is None:
            return
        slug = btn.property("slug")
        self.restore_requested.emit(slug)

    def _on_delete(self) -> None:
        btn = self.sender()
        if btn is None:
            return
        slug = btn.property("slug")
        # Find human name for confirm dialog
        name = slug
        for row in range(self._table.rowCount()):
            item = self._table.item(row, self._COL_NAME)
            if item and item.data(Qt.UserRole) == slug:
                name = item.text()
                break
        reply = QMessageBox.question(
            self,
            "Delete snapshot",
            f'Delete snapshot "{name}"? This cannot be undone.',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        snap_io.delete_snapshot(slug)
        self._refresh()

    # ------------------------------------------------------------------ QDialog

    def accept(self) -> None:
        self.dialog_done.emit()
        super().accept()

    def reject(self) -> None:
        self.dialog_done.emit()
        super().reject()
