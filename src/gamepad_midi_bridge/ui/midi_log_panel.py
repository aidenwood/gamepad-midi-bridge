"""MIDI Activity Log Panel — scrolling list of every MIDI message sent/received.

Shows timestamped, colour-coded bytes with diff highlighting to help producers
debug routing and controller events. Separate from the general log_console which
mixes app messages with MIDI events.

Filter dropdown: All / Sent only / Received only / Notes only / CCs only.
Auto-scroll to bottom unless user manually scrolled.
Capped at 500 rows (drops oldest).

Collapsible header with ▾/▴ toggle mirrors LogConsole exactly. Open state
persists across launches via the config file (key ``midi_panel_open``).
"""
from __future__ import annotations

import json
from datetime import datetime
from enum import Enum
from typing import Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QVBoxLayout, QWidget,
)

from ..paths import config_path

CONFIG_KEY = "midi_panel_open"


class MidiFilter(Enum):
    """Filter categories for MIDI activity."""
    ALL = "All"
    SENT = "Sent only"
    RECEIVED = "Received only"
    NOTES = "Notes only"
    CCS = "CCs only"


class MidiLogPanel(QWidget):
    """Scrolling MIDI activity log with filtering and auto-cap.

    Collapsible: header strip with ▾/▴ toggle mirrors LogConsole. Splitter
    sizing in MainWindow listens to :pyattr:`collapse_changed` so the bottom
    dock animates open/closed cleanly without two systems fighting each other.
    """

    MAX_ROWS = 500

    # Emitted whenever the panel collapses or expands. Payload is the new
    # ``is_collapsed()`` state (True = collapsed). MainWindow uses this to
    # recompute QSplitter sizes (see :pymeth:`MainWindow._set_bottom_panel_sizes`).
    collapse_changed = Signal(bool)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._current_filter = MidiFilter.ALL
        self._all_rows: list[tuple[MidiFilter, str]] = []  # (filter_tag, formatted_text)
        self._visible_count = 0
        self._collapsed = not _read_open_state()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._build_header())
        outer.addWidget(self._build_body(), 1)

        self._apply_collapsed()

    # ============================================================== public API

    def toggle_collapsed(self) -> None:
        self._collapsed = not self._collapsed
        self._apply_collapsed()
        _write_open_state(not self._collapsed)
        self.collapse_changed.emit(self._collapsed)

    def set_collapsed(self, collapsed: bool) -> None:
        if collapsed == self._collapsed:
            return
        self._collapsed = collapsed
        self._apply_collapsed()
        self.collapse_changed.emit(self._collapsed)

    def is_collapsed(self) -> bool:
        return self._collapsed

    # ============================================================== layout

    def _build_header(self) -> QFrame:
        bar = QFrame()
        # No border-top — QSplitter handle above is the visual divider.
        bar.setStyleSheet("background-color: #16181d;")
        bar.setFixedHeight(48)
        h = QHBoxLayout(bar)
        h.setContentsMargins(14, 11, 10, 11)
        h.setSpacing(8)

        title = QLabel("MIDI ACTIVITY")
        title.setMinimumHeight(20)
        title.setStyleSheet(
            "color: #8a9099; font-size: 10px; font-weight: 700; "
            "letter-spacing: 1px;"
        )
        h.addWidget(title)
        h.addStretch(1)

        self._filter_combo = QComboBox()
        self._filter_combo.setMaximumWidth(140)
        self._filter_combo.setFixedHeight(26)
        self._filter_combo.setStyleSheet(
            "QComboBox { color: #c2c6cc; background-color: #0e0f12; "
            "border: 1px solid #2c313b; border-radius: 3px; "
            "padding: 1px 6px; font-size: 11px; }"
            "QComboBox::drop-down { border: none; }"
        )
        for f in MidiFilter:
            self._filter_combo.addItem(f.value, f)
        self._filter_combo.currentIndexChanged.connect(self._on_filter_changed)
        h.addWidget(self._filter_combo)

        clear_btn = QPushButton("Clear")
        clear_btn.setFlat(True)
        clear_btn.setFixedHeight(26)
        clear_btn.setStyleSheet(
            "color: #8a9099; font-size: 11px; padding: 2px 8px;"
        )
        clear_btn.clicked.connect(self._clear_all)
        h.addWidget(clear_btn)

        self._toggle_btn = QPushButton("▾")
        self._toggle_btn.setFlat(True)
        self._toggle_btn.setFixedSize(28, 26)
        self._toggle_btn.setStyleSheet(
            "color: #c2c6cc; font-size: 14px; padding: 0; margin: 0;"
        )
        self._toggle_btn.clicked.connect(self.toggle_collapsed)
        h.addWidget(self._toggle_btn)

        return bar

    def _build_body(self) -> QWidget:
        container = QWidget()
        v = QVBoxLayout(container)
        v.setContentsMargins(8, 4, 8, 8)
        v.setSpacing(0)

        self._list = QListWidget()
        self._list.setStyleSheet(
            "QListWidget { background-color: #0e0f12; color: #c2c6cc; "
            "border: none; selection-background-color: #1f3a36; }"
        )
        # Minimum height keeps the list scrollable when fully expanded;
        # the parent QSplitter owns the actual size.
        self._list.setMinimumHeight(80)
        self._list.itemSelectionChanged.connect(self._on_selection_changed)
        v.addWidget(self._list, 1)

        self._user_scrolled = False
        self._list.verticalScrollBar().valueChanged.connect(self._on_scroll_changed)

        self._body = container
        return container

    def _apply_collapsed(self) -> None:
        # NOTE: do NOT self-impose ``setMaximumHeight`` here. The parent
        # ``QSplitter`` owns sizing — see ``MainWindow._set_bottom_panel_sizes``.
        # Self-resizing fights the splitter and produces drag flicker.
        self._toggle_btn.setText("▴" if self._collapsed else "▾")
        self._body.setVisible(not self._collapsed)

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


# ----------------------------------------------------------------- persistence


def _read_open_state() -> bool:
    """Was the MIDI panel open last time? Default closed so first launch is calm."""
    path = config_path()
    if not path.exists():
        return False
    try:
        return bool(json.loads(path.read_text(encoding="utf-8")).get(CONFIG_KEY, False))
    except Exception:
        return False


def _write_open_state(open_: bool) -> None:
    path = config_path()
    data: dict = {}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    data[CONFIG_KEY] = bool(open_)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
