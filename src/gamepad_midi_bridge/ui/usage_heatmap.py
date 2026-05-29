"""UsageHeatmap — controller silhouette tinted by per-control usage frequency.

Colour ramp: dark-grey (0) → blue (low) → teal (medium) → yellow (heavy).
Refreshes from UsageTracker every 2 s via QTimer.
"""
from __future__ import annotations

from typing import Dict, Optional

from PySide6.QtCore import QRect, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)

from ..usage_stats import tracker, UsageRecord


# ---------------------------------------------------------------------------
# Colour ramp: count=0 → dark grey, low → blue, mid → teal, high → yellow
# ---------------------------------------------------------------------------

_COLD   = QColor("#1a1d26")   # 0  — not pressed at all
_BLUE   = QColor("#2563eb")   # low usage
_TEAL   = QColor("#2dd4bf")   # medium
_YELLOW = QColor("#facc15")   # heavy


def _heat_color(t: float) -> QColor:
    """Interpolate through cold→blue→teal→yellow for t in 0..1."""
    if t <= 0.0:
        return _COLD
    if t < 0.33:
        s = t / 0.33
        return _lerp(_COLD, _BLUE, s)
    if t < 0.66:
        s = (t - 0.33) / 0.33
        return _lerp(_BLUE, _TEAL, s)
    s = (t - 0.66) / 0.34
    return _lerp(_TEAL, _YELLOW, s)


def _lerp(a: QColor, b: QColor, t: float) -> QColor:
    return QColor(
        int(a.red()   + (b.red()   - a.red())   * t),
        int(a.green() + (b.green() - a.green()) * t),
        int(a.blue()  + (b.blue()  - a.blue())  * t),
    )


# ---------------------------------------------------------------------------
# Control geometry — same coordinate system as controller_preview.py (280×200)
# ---------------------------------------------------------------------------

_BG      = QColor("#0a0b0e")
_BORDER  = QColor("#3a3f52")
_TEXT    = QColor("#8a9099")
_TEXT_DK = QColor("#0e0f12")   # label on bright cells

BODY_RECT = QRectF(10, 30, 260, 150)

LS_CX, LS_CY, LS_R = 72, 115, 18
RS_CX, RS_CY, RS_R = 168, 115, 18

DPAD_CX, DPAD_CY = 100, 110
DPAD_ARM, DPAD_LEN = 9, 20

FACE_BUTTONS = {
    "triangle": (210, 88,  9, "△"),
    "cross":    (210, 110, 9, "✕"),
    "circle":   (222, 99,  9, "○"),
    "square":   (198, 99,  9, "□"),
}

L1_RECT = QRectF(28,  18, 44, 14)
R1_RECT = QRectF(208, 18, 44, 14)
L2_RECT = QRectF(28,  4,  44, 14)
R2_RECT = QRectF(208, 4,  44, 14)
TP_RECT = QRectF(108, 50, 64, 38)

OPTIONS_CX, OPTIONS_CY, OPTIONS_R = 186, 65, 7
CREATE_CX,  CREATE_CY,  CREATE_R  = 140, 65, 7


# ---------------------------------------------------------------------------
# Map (kind, index) → shape name.  Mirrors the canonical button indices used
# by the bridge so record() keys resolve to the right silhouette region.
# ---------------------------------------------------------------------------

_BUTTON_SHAPE: Dict[int, str] = {
    0: "cross", 1: "circle", 2: "square", 3: "triangle",
    4: "l1", 5: "r1", 6: "l2_btn", 7: "r2_btn",
    8: "create", 9: "options", 10: "l3", 11: "r3",
}
_HAT_SHAPE: Dict[str, str] = {
    "up": "dpad_up", "down": "dpad_down",
    "left": "dpad_left", "right": "dpad_right",
}
_AXIS_SHAPE: Dict[int, str] = {
    0: "ls", 1: "ls", 2: "rs", 3: "rs", 4: "l2", 5: "r2",
}
_CORNER_SHAPE: Dict[str, str] = {"L": "ls", "R": "rs"}


def _records_to_heat(records: list[UsageRecord]) -> Dict[str, float]:
    """Convert snapshot → shape → normalised heat (0..1)."""
    counts: Dict[str, int] = {}
    for r in records:
        shape: Optional[str] = None
        if r.kind == "button":
            shape = _BUTTON_SHAPE.get(int(r.index) if isinstance(r.index, int) else -1)
        elif r.kind == "hat":
            shape = _HAT_SHAPE.get(str(r.index))
        elif r.kind == "axis":
            shape = _AXIS_SHAPE.get(int(r.index) if isinstance(r.index, int) else -1)
        elif r.kind == "corner":
            shape = _CORNER_SHAPE.get(str(r.index))
        if shape:
            counts[shape] = counts.get(shape, 0) + r.count

    if not counts:
        return {}
    max_count = max(counts.values())
    if max_count == 0:
        return {}
    return {s: c / max_count for s, c in counts.items()}


