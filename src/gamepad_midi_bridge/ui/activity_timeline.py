"""ActivityTimeline widget — scrollable session event log.

Renders a QListWidget row per ``ActivityEvent`` with:
  - timestamp (HH:MM:SS)
  - coloured severity icon  (● info=teal, ⚠ warning=amber, ✕ error=red)
  - message text

Auto-scrolls to the bottom on new events; the user can scroll up freely to
review history.  A "Clear log" button empties the ring buffer.
"""
from __future__ import annotations

import datetime
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..activity_log import ActivityEvent, log as _log

# Palette ── matches the rest of the Visualise tab.
_BG        = "#13151a"
_ITEM_BG   = "#1a1d24"
_TEXT      = "#d0d4dc"
_DIM       = "#5a606b"
_TEAL      = "#2dd4bf"
_AMBER     = "#f59e0b"
_RED       = "#f87171"

_SEVERITY_ICON: dict[str, str] = {
    "info":    "●",
    "warning": "⚠",
    "error":   "✕",
}
_SEVERITY_COLOR: dict[str, str] = {
    "info":    _TEAL,
    "warning": _AMBER,
    "error":   _RED,
}


def _ts(epoch: float) -> str:
    return datetime.datetime.fromtimestamp(epoch).strftime("%H:%M:%S")


def _make_item(event: ActivityEvent) -> QListWidgetItem:
    icon  = _SEVERITY_ICON.get(event.severity, "●")
    color = _SEVERITY_COLOR.get(event.severity, _TEAL)
    text  = f"{_ts(event.timestamp)}  {icon}  {event.message}"
    item  = QListWidgetItem(text)
    item.setForeground(QColor(color if event.severity != "info" else _TEXT))
    item.setBackground(QColor(_ITEM_BG))
    item.setFont(QFont("monospace", 10))
    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
    return item


class ActivityTimeline(QWidget):
    """Scrollable timeline of session events backed by the global ActivityLog.

    Wire it up by connecting ``log().signaller.activity_log_updated`` to
    ``_refresh``, which ``attach_to_log()`` does automatically.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._auto_scroll = True   # flip False while user scrolls up
        self._build_ui()
        self.attach_to_log()

    # ---------------------------------------------------------------- UI

    def _build_ui(self) -> None:
        self.setStyleSheet(f"background-color: {_BG};")
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 8)
        root.setSpacing(8)

        # Header row
        header = QHBoxLayout()
        title = QLabel("SESSION TIMELINE")
        title.setStyleSheet(
            "color: #8a9099; font-size: 10px; font-weight: 700; letter-spacing: 1px;"
        )
        header.addWidget(title)
        header.addStretch()

        self._clear_btn = QPushButton("Clear log")
        self._clear_btn.setFixedHeight(24)
        self._clear_btn.setStyleSheet(
            "QPushButton { background: #1f232b; color: #8a9099; border: 1px solid #2c313b;"
            "border-radius: 4px; font-size: 10px; padding: 0 10px; }"
            "QPushButton:hover { background: #262b35; color: #d0d4dc; }"
        )
        self._clear_btn.clicked.connect(self._on_clear)
        header.addWidget(self._clear_btn)
        root.addLayout(header)

        # List
        self._list = QListWidget()
        self._list.setStyleSheet(
            f"QListWidget {{ background: {_BG}; border: none; }}"
            f"QListWidget::item {{ background: {_ITEM_BG}; border-radius: 4px;"
            f"  padding: 4px 8px; margin-bottom: 2px; }}"
            f"QListWidget::item:selected {{ background: #24272f; }}"
        )
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # Track user scroll to suppress auto-scroll when looking back.
        self._list.verticalScrollBar().valueChanged.connect(self._on_scroll)
        root.addWidget(self._list, 1)

        # Empty-state label (shown when list is empty)
        self._empty_label = QLabel("No events yet — start the bridge to begin recording.")
        self._empty_label.setAlignment(Qt.AlignCenter)
        self._empty_label.setStyleSheet(f"color: {_DIM}; font-size: 11px;")
        root.addWidget(self._empty_label)
        self._empty_label.setVisible(True)

    # ---------------------------------------------------------------- wiring

    def attach_to_log(self) -> None:
        """Connect to the global ActivityLog singleton's update signal."""
        _log().signaller.activity_log_updated.connect(self._refresh)
        self._refresh()

    # ---------------------------------------------------------------- slots

    def _refresh(self) -> None:
        """Repopulate the list from the current log snapshot."""
        events = _log().snapshot()
        self._empty_label.setVisible(len(events) == 0)
        self._list.setVisible(len(events) > 0)

        # Cheapest approach: rebuild only if count changed; otherwise append.
        # Full rebuild on clear (list emptied externally).
        current = self._list.count()
        if current > len(events):
            # Clear was called or ring buffer wrapped in an unusual way — rebuild.
            self._list.clear()
            for e in events:
                self._list.addItem(_make_item(e))
        else:
            # Append only new tail items.
            for e in events[current:]:
                self._list.addItem(_make_item(e))

        if self._auto_scroll and self._list.count() > 0:
            self._list.scrollToBottom()

    def _on_scroll(self, value: int) -> None:
        """Disable auto-scroll when user scrolls up; re-enable at bottom."""
        sb = self._list.verticalScrollBar()
        self._auto_scroll = (value == sb.maximum())

    def _on_clear(self) -> None:
        _log().clear()   # triggers activity_log_updated → _refresh
        self._auto_scroll = True
