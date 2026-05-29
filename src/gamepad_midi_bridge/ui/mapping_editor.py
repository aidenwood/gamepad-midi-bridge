"""Mapping editor tab. Pro feature — shows the current mapping as a table.

Visible in free mode behind a ProLockOverlay so users can see what they're missing.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal, QSettings
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout, QFrame, QGroupBox, QHeaderView,
    QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QSpinBox, QStackedLayout, QTableWidget, QTableWidgetItem, QVBoxLayout,
    QWidget,
)

from .. import presets as _presets

from ..license import is_pro
from ..mapping import L2_AXIS, R2_AXIS, STICK_AXES, Mapping
from ..scales import SCALES
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

        # ── Onboarding tip (feature #24) ──
        self._tip_dismissed = False
        # Load dismissal state from config if available
        settings = QSettings()
        self._tip_dismissed = bool(settings.value("mapping_editor_tip_dismissed", False))
        
        if not self._tip_dismissed:
            tip_strip = QWidget()
            # Style belongs on the widget, not on its layout — QHBoxLayout
            # has no setStyleSheet method.
            tip_strip.setStyleSheet("background: #1c2d44; border-radius: 4px;")
            tip_layout = QHBoxLayout(tip_strip)
            tip_layout.setContentsMargins(10, 8, 10, 8)
            tip_layout.setSpacing(8)
            
            tip_icon = QLabel("💡")
            tip_icon.setStyleSheet("font-size: 16px; color: #3b82f6;")
            tip_layout.addWidget(tip_icon)
            
            tip_text = QLabel("Click any row to edit its config in the right panel. 4 trigger modes available — try Latch for toggle-style triggers.")
            tip_text.setStyleSheet("color: #93c5fd; font-size: 11px;")
            tip_text.setWordWrap(True)
            tip_layout.addWidget(tip_text, 1)
            
            def _dismiss_tip() -> None:
                self._tip_dismissed = True
                settings.setValue("mapping_editor_tip_dismissed", True)
                tip_strip.setVisible(False)
            
            close_btn = QPushButton("×")
            close_btn.setStyleSheet(
                "color: #93c5fd; border: none; background: transparent; "
                "font-size: 16px; padding: 0; min-width: 20px;"
            )
            close_btn.setFlat(True)
            close_btn.clicked.connect(_dismiss_tip)
            tip_layout.addWidget(close_btn)
            
            v.addWidget(tip_strip)

        # ── Port name override (feature #23) ──
        v.addWidget(self._section_label("MIDI PORT"))
        port_row = QWidget()
        port_layout = QHBoxLayout(port_row)
        port_layout.setContentsMargins(0, 0, 0, 0)
        port_layout.setSpacing(6)
        port_layout.addWidget(QLabel("Override port name:"))
        self._port_name_input = QLineEdit()
        self._port_name_input.setPlaceholderText("Leave empty for default")
        if self._mapping.port_name_override:
            self._port_name_input.setText(self._mapping.port_name_override)
        def _on_port_name_changed(text: str) -> None:
            self._mapping.port_name_override = text or None
            self.mapping_changed.emit()
        self._port_name_input.textChanged.connect(_on_port_name_changed)
        port_layout.addWidget(self._port_name_input, 1)
        v.addWidget(port_row)
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet('color: #1c1e25;')
        v.addWidget(line)


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

        v.addWidget(self._section_label("CORNER SCALE QUANTIZE (Pro)"))
        self._scale_group_left = self._make_scale_group("Left Stick", left=True)
        v.addWidget(self._scale_group_left)
        self._scale_group_right = self._make_scale_group("Right Stick", left=False)
        v.addWidget(self._scale_group_right)

        v.addWidget(self._section_label("PROGRAM CHANGE → PRESET"))
        self._pc_group = self._make_pc_group()
        v.addWidget(self._pc_group)

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
        self._refresh_scale_group(self._scale_group_left, left=True)
        self._refresh_scale_group(self._scale_group_right, left=False)
        self._refresh_pc_group()
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

    # ---------------------------------------------------------------- scale quantize

    def _make_scale_group(self, title: str, left: bool) -> QGroupBox:
        """Build the Scale Quantize inline form group for one stick."""
        box = QGroupBox(title)
        box.setFlat(True)
        form = QFormLayout(box)
        form.setContentsMargins(0, 4, 0, 4)
        form.setSpacing(6)

        cfg = self._mapping.left_stick_corners if left else self._mapping.right_stick_corners

        enabled_cb = QCheckBox()
        enabled_cb.setChecked(cfg.scale_quantize_enabled)
        enabled_cb.toggled.connect(lambda v, l=left: self._on_scale_enabled(v, l))
        form.addRow("Scale Quantize", enabled_cb)

        root_spin = QSpinBox()
        root_spin.setRange(0, 127)
        root_spin.setValue(cfg.scale_root)
        root_spin.setToolTip("Root note (0=C-1 … 60=C4 … 127=G9)")
        root_spin.valueChanged.connect(lambda v, l=left: self._on_scale_root(v, l))
        form.addRow("Root Note", root_spin)

        scale_combo = QComboBox()
        for name in sorted(SCALES.keys()):
            scale_combo.addItem(name, name)
        current_idx = scale_combo.findData(cfg.scale_name)
        scale_combo.setCurrentIndex(max(0, current_idx))
        scale_combo.currentIndexChanged.connect(lambda _i, l=left, c=scale_combo: self._on_scale_name(c.currentData(), l))
        form.addRow("Scale", scale_combo)

        hint = QLabel("Sectors play scale degrees in ascending pitch; wraps at octave boundary")
        hint.setStyleSheet("color: #8a9099; font-size: 11px;")
        hint.setWordWrap(True)
        form.addRow(hint)

        # Stash widget refs so _refresh can update them.
        box.setProperty("_sq_enabled_cb", enabled_cb)
        box.setProperty("_sq_root_spin", root_spin)
        box.setProperty("_sq_scale_combo", scale_combo)
        box.setProperty("_sq_left", left)
        return box

    def _refresh_scale_group(self, box: QGroupBox, left: bool) -> None:
        """Sync scale quantize widgets to the current mapping."""
        cfg = self._mapping.left_stick_corners if left else self._mapping.right_stick_corners
        enabled_cb: QCheckBox = box.property("_sq_enabled_cb")
        root_spin: QSpinBox = box.property("_sq_root_spin")
        scale_combo: QComboBox = box.property("_sq_scale_combo")
        if enabled_cb is None or root_spin is None or scale_combo is None:
            return
        enabled_cb.blockSignals(True)
        root_spin.blockSignals(True)
        scale_combo.blockSignals(True)
        enabled_cb.setChecked(cfg.scale_quantize_enabled)
        root_spin.setValue(cfg.scale_root)
        idx = scale_combo.findData(cfg.scale_name)
        scale_combo.setCurrentIndex(max(0, idx))
        enabled_cb.blockSignals(False)
        root_spin.blockSignals(False)
        scale_combo.blockSignals(False)

    def _on_scale_enabled(self, value: bool, left: bool) -> None:
        cfg = self._mapping.left_stick_corners if left else self._mapping.right_stick_corners
        cfg.scale_quantize_enabled = value
        self.mapping_changed.emit()

    def _on_scale_root(self, value: int, left: bool) -> None:
        cfg = self._mapping.left_stick_corners if left else self._mapping.right_stick_corners
        cfg.scale_root = max(0, min(127, value))
        self.mapping_changed.emit()

    def _on_scale_name(self, name: str, left: bool) -> None:
        cfg = self._mapping.left_stick_corners if left else self._mapping.right_stick_corners
        cfg.scale_name = name or "major"
        self.mapping_changed.emit()

    # ---------------------------------------------------------------- program change

    def _make_pc_group(self) -> QGroupBox:
        """Build the Program Change -> Preset inline form group."""
        box = QGroupBox()
        box.setFlat(True)
        form = QFormLayout(box)
        form.setContentsMargins(0, 4, 0, 4)
        form.setSpacing(6)

        cfg = self._mapping.program_change

        self._pc_enabled_cb = QCheckBox()
        self._pc_enabled_cb.setChecked(cfg.enabled)
        self._pc_enabled_cb.toggled.connect(self._on_pc_enabled_changed)
        form.addRow("Enabled", self._pc_enabled_cb)

        self._pc_channel_spin = QSpinBox()
        self._pc_channel_spin.setRange(-1, 15)
        self._pc_channel_spin.setSpecialValueText("any")
        self._pc_channel_spin.setValue(cfg.listen_channel)
        self._pc_channel_spin.setToolTip("-1 = any channel; 0-15 = specific channel")
        self._pc_channel_spin.valueChanged.connect(self._on_pc_channel_changed)
        form.addRow("Listen Channel", self._pc_channel_spin)

        self._pc_table = QTableWidget(0, 2)
        self._pc_table.setHorizontalHeaderLabels(["PC #", "Preset Slug"])
        self._pc_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._pc_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._pc_table.verticalHeader().setVisible(False)
        self._pc_table.setAlternatingRowColors(False)
        self._pc_table.setShowGrid(False)
        self._pc_table.setSelectionBehavior(QTableWidget.SelectRows)
        form.addRow(self._pc_table)

        btn_row = QWidget()
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(6)
        add_btn = QPushButton("Add")
        add_btn.setFixedWidth(60)
        add_btn.clicked.connect(self._on_pc_add)
        remove_btn = QPushButton("Remove")
        remove_btn.setFixedWidth(70)
        remove_btn.clicked.connect(self._on_pc_remove)
        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(remove_btn)
        btn_layout.addStretch()
        form.addRow(btn_row)

        hint = QLabel("DAW sends PC# -> app loads the mapped preset slug instantly")
        hint.setStyleSheet("color: #8a9099; font-size: 11px;")
        hint.setWordWrap(True)
        form.addRow(hint)

        self._fill_pc_table()
        return box

    def _fill_pc_table(self) -> None:
        """Populate the PC bindings table from the current mapping."""
        cfg = self._mapping.program_change
        bindings = sorted(cfg.bindings.items())
        self._pc_table.setRowCount(len(bindings))
        for r, (pc_num, slug) in enumerate(bindings):
            pc_item = QTableWidgetItem(str(pc_num))
            pc_item.setTextAlignment(Qt.AlignCenter)
            self._pc_table.setItem(r, 0, pc_item)

            slug_combo = QComboBox()
            slug_combo.addItem("(none)", "")
            for s in _presets.list_presets():
                slug_combo.addItem(s, s)
            idx = slug_combo.findData(slug)
            slug_combo.setCurrentIndex(max(0, idx))
            slug_combo.currentIndexChanged.connect(
                lambda _i, row=r, combo=slug_combo:
                self._on_pc_slug_changed(row, combo.currentData() or "")
            )
            self._pc_table.setCellWidget(r, 1, slug_combo)

    def _refresh_pc_group(self) -> None:
        """Sync Program Change widgets to the current mapping (called on set_mapping)."""
        cfg = self._mapping.program_change
        self._pc_enabled_cb.blockSignals(True)
        self._pc_channel_spin.blockSignals(True)
        self._pc_enabled_cb.setChecked(cfg.enabled)
        self._pc_channel_spin.setValue(cfg.listen_channel)
        self._pc_enabled_cb.blockSignals(False)
        self._pc_channel_spin.blockSignals(False)
        self._fill_pc_table()

    def _on_pc_enabled_changed(self, checked: bool) -> None:
        self._mapping.program_change.enabled = checked
        self.mapping_changed.emit()

    def _on_pc_channel_changed(self, value: int) -> None:
        self._mapping.program_change.listen_channel = value
        self.mapping_changed.emit()

    def _on_pc_add(self) -> None:
        """Add a new PC->slug binding row with the next unused PC number."""
        cfg = self._mapping.program_change
        used = set(cfg.bindings.keys())
        new_pc = next((i for i in range(128) if i not in used), None)
        if new_pc is None:
            return
        cfg.bindings[new_pc] = ""
        self._fill_pc_table()
        self.mapping_changed.emit()

    def _on_pc_remove(self) -> None:
        """Remove the selected PC binding row."""
        row = self._pc_table.currentRow()
        if row < 0:
            return
        item = self._pc_table.item(row, 0)
        if item is None:
            return
        try:
            pc_num = int(item.text())
        except (ValueError, TypeError):
            return
        self._mapping.program_change.bindings.pop(pc_num, None)
        self._fill_pc_table()
        self.mapping_changed.emit()

    def _on_pc_slug_changed(self, row: int, slug: str) -> None:
        """Update the slug for the binding at row."""
        item = self._pc_table.item(row, 0)
        if item is None:
            return
        try:
            pc_num = int(item.text())
        except (ValueError, TypeError):
            return
        if slug:
            self._mapping.program_change.bindings[pc_num] = slug
        else:
            self._mapping.program_change.bindings.pop(pc_num, None)
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
