"""Mapping editor tab. Pro feature — shows the current mapping as a table.

Visible in free mode behind a ProLockOverlay so users can see what they're missing.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout, QGroupBox, QHeaderView, QLabel, QPushButton,
    QSpinBox, QStackedLayout, QTableWidget, QTableWidgetItem, QVBoxLayout,
    QWidget,
)

from .. import presets as _presets

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
        self._worker = None  # set via set_worker() after construction
        # Track the last selected (table, kind) so set_mapping can re-emit selection.
        self._last_selected_table: Optional[QTableWidget] = None
        self._last_selected_kind: Optional[str] = None

        # Stacked: actual editor underneath, lock overlay on top when not Pro.
        self._stack = QStackedLayout(self)

        content = QWidget()
        v = QVBoxLayout(content)
        v.setContentsMargins(20, 20, 20, 20)
        v.setSpacing(12)

        v.addWidget(self._section_label("BUTTONS → NOTES"))
        self._buttons_table = self._make_table(["Button #", "MIDI Note"], capture_kind="button")
        self._buttons_table.itemSelectionChanged.connect(
            lambda: self._emit_selection(self._buttons_table, "button")
        )
        v.addWidget(self._buttons_table)

        v.addWidget(self._section_label("AXES → CC"))
        self._axes_table = self._make_table(["Axis #", "MIDI CC"], capture_kind="axis")
        self._axes_table.itemSelectionChanged.connect(
            lambda: self._emit_selection(self._axes_table, "axis")
        )
        v.addWidget(self._axes_table)

        v.addWidget(self._section_label("D-PAD → NOTES"))
        self._hats_table = self._make_table(["Direction", "MIDI Note"], capture_kind="hat")
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

        v.addWidget(self._section_label("SHIFT LAYER (Pro)"))
        self._shift_group = self._make_shift_group()
        v.addWidget(self._shift_group)

        v.addWidget(self._section_label("A/B COMPARE"))
        self._ab_group = self._make_ab_group()
        v.addWidget(self._ab_group)

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

    def set_worker(self, worker) -> None:
        """Provide a reference to the running BridgeWorker so the Capture
        buttons can listen to controller events.  Safe to call before or after
        construction; ``None`` is accepted (Capture buttons will open the dialog
        but never auto-confirm)."""
        self._worker = worker

    def set_mapping(self, mapping: Mapping) -> None:
        self._mapping = mapping
        self._refresh_tables()
        self._refresh_shift_group()
        self._refresh_ab_group()
        # Re-emit selection if a row was previously selected so the inspector refreshes.
        if self._last_selected_table is not None and self._last_selected_kind is not None:
            self._emit_selection(self._last_selected_table, self._last_selected_kind)

    def refresh_lock(self) -> None:
        # Show overlay (index 1) if not Pro, editor (index 0) if Pro.
        self._stack.setCurrentIndex(0 if is_pro() else 1)

    # ------------------------------------------------------------------ helpers

    def _make_shift_group(self) -> QGroupBox:
        """Build the Shift Layer inline form group."""
        box = QGroupBox()
        box.setFlat(True)
        form = QFormLayout(box)
        form.setContentsMargins(0, 4, 0, 4)
        form.setSpacing(6)

        sl = self._mapping.shift_layer

        self._shift_enabled_cb = QCheckBox()
        self._shift_enabled_cb.setChecked(sl.enabled)
        self._shift_enabled_cb.toggled.connect(self._on_shift_enabled_changed)
        form.addRow("Enabled", self._shift_enabled_cb)

        self._shift_button_spin = QSpinBox()
        self._shift_button_spin.setRange(-1, 31)
        self._shift_button_spin.setSpecialValueText("(unset)")
        self._shift_button_spin.setValue(sl.shift_button)
        self._shift_button_spin.valueChanged.connect(self._on_shift_button_changed)
        form.addRow("Shift Button", self._shift_button_spin)

        hint = QLabel("Held button swaps the mapping; otherwise base mapping plays")
        hint.setStyleSheet("color: #8a9099; font-size: 11px;")
        hint.setWordWrap(True)
        form.addRow(hint)

        return box

    def _refresh_shift_group(self) -> None:
        """Sync the shift layer widgets to the current mapping (called on set_mapping)."""
        sl = self._mapping.shift_layer
        # Block signals so programmatic updates don't trigger on_change callbacks.
        self._shift_enabled_cb.blockSignals(True)
        self._shift_button_spin.blockSignals(True)
        self._shift_enabled_cb.setChecked(sl.enabled)
        self._shift_button_spin.setValue(sl.shift_button)
        self._shift_enabled_cb.blockSignals(False)
        self._shift_button_spin.blockSignals(False)

    def _on_shift_enabled_changed(self, checked: bool) -> None:
        self._mapping.shift_layer.enabled = checked
        self.mapping_changed.emit()

    def _on_shift_button_changed(self, value: int) -> None:
        self._mapping.shift_layer.shift_button = value
        self.mapping_changed.emit()

    # ---------------------------------------------------------------- A/B compare

    def _make_ab_group(self) -> QGroupBox:
        """Build the A/B Compare inline form group."""
        box = QGroupBox()
        box.setFlat(True)
        form = QFormLayout(box)
        form.setContentsMargins(0, 4, 0, 4)
        form.setSpacing(6)

        m = self._mapping

        self._ab_enabled_cb = QCheckBox()
        self._ab_enabled_cb.setChecked(m.ab_compare_enabled)
        self._ab_enabled_cb.toggled.connect(self._on_ab_enabled_changed)
        form.addRow("Enabled", self._ab_enabled_cb)

        self._ab_button_spin = QSpinBox()
        self._ab_button_spin.setRange(-1, 31)
        self._ab_button_spin.setSpecialValueText("(unset)")
        self._ab_button_spin.setValue(m.ab_compare_button)
        self._ab_button_spin.valueChanged.connect(self._on_ab_button_changed)
        form.addRow("B Button", self._ab_button_spin)

        self._ab_preset_combo = QComboBox()
        self._ab_preset_combo.addItem("(none)", None)
        for slug in _presets.list_presets():
            self._ab_preset_combo.addItem(slug, slug)
        current_slug = m.ab_b_preset_slug or ""
        idx = self._ab_preset_combo.findData(current_slug) if current_slug else 0
        self._ab_preset_combo.setCurrentIndex(max(0, idx))
        self._ab_preset_combo.currentIndexChanged.connect(self._on_ab_preset_changed)
        form.addRow("B Preset", self._ab_preset_combo)

        hint = QLabel("Hold B button to swap to the B preset; release to return to A")
        hint.setStyleSheet("color: #8a9099; font-size: 11px;")
        hint.setWordWrap(True)
        form.addRow(hint)

        return box

    def _refresh_ab_group(self) -> None:
        """Sync A/B Compare widgets to the current mapping (called on set_mapping)."""
        m = self._mapping
        self._ab_enabled_cb.blockSignals(True)
        self._ab_button_spin.blockSignals(True)
        self._ab_preset_combo.blockSignals(True)

        self._ab_enabled_cb.setChecked(m.ab_compare_enabled)
        self._ab_button_spin.setValue(m.ab_compare_button)

        # Repopulate combo in case presets changed since widget was built.
        self._ab_preset_combo.clear()
        self._ab_preset_combo.addItem("(none)", None)
        for slug in _presets.list_presets():
            self._ab_preset_combo.addItem(slug, slug)
        current_slug = m.ab_b_preset_slug or ""
        idx = self._ab_preset_combo.findData(current_slug) if current_slug else 0
        self._ab_preset_combo.setCurrentIndex(max(0, idx))

        self._ab_enabled_cb.blockSignals(False)
        self._ab_button_spin.blockSignals(False)
        self._ab_preset_combo.blockSignals(False)

    def _on_ab_enabled_changed(self, checked: bool) -> None:
        self._mapping.ab_compare_enabled = checked
        self.mapping_changed.emit()

    def _on_ab_button_changed(self, value: int) -> None:
        self._mapping.ab_compare_button = value
        self.mapping_changed.emit()

    def _on_ab_preset_changed(self, _index: int) -> None:
        slug = self._ab_preset_combo.currentData()
        self._mapping.ab_b_preset_slug = slug or None
        self.mapping_changed.emit()

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            "color: #8a9099; font-size: 11px; font-weight: 700; "
            "letter-spacing: 1px; padding-top: 8px;"
        )
        return lbl

    def _make_table(self, headers: list, capture_kind: str = "") -> QTableWidget:
        # When capture_kind is given, add a read-only "Capture" column.
        all_headers = headers + ["Capture"] if capture_kind else headers
        t = QTableWidget(0, len(all_headers))
        t.setHorizontalHeaderLabels(all_headers)
        if capture_kind:
            # Data columns stretch equally; capture column stays narrow.
            hdr = t.horizontalHeader()
            for col in range(len(headers)):
                hdr.setSectionResizeMode(col, QHeaderView.Stretch)
            hdr.setSectionResizeMode(len(headers), QHeaderView.ResizeToContents)
        else:
            t.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        t.verticalHeader().setVisible(False)
        t.setAlternatingRowColors(False)
        t.setEditTriggers(QTableWidget.AllEditTriggers)
        t.setSelectionBehavior(QTableWidget.SelectRows)
        t.setShowGrid(False)
        if capture_kind:
            # Store kind on the widget so _fill can create the right buttons.
            t.setProperty("capture_kind", capture_kind)
        return t

    def _refresh_tables(self) -> None:
        self._fill(self._buttons_table, [(str(k), str(v)) for k, v in sorted(self._mapping.buttons.items())])
        self._fill(self._axes_table, [(str(k), str(v)) for k, v in sorted(self._mapping.axes.items())])
        self._fill(self._hats_table, [(k, str(v)) for k, v in self._mapping.hats.items()])
        tp = self._mapping.touchpad
        tp_info = f"x:{tp.x_cc} y:{tp.y_cc} | mode:{tp.mode}" if tp.enabled else "disabled"
        self._fill(self._touchpad_table, [("DualSense touchpad", tp_info)])

    def _fill(self, table: QTableWidget, rows: list) -> None:
        capture_kind = table.property("capture_kind") or ""
        table.setRowCount(len(rows))
        for r, (a, b) in enumerate(rows):
            ai = QTableWidgetItem(a)
            ai.setFlags(ai.flags() & ~Qt.ItemIsEditable)
            ai.setTextAlignment(Qt.AlignCenter)
            table.setItem(r, 0, ai)
            bi = QTableWidgetItem(b)
            bi.setTextAlignment(Qt.AlignCenter)
            table.setItem(r, 1, bi)
            if capture_kind:
                btn = QPushButton("⊙")
                btn.setToolTip("Press a controller input to assign this row")
                btn.setFixedSize(28, 22)
                btn.setStyleSheet(
                    "QPushButton { font-size: 11px; padding: 0; border-radius: 4px; "
                    "background: #1c1e25; color: #8a9099; border: 1px solid #2c313b; }"
                    "QPushButton:hover { background: #252830; color: #f5f7fa; }"
                )
                btn.clicked.connect(
                    lambda _checked, row=r, kind=capture_kind, tbl=table:
                    self._on_capture_clicked(tbl, row, kind)
                )
                table.setCellWidget(r, 2, btn)

    def _on_capture_clicked(self, table: QTableWidget, row: int, kind: str) -> None:
        """Open CaptureDialog; on accept, update the row index and mapping dict."""
        from .capture_dialog import CaptureDialog
        dlg = CaptureDialog(self._worker, kind, parent=self)
        if dlg.exec() != CaptureDialog.Accepted:
            return
        new_index = dlg.captured_index
        if new_index is None:
            return

        item = table.item(row, 0)
        if item is None:
            return
        old_index_str = item.text()
        item.setText(str(new_index))

        if kind == "button":
            try:
                old_key = int(old_index_str)
            except (ValueError, TypeError):
                return
            value = self._mapping.buttons.pop(old_key, 0)
            self._mapping.buttons[int(new_index)] = value
        elif kind == "axis":
            try:
                old_key = int(old_index_str)
            except (ValueError, TypeError):
                return
            value = self._mapping.axes.pop(old_key, 0)
            self._mapping.axes[int(new_index)] = value
        elif kind == "hat":
            value = self._mapping.hats.pop(old_index_str, 0)
            self._mapping.hats[str(new_index)] = value

        self.mapping_changed.emit()

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
        # Track this selection for re-emission on set_mapping.
        self._last_selected_table = table
        self._last_selected_kind = kind
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
        # Wire callback so renderers emit mapping_changed when they mutate.
        payload["on_change"] = self.mapping_changed.emit

        self.selection_changed.emit(payload)

    def _emit_touchpad_selection(self) -> None:
        """Emit a touchpad payload so the inspector renders TouchpadConfig."""
        row = self._touchpad_table.currentRow()
        if row < 0:
            return
        # Track this selection for re-emission on set_mapping.
        self._last_selected_table = self._touchpad_table
        self._last_selected_kind = "touchpad"
        payload: dict = {
            "kind": "touchpad",
            "label": "DualSense Touchpad",
            "config": self._mapping.touchpad,
            "on_change": self.mapping_changed.emit,
        }
        self.selection_changed.emit(payload)
