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
from ..mapping import L2_AXIS, R2_AXIS, STICK_AXES, Mapping
from .pro_lock import ProLockOverlay


class MappingEditor(QWidget):
    upgrade_clicked = Signal()
    activate_clicked = Signal()
    # Emitted whenever the user selects a row in one of the three tables.
    # Main window forwards this to the right-hand inspector. Payload shape:
    #   { "kind": "button"|"axis"|"hat"|"trigger"|"stick"|"touchpad",
    #     "index": str, "midi": int, "label": str, "config": dataclass|None }
    selection_changed = Signal(dict)
    # Emitted after any config dataclass mutates so the caller can persist.
    mapping_changed = Signal()

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
        self._buttons_table.itemSelectionChanged.connect(
            lambda: self._emit_selection(self._buttons_table, "button")
        )
        v.addWidget(self._buttons_table)

        v.addWidget(self._section_label("AXES → CC"))
        self._axes_table = self._make_table(["Axis #", "MIDI CC"])
        self._axes_table.itemSelectionChanged.connect(
            lambda: self._emit_selection(self._axes_table, "axis")
        )
        v.addWidget(self._axes_table)

        v.addWidget(self._section_label("D-PAD → NOTES"))
        self._hats_table = self._make_table(["Direction", "MIDI Note"])
        self._hats_table.itemSelectionChanged.connect(
            lambda: self._emit_selection(self._hats_table, "hat")
        )
        v.addWidget(self._hats_table)

        v.addWidget(self._section_label("TOUCHPAD → CC"))
        self._touchpad_table = self._make_table(["Control", "Info"])
        self._touchpad_table.itemSelectionChanged.connect(
            lambda: self._emit_touchpad_selection()
        )
        v.addWidget(self._touchpad_table)

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
        tp = self._mapping.touchpad
        tp_info = f"x:{tp.x_cc} y:{tp.y_cc} | mode:{tp.mode}" if tp.enabled else "disabled"
        self._fill(self._touchpad_table, [("DualSense touchpad", tp_info)])

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

    def _emit_selection(self, table: QTableWidget, kind: str) -> None:
        """Forward a row-click into a selection payload the inspector can render.

        For axis rows that map to triggers (L2=4, R2=5) or sticks (0..3) we
        promote `kind` to "trigger" or "stick" and attach the corresponding
        config dataclass under the "config" key so the inspector can render a
        richer editor instead of the generic key-value view.
        """
        row = table.currentRow()
        if row < 0 or row >= table.rowCount():
            return
        idx_item = table.item(row, 0)
        midi_item = table.item(row, 1)
        if idx_item is None or midi_item is None:
            return
        idx = idx_item.text()
        midi = midi_item.text()
        channel = str(self._mapping.midi_channel + 1)

        # Determine whether this axis gets a richer editor.
        promoted_kind = kind
        config = None
        if kind == "axis":
            try:
                axis_index = int(idx)
            except (ValueError, TypeError):
                axis_index = -1

            if axis_index == L2_AXIS:
                promoted_kind = "trigger"
                config = self._mapping.l2_trigger
                label = "L2 Trigger"
            elif axis_index == R2_AXIS:
                promoted_kind = "trigger"
                config = self._mapping.r2_trigger
                label = "R2 Trigger"
            elif axis_index in STICK_AXES:
                promoted_kind = "stick"
                if axis_index in (0, 1):
                    config = self._mapping.left_stick
                    label = f"Left Stick  (axis {axis_index})"
                else:
                    config = self._mapping.right_stick
                    label = f"Right Stick  (axis {axis_index})"
            else:
                label = f"Axis {idx}"
        else:
            label_map = {"button": f"Button {idx}", "hat": f"D-pad {idx}"}
            label = label_map.get(kind, f"{kind} {idx}")

        payload: dict = {
            "kind": promoted_kind,
            "label": label,
            "index": idx,
            "midi": midi,
            "channel": channel,
        }
        if config is not None:
            payload["config"] = config

        self.selection_changed.emit(payload)

    def _emit_touchpad_selection(self) -> None:
        """Emit a touchpad payload so the inspector renders TouchpadConfig."""
        row = self._touchpad_table.currentRow()
        if row < 0:
            return
        payload: dict = {
            "kind": "touchpad",
            "label": "DualSense Touchpad",
            "config": self._mapping.touchpad,
        }
        self.selection_changed.emit(payload)
