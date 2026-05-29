"""Stick trail visualiser — 2D polyline showing last few seconds of stick movement.

Holds a ring buffer of (timestamp, x, y) samples and renders a fading polyline
where older samples are dimmer (representing past) and newest sample is full teal.
Includes a deadzone tint, crosshair, and outer ring at full extent.
"""
from __future__ import annotations

import time
from collections import deque
from typing import Deque, Optional, Tuple

from PySide6.QtCore import Qt, QPointF, QRectF, QTimer
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from .accessibility import prefers_reduced_motion


# Palette — match controller_meter.py + visualise_tab.py
STICK_BG = QColor("#16181d")
STICK_BORDER = QColor("#24262d")
STICK_DOT = QColor("#2dd4bf")
TEXT_DIM = QColor("#8a9099")
DEADZONE_TINT = QColor("#1a1d25")
GRID_LINE = QColor("#1f232b")

# Buffer constants
BUFFER_CAPACITY = 150  # ~5 seconds at 30 Hz repaint
REPAINT_THROTTLE_HZ = 30
DEADZONE_RADIUS = 0.15  # Normalized -1..+1 units


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


class StickTrail(QWidget):
    """2D stick trail visualiser. Renders a fading polyline of stick movement
    over the past ~5 seconds."""

    def __init__(self, label: str = "", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._label = label
        self._buffer: Deque[Tuple[float, float, float]] = deque(maxlen=BUFFER_CAPACITY)
        self._last_x = 0.0
        self._last_y = 0.0
        self._last_repaint_time = time.perf_counter()

        self.setFixedSize(180, 180)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        # Throttle repaints to 30 Hz
        self._throttle_timer = QTimer(self)
        self._throttle_timer.setInterval(int(1000 / REPAINT_THROTTLE_HZ))
        self._throttle_timer.timeout.connect(self.update)
        self._throttle_timer.start()

    def add_sample(self, x: float, y: float) -> None:
        """Append a new (timestamp, x, y) sample. x, y should be in -1..+1."""
        # Clamp to -1..+1
        x = max(-1.0, min(1.0, float(x)))
        y = max(-1.0, min(1.0, float(y)))

        ts = time.perf_counter()
        self._buffer.append((ts, x, y))
        self._last_x = x
        self._last_y = y

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        # Background circle
        _filled_rect(p, QRectF(0, 0, w, h), STICK_BG, radius=20)

        # Center point
        cx, cy = w / 2.0, h / 2.0

        # Deadzone circle (tinted)
        deadzone_px = DEADZONE_RADIUS * (w / 2.0 - 6)
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(DEADZONE_TINT))
        p.drawEllipse(QPointF(cx, cy), deadzone_px, deadzone_px)

        # Crosshair at center
        p.setPen(QPen(GRID_LINE, 0.5, Qt.DashLine))
        p.drawLine(QPointF(cx - 12, cy), QPointF(cx + 12, cy))
        p.drawLine(QPointF(cx, cy - 12), QPointF(cx, cy + 12))

        # Draw trail polyline with fading alpha (skip fade if reduce_motion)
        if len(self._buffer) >= 2:
            now = time.perf_counter()
            max_age = (BUFFER_CAPACITY / REPAINT_THROTTLE_HZ)  # ~5 seconds
            reduce_motion = prefers_reduced_motion()

            for i, (ts, x, y) in enumerate(self._buffer):
                age = now - ts
                # Fade from 0% (oldest) to 100% (newest), or full opacity if reduce_motion
                if reduce_motion:
                    alpha = 255
                else:
                    alpha = int(255 * (age / max_age)) if age < max_age else 0
                    alpha = max(0, min(255, 255 - alpha))  # Invert: newest is bright

                color = QColor(STICK_DOT)
                color.setAlpha(alpha)
                p.setPen(QPen(color, 1.5))
                p.setBrush(Qt.NoBrush)

                px = cx + x * (w / 2.0 - 12)
                py = cy + y * (h / 2.0 - 12)

                if i == 0:
                    p.drawPoint(QPointF(px, py))
                else:
                    prev_ts, prev_x, prev_y = self._buffer[i - 1]
                    prev_px = cx + prev_x * (w / 2.0 - 12)
                    prev_py = cy + prev_y * (h / 2.0 - 12)
                    p.drawLine(QPointF(prev_px, prev_py), QPointF(px, py))

        # Current position dot (full brightness)
        px = cx + self._last_x * (w / 2.0 - 12)
        py = cy + self._last_y * (h / 2.0 - 12)
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(STICK_DOT))
        p.drawEllipse(QPointF(px, py), 5, 5)

        # Outer ring at full extent
        max_radius = w / 2.0 - 6
        p.setPen(QPen(GRID_LINE, 1))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(cx, cy), max_radius, max_radius)

        # Label (if provided)
        if self._label:
            _label(p, QRectF(6, h - 16, w - 12, 14), self._label, TEXT_DIM, size=8, bold=False, align=Qt.AlignCenter)
