"""Mapping editor tab. Pro feature — shows the current mapping as a table.

Visible in free mode behind a ProLockOverlay so users can see what they're missing.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHeaderView, QLabel, QStackedLayout, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from ..license import is_pro
from ..mapping import Mapping
from .pro_lock import ProLockOverlay


class MappingEditor(QWidget):
    upgrade_clicked = Signal()
    activate_clicked = Signal()

    def __init__(self, mapping: Mapping, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._mapping = mapping

        # Stacked: actual editor underneath, lock overlay on top when not Pro.
        self._stack = QStackedLayout(self)

        content = QWidget()
        v = QVBoxLayout(content)
        v.setContentsMargins(20, 20, 20, 20)
        v.setSpacing(12)

        v.addWidget(self._section_label("BUTTONS → NOTES"))
        self._buttons_table = self._make_table(["Button #", "MIDI Note"])
        v.addWidget(self._buttons_table)

        v.addWidget(self._section_label("AXES → CC"))
        self._axes_table = self._make_table(["Axis #", "MIDI CC"])
        v.addWidget(self._axes_table)

        v.addWidget(self._section_label("D-PAD → NOTES"))
        self._hats_table = self._make_table(["Direction", "MIDI Note"])
        v.addWidget(self._hats_table)

        self._stack.addWidget(content)

        self._lock = ProLockOverlay(
            "Custom Mapping Editor",
            "Re-assign every button, stick axis, and D-pad direction to any "
            "MIDI note or CC. Save unlimited presets per project. Switch "
            "instantly while performing.",
        )
        self._lock.upgrade_clicked.connect(self.upgrade_clicked.emit)
        self._lock.activate_clicked.connect(self.activate_clicked.emit)
        self._stack.addWidget(self._lock)

        self._refresh_tables()
        self.refresh_lock()

    # ------------------------------------------------------------------ public

    def set_mapping(self, mapping: Mapping) -> None:
        self._mapping = mapping
        self._refresh_tables()

    def refresh_lock(self) -> None:
        # Show overlay (index 1) if not Pro, editor (index 0) if Pro.
        self._stack.setCurrentIndex(0 if is_pro() else 1)

    # ------------------------------------------------------------------ helpers

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            "color: #8a9099; font-size: 11px; font-weight: 700; "
            "letter-spacing: 1px; padding-top: 8px;"
        )
        return lbl

    def _make_table(self, headers: list) -> QTableWidget:
        t = QTableWidget(0, len(headers))
        t.setHorizontalHeaderLabels(headers)
        t.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        t.verticalHeader().setVisible(False)
        t.setAlternatingRowColors(False)
        t.setEditTriggers(QTableWidget.AllEditTriggers)
        t.setSelectionBehavior(QTableWidget.SelectRows)
        t.setShowGrid(False)
        return t

    def _refresh_tables(self) -> None:
        self._fill(self._buttons_table, [(str(k), str(v)) for k, v in sorted(self._mapping.buttons.items())])
        self._fill(self._axes_table, [(str(k), str(v)) for k, v in sorted(self._mapping.axes.items())])
        self._fill(self._hats_table, [(k, str(v)) for k, v in self._mapping.hats.items()])

    def _fill(self, table: QTableWidget, rows: list) -> None:
        table.setRowCount(len(rows))
        for r, (a, b) in enumerate(rows):
            ai = QTableWidgetItem(a)
            ai.setFlags(ai.flags() & ~Qt.ItemIsEditable)
            ai.setTextAlignment(Qt.AlignCenter)
            table.setItem(r, 0, ai)
            bi = QTableWidgetItem(b)
            bi.setTextAlignment(Qt.AlignCenter)
            table.setItem(r, 1, bi)