class _SilhouetteHeatmap(QWidget):
    """280×200 controller silhouette with heat-tinted controls."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedSize(280, 200)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self._heat: Dict[str, float] = {}

    def set_heat(self, heat: Dict[str, float]) -> None:
        self._heat = heat
        self.update()

    # ---- paint ------------------------------------------------------------

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), _BG)

        # Body
        p.setPen(QPen(_BORDER, 1.5))
        p.setBrush(_COLD)
        p.drawRoundedRect(BODY_RECT, 30, 30)

        # Shoulders L1/R1
        self._rect_ctrl(p, L1_RECT, "l1", "L1")
        self._rect_ctrl(p, R1_RECT, "r1", "R1")

        # Triggers L2/R2
        self._rect_ctrl(p, L2_RECT, "l2", "L2")
        self._rect_ctrl(p, R2_RECT, "r2", "R2")

        # Touchpad (maps from axis/touch data — keep dim for now)
        p.setPen(QPen(_BORDER, 1.5))
        p.setBrush(_COLD)
        p.drawRoundedRect(TP_RECT, 4, 4)
        self._tiny_label(p, TP_RECT, "TP")

        # D-pad
        self._draw_dpad(p)

        # Sticks
        self._circle_ctrl(p, LS_CX, LS_CY, LS_R, "ls", "LS")
        self._circle_ctrl(p, RS_CX, RS_CY, RS_R, "rs", "RS")

        # Face buttons
        for shape, (cx, cy, r, sym) in FACE_BUTTONS.items():
            t = self._heat.get(shape, 0.0)
            fill = _heat_color(t)
            p.setPen(QPen(_BORDER, 1.5))
            p.setBrush(fill)
            p.drawEllipse(int(cx - r), int(cy - r), r * 2, r * 2)
            p.setPen(_TEXT_DK if t > 0.4 else _TEXT)
            f = QFont(); f.setPixelSize(7); p.setFont(f)
            p.drawText(QRect(int(cx - r), int(cy - r), r * 2, r * 2),
                       Qt.AlignCenter, sym)

        # Options / Create
        self._small_btn(p, OPTIONS_CX, OPTIONS_CY, OPTIONS_R, "options", "⋯")
        self._small_btn(p, CREATE_CX,  CREATE_CY,  CREATE_R,  "create",  "+")

        p.end()

    # ---- helpers ----------------------------------------------------------

    def _rect_ctrl(self, p: QPainter, rect: QRectF, key: str, lbl: str) -> None:
        t = self._heat.get(key, 0.0)
        fill = _heat_color(t)
        p.setPen(QPen(_BORDER, 1.5))
        p.setBrush(fill)
        p.drawRoundedRect(rect, 4, 4)
        p.setPen(_TEXT_DK if t > 0.4 else _TEXT)
        f = QFont(); f.setPixelSize(7); p.setFont(f)
        p.drawText(rect.toRect(), Qt.AlignCenter, lbl)

    def _circle_ctrl(self, p: QPainter, cx: int, cy: int, r: int,
                     key: str, lbl: str) -> None:
        t = self._heat.get(key, 0.0)
        fill = _heat_color(t)
        p.setPen(QPen(_BORDER, 1.5))
        p.setBrush(fill)
        p.drawEllipse(cx - r, cy - r, r * 2, r * 2)
        p.setPen(_TEXT_DK if t > 0.4 else _TEXT)
        f = QFont(); f.setPixelSize(7); p.setFont(f)
        p.drawText(QRect(cx - r, cy - r, r * 2, r * 2), Qt.AlignCenter, lbl)

    def _draw_dpad(self, p: QPainter) -> None:
        cx, cy = DPAD_CX, DPAD_CY
        arms = [
            ("dpad_up",    QRect(cx - DPAD_ARM, cy - DPAD_LEN - DPAD_ARM, DPAD_ARM * 2, DPAD_LEN)),
            ("dpad_down",  QRect(cx - DPAD_ARM, cy + DPAD_ARM,            DPAD_ARM * 2, DPAD_LEN)),
            ("dpad_left",  QRect(cx - DPAD_LEN - DPAD_ARM, cy - DPAD_ARM, DPAD_LEN,    DPAD_ARM * 2)),
            ("dpad_right", QRect(cx + DPAD_ARM, cy - DPAD_ARM,            DPAD_LEN,    DPAD_ARM * 2)),
        ]
        f = QFont(); f.setPixelSize(5)
        for key, rect in arms:
            t = self._heat.get(key, 0.0)
            fill = _heat_color(t)
            p.setPen(QPen(_BORDER, 1.0))
            p.setBrush(fill)
            p.drawRect(rect)

    def _small_btn(self, p: QPainter, cx: int, cy: int, r: int,
                   key: str, sym: str) -> None:
        t = self._heat.get(key, 0.0)
        fill = _heat_color(t)
        p.setPen(QPen(_BORDER, 1.0))
        p.setBrush(fill)
        p.drawEllipse(cx - r, cy - r, r * 2, r * 2)
        p.setPen(_TEXT_DK if t > 0.4 else _TEXT)
        f = QFont(); f.setPixelSize(6); p.setFont(f)
        p.drawText(QRect(cx - r, cy - r, r * 2, r * 2), Qt.AlignCenter, sym)

    def _tiny_label(self, p: QPainter, rect: QRectF, text: str) -> None:
        p.setPen(_TEXT)
        f = QFont(); f.setPixelSize(7); p.setFont(f)
        p.drawText(rect.toRect(), Qt.AlignCenter, text)


# ---------------------------------------------------------------------------
# Top-5 list widget
# ---------------------------------------------------------------------------

class _Top5List(QWidget):
    """Compact ranked list showing the 5 most-used controls."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(3)
        self._rows: list[QLabel] = []
        for _ in range(5):
            lbl = QLabel("—")
            lbl.setStyleSheet("color: #8a9099; font-size: 11px;")
            v.addWidget(lbl)
            self._rows.append(lbl)

    def update_records(self, records: list[UsageRecord]) -> None:
        for i, lbl in enumerate(self._rows):
            if i < len(records):
                r = records[i]
                idx_str = str(r.index)
                lbl.setText(f"#{i + 1}  {r.kind}[{idx_str}]  ×{r.count:,}")
            else:
                lbl.setText("—")


