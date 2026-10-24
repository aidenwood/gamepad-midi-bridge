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
import time
from datetime import datetime
from enum import Enum
from typing import Optional

from PySide6.QtCore import QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QVBoxLayout, QWidget,
)

from ..paths import config_path

from .panel_metrics import HEADER_MIN_PX, header_height_for

CONFIG_KEY = "midi_panel_open"


class _ClickableFrame(QFrame):
    """QFrame that emits ``clicked`` on bare-surface mouse-release.

    Doubles the toggle target so users don't have to hunt for the ▾ arrow.
    Child widgets (Clear, filter combo, ▾) consume their own clicks first.
    """
    clicked = Signal()

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class MidiFilter(Enum):
    """Filter categories for MIDI activity."""
    ALL = "All"
    SENT = "Sent only"
    RECEIVED = "Received only"
    NOTES = "Notes only"
    CCS = "CCs only"


BLINK_DECAY_S = 0.35


class ChannelBlinkers(QWidget):
    """Sixteen per-channel lamps that blink on outgoing MIDI.

    Lives in the panel HEADER, not the body, so it stays visible when the
    log is collapsed — the point is to confirm "my press reached MIDI"
    without opening a scrolling text log and reading timestamps.

    Notes light brighter than CCs: a stick sweep otherwise holds every lamp
    on and tells you nothing about button presses.
    """

    CELL_W = 13
    CELL_H = 13
    GAP = 2
    # Narrow-pane sizes. All sixteen lamps stay — shrinking them keeps the
    # "my press reached MIDI" answer visible at a phone-ish width, where
    # hiding them would remove the one indicator the header exists for.
    COMPACT_CELL_W = 6
    COMPACT_GAP = 1

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._stamps: dict = {}     # channel -> (time, is_note)
        self._compact = False
        self._apply_metrics()
        self.setToolTip(
            "MIDI channels 1-16. A lamp blinks when this app sends on that "
            "channel — bright for notes, dim for CCs.")
        # Only repaints while something is actually decaying.
        self._timer = QTimer(self)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self._tick)

    def _cell(self) -> tuple[int, int]:
        """(cell width, gap) for the current presentation."""
        if self._compact:
            return self.COMPACT_CELL_W, self.COMPACT_GAP
        return self.CELL_W, self.GAP

    def _apply_metrics(self) -> None:
        cell, gap = self._cell()
        self.setFixedSize(16 * cell + 15 * gap, self.CELL_H)

    def set_compact(self, compact: bool) -> None:
        """Shrink the lamps for a narrow pane. All sixteen stay visible."""
        compact = bool(compact)
        if compact == self._compact:
            return
        self._compact = compact
        self._apply_metrics()
        self.update()

    def blink(self, channel: int, is_note: bool) -> None:
        if not 0 <= channel <= 15:
            return
        self._stamps[channel] = (time.perf_counter(), is_note)
        if not self._timer.isActive():
            self._timer.start()

    def clear(self) -> None:
        self._stamps.clear()
        self._timer.stop()
        self.update()

    def _tick(self) -> None:
        now = time.perf_counter()
        self._stamps = {ch: v for ch, v in self._stamps.items()
                        if now - v[0] < BLINK_DECAY_S}
        if not self._stamps:
            self._timer.stop()
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        now = time.perf_counter()
        off = QColor("#1f232b")
        cell, gap = self._cell()
        for ch in range(16):
            x = ch * (cell + gap)
            rect = QRectF(x, 0, cell, self.CELL_H)
            stamp = self._stamps.get(ch)
            if stamp is None:
                colour = off
            else:
                t = max(0.0, 1.0 - (now - stamp[0]) / BLINK_DECAY_S)
                peak = QColor("#2dd4bf") if stamp[1] else QColor("#1d7f74")
                colour = QColor(
                    int(off.red() + (peak.red() - off.red()) * t),
                    int(off.green() + (peak.green() - off.green()) * t),
                    int(off.blue() + (peak.blue() - off.blue()) * t),
                )
            p.setPen(QPen(QColor("#24262d"), 1))
            p.setBrush(QBrush(colour))
            p.drawRoundedRect(rect, 2, 2)


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

    # Emitted when a row lands. MainWindow uses it to re-hug an auto-sized
    # bottom dock to the new content height; it throttles on its side,
    # because this fires on the MIDI hot path.
    content_grew = Signal()

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
        # Pin the header to the top. With the body hidden there is nothing
        # left that can expand, so QVBoxLayout centres the lone header in
        # whatever height it was given — which side-by-side panels now hit
        # whenever one is collapsed and its neighbour is open.
        outer.addStretch(0)

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

    def set_collapsed_silent(self, collapsed: bool) -> None:
        """Match collapse state to a live splitter drag WITHOUT emitting
        collapse_changed (which would snap-resize and undo the drag). Mirrors
        LogConsole.set_collapsed_silent — shows/hides the body to track the drag."""
        if collapsed == self._collapsed:
            return
        self._collapsed = collapsed
        self._apply_collapsed()
        _write_open_state(not self._collapsed)

    def is_collapsed(self) -> bool:
        return self._collapsed

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        """Floor is the header — a panel can always shrink to its own strip.

        Qt otherwise derives this from the QListWidget inside (~120 px even
        when empty), which beats the auto-sized dock's smaller request: the
        splitter hands over less than the panel insists on, and the header
        renders vertically clipped. Collapsing already proves a panel can
        live at header height, so that is the honest floor.
        """
        hint = super().minimumSizeHint()
        return QSize(hint.width(), min(hint.height(), self.header_height()))

    def content_height(self) -> int:
        """Height this panel would like, given what is actually in it.

        Collapsed or empty, that is the header alone — an empty log does not
        earn a slab of black. Otherwise it is the header plus the rows it
        holds, so the dock grows as messages arrive instead of reserving
        space for messages that may never come. The caller caps it.
        """
        header = self.header_height()
        if self._collapsed or self._visible_count == 0:
            return header
        row = self._list.sizeHintForRow(0)
        if row <= 0:
            row = 18
        margins = self._body.layout().contentsMargins()
        frame = self._list.frameWidth() * 2
        return (header + margins.top() + margins.bottom() + frame
                + row * self._visible_count)

    def set_compact(self, compact: bool) -> None:
        """Narrow-pane presentation of the header.

        The untouched header needs roughly 620 px — title + sixteen 13 px
        lamps + a 140 px filter combo + Clear + the toggle — which is wider
        than the whole window in a phone-shaped layout, so the pane could
        never shrink below it. Compact keeps every control reachable:
        the title abbreviates, the lamps shrink, and the filter moves into
        the Clear button's place as an icon-width combo.
        """
        compact = bool(compact)
        if compact == getattr(self, "_compact", None):
            return
        self._compact = compact
        self._header_title.setText("MIDI" if compact else "MIDI ACTIVITY")
        self._blinkers.set_compact(compact)
        self._filter_combo.setMaximumWidth(72 if compact else 140)
        # Clear keeps its slot and its action — it just loses the word. A
        # control that disappears at a window size is a control the user has
        # to resize the window to reach.
        self._clear_btn.setText("✕" if compact else "Clear")
        self._clear_btn.setToolTip("Clear the MIDI activity log")
        self.refresh_header_height()
        # Qt caches a layout's minimum size. Without invalidating it the
        # panel keeps reporting its 572 px full-header floor after
        # compacting, and the splitter refuses to give it anything less —
        # the compaction happens but buys no width at all.
        self._header_bar.layout().invalidate()
        if self.layout() is not None:
            self.layout().invalidate()
        self.updateGeometry()

    # ============================================================== layout

    def _build_header(self) -> QFrame:
        bar = _ClickableFrame()
        # No border-top — QSplitter handle above is the visual divider.
        # Styling lives in styles.qss → "MIDI ACTIVITY LOG PANEL".
        bar.setObjectName("MidiLogPanelHeader")
        bar.setAttribute(Qt.WA_StyledBackground, True)
        # Height is set at the END of this method from the populated
        # layout's own sizeHint — a hardcoded 36 clips the title once the
        # A+/A- buttons scale the app font. See panel_metrics.
        self._header_bar = bar
        bar.setCursor(Qt.PointingHandCursor)
        bar.clicked.connect(self.toggle_collapsed)
        h = QHBoxLayout(bar)
        h.setContentsMargins(12, 5, 8, 5)
        h.setSpacing(8)

        title = QLabel("MIDI ACTIVITY")
        title.setObjectName("MidiLogPanelTitle")
        title.setMinimumHeight(20)
        self._header_title = title
        h.addWidget(title)

        # Press blinkers sit next to the title, so a user can confirm MIDI is
        # actually leaving the app without expanding the log.
        self._blinkers = ChannelBlinkers()
        h.addSpacing(10)
        h.addWidget(self._blinkers, 0, Qt.AlignVCenter)

        h.addStretch(1)

        self._filter_combo = QComboBox()
        self._filter_combo.setObjectName("MidiLogPanelFilterCombo")
        self._filter_combo.setMaximumWidth(140)
        self._filter_combo.setFixedHeight(26)
        for f in MidiFilter:
            self._filter_combo.addItem(f.value, f)
        self._filter_combo.currentIndexChanged.connect(self._on_filter_changed)
        h.addWidget(self._filter_combo)

        clear_btn = QPushButton("Clear")
        clear_btn.setObjectName("MidiLogPanelClearButton")
        clear_btn.setFlat(True)
        clear_btn.setFixedHeight(26)
        clear_btn.clicked.connect(self._clear_all)
        self._clear_btn = clear_btn
        h.addWidget(clear_btn)

        self._toggle_btn = QPushButton("▾")
        self._toggle_btn.setObjectName("MidiLogPanelToggleButton")
        self._toggle_btn.setFlat(True)
        self._toggle_btn.setFixedSize(28, 26)
        self._toggle_btn.clicked.connect(self.toggle_collapsed)
        h.addWidget(self._toggle_btn)

        bar.setFixedHeight(header_height_for(title, h))
        return bar

    def _build_body(self) -> QWidget:
        container = QWidget()
        v = QVBoxLayout(container)
        v.setContentsMargins(8, 4, 8, 8)
        v.setSpacing(0)

        self._list = QListWidget()
        self._list.setObjectName("MidiLogPanelList")
        # No minimum height. The dock is auto-sized from content
        # (MainWindow._bottom_wanted_height), so an EMPTY list must be able
        # to take zero height — an 80 px floor on an empty log is exactly
        # the slab of black the auto-height exists to remove, and when the
        # dock honours the smaller request anyway the header gets squashed
        # and clipped instead. The parent QSplitter owns the actual size.
        self._list.setMinimumHeight(0)
        self._list.itemSelectionChanged.connect(self._on_selection_changed)
        v.addWidget(self._list, 1)

        self._user_scrolled = False
        self._list.verticalScrollBar().valueChanged.connect(self._on_scroll_changed)

        self._body = container
        return container

    def header_height(self) -> int:
        """Current header height in px — the collapsed height of this panel.

        MainWindow sizes the bottom splitter from this instead of a hardcoded
        36 so the header can never be clipped at a larger font scale.
        """
        bar = getattr(self, "_header_bar", None)
        return bar.height() if bar is not None else HEADER_MIN_PX

    def refresh_header_height(self) -> None:
        """Re-measure after a font-scale change so the header still fits."""
        bar = getattr(self, "_header_bar", None)
        title = getattr(self, "_header_title", None)
        if bar is not None and title is not None:
            bar.setFixedHeight(header_height_for(title, bar.layout()))
        self.setMinimumHeight(self.header_height())

    def _apply_collapsed(self) -> None:
        # NOTE: do NOT self-impose ``setMaximumHeight`` here. The parent
        # ``QSplitter`` owns sizing — see ``MainWindow._set_bottom_panel_sizes``.
        # Self-resizing fights the splitter and produces drag flicker.
        self._toggle_btn.setText("▴" if self._collapsed else "▾")
        self._sync_body_visibility()

    def _sync_body_visibility(self) -> None:
        """An open panel with nothing in it shows no body.

        This is NOT collapsing — the ▾ state is the user's choice and stays
        untouched. It stops an empty list painting a slab of black, and at
        the auto-sized dock's tight heights it stops that slab being laid
        out ON TOP of the header strip, which read as a clipped header.
        """
        self._body.setVisible(not self._collapsed and self._visible_count > 0)

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
        # Blink before the row is filtered — the lamp reports what was SENT,
        # not what the current filter happens to show.
        self._blinkers.blink(channel, "NOTE-ON" in status_label.upper())
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

        # First row in an empty panel brings the body back.
        self._sync_body_visibility()

        # Auto-scroll to bottom unless user scrolled.
        if not self._user_scrolled:
            self._list.scrollToBottom()

        # Tell the dock its content grew, so an auto-sized dock can follow.
        # Throttled by the listener, not here — this is a hot path.
        self.content_grew.emit()

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
        # A filter can empty the visible list without emptying the panel.
        self._sync_body_visibility()
        self.content_grew.emit()
        if not self._user_scrolled:
            self._list.scrollToBottom()

    def _clear_all(self) -> None:
        """Clear all rows."""
        self._all_rows.clear()
        self._list.clear()
        self._visible_count = 0
        self._user_scrolled = False
        self._blinkers.clear()
        # Cleared means empty: drop the body and let the dock shrink back.
        self._sync_body_visibility()
        self.content_grew.emit()

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
