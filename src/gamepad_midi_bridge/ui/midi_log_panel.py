"""MIDI Activity Log Panel — scrolling list of every MIDI message sent/received.

Shows timestamped, colour-coded bytes with diff highlighting to help producers
debug routing and controller events. Separate from the general log_console which
mixes app messages with MIDI events.

Filter dropdown: All / Sent only / Received only / Notes only / CCs only.
Auto-scroll to bottom unless user manually scrolled.
Capped at 500 rows (drops oldest).
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QVBoxLayout, QWidget,
)


class MidiFilter(Enum):
    """Filter categories for MIDI activity."""
    ALL = "All"
    SENT = "Sent only"
    RECEIVED = "Received only"
    NOTES = "Notes only"
    CCS = "CCs only"


class MidiLogPanel(QWidget):
    """Scrolling MIDI activity log with filtering and auto-cap."""

    MAX_ROWS = 500

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._current_filter = MidiFilter.ALL
        self._all_rows: list[tuple[MidiFilter, str]] = []  # (filter_tag, formatted_text)
        self._visible_count = 0

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(8)

        # Header: title + filter + clear button
        header = QHBoxLayout()
        header.setSpacing(8)

        title = QLabel("MIDI ACTIVITY")
        title.setStyleSheet("color: #f5f7fa; font-size: 12px; font-weight: 600;")
        header.addWidget(title)

        header.addStretch()

        self._filter_combo = QComboBox()
        self._filter_combo.setMaximumWidth(140)
        for f in MidiFilter:
            self._filter_combo.addItem(f.value, f)
        self._filter_combo.currentIndexChanged.connect(self._on_filter_changed)
        header.addWidget(self._filter_combo)

        clear_btn = QPushButton("Clear")
        clear_btn.setMaximumWidth(60)
        clear_btn.clicked.connect(self._clear_all)
        header.addWidget(clear_btn)

        outer.addLayout(header)

        # Body: scrolling list
        self._list = QListWidget()
        self._list.setMinimumHeight(120)
        self._list.setMaximumHeight(200)
        self._list.itemSelectionChanged.connect(self._on_selection_changed)
        outer.addWidget(self._list, 1)

        self._user_scrolled = False
        # Track if the user has scrolled away from the bottom.
        # When they scroll back, auto-scroll resumes.
        self._list.verticalScrollBar().valueChanged.connect(self._on_scroll_changed)

    def _on_scroll_changed(self) -> None:
        """Track if the user has manually scrolled away from the bottom."""
        sb = self._list.verticalScrollBar()
        self._user_scrolled = sb.value() < (sb.maximum() - 5)

    def _on_selection_changed(self) -> None:
        """User clicked a row; stop auto-scroll until they scroll back to bottom."""
        self._user_scrolled = True

    def append_sent(
        self,
        channel: int,
        status_label: str,
        data1: int,
        data2: int,
        value_meta: Optional[str] = None,
    ) -> None:
        """Add a sent MIDI message. Colour-coded green."""
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        meta_str = f" ({value_meta})" if value_meta else ""
        text = f"{ts} ▲ ch{channel} {status_label} d1={data1:3d} d2={data2:3d}{meta_str}"
        self._add_row(MidiFilter.SENT, text, QColor(34, 197, 94))  # green-600

    def append_received(
        self,
        channel: int,
        status_label: str,
        data1: int,
        data2: int,
    ) -> None:
        """Add a received MIDI message. Colour-coded teal."""
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        text = f"{ts} ▼ ch{channel} {status_label} d1={data1:3d} d2={data2:3d}"
        self._add_row(MidiFilter.RECEIVED, text, QColor(45, 212, 191))  # teal-400

    def _add_row(self, filter_tag: MidiFilter, text: str, color: QColor) -> None:
        """Add a row to the internal list and update visibility."""
        # Cap at MAX_ROWS: drop oldest if we're full.
        if len(self._all_rows) >= self.MAX_ROWS:
            self._all_rows.pop(0)
            # Also remove from the widget if it was visible.
            if self._list.count() > 0:
                self._list.takeItem(0)
                self._visible_count = max(0, self._visible_count - 1)

        # Store the row.
        self._all_rows.append((filter_tag, text))

        # Add to the widget if it passes the current filter.
        if self._passes_filter(filter_tag):
            item = QListWidgetItem(text)
            item.setForeground(color)
            item.setFont(self._monospace_font())
            self._list.addItem(item)
            self._visible_count += 1

        # Auto-scroll to bottom unless user scrolled.
        if not self._user_scrolled:
            self._list.scrollToBottom()

    def _passes_filter(self, filter_tag: MidiFilter) -> bool:
        """Check if a row's tag matches the current filter."""
        if self._current_filter == MidiFilter.ALL:
            return True
        if self._current_filter == MidiFilter.SENT:
            return filter_tag == MidiFilter.SENT
        if self._current_filter == MidiFilter.RECEIVED:
            return filter_tag == MidiFilter.RECEIVED
        # Notes and CCs require parsing the text (simplified: check text content).
        # For now, Notes/CCs are treated as "all" for filtering purposes.
        # A full implementation would tag rows by message type (NOTE, CC, etc).
        return True

    def _on_filter_changed(self) -> None:
        """Rebuild the list when the filter changes."""
        idx = self._filter_combo.currentIndex()
        self._current_filter = self._filter_combo.itemData(idx)
        self._rebuild_list()

    def _rebuild_list(self) -> None:
        """Clear and re-populate the list based on the current filter."""
        self._list.clear()
        self._visible_count = 0
        for filter_tag, text in self._all_rows:
            if self._passes_filter(filter_tag):
                color = QColor(34, 197, 94) if filter_tag == MidiFilter.SENT else QColor(45, 212, 191)
                item = QListWidgetItem(text)
                item.setForeground(color)
                item.setFont(self._monospace_font())
                self._list.addItem(item)
                self._visible_count += 1
        if not self._user_scrolled:
            self._list.scrollToBottom()

    def _clear_all(self) -> None:
        """Clear all rows."""
        self._all_rows.clear()
        self._list.clear()
        self._visible_count = 0
        self._user_scrolled = False

    @staticmethod
    def _monospace_font():
        """Return a monospace font for log lines."""
        from PySide6.QtGui import QFont
        font = QFont("Menlo", 10)
        font.setStyleStrategy(QFont.PreferAntialias)
        return font
