"""Oscilloscope-style trace for a single axis.

Extracted from visualise_tab.py so both the visualise tab and the live
inspector can reuse the same widget.
"""
from __future__ import annotations

from collections import deque
from typing import Deque, Optional

from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QSizePolicy, QWidget


# Palette — match controller_meter.py + visualise_tab.py
STICK_BG = QColor("#16181d")
STICK_BORDER = QColor("#24262d")
STICK_DOT = QColor("#2dd4bf")
TEXT_DIM = QColor("#8a9099")
PANEL_BG = QColor("#13151a")
GRID_LINE = QColor("#1f232b")

OSCILLOSCOPE_SAMPLES = 150  # ~5 seconds at 30 Hz repaint
OSCILLOSCOPE_WIDTH = 280
OSCILLOSCOPE_HEIGHT = 60


def _font(size: int, bold: bool = False) -> QFont:
    f = QFont()
    f.setPointSize(size)
    f.setBold(bold)
    return f


def _filled_rect(
    p: QPainter,
    rect: QRectF,
    fill: QColor,
    radius: float = 4.0,
    border: QColor = STICK_BORDER,
) -> None:
    p.setPen(QPen(border, 1))
    p.setBrush(QBrush(fill))
    p.drawRoundedRect(rect, radius, radius)


def _label(
    p: QPainter,
    rect: QRectF,
    text: str,
    color: QColor,
    size: int = 8,
    bold: bool = True,
    align=Qt.AlignCenter,
) -> None:
    p.setPen(QPen(color))
    p.setFont(_font(size, bold))
    p.drawText(rect, align, text)


class AxisScope(QWidget):
    """Oscilloscope-style trace for a single axis. Shows last ~5 seconds
    of values in real time. Sticks: -1..+1 centered. Triggers: 0..1."""

    def __init__(self, axis_index: int, label: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._axis_index = axis_index
        self._label = label
        self._samples: Deque[float] = deque(maxlen=OSCILLOSCOPE_SAMPLES)
        self._is_trigger = axis_index >= 4  # 4=L2, 5=R2
        self.setFixedHeight(OSCILLOSCOPE_HEIGHT)
        self.setMinimumWidth(OSCILLOSCOPE_WIDTH)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def add_sample(self, value: float) -> None:
        """Append a new value and drop oldest if at capacity."""
        if self._is_trigger:
            # Trigger: clamp to 0..1
            self._samples.append(max(0.0, min(1.0, float(value))))
        else:
            # Stick: clamp to -1..+1
            self._samples.append(max(-1.0, min(1.0, float(value))))

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        # Background
        _filled_rect(p, QRectF(0, 0, w, h), PANEL_BG, radius=6)

        # Axis label (top-left)
        _label(
            p, QRectF(6, 2, w - 12, 14), self._label, TEXT_DIM, size=7, align=Qt.AlignLeft
        )

        # Current value (top-right, mono font for precision)
        if self._samples:
            val = self._samples[-1]
            val_text = f"{val:+.3f}" if not self._is_trigger else f"{val:.3f}"
        else:
            val_text = "—"
        _label(p, QRectF(6, 2, w - 12, 14), val_text, TEXT_DIM, size=7, align=Qt.AlignRight)

        # Draw center baseline (dashed)
        mid_y = h / 2.0 if not self._is_trigger else h - 10
        p.setPen(QPen(GRID_LINE, 0.5, Qt.DashLine))
        p.drawLine(QPointF(6, mid_y), QPointF(w - 6, mid_y))

        # Draw oscilloscope trace
        if len(self._samples) < 2:
            return

        x_start = 6.0
        x_end = w - 6
        y_top = 18.0
        y_bottom = h - 6.0
        span_y = max(1.0, y_bottom - y_top)
        n = len(self._samples)
        step = (x_end - x_start) / max(1, n - 1)

        poly = QPolygonF()
        for i, val in enumerate(self._samples):
            x = x_start + i * step
            if self._is_trigger:
                # Trigger: 0..1 → bottom..top
                y = y_bottom - (val * span_y)
            else:
                # Stick: -1..+1 centered at mid
                y = y_top + ((1.0 - (val + 1.0) / 2.0) * span_y)
            poly.append(QPointF(x, y))

        p.setPen(QPen(STICK_DOT, 1.2))
        p.setBrush(Qt.NoBrush)
        p.drawPolyline(poly)