# ---------------------------------------------------------------------------
# Public widget
# ---------------------------------------------------------------------------

class UsageHeatmap(QWidget):
    """Controller silhouette heatmap + top-5 list + Reset button.

    Auto-refreshes every 2 s from the global UsageTracker singleton.
    Can be embedded anywhere — currently wired into VisualiseTab.
    """

    REFRESH_MS = 2000

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._build_ui()

        self._timer = QTimer(self)
        self._timer.setInterval(self.REFRESH_MS)
        self._timer.timeout.connect(self._refresh)
        self._timer.start()

        # Initial paint with whatever's already in the tracker.
        self._refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        # Header row: title + reset button
        header = QHBoxLayout()
        title = QLabel("CONTROL USAGE")
        title.setStyleSheet(
            "color: #8a9099; font-size: 10px; font-weight: 700; letter-spacing: 1px;"
        )
        header.addWidget(title)
        header.addStretch()
        reset_btn = QPushButton("Reset stats")
        reset_btn.setFixedHeight(22)
        reset_btn.setStyleSheet(
            "QPushButton { background: #1f232b; color: #8a9099; border: 1px solid #2c3040;"
            " border-radius: 4px; padding: 0 8px; font-size: 10px; }"
            "QPushButton:hover { background: #2c3040; color: #f5f7fa; }"
        )
        reset_btn.clicked.connect(self._reset)
        header.addWidget(reset_btn)
        root.addLayout(header)

        # Silhouette + top-5 side-by-side
        body = QHBoxLayout()
        body.setSpacing(16)
        self._silhouette = _SilhouetteHeatmap()
        body.addWidget(self._silhouette)

        right = QVBoxLayout()
        right.setSpacing(4)
        top5_title = QLabel("TOP 5")
        top5_title.setStyleSheet(
            "color: #5a606b; font-size: 9px; font-weight: 600;"
        )
        right.addWidget(top5_title)
        self._top5 = _Top5List()
        right.addWidget(self._top5)
        right.addStretch()
        body.addLayout(right)
        root.addLayout(body)

    def _refresh(self) -> None:
        t = tracker()
        records = t.snapshot()
        heat = _records_to_heat(records)
        self._silhouette.set_heat(heat)
        self._top5.update_records(t.top_n(5))

    def _reset(self) -> None:
        tracker().reset()
        self._refresh()
