"""Visual template builder tab.

WHY: MappingEditor is a Pro-locked table — opaque for the 80% of users who
just want "click L2, type 'Filter cutoff', export to Resolume". This tab
gives that workflow visually for free, then exports a portable .umct.json
plus host-specific files via the connectors module. Free tier on purpose:
helps users keep their work if they downgrade off Pro.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Tuple

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QFrame, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QMessageBox, QPushButton, QScrollArea, QSizePolicy, QSpinBox,
    QSplitter, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from ..mapping import Mapping
from ..templates import TEMPLATES, Template


# Palette matches controller_meter.py + global teal accent.
COL_BG = QColor("#0e0f12")
COL_BODY = QColor("#16181d")
COL_BORDER = QColor("#24262d")
COL_UNBOUND = QColor("#5a606b")
COL_BOUND = QColor("#2dd4bf")
COL_BOUND_FILL = QColor(45, 212, 191, 60)   # 30% teal glow
COL_SELECT = QColor("#2dd4bf")
COL_TEXT = QColor("#f5f7fa")
COL_TEXT_DIM = QColor("#8a9099")


@dataclass(frozen=True)
class ControlSpec:
    """One hit-testable control on the diagram.

    WHY a single string id ("button_0", "axis_3", "hat_up", "touchpad_x")
    lets us key labels + selection + hit-tests uniformly across the diverse
    Mapping shape.
    """
    cid: str
    display: str
    kind: str        # "button" | "axis" | "hat" | "touchpad"
    payload: object  # int idx / hat dir / touchpad axis name

    @property
    def default_type(self) -> str:
        return "Note" if self.kind in ("button", "hat") else "CC"


# Indices follow pygame DualSense ordering (matches mapping.py defaults).
CONTROLS: Tuple[ControlSpec, ...] = (
    ControlSpec("button_0", "Cross",    "button", 0),
    ControlSpec("button_1", "Circle",   "button", 1),
    ControlSpec("button_2", "Square",   "button", 2),
    ControlSpec("button_3", "Triangle", "button", 3),
    ControlSpec("button_4", "L1", "button", 4),
    ControlSpec("button_5", "R1", "button", 5),
    ControlSpec("button_6", "Share",   "button", 6),
    ControlSpec("button_7", "Options", "button", 7),
    ControlSpec("button_8", "PS",      "button", 8),
    ControlSpec("button_9",  "L3", "button", 9),
    ControlSpec("button_10", "R3", "button", 10),
    ControlSpec("axis_0", "LX", "axis", 0),
    ControlSpec("axis_1", "LY", "axis", 1),
    ControlSpec("axis_2", "RX", "axis", 2),
    ControlSpec("axis_3", "RY", "axis", 3),
    ControlSpec("axis_4", "L2", "axis", 4),
    ControlSpec("axis_5", "R2", "axis", 5),
    ControlSpec("hat_up",    "D-Up",    "hat", "up"),
    ControlSpec("hat_down",  "D-Down",  "hat", "down"),
    ControlSpec("hat_left",  "D-Left",  "hat", "left"),
    ControlSpec("hat_right", "D-Right", "hat", "right"),
    ControlSpec("touchpad_x", "TP-X", "touchpad", "x"),
    ControlSpec("touchpad_y", "TP-Y", "touchpad", "y"),
)
CONTROLS_BY_ID: Dict[str, ControlSpec] = {c.cid: c for c in CONTROLS}


# ============================================================ diagram widget

class DualSenseDiagram(QWidget):
    """Clickable DualSense silhouette with per-control hit regions.

    WHY custom-painted instead of extending ControllerMeter: meter is a
    live data visualiser. Repurposing it for static click-targets would
    muddy both. Standalone painter lets us tune hit boxes independently.
    """

    control_clicked = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        # Drop the old 420×360 floor — the parent scroll area handles
        # overflow, and the diagram paints to whatever space it's given.
        self.setMinimumSize(180, 140)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMouseTracking(True)
        self._hit_rects: Dict[str, QRectF] = {}
        self._selected: Optional[str] = None
        self._bound: Dict[str, str] = {}
        self._hover: Optional[str] = None

    def set_selected(self, cid: Optional[str]) -> None:
        self._selected = cid
        self.update()

    def set_bindings(self, bound: Dict[str, str]) -> None:
        self._bound = dict(bound)
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.LeftButton:
            return
        hit = self._hit_test(event.position())
        if hit is not None:
            self.control_clicked.emit(hit)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        # WHY: repaint only when hovered control changes — skip cycles on drift.
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
        # Insertion-order iteration; small overlaps favour earliest control.
        for cid, rect in self._hit_rects.items():
            if rect.contains(pos):
                return cid
        return None

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), COL_BG)
        w, h = self.width(), self.height()
        # Normalised 1000x800 design space scaled + centred.
        s = min(w / 1000.0, h / 800.0)
        ox = (w - 1000.0 * s) / 2.0
        oy = (h - 800.0 * s) / 2.0

        def R(x: float, y: float, ww: float, hh: float) -> QRectF:
            return QRectF(ox + x * s, oy + y * s, ww * s, hh * s)

        self._hit_rects.clear()
        # Body + grips silhouette
        p.setPen(QPen(COL_BORDER, max(1.0, 2.0 * s)))
        p.setBrush(QBrush(COL_BODY))
        p.drawRoundedRect(R(60, 180, 880, 480), 80 * s, 80 * s)
        p.drawRoundedRect(R(60, 380, 200, 320), 90 * s, 90 * s)
        p.drawRoundedRect(R(740, 380, 200, 320), 90 * s, 90 * s)
        # Triggers + shoulders
        self._paint_control(p, "axis_4", R(140, 90, 180, 90), rounded=20)
        self._paint_control(p, "button_4", R(150, 175, 160, 50), rounded=14)
        self._paint_control(p, "axis_5", R(680, 90, 180, 90), rounded=20)
        self._paint_control(p, "button_5", R(690, 175, 160, 50), rounded=14)
        # D-pad
        self._paint_control(p, "hat_up",    R(195, 285, 70, 65), rounded=10)
        self._paint_control(p, "hat_down",  R(195, 425, 70, 65), rounded=10)
        self._paint_control(p, "hat_left",  R(120, 355, 70, 65), rounded=10)
        self._paint_control(p, "hat_right", R(270, 355, 70, 65), rounded=10)
        # Face buttons (Sony diamond)
        self._paint_control(p, "button_3", R(795, 285, 70, 70), rounded=35)
        self._paint_control(p, "button_2", R(720, 355, 70, 70), rounded=35)
        self._paint_control(p, "button_1", R(870, 355, 70, 70), rounded=35)
        self._paint_control(p, "button_0", R(795, 425, 70, 70), rounded=35)
        # Sticks split top=Y / bottom=X for independent CC binding.
        self._paint_stick(p, "axis_0", "axis_1", R(370, 510, 130, 130))
        self._paint_stick(p, "axis_2", "axis_3", R(580, 510, 130, 130))
        self._paint_control(p, "button_9",  R(370, 645, 60, 28), rounded=8)
        self._paint_control(p, "button_10", R(650, 645, 60, 28), rounded=8)
        # Touchpad + system buttons
        self._paint_control(p, "touchpad_x", R(395, 300, 105, 80), rounded=12)
        self._paint_control(p, "touchpad_y", R(500, 300, 105, 80), rounded=12)
        self._paint_control(p, "button_6", R(345, 245, 50, 36), rounded=8)
        self._paint_control(p, "button_7", R(605, 245, 50, 36), rounded=8)
        self._paint_control(p, "button_8", R(475, 395, 50, 50), rounded=25)
        # Hint footer
        p.setPen(QPen(COL_TEXT_DIM))
        f = QFont(); f.setPointSize(9); p.setFont(f)
        p.drawText(
            QRectF(0, h - 22, w, 18),
            int(Qt.AlignCenter),
            "Click a control to assign MIDI · teal = bound · grey = unbound",
        )
        p.end()

    def _paint_control(self, p: QPainter, cid: str, rect: QRectF,
                       rounded: float = 10.0) -> None:
        spec = CONTROLS_BY_ID[cid]
        bound = cid in self._bound
        selected = cid == self._selected
        fill = COL_BOUND_FILL if bound else QColor(35, 38, 45)
        border = COL_SELECT if selected else (COL_BOUND if bound else COL_UNBOUND)
        p.setPen(QPen(border, 2.0 if selected else 1.4))
        p.setBrush(QBrush(fill))
        rpx = rounded * (rect.width() / 70.0)
        p.drawRoundedRect(rect, rpx, rpx)
        p.setPen(QPen(COL_TEXT if bound or selected else COL_TEXT_DIM))
        f = QFont(); f.setPointSize(8); f.setBold(selected); p.setFont(f)
        p.drawText(rect, int(Qt.AlignCenter), spec.display)
        self._hit_rects[cid] = rect

    def _paint_stick(self, p: QPainter, cid_x: str, cid_y: str,
                     rect: QRectF) -> None:
        # Outer ring backdrop
        p.setPen(QPen(COL_BORDER, 1.5))
        p.setBrush(QBrush(QColor(28, 31, 38)))
        p.drawEllipse(rect)
        top = QRectF(rect.x(), rect.y(), rect.width(), rect.height() / 2.0)
        bot = QRectF(rect.x(), rect.y() + rect.height() / 2.0,
                     rect.width(), rect.height() / 2.0)
        for half, cid in ((top, cid_y), (bot, cid_x)):
            spec = CONTROLS_BY_ID[cid]
            bound = cid in self._bound
            selected = cid == self._selected
            fill = COL_BOUND_FILL if bound else QColor(0, 0, 0, 0)
            border = COL_SELECT if selected else (COL_BOUND if bound else COL_UNBOUND)
            p.setPen(QPen(border, 2.0 if selected else 1.2))
            p.setBrush(QBrush(fill))
            p.save(); p.setClipRect(half); p.drawEllipse(rect); p.restore()
            p.setPen(QPen(COL_TEXT if bound or selected else COL_TEXT_DIM))
            f = QFont(); f.setPointSize(8); f.setBold(selected); p.setFont(f)
            p.drawText(half, int(Qt.AlignCenter), spec.display)
            self._hit_rects[cid] = half


# ============================================================ main tab

class TemplateBuilderTab(QWidget):
    """Visual MIDI mapping builder + multi-format template exporter.

    Emits ``mapping_changed`` after every saved binding so MainWindow can
    forward to the live bridge worker and persist.
    """

    mapping_changed = Signal(Mapping)

    def __init__(self, mapping: Mapping, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        # Deep copy — avoid mutating caller until user explicitly saves so
        # "Reset to defaults" + Cancel-style bail-outs are clean.
        self._mapping: Mapping = Mapping.from_dict(
            json.loads(json.dumps(mapping.to_dict()))
        )
        # Labels live alongside Mapping (which stays runtime-lean) and persist
        # inside .umct.json only.
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
        # Global QSplitter::handle style in styles.qss handles the look.
        splitter.setHandleWidth(6)

        self._diagram = DualSenseDiagram()
        self._diagram.control_clicked.connect(self._on_control_clicked)
        splitter.addWidget(self._diagram)

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
        fl = QVBoxLayout(form); fl.setSpacing(6)

        row_type = QHBoxLayout()
        row_type.addWidget(QLabel("Type"))
        self._type_combo = QComboBox(); self._type_combo.addItems(["Note", "CC"])
        row_type.addWidget(self._type_combo, 1)
        row_type.addSpacing(8)
        row_type.addWidget(QLabel("Number"))
        self._value_spin = QSpinBox(); self._value_spin.setRange(0, 127)
        row_type.addWidget(self._value_spin, 1)
        fl.addLayout(row_type)

        row_chan = QHBoxLayout()
        row_chan.addWidget(QLabel("Channel"))
        self._channel_spin = QSpinBox(); self._channel_spin.setRange(1, 16)
        self._channel_spin.setValue(self._mapping.midi_channel + 1)
        row_chan.addWidget(self._channel_spin, 1); row_chan.addStretch(1)
        fl.addLayout(row_chan)

        row_name = QHBoxLayout()
        row_name.addWidget(QLabel("Parameter name"))
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("e.g. Filter cutoff")
        row_name.addWidget(self._name_edit, 2)
        fl.addLayout(row_name)

        row_btn = QHBoxLayout()
        self._save_btn = QPushButton("Save binding")
        self._save_btn.setObjectName("PrimaryButton")
        self._save_btn.setStyleSheet(
            "background:#2dd4bf; color:#0e0f12; font-weight:600; padding:6px 12px;"
        )
        self._save_btn.clicked.connect(self._on_save_binding)
        self._clear_btn = QPushButton("Clear binding")
        self._clear_btn.clicked.connect(self._on_clear_binding)
        row_btn.addWidget(self._save_btn); row_btn.addWidget(self._clear_btn)
        row_btn.addStretch(1)
        fl.addLayout(row_btn)
        v.addWidget(form)

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["Control", "Type", "Value", "Name"])
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setSelectionMode(QTableWidget.SingleSelection)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.itemSelectionChanged.connect(self._on_table_selection)
        v.addWidget(self._table, 1)

        actions = QHBoxLayout()
        for label, slot in (
            ("Save template…", self._on_save_template),
            ("Load template…", self._on_load_template),
            ("Export for Resolume", self._on_export_resolume),
            ("Export for Ableton", self._on_export_ableton),
            ("Reset to defaults", self._on_reset_defaults),
        ):
            b = QPushButton(label); b.clicked.connect(slot); actions.addWidget(b)
        actions.addStretch(1)
        v.addLayout(actions)

        v.addWidget(self._build_templates_panel())

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 55)
        splitter.setStretchFactor(1, 45)
        splitter.setSizes([550, 450])
        root.addWidget(splitter, 1)

    # --------------------------------------------------------- starter templates

    # Tag colour accents — muted but distinct so cards scan quickly.
    _TAG_COLORS: Dict[str, str] = {
        "Drums":     "#e05c5c",
        "DJ":        "#e09a5c",
        "VJ":        "#9a5ce0",
        "Synth":     "#5c9ae0",
        "Modular":   "#5ce07a",
        "Streaming": "#e05ca0",
    }

    def _build_templates_panel(self) -> QWidget:
        """Scrollable row of starter-template cards with one-click Apply."""
        outer = QFrame()
        outer.setObjectName("TemplatesPanel")
        outer.setStyleSheet(
            "QFrame#TemplatesPanel { background:#0e0f12; border:1px solid #24262d; "
            "border-radius:8px; padding:6px; }"
        )
        ol = QVBoxLayout(outer); ol.setContentsMargins(6, 6, 6, 6); ol.setSpacing(4)

        hdr = QLabel("Starter Templates")
        hdr.setStyleSheet("color:#f5f7fa; font-size:12px; font-weight:600;")
        ol.addWidget(hdr)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFixedHeight(104)
        scroll.setStyleSheet("background:transparent; border:none;")

        cards_widget = QWidget()
        cards_widget.setStyleSheet("background:transparent;")
        cards_layout = QHBoxLayout(cards_widget)
        cards_layout.setContentsMargins(0, 0, 0, 0)
        cards_layout.setSpacing(8)

        for tmpl in TEMPLATES:
            cards_layout.addWidget(self._make_template_card(tmpl))
        cards_layout.addStretch(1)

        scroll.setWidget(cards_widget)
        ol.addWidget(scroll)
        return outer

    def _make_template_card(self, tmpl: Template) -> QWidget:
        """One compact card: tag badge + name + description + Apply button."""
        accent = self._TAG_COLORS.get(tmpl.tag, "#2dd4bf")

        card = QFrame()
        card.setObjectName("TemplateCard")
        card.setFixedWidth(160)
        card.setStyleSheet(
            f"QFrame#TemplateCard {{ background:#16181d; border:1px solid #24262d; "
            f"border-radius:6px; }}"
            f"QFrame#TemplateCard:hover {{ border:1px solid {accent}; }}"
        )
        cl = QVBoxLayout(card)
        cl.setContentsMargins(8, 6, 8, 6)
        cl.setSpacing(3)

        tag_lbl = QLabel(tmpl.tag)
        tag_lbl.setStyleSheet(
            f"background:{accent}22; color:{accent}; font-size:9px; "
            f"font-weight:700; border-radius:3px; padding:1px 5px;"
        )
        tag_lbl.setFixedHeight(16)
        cl.addWidget(tag_lbl)

        name_lbl = QLabel(tmpl.name)
        name_lbl.setStyleSheet("color:#f5f7fa; font-size:11px; font-weight:600;")
        cl.addWidget(name_lbl)

        # Truncate description to keep cards compact.
        desc = tmpl.description
        if len(desc) > 72:
            desc = desc[:69] + "…"
        desc_lbl = QLabel(desc)
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet("color:#8a9099; font-size:9px;")
        desc_lbl.setFixedHeight(30)
        cl.addWidget(desc_lbl)

        apply_btn = QPushButton("Apply")
        apply_btn.setFixedHeight(22)
        apply_btn.setStyleSheet(
            f"background:{accent}; color:#0e0f12; font-size:10px; "
            f"font-weight:700; border-radius:4px; padding:0 6px;"
        )
        apply_btn.setToolTip(tmpl.description)
        # Capture tmpl in the lambda via default arg to avoid late-binding.
        apply_btn.clicked.connect(lambda _=False, t=tmpl: self._on_apply_template(t))
        cl.addWidget(apply_btn)

        return card

    def _on_apply_template(self, tmpl: Template) -> None:
        """Load a starter template, replacing the current working mapping."""
        resp = QMessageBox.question(
            self,
            f'Apply "{tmpl.name}"?',
            f'This replaces the current bindings with the "{tmpl.name}" template.\n'
            "Unsaved changes will be lost. Continue?",
        )
        if resp != QMessageBox.Yes:
            return
        self._mapping = tmpl.build_mapping()
        self._labels = {}
        self._selected = None
        self._diagram.set_selected(None)
        self._sel_header.setText("Selected: —")
        self._refresh_diagram()
        self._refresh_table()
        self.mapping_changed.emit(self._mapping)

    # --------------------------------------------------------- selection

    def _on_control_clicked(self, cid: str) -> None:
        # Pre-populate the editor with current values so the user edits
        # in-place rather than recreating each time.
        self._selected = cid
        spec = CONTROLS_BY_ID[cid]
        self._sel_header.setText(f"Selected: {spec.display}")
        self._diagram.set_selected(cid)
        binding = self._lookup_binding(cid)
        if binding is not None:
            kind, value = binding
            self._type_combo.setCurrentText(kind)
            self._value_spin.setValue(value)
        else:
            self._type_combo.setCurrentText(spec.default_type)
            self._value_spin.setValue(_suggest_value(spec))
        self._channel_spin.setValue(self._mapping.midi_channel + 1)
        self._name_edit.setText(self._labels.get(cid, ""))

    def _on_table_selection(self) -> None:
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            return
        item = self._table.item(rows[0].row(), 0)
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
            return ("CC", int(tp.x_cc if spec.payload == "x" else tp.y_cc))
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
        # Enforce type per control-class to keep Mapping consistent.
        if spec.kind in ("button", "hat") and kind != "Note":
            kind = "Note"; self._type_combo.setCurrentText("Note")
        elif spec.kind in ("axis", "touchpad") and kind != "CC":
            kind = "CC"; self._type_combo.setCurrentText("CC")

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
            # Auto-enable touchpad on bind — otherwise the CCs sit unused
            # which silently confuses users.
            self._mapping.touchpad.enabled = True

        new_channel = int(self._channel_spin.value()) - 1
        if new_channel != self._mapping.midi_channel:
            self._mapping.midi_channel = new_channel

        name = self._name_edit.text().strip()
        if name:
            self._labels[cid] = name
        else:
            self._labels.pop(cid, None)

        self._refresh_diagram(); self._refresh_table()
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
            # touchpad x/y are flat CCs without a natural "unset" — clear
            # just disables the block.
            self._mapping.touchpad.enabled = False
        self._labels.pop(cid, None)
        self._refresh_diagram(); self._refresh_table()
        self.mapping_changed.emit(self._mapping)

    # --------------------------------------------------------- refresh

    def _refresh_diagram(self) -> None:
        bound: Dict[str, str] = {}
        for spec in CONTROLS:
            b = self._lookup_binding(spec.cid)
            if b is None:
                continue
            if spec.kind == "touchpad" and not self._mapping.touchpad.enabled:
                continue
            kind, val = b
            label = self._labels.get(spec.cid)
            bound[spec.cid] = f"{kind} {val}" + (f" · {label}" if label else "")
        self._diagram.set_bindings(bound)

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
            "exported_at": _now_iso(),
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
        # Accept {"mapping": ..., "labels": ...} or a bare Mapping dict.
        if "mapping" in data:
            self._mapping = Mapping.from_dict(data["mapping"])
            self._labels = {str(k): str(v) for k, v in data.get("labels", {}).items()}
        else:
            self._mapping = Mapping.from_dict(data)
            self._labels = {}
        self._selected = None
        self._diagram.set_selected(None)
        self._sel_header.setText("Selected: —")
        self._refresh_diagram(); self._refresh_table()
        self.mapping_changed.emit(self._mapping)

    def _on_export_resolume(self) -> None:
        """Copy bundled Resolume XML + sidecar JSON of user bindings.

        WHY sidecar: Resolume's XML schema is large and binding-specific
        (path strings hand-mapped to clip/layer routes). Rebuilding it
        per-binding is a future research task; the curated default ships
        as-is, paired with a human-readable JSON dump of bindings so the
        user can wire extras in Resolume's MIDI Learn.
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
            Path(path_str).with_suffix(".bindings.json").write_text(
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
        # Same shape as Resolume export — connectors module owns the schema;
        # this tab is a UI entry point so users can save anywhere.
        path_str = QFileDialog.getExistingDirectory(
            self, "Choose destination folder for Remote Script",
        )
        if not path_str:
            return
        try:
            from ..connectors.ableton import (
                REMOTE_SCRIPT_FOLDER, _template_source,
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
        self._refresh_diagram(); self._refresh_table()
        self.mapping_changed.emit(self._mapping)

    def _template_payload(self) -> dict:
        return {
            "schema_version": 1,
            "name": self._mapping.name or "Untitled",
            "exported_at": _now_iso(),
            "mapping": self._mapping.to_dict(),
            "labels": dict(self._labels),
        }


def _now_iso() -> str:
    return (
        datetime.now(timezone.utc).replace(microsecond=0)
        .isoformat().replace("+00:00", "Z")
    )


def _suggest_value(spec: ControlSpec) -> int:
    """Default MIDI number for a freshly-selected control.

    WHY: spinbox defaults to 0 which is rarely what the user wants; fall
    back to the factory default for that index so the user can save without
    typing.
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
