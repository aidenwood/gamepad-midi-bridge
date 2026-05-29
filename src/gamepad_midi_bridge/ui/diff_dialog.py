"""Preset comparison dialog showing mapping differences."""
from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QHeaderView, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from ..mapping import Mapping
from ..mapping_diff import DiffEntry, diff_mappings


class DiffDialog(QDialog):
    """Side-by-side diff of two presets."""

    def __init__(
        self,
        mapping_a: Mapping,
        mapping_b: Mapping,
        name_a: str,
        name_b: str,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Diff: {name_a} → {name_b}")
        self.resize(800, 500)

        self._entries = diff_mappings(mapping_a, mapping_b)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Table with columns: Path, A, B, Change
        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["Path", name_a, name_b, "Change"])
        self._table.horizontalHeader().setStretchLastSection(False)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)

        # Populate table
        self._populate_table()
        layout.addWidget(self._table, 1)

        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch(1)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    def _populate_table(self) -> None:
        """Fill the table with diff entries."""
        self._table.setRowCount(len(self._entries))

        for row, entry in enumerate(self._entries):
            # Path column
            path_item = QTableWidgetItem(entry.path)
            path_item.setFlags(path_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._table.setItem(row, 0, path_item)

            # Left (A) column
            left_text = self._format_value(entry.left) if entry.left is not None else "—"
            left_item = QTableWidgetItem(left_text)
            left_item.setFlags(left_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._table.setItem(row, 1, left_item)

            # Right (B) column
            right_text = self._format_value(entry.right) if entry.right is not None else "—"
            right_item = QTableWidgetItem(right_text)
            right_item.setFlags(right_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._table.setItem(row, 2, right_item)

            # Change kind column
            kind_item = QTableWidgetItem(entry.kind)
            kind_item.setFlags(kind_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._table.setItem(row, 3, kind_item)

            # Colour rows by kind
            bg_color = {
                "added": (144, 238, 144),      # light green
                "removed": (255, 127, 127),    # light red
                "changed": (255, 200, 87),     # amber
            }.get(entry.kind, (255, 255, 255))

            for col in range(4):
                item = self._table.item(row, col)
                if item:
                    item.setBackground(item.background().__class__(*bg_color))

    @staticmethod
    def _format_value(val) -> str:
        """Format a value for display in the table."""
        if val is None:
            return "—"
        if isinstance(val, bool):
            return "Yes" if val else "No"
        if isinstance(val, dict):
            return f"{{...}} ({len(val)} items)"
        if isinstance(val, list):
            return f"[...] ({len(val)} items)"
        return str(val)
