"""Live controller visualizer — two stick crosshairs + a button grid.

Subscribes to BridgeWorker.axis_value / button_state signals. Repaints at the
signal rate (already throttled to ~30Hz by the bridge).
"""
from __future__ import annotations

from typing import Dict, Optional

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget


STICK_BG = QColor("#16181d")
STICK_BORDER = QColor("#24262d")
STICK_DOT = QColor("#2dd4bf")
BUTTON_OFF = QColor("#1f232b")
BUTTON_ON = QColor("#2dd4bf")
TEXT_DIM = QColor("#8a9099")


class ControllerMeter(QWidget):
    """Visualises stick positions, trigger pressure, and button state."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(460)
        self._axes: Dict[int, float] = {}
        self._buttons: Dict[int, bool] = {}
        self._hats: Dict[str, bool] = {}
        self._connected = False
        self._controller_name = ""
        # Touchpad state
        self._touch_contact = False
        self._touch_x = 0.5
        self._touch_y = 0.5
        # Battery / transport state
        self._battery_percent: int = -1   # -1 = unknown
        self._battery_charging = False
        self._battery_full = False
        self._wired = False

    # ---------------------------------------------------------- public setters

    def set_connected(self, connected: bool, name: str = "") -> None:
        self._connected = connected
        self._controller_name = name
        if not connected:
            self._axes.clear()
            self._buttons.clear()
            self._hats.clear()
            self._touch_contact = False
            self._touch_x = 0.5
            self._touch_y = 0.5
            self._battery_percent = -1
            self._battery_charging = False
            self._battery_full = False
            self._wired = False
        self.update()

    def on_axis(self, idx: int, value: float) -> None:
        self._axes[idx] = value
        self.update()

    def on_button(self, idx: int, pressed: bool) -> None:
        self._buttons[idx] = pressed
        self.update()

    def on_hat(self, direction: str, pressed: bool) -> None:
        self._hats[direction] = pressed
        self.update()

    def on_touchpad(self, contact: bool, x_norm: float, y_norm: float) -> None:
        self._touch_contact = contact
        self._touch_x = x_norm   # 0..1, 0 = left
        self._touch_y = y_norm   # 0..1, 0 = top
        self.update()

    def on_battery(self, percent: int, charging: bool, fully_charged: bool) -> None:
        self._battery_percent = percent
        self._battery_charging = charging
        self._battery_full = fully_charged
        self.update()

    def on_transport(self, wired: bool) -> None:
        self._wired = wired
        self.update()

    # ---------------------------------------------------------- painting

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        if not self._connected:
            p.setPen(QPen(TEXT_DIM))
            f = QFont()
            f.setPointSize(13)
            p.setFont(f)
            p.drawText(self.rect(), Qt.AlignCenter,
                       "No controller connected.\nPlug in a PS5 or Xbox controller, then click Start.")
            return

        w = self.width()
        h = self.height()
        margin = 24
        stick_size = min((w - margin * 3) / 2, 180)
        stick_y = margin + 28

        # Header
        p.setPen(QPen(QColor("#f5f7fa")))
        f = QFont()
        f.setPointSize(11)
        f.setBold(True)
        p.setFont(f)
        p.drawText(margin, margin + 12, self._controller_name)

        # Top-right battery + transport cluster (only if we have a DualSense handle)
        if self._battery_percent != -1:
            self._draw_status_cluster(p, w - margin, margin)

        # Left stick (axes 0/1) and right stick (axes 2/3)
        self._draw_stick(p, margin, stick_y, stick_size,
                         self._axes.get(0, 0.0), self._axes.get(1, 0.0), "L STICK")
        self._draw_stick(p, w - margin - stick_size, stick_y, stick_size,
                         self._axes.get(2, 0.0), self._axes.get(3, 0.0), "R STICK")

        # Triggers (axes 4/5) — horizontal bars under the sticks
        trigger_y = stick_y + stick_size + 24
        self._draw_trigger(p, margin, trigger_y, stick_size, self._axes.get(4, -1.0), "L2")
        self._draw_trigger(p, w - margin - stick_size, trigger_y,
                           stick_size, self._axes.get(5, -1.0), "R2")

        # Button row — face/shoulder buttons indexed 0..10
        button_y = trigger_y + 40
        button_size = 26
        gap = 8
        total = 11
        total_width = total * button_size + (total - 1) * gap
        start_x = (w - total_width) // 2
        for i in range(total):
            x = start_x + i * (button_size + gap)
            self._draw_button(p, x, button_y, button_size, self._buttons.get(i, False), str(i))

        # D-pad
        dpad_y = button_y + button_size + 24
        self._draw_dpad(p, w // 2 - 50, dpad_y)

        # Touchpad — horizontal rect (~2:1) centred below the d-pad
        dpad_height = 24 * 3 + 4 * 2  # three cells + two gaps
        touch_w = 280
        touch_h = 90
        touch_x = (w - touch_w) // 2
        touch_y = dpad_y + dpad_height + 28
        self._draw_touchpad(p, touch_x, touch_y, touch_w, touch_h)

    def _draw_stick(self, p: QPainter, x: float, y: float, size: float,
                    x_val: float, y_val: float, label: str) -> None:
        rect = QRectF(x, y, size, size)
        p.setPen(QPen(STICK_BORDER, 1))
        p.setBrush(QBrush(STICK_BG))
        p.drawRoundedRect(rect, 12, 12)

        # Crosshair
        cx, cy = x + size / 2, y + size / 2
        p.setPen(QPen(QColor("#24262d"), 1, Qt.DashLine))
        p.drawLine(QPointF(x + 12, cy), QPointF(x + size - 12, cy))
        p.drawLine(QPointF(cx, y + 12), QPointF(cx, y + size - 12))

        # Dot
        dot_x = cx + (x_val * (size / 2 - 14))
        dot_y = cy + (y_val * (size / 2 - 14))
        p.setBrush(QBrush(STICK_DOT))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(dot_x, dot_y), 10, 10)

        # Label
        p.setPen(QPen(TEXT_DIM))
        f = QFont()
        f.setPointSize(9)
        f.setBold(True)
        p.setFont(f)
        p.drawText(QRectF(x, y - 18, size, 16), Qt.AlignCenter, label)

    def _draw_trigger(self, p: QPainter, x: float, y: float, width: float,
                      raw_value: float, label: str) -> None:
        # Trigger axis is -1 (released) to +1 (fully pressed). Normalize to 0..1.
        normalized = max(0.0, (raw_value + 1.0) / 2.0)
        bg = QRectF(x, y, width, 14)
        p.setPen(QPen(STICK_BORDER, 1))
        p.setBrush(QBrush(STICK_BG))
        p.drawRoundedRect(bg, 7, 7)

        if normalized > 0:
            fill = QRectF(x, y, width * normalized, 14)
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(STICK_DOT))
            p.drawRoundedRect(fill, 7, 7)

        p.setPen(QPen(TEXT_DIM))
        f = QFont()
        f.setPointSize(9)
        p.setFont(f)
        p.drawText(QRectF(x, y + 18, width, 14), Qt.AlignLeft, label)
        p.drawText(QRectF(x, y + 18, width, 14), Qt.AlignRight,
                   f"{int(normalized * 100)}%")

    def _draw_button(self, p: QPainter, x: float, y: float, size: float,
                     pressed: bool, label: str) -> None:
        rect = QRectF(x, y, size, size)
        p.setPen(QPen(STICK_BORDER, 1))
        p.setBrush(QBrush(BUTTON_ON if pressed else BUTTON_OFF))
        p.drawRoundedRect(rect, 4, 4)
        p.setPen(QPen(QColor("#0e0f12") if pressed else TEXT_DIM))
        f = QFont()
        f.setPointSize(9)
        f.setBold(True)
        p.setFont(f)
        p.drawText(rect, Qt.AlignCenter, label)

    def _draw_dpad(self, p: QPainter, x: float, y: float) -> None:
        size = 24
        gap = 4
        # cross layout
        positions = {
            "up":    (x + size + gap, y),
            "left":  (x, y + size + gap),
            "right": (x + (size + gap) * 2, y + size + gap),
            "down":  (x + size + gap, y + (size + gap) * 2),
        }
        for direction, (px, py) in positions.items():
            pressed = self._hats.get(direction, False)
            rect = QRectF(px, py, size, size)
            p.setPen(QPen(STICK_BORDER, 1))
            p.setBrush(QBrush(BUTTON_ON if pressed else BUTTON_OFF))
            p.drawRoundedRect(rect, 3, 3)

    def _draw_touchpad(self, p: QPainter, x: float, y: float,
                       width: float, height: float) -> None:
        # Label (matches L STICK / R STICK style)
        p.setPen(QPen(TEXT_DIM))
        f = QFont()
        f.setPointSize(9)
        f.setBold(True)
        p.setFont(f)
        p.drawText(QRectF(x, y - 18, width, 16), Qt.AlignCenter, "TOUCHPAD")

        # Outline rectangle
        rect = QRectF(x, y, width, height)
        p.setPen(QPen(STICK_BORDER, 1))
        p.setBrush(QBrush(STICK_BG))
        p.drawRoundedRect(rect, 10, 10)

        if not self._touch_contact:
            return

        # Clamp finger position into 0..1 then map onto the pad
        tx = max(0.0, min(1.0, self._touch_x))
        ty = max(0.0, min(1.0, self._touch_y))
        pad = 10.0
        dot_x = x + pad + tx * (width - pad * 2)
        dot_y = y + pad + ty * (height - pad * 2)

        # Glow halo
        halo = QColor(STICK_DOT)
        halo.setAlpha(60)
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(halo))
        p.drawEllipse(QPointF(dot_x, dot_y), 16, 16)

        # Solid dot
        p.setBrush(QBrush(STICK_DOT))
        p.drawEllipse(QPointF(dot_x, dot_y), 8, 8)

    def _draw_status_cluster(self, p: QPainter, right_x: float, top_y: float) -> None:
        # Transport chip (USB / BT) sits to the LEFT of the battery pill
        chip_w = 32
        chip_h = 18
        pill_w = 60
        pill_h = 18
        gap = 6

        pill_x = right_x - pill_w
        chip_x = pill_x - gap - chip_w

        # Transport chip
        chip_rect = QRectF(chip_x, top_y, chip_w, chip_h)
        p.setPen(QPen(STICK_BORDER, 1))
        p.setBrush(QBrush(BUTTON_OFF))
        p.drawRoundedRect(chip_rect, 4, 4)
        chip_label = "USB" if self._wired else "BT"
        chip_text_color = QColor("#2dd4bf") if self._wired else TEXT_DIM
        p.setPen(QPen(chip_text_color))
        f = QFont()
        f.setPointSize(8)
        f.setBold(True)
        p.setFont(f)
        p.drawText(chip_rect, Qt.AlignCenter, chip_label)

        # Battery pill
        pct = self._battery_percent
        pill_rect = QRectF(pill_x, top_y, pill_w, pill_h)
        if pct == -1:
            fill_color = QColor("#1f232b")
        elif pct >= 80:
            fill_color = QColor("#2dd4bf")
        elif pct >= 30:
            fill_color = QColor("#f5c450")
        else:
            fill_color = QColor("#f97373")
        p.setPen(QPen(STICK_BORDER, 1))
        p.setBrush(QBrush(fill_color))
        p.drawRoundedRect(pill_rect, 9, 9)

        # Text inside pill — percent + charging glyph
        if pct == -1:
            label = "—"
        else:
            bolt = "⚡" if self._battery_charging or self._battery_full else ""
            label = f"{bolt}{pct}%" if bolt else f"{pct}%"
        # Dark text on bright fills, dim text on unknown grey
        text_color = QColor("#0e0f12") if pct != -1 else TEXT_DIM
        p.setPen(QPen(text_color))
        f = QFont()
        f.setPointSize(8)
        f.setBold(True)
        p.setFont(f)
        p.drawText(pill_rect, Qt.AlignCenter, label)
