"""Visual template builder tab.

WHY: existing MappingEditor is a Pro-locked table — opaque for the 80% of
users who just want "click L2, type 'Filter cutoff', export to Resolume".
This tab gives that workflow visually for free, then exports a portable
.umct.json (Universal MIDI Controller Template) plus host-specific files
for Resolume/Ableton via the connectors module. Free tier on purpose:
helps users move OFF a Pro mapping if they downgrade.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Tuple

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QBrush, QColor, QFont, QMouseEvent, QPainter, QPen, QPolygonF,
)
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QFrame, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QMessageBox, QPushButton, QSizePolicy, QSpinBox, QSplitter,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from ..mapping import Mapping


# ----- palette (matches controller_meter.py + global teal accent)
COL_BG = QColor("#0e0f12")
COL_BODY = QColor("#16181d")
COL_BORDER = QColor("#24262d")
COL_UNBOUND = QColor("#5a606b")
COL_BOUND = QColor("#2dd4bf")
COL_BOUND_FILL = QColor(45, 212, 191, 60)   # 30% teal glow
COL_SELECT = QColor("#2dd4bf")
COL_TEXT = QColor("#f5f7fa")
COL_TEXT_DIM = QColor("#8a9099")


# Control ID schema. WHY: a single string id ("button_0", "axis_3", "hat_up",
# "touchpad_x", "l_stick_corner") lets us key labels + selection + diagram
# hit-tests uniformly across the diverse Mapping shape.
@dataclass(frozen=True)
class ControlSpec:
    """Static metadata for one hit-testable control on the diagram."""
    cid: str          # canonical id
    display: str      # short label shown on diagram
    kind: str         # "button" | "axis" | "hat" | "touchpad" | "corner"
    payload: object   # int idx / hat direction string / touchpad axis name

    @property
    def default_type(self) -> str:
        # WHY: buttons + hats emit Notes by default; axes/touchpad emit CCs.
        if self.kind in ("button", "hat", "corner"):
            return "Note"
        return "CC"


# Canonical control roster. Indices follow pygame DualSense ordering used
# throughout the rest of the app (mapping.py defaults).
CONTROLS: Tuple[ControlSpec, ...] = (
    # Face buttons (Sony layout): Cross/Circle/Square/Triangle = 0/1/2/3
    ControlSpec("button_0", "Cross",    "button", 0),
    ControlSpec("button_1", "Circle",   "button", 1),
    ControlSpec("button_2", "Square",   "button", 2),
    ControlSpec("button_3", "Triangle", "button", 3),
    # Shoulder + stick clicks
    ControlSpec("button_4", "L1", "button", 4),
    ControlSpec("button_5", "R1", "button", 5),
    ControlSpec("button_6", "Share",   "button", 6),
    ControlSpec("button_7", "Options", "button", 7),
    ControlSpec("button_8", "PS",      "button", 8),
    ControlSpec("button_9",  "L3", "button", 9),
    ControlSpec("button_10", "R3", "button", 10),
    # Sticks as CC streams (X/Y per side)
    ControlSpec("axis_0", "LX", "axis", 0),
    ControlSpec("axis_1", "LY", "axis", 1),
    ControlSpec("axis_2", "RX", "axis", 2),
    ControlSpec("axis_3", "RY", "axis", 3),
    # Triggers as CC streams
    ControlSpec("axis_4", "L2", "axis", 4),
    ControlSpec("axis_5", "R2", "axis", 5),
    # D-pad
    ControlSpec("hat_up",    "D-Up",    "hat", "up"),
    ControlSpec("hat_down",  "D-Down",  "hat", "down"),
    ControlSpec("hat_left",  "D-Left",  "hat", "left"),
    ControlSpec("hat_right", "D-Right", "hat", "right"),
    # Touchpad (X/Y CCs)
    ControlSpec("touchpad_x", "TP-X", "touchpad", "x"),
    ControlSpec("touchpad_y", "TP-Y", "touchpad", "y"),
)

CONTROLS_BY_ID: Dict[str, ControlSpec] = {c.cid: c for c in CONTROLS}


# ============================================================ diagram widget

class DualSenseDiagram(QWidget):
    """Clickable DualSense silhouette with per-control hit regions.

    WHY custom-painted instead of extending ControllerMeter: meter is a
    live data visualiser (state pours in via signals at 30Hz) — repurposing
    it for static click-targets would muddy both. A short standalone painter
    is easier to maintain and lets us tune hit boxes independently.
    """

    control_clicked = Signal(str)  # emits ControlSpec.cid

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(420, 360)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMouseTracking(True)
        # cid -> rect in widget coords, recomputed per resize so hit-test
        # always reflects the current paint.
        self._hit_rects: Dict[str, QRectF] = {}
        self._selected: Optional[str] = None
        self._bound: Dict[str, str] = {}   # cid -> tooltip text (e.g. "CC 1")
        self._hover: Optional[str] = None

    # --- public api ---------------------------------------------------

    def set_selected(self, cid: Optional[str]) -> None:
        self._selected = cid
        self.update()

    def set_bindings(self, bound: Dict[str, str]) -> None:
        self._bound = dict(bound)
        self.update()

    # --- events -------------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.LeftButton:
            return
        pos = event.position()
        hit = self._hit_test(pos)
        if hit is not None:
            self.control_clicked.emit(hit)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        # Hover tooltip — repaint only when the hovered control changes so
        # we don't burn cycles on every pixel of mouse drift.
        hit = self._hit_test(event.position())
        if hit != self._hover:
            self._hover = hit
            if hit and hit in self._bound:
                self.setToolTip(f"{CONTROLS_BY_ID[hit].display} → {self._bound[hit]}")
            elif hit:
                self.setToolTip(f"{CONTROLS_BY_ID[hit].display} (unbound)")
            else:
                self.setToolTip("")

    def _hit_test(self, pos: QPointF) -> Optional[str]:
        # Iterate in insertion order; small overlaps favour earliest control.
        for cid, rect in self._hit_rects.items():
            if rect.contains(pos):
                return cid
        return None

    # --- painting -----------------------------------------------------

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), COL_BG)

        w = self.width()
        h = self.height()
        # Layout uses a normalised 1000x800 design space, then scales.
        sx = w / 1000.0
        sy = h / 800.0
        s = min(sx, sy)
        # Centre the design space inside the widget so resizing keeps the
        # controller centred rather than left-anchored.
        ox = (w - 1000.0 * s) / 2.0
        oy = (h - 800.0 * s) / 2.0

        def R(x: float, y: float, ww: float, hh: float) -> QRectF:
            return QRectF(ox + x * s, oy + y * s, ww * s, hh * s)

        self._hit_rects.clear()

        # Body silhouette — rounded blob behind everything.
        p.setPen(QPen(COL_BORDER, max(1.0, 2.0 * s)))
        p.setBrush(QBrush(COL_BODY))
        body = R(60, 180, 880, 480)
        p.drawRoundedRect(body, 80 * s, 80 * s)

        # Grips
        grip_l = R(60, 380, 200, 320)
        grip_r = R(740, 380, 200, 320)
        p.drawRoundedRect(grip_l, 90 * s, 90 * s)
        p.drawRoundedRect(grip_r, 90 * s, 90 * s)

        # Triggers (top)
        self._paint_control(p, "axis_4", R(140, 90, 180, 90), rounded=20, label_below=False)
        self._paint_control(p, "button_4", R(150, 175, 160, 50), rounded=14, label_below=False)
        self._paint_control(p, "axis_5", R(680, 90, 180, 90), rounded=20, label_below=False)
        self._paint_control(p, "button_5", R(690, 175, 160, 50), rounded=14, label_below=False)

        # D-pad cluster (left)
        self._paint_control(p, "hat_up",    R(195, 285, 70, 65), rounded=10)
        self._paint_control(p, "hat_down",  R(195, 425, 70, 65), rounded=10)
        self._paint_control(p, "hat_left",  R(120, 355, 70, 65), rounded=10)
        self._paint_control(p, "hat_right", R(270, 355, 70, 65), rounded=10)

        # Face buttons (right) — Triangle/Square/Circle/Cross diamond.
        self._paint_control(p, "button_3", R(795, 285, 70, 70), rounded=35)
        self._paint_control(p, "button_2", R(720, 355, 70, 70), rounded=35)
        self._paint_control(p, "button_1", R(870, 355, 70, 70), rounded=35)
        self._paint_control(p, "button_0", R(795, 425, 70, 70), rounded=35)

        # Sticks — drawn as outer circle (axis-Y) + smaller fill (axis-X)
        # so the user can click either label region. WHY two: each axis is
        # an independently bindable CC. We split the click area top/bottom.
        self._paint_stick(p, "axis_0", "axis_1", R(370, 510, 130, 130))
        self._paint_stick(p, "axis_2", "axis_3", R(580, 510, 130, 130))
        # Stick-click buttons sit under the stick label cluster
        self._paint_control(p, "button_9",  R(370, 645, 60, 28), rounded=8)
        self._paint_control(p, "button_10", R(650, 645, 60, 28), rounded=8)

        # Touchpad (centre top)
        self._paint_control(p, "touchpad_x", R(395, 300, 105, 80), rounded=12)
        self._paint_control(p, "touchpad_y", R(500, 300, 105, 80), rounded=12)

        # Share / Options / PS
        self._paint_control(p, "button_6", R(345, 245, 50, 36), rounded=8)
        self._paint_control(p, "button_7", R(605, 245, 50, 36), rounded=8)
        self._paint_control(p, "button_8", R(475, 395, 50, 50), rounded=25)

        # Helper hint at bottom — keep brief, no scope creep
        p.setPen(QPen(COL_TEXT_DIM))
        f = QFont()
        f.setPointSize(9)
        p.setFont(f)
        p.drawText(
            QRectF(0, h - 22, w, 18),
            int(Qt.AlignCenter),
            "Click a control to assign MIDI · teal = bound · grey = unbound",
        )

        p.end()

    def _paint_control(
        self,
        p: QPainter,
        cid: str,
        rect: QRectF,
        rounded: float = 10.0,
        label_below: bool = True,
    ) -> None:
        """Paint one control box and register its hit-rect."""
        spec = CONTROLS_BY_ID[cid]
        bound = cid in self._bound
        selected = cid == self._selected

        fill = COL_BOUND_FILL if bound else QColor(35, 38, 45)
        border = COL_BOUND if bound else COL_UNBOUND
        if selected:
            border = COL_SELECT

        pen_width = 2.0 if selected else 1.4
        p.setPen(QPen(border, pen_width))
        p.setBrush(QBrush(fill))
        rounded_px = rounded * (rect.width() / 70.0)
        p.drawRoundedRect(rect, rounded_px, rounded_px)

        # Label inside the control box
        p.setPen(QPen(COL_TEXT if bound or selected else COL_TEXT_DIM))
        f = QFont()
        f.setPointSize(8)
        f.setBold(selected)
        p.setFont(f)
        p.drawText(rect, int(Qt.AlignCenter), spec.display)

        self._hit_rects[cid] = rect

    def _paint_stick(
        self,
        p: QPainter,
        cid_x: str,
        cid_y: str,
        rect: QRectF,
    ) -> None:
        """Split a stick into two half-discs for X and Y CC binding."""
        # Outer ring backdrop
        p.setPen(QPen(COL_BORDER, 1.5))
        p.setBrush(QBrush(QColor(28, 31, 38)))
        p.drawEllipse(rect)

        # Top half = Y axis hit zone, bottom half = X axis hit zone. Slice
        # ends are flat so they line up with the ellipse outline.
        top_rect = QRectF(rect.x(), rect.y(), rect.width(), rect.height() / 2.0)
        bot_rect = QRectF(
            rect.x(), rect.y() + rect.height() / 2.0,
            rect.width(), rect.height() / 2.0,
        )

        for half, cid in ((top_rect, cid_y), (bot_rect, cid_x)):
            spec = CONTROLS_BY_ID[cid]
            bound = cid in self._bound
            selected = cid == self._selected
            fill = COL_BOUND_FILL if bound else QColor(0, 0, 0, 0)
            p.setPen(QPen(COL_SELECT if selected else (
                COL_BOUND if bound else COL_UNBOUND
            ), 2.0 if selected else 1.2))
            p.setBrush(QBrush(fill))
            # Use a clipped ellipse so the highlight matches the stick shape
            p.save()
            p.setClipRect(half)
            p.drawEllipse(rect)
            p.restore()
            p.setPen(QPen(COL_TEXT if bound or selected else COL_TEXT_DIM))
            f = QFont()
            f.setPointSize(8)
            f.setBold(selected)
            p.setFont(f)
            p.drawText(half, int(Qt.AlignCenter), spec.display)
            self._hit_rects[cid] = half


# ============================================================ main tab

class TemplateBuilderTab(QWidget):
    """Visual MIDI mapping builder + multi-format template exporter.

    Emits ``mapping_changed`` after every saved binding so MainWindow can
    forward the new mapping to the live bridge worker and persist it.
    """

    mapping_changed = Signal(Mapping)

    def __init__(self, mapping: Mapping, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        # Work on a copy. WHY: avoid mutating the caller's reference until
        # the user explicitly saves a binding; lets "Reset to defaults"
        # bail out cleanly.
        self._mapping: Mapping = Mapping.from_dict(json.loads(json.dumps(mapping.to_dict())))
        # Labels are NOT part of Mapping (kept lean for the runtime); we
        # carry them alongside in the tab and persist them inside .umct.json.
        self._labels: Dict[str, str] = {}
        self._selected: Optional[str] = None

        self._build_ui()
        self._refresh_diagram()
        self._refresh_table()

    # --------------------------------------------------------- ui

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(2)

        # --- left: diagram
        self._diagram = DualSenseDiagram()
        self._diagram.control_clicked.connect(self._on_control_clicked)
        splitter.addWidget(self._diagram)

        # --- right: editor + table + actions
        right = QWidget()
        v = QVBoxLayout(right)
        v.setContentsMargins(8, 0, 0, 0)
        v.setSpacing(10)

        self._sel_header = QLabel("Selected: —")
        self._sel_header.setStyleSheet(
            "font-size: 15px; font-weight: 600; color: #f5f7fa;"
        )
        v.addWidget(self._sel_header)

        form = QFrame()
        form.setObjectName("BuilderForm")
        form.setStyleSheet(
            "QFrame#BuilderForm { background:#16181d; border:1px solid #24262d; "
            "border-radius:8px; padding:10px; }"
            "QLabel { color:#8a9099; font-size:11px; }"
        )
        fl = QVBoxLayout(form)
        fl.setSpacing(6)

        # Type / value row
        row_type = QHBoxLayout()
        row_type.addWidget(QLabel("Type"))
        self._type_combo = QComboBox()
        self._type_combo.addItems(["Note", "CC"])
        row_type.addWidget(self._type_combo, 1)
        row_type.addSpacing(8)
        row_type.addWidget(QLabel("Number"))
        self._value_spin = QSpinBox()
        self._value_spin.setRange(0, 127)
        row_type.addWidget(self._value_spin, 1)
        fl.addLayout(row_type)

        row_chan = QHBoxLayout()
        row_chan.addWidget(QLabel("Channel"))
        self._channel_spin = QSpinBox()
        self._channel_spin.setRange(1, 16)
        self._channel_spin.setValue(self._mapping.midi_channel + 1)
        row_chan.addWidget(self._channel_spin, 1)
        row_chan.addStretch(1)
        fl.addLayout(row_chan)

        row_name = QHBoxLayout()
        row_name.addWidget(QLabel("Parameter name"))
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("e.g. Filter cutoff")
        row_name.addWidget(self._name_edit, 2)
        fl.addLayout(row_name)

        # Save/Clear row
        row_btn = QHBoxLayout()
        self._save_btn = QPushButton("Save binding")
        self._save_btn.setObjectName("PrimaryButton")
        self._save_btn.setStyleSheet(
            "background:#2dd4bf; color:#0e0f12; font-weight:600; padding:6px 12px;"
        )
        self._save_btn.clicked.connect(self._on_save_binding)
        self._clear_btn = QPushButton("Clear binding")
        self._clear_btn.clicked.connect(self._on_clear_binding)
        row_btn.addWidget(self._save_btn)
        row_btn.addWidget(self._clear_btn)
        row_btn.addStretch(1)
        fl.addLayout(row_btn)

        v.addWidget(form)

        # Bindings table
        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["Control", "Type", "Value", "Name"])
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setSelectionMode(QTableWidget.SingleSelection)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.itemSelectionChanged.connect(self._on_table_selection)
        v.addWidget(self._table, 1)

        # Action row
        actions = QHBoxLayout()
        self._save_tpl_btn = QPushButton("Save template…")
        self._save_tpl_btn.clicked.connect(self._on_save_template)
        self._load_tpl_btn = QPushButton("Load template…")
        self._load_tpl_btn.clicked.connect(self._on_load_template)
        self._exp_res_btn = QPushButton("Export for Resolume")
        self._exp_res_btn.clicked.connect(self._on_export_resolume)
        self._exp_abl_btn = QPushButton("Export for Ableton")
        self._exp_abl_btn.clicked.connect(self._on_export_ableton)
        self._reset_btn = QPushButton("Reset to defaults")
        self._reset_btn.clicked.connect(self._on_reset_defaults)
        for b in (self._save_tpl_btn, self._load_tpl_btn, self._exp_res_btn,
                  self._exp_abl_btn, self._reset_btn):
            actions.addWidget(b)
        actions.addStretch(1)
        v.addLayout(actions)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 55)
        splitter.setStretchFactor(1, 45)
        splitter.setSizes([550, 450])
        root.addWidget(splitter, 1)

    # --------------------------------------------------------- selection

    def _on_control_clicked(self, cid: str) -> None:
        self._selected = cid
        spec = CONTROLS_BY_ID[cid]
        self._sel_header.setText(f"Selected: {spec.display}")
        self._diagram.set_selected(cid)

        # Pre-populate the editor with current binding values so the user
        # is editing in-place rather than recreating each time.
        binding = self._lookup_binding(cid)
        if binding is not None:
            kind, value = binding
            self._type_combo.setCurrentText(kind)
            self._value_spin.setValue(value)
        else:
            self._type_combo.setCurrentText(spec.default_type)
            self._value_spin.setValue(_suggest_value(spec, self._mapping))
        self._channel_spin.setValue(self._mapping.midi_channel + 1)
        self._name_edit.setText(self._labels.get(cid, ""))

    def _on_table_selection(self) -> None:
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            return
        row = rows[0].row()
        item = self._table.item(row, 0)
        if item is None:
            return
        cid = item.data(Qt.UserRole)
        if cid:
            self._on_control_clicked(cid)

    # --------------------------------------------------------- binding I/O

    def _lookup_binding(self, cid: str) -> Optional[Tuple[str, int]]:
        """Return (Note|CC, value) for the binding currently in mapping."""
        spec = CONTROLS_BY_ID[cid]
        m = self._mapping
        if spec.kind == "button" and spec.payload in m.buttons:
            return ("Note", int(m.buttons[spec.payload]))
        if spec.kind == "axis" and spec.payload in m.axes:
            return ("CC", int(m.axes[spec.payload]))
        if spec.kind == "hat" and spec.payload in m.hats:
            return ("Note", int(m.hats[spec.payload]))
        if spec.kind == "touchpad":
            tp = m.touchpad
            if spec.payload == "x":
                return ("CC", int(tp.x_cc))
            if spec.payload == "y":
                return ("CC", int(tp.y_cc))
        return None

    def _on_save_binding(self) -> None:
        if not self._selected:
            QMessageBox.information(
                self, "Pick a control first",
                "Click a button, stick, or trigger on the diagram, then save.",
            )
            return
        cid = self._selected
        spec = CONTROLS_BY_ID[cid]
        kind = self._type_combo.currentText()
        value = int(self._value_spin.value())
        # Type is enforced per-control-class to keep Mapping consistent.
        if spec.kind in ("button", "hat") and kind != "Note":
            QMessageBox.information(
                self, "Buttons send notes",
                f"{spec.display} is a button/hat — switching its type to Note.",
            )
            kind = "Note"
            self._type_combo.setCurrentText("Note")
        if spec.kind in ("axis", "touchpad") and kind != "CC":
            QMessageBox.information(
                self, "Continuous controls send CC",
                f"{spec.display} is an analog control — switching to CC.",
            )
            kind = "CC"
            self._type_combo.setCurrentText("CC")

        if spec.kind == "button":
            self._mapping.buttons[int(spec.payload)] = value
        elif spec.kind == "axis":
            self._mapping.axes[int(spec.payload)] = value
        elif spec.kind == "hat":
            self._mapping.hats[str(spec.payload)] = value
        elif spec.kind == "touchpad":
            if spec.payload == "x":
                self._mapping.touchpad.x_cc = value
            else:
                self._mapping.touchpad.y_cc = value
            # Auto-enable touchpad if user is binding it — otherwise the
            # CC numbers sit unused which is confusing.
            self._mapping.touchpad.enabled = True

        # Channel is global (Mapping holds one channel for now). Update if
        # user edited it. Convert 1-16 UI -> 0-15 internal.
        new_channel = int(self._channel_spin.value()) - 1
        if new_channel != self._mapping.midi_channel:
            self._mapping.midi_channel = new_channel

        name = self._name_edit.text().strip()
        if name:
            self._labels[cid] = name
        else:
            self._labels.pop(cid, None)

        self._refresh_diagram()
        self._refresh_table()
        self.mapping_changed.emit(self._mapping)

    def _on_clear_binding(self) -> None:
        if not self._selected:
            return
        cid = self._selected
        spec = CONTROLS_BY_ID[cid]
        if spec.kind == "button":
            self._mapping.buttons.pop(int(spec.payload), None)
        elif spec.kind == "axis":
            self._mapping.axes.pop(int(spec.payload), None)
        elif spec.kind == "hat":
            self._mapping.hats.pop(str(spec.payload), None)
        elif spec.kind == "touchpad":
            # WHY no-op-on-clear: touchpad x/y are flat CC numbers without a
            # natural "unset" — clear just disables the touchpad block.
            self._mapping.touchpad.enabled = False
        self._labels.pop(cid, None)
        self._refresh_diagram()
        self._refresh_table()
        self.mapping_changed.emit(self._mapping)

    # --------------------------------------------------------- refresh

    def _refresh_diagram(self) -> None:
        bound: Dict[str, str] = {}
        for spec in CONTROLS:
            b = self._lookup_binding(spec.cid)
            if b is None:
                continue
            kind, val = b
            label = self._labels.get(spec.cid)
            text = f"{kind} {val}" + (f" · {label}" if label else "")
            bound[spec.cid] = text
        self._diagram.set_bindings(bound)
        # Skip touchpad bindings if the user disabled the block — keeps the
        # diagram honest about what'll actually fire at runtime.
        if not self._mapping.touchpad.enabled:
            self._diagram._bound.pop("touchpad_x", None)
            self._diagram._bound.pop("touchpad_y", None)
        self._diagram.update()

    def _refresh_table(self) -> None:
        rows = []
        for spec in CONTROLS:
            b = self._lookup_binding(spec.cid)
            if b is None:
                continue
            if spec.kind == "touchpad" and not self._mapping.touchpad.enabled:
                continue
            kind, val = b
            rows.append((spec, kind, val, self._labels.get(spec.cid, "")))
        self._table.setRowCount(len(rows))
        for i, (spec, kind, val, label) in enumerate(rows):
            item0 = QTableWidgetItem(spec.display)
            item0.setData(Qt.UserRole, spec.cid)
            self._table.setItem(i, 0, item0)
            self._table.setItem(i, 1, QTableWidgetItem(kind))
            self._table.setItem(i, 2, QTableWidgetItem(str(val)))
            self._table.setItem(i, 3, QTableWidgetItem(label))

    # --------------------------------------------------------- file ops

    def _on_save_template(self) -> None:
        path_str, _ = QFileDialog.getSaveFileName(
            self, "Save template", "universal-controller.umct.json",
            "Universal MIDI Controller Template (*.umct.json *.json)",
        )
        if not path_str:
            return
        path = Path(path_str)
        if not path.name.endswith(".umct.json") and path.suffix != ".json":
            path = path.with_suffix(".umct.json")
        payload = {
            "schema_version": 1,
            "name": self._mapping.name or path.stem,
            "description": "",
            "exported_at": datetime.now(timezone.utc)
                .replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "mapping": self._mapping.to_dict(),
            "labels": dict(self._labels),
        }
        try:
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except OSError as e:
            QMessageBox.warning(self, "Save failed", str(e))
            return
        QMessageBox.information(self, "Template saved", f"Wrote {path}.")

    def _on_load_template(self) -> None:
        path_str, _ = QFileDialog.getOpenFileName(
            self, "Load template", "",
            "Universal MIDI Controller Template (*.umct.json *.json);;All files (*)",
        )
        if not path_str:
            return
        try:
            data = json.loads(Path(path_str).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            QMessageBox.warning(self, "Load failed", str(e))
            return
        # Accept either {"mapping": ..., "labels": ...} or a bare Mapping dict.
        if "mapping" in data:
            self._mapping = Mapping.from_dict(data["mapping"])
            self._labels = {str(k): str(v) for k, v in data.get("labels", {}).items()}
        else:
            self._mapping = Mapping.from_dict(data)
            self._labels = {}
        self._selected = None
        self._diagram.set_selected(None)
        self._sel_header.setText("Selected: —")
        self._refresh_diagram()
        self._refresh_table()
        self.mapping_changed.emit(self._mapping)

    def _on_export_resolume(self) -> None:
        """Copy the bundled Resolume template + augment with a sidecar JSON
        of the user's actual bindings so they can audit what shipped.

        WHY a sidecar: Resolume's XML schema is large and binding-specific
        (path strings hand-mapped to clip/layer routes). Rebuilding it
        per-binding is a future research task — for now we ship the curated
        default and pair it with a human-readable JSON dump of the user
        bindings so they can manually wire any extras inside Resolume's
        MIDI Learn.
        """
        path_str, _ = QFileDialog.getSaveFileName(
            self, "Export Resolume shortcut XML",
            "Universal Controller MIDI.xml", "Resolume Shortcuts (*.xml)",
        )
        if not path_str:
            return
        try:
            from ..connectors.resolume import _template_path, TEMPLATE_FILENAME
        except ImportError as e:
            QMessageBox.warning(self, "Export failed", f"Connector missing: {e}")
            return
        template = _template_path(TEMPLATE_FILENAME)
        try:
            Path(path_str).write_bytes(template.read_bytes())
            sidecar = Path(path_str).with_suffix(".bindings.json")
            sidecar.write_text(
                json.dumps(self._template_payload(), indent=2), encoding="utf-8",
            )
        except OSError as e:
            QMessageBox.warning(self, "Export failed", str(e))
            return
        QMessageBox.information(
            self, "Resolume export ready",
            f"Wrote {path_str} + bindings sidecar.\n"
            "Open Resolume → Shortcuts → Application Map to load it.",
        )

    def _on_export_ableton(self) -> None:
        """Copy the bundled Remote Script folder. WHY same shape as Resolume
        export: the connectors module owns the schema; this tab is just a
        UI entry point to those exporters so users can save anywhere."""
        path_str = QFileDialog.getExistingDirectory(
            self, "Choose destination folder for Remote Script",
        )
        if not path_str:
            return
        try:
            from ..connectors.ableton import (
                REMOTE_SCRIPT_FOLDER, TEMPLATE_SUBDIR, _template_source,
            )
        except ImportError as e:
            QMessageBox.warning(self, "Export failed", f"Connector missing: {e}")
            return
        import shutil
        dest_root = Path(path_str) / REMOTE_SCRIPT_FOLDER
        try:
            if dest_root.exists():
                shutil.rmtree(dest_root)
            shutil.copytree(_template_source(), dest_root)
            (dest_root / "bindings.json").write_text(
                json.dumps(self._template_payload(), indent=2), encoding="utf-8",
            )
        except OSError as e:
            QMessageBox.warning(self, "Export failed", str(e))
            return
        QMessageBox.information(
            self, "Ableton export ready",
            f"Wrote {dest_root}.\n"
            "Move it into Live's Remote Scripts folder if it isn't already there.",
        )

    def _on_reset_defaults(self) -> None:
        resp = QMessageBox.question(
            self, "Reset to defaults?",
            "This discards the current bindings and labels and reverts to "
            "the factory mapping. Continue?",
        )
        if resp != QMessageBox.Yes:
            return
        self._mapping = Mapping()
        self._labels = {}
        self._selected = None
        self._diagram.set_selected(None)
        self._sel_header.setText("Selected: —")
        self._refresh_diagram()
        self._refresh_table()
        self.mapping_changed.emit(self._mapping)

    # --------------------------------------------------------- helpers

    def _template_payload(self) -> dict:
        return {
            "schema_version": 1,
            "name": self._mapping.name or "Untitled",
            "exported_at": datetime.now(timezone.utc)
                .replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "mapping": self._mapping.to_dict(),
            "labels": dict(self._labels),
        }


# ----- value suggestion -----------------------------------------------------

def _suggest_value(spec: ControlSpec, mapping: Mapping) -> int:
    """Pick a sensible default MIDI number for a freshly-selected control.

    WHY: the spinbox defaults to 0 which is rarely what the user wants; if
    the current mapping already has a value for this control, surface it;
    otherwise fall back to the global factory default for that index.
    """
    factory = Mapping()
    if spec.kind == "button":
        return int(factory.buttons.get(int(spec.payload), 60))
    if spec.kind == "axis":
        return int(factory.axes.get(int(spec.payload), 1))
    if spec.kind == "hat":
        return int(factory.hats.get(str(spec.payload), 78))
    if spec.kind == "touchpad":
        return 16 if spec.payload == "x" else 17
    return 0
