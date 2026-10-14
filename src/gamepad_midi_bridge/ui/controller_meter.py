"""Live controller visualizer — two stick crosshairs + a button grid.

Subscribes to BridgeWorker.axis_value / button_state signals. Repaints at the
signal rate (already throttled to ~30Hz by the bridge).
"""
from __future__ import annotations

from typing import Dict, Optional

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

from ..control_labels import (
    DPAD_ARROWS, DPAD_LABELS, button_glyph, button_label, family_for,
    has_touchpad, shoulder_label, trigger_label,
)


STICK_BG = QColor("#16181d")
STICK_BORDER = QColor("#24262d")
STICK_DOT = QColor("#2dd4bf")
BUTTON_OFF = QColor("#1f232b")
BUTTON_ON = QColor("#2dd4bf")
TEXT_DIM = QColor("#8a9099")


class ControllerMeter(QWidget):
    """Visualises stick positions, trigger pressure, and button state."""

    selection_changed = Signal(dict)


    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        # 460 was the old hard floor — keeping it as the preferred height
        # via sizeHint while leaving the minimum at 0 so the parent
        # QScrollArea can shrink past it when the window is collapsed.
        self.setMinimumHeight(0)
        self.setMinimumWidth(200)
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
        # Cache for clickable control rectangles — used for hitbox detection
        self._stick_rects: Dict[str, tuple] = {}  # "left"|"right" -> (x, y, size)
        self._button_rects: Dict[int, tuple] = {}  # button_idx -> (x, y, size)
        self._dpad_rects: Dict[str, tuple] = {}    # "up"|"down"|"left"|"right" -> (x, y, size)
        self._trigger_rects: Dict[str, tuple] = {} # "L2"|"R2" -> (x, y, width, height)
        self._touchpad_rect: Optional[tuple] = None  # (x, y, width, height)

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

    def mousePressEvent(self, event) -> None:
        """Detect clicks on stick, button, d-pad, trigger, or touchpad and emit selection."""
        x, y = event.position().x(), event.position().y()
        
        # Check sticks
        for stick_name, (sx, sy, size) in self._stick_rects.items():
            if sx <= x <= sx + size and sy <= y <= sy + size:
                idx = 0 if stick_name == "left" else 2
                payload = {
                    "kind": "stick",
                    "index": idx,
                    "label": f"{stick_name.title()} Stick",
                    "value": 0.0,
                }
                self.selection_changed.emit(payload)
                return
        
        # Check buttons
        for btn_idx, (bx, by, bsize) in self._button_rects.items():
            if bx <= x <= bx + bsize and by <= y <= by + bsize:
                payload = {
                    "kind": "button",
                    "index": btn_idx,
                    "value": 1.0 if self._buttons.get(btn_idx, False) else 0.0,
                    "label": f"Button {btn_idx}",
                }
                self.selection_changed.emit(payload)
                return
        
        # Check d-pad
        for direction, (dx, dy, dsize) in self._dpad_rects.items():
            if dx <= x <= dx + dsize and dy <= y <= dy + dsize:
                payload = {
                    "kind": "dpad",
                    "index": direction,
                    "value": 1.0 if self._hats.get(direction, False) else 0.0,
                    "label": f"D-Pad {direction.title()}",
                }
                self.selection_changed.emit(payload)
                return
        
        # Check triggers
        for trigger_name, (tx, ty, tw, th) in self._trigger_rects.items():
            if tx <= x <= tx + tw and ty <= y <= ty + th:
                idx = 4 if trigger_name == "L2" else 5
                payload = {
                    "kind": "trigger",
                    "index": idx,
                    "value": self._axes.get(idx, -1.0),
                    "label": trigger_name,
                }
                self.selection_changed.emit(payload)
                return
        
        # Check touchpad
        if self._touchpad_rect:
            tx, ty, tw, th = self._touchpad_rect
            if tx <= x <= tx + tw and ty <= y <= ty + th:
                payload = {
                    "kind": "touchpad",
                    "index": -1,
                    "value": 1.0 if self._touch_contact else 0.0,
                    "label": "Touchpad",
                }
                self.selection_changed.emit(payload)
                return

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

        family = family_for(self._controller_name)
        w = self.width()
        margin = 20

        # Header
        p.setPen(QPen(QColor("#f5f7fa")))
        f = QFont()
        f.setPointSize(11)
        f.setBold(True)
        p.setFont(f)
        p.drawText(margin, margin + 12, self._controller_name)

        if self._battery_percent != -1:
            self._draw_status_cluster(p, w - margin, margin)

        # ---- Three-column layout -------------------------------------
        # Left rail: shoulder/trigger + D-pad, right rail: shoulder/trigger
        # + face buttons, centre: the sticks with live numeric readouts.
        # Mirrors the Max-for-Live "Gamepad Control" layout so every input
        # has a NAME on screen instead of an anonymous numbered square.
        top = margin + 34
        rail_w = max(132, min(190, int((w - margin * 2) * 0.26)))
        centre_x = margin + rail_w + 20
        centre_w = max(160, w - (margin + rail_w + 20) * 2)
        right_x = w - margin - rail_w

        row_h = 26
        row_gap = 6

        # --- left rail: L1 / L2, then the D-pad rows ---
        y = top
        self._draw_control_row(p, margin, y, rail_w, row_h,
                               shoulder_label("L1", family),
                               self._buttons.get(4, False), button_index=4)
        y += row_h + row_gap
        self._draw_trigger_row(p, margin, y, rail_w, row_h,
                               trigger_label("L2", family),
                               self._axes.get(4, -1.0), "L2")
        y += row_h + row_gap * 2
        for direction in ("up", "down", "left", "right"):
            self._draw_control_row(
                p, margin, y, rail_w, row_h,
                f"{DPAD_ARROWS[direction]}  {DPAD_LABELS[direction]}",
                self._hats.get(direction, False), hat=direction)
            y += row_h + row_gap
        left_bottom = y

        # --- right rail: R1 / R2, then the face buttons ---
        y = top
        self._draw_control_row(p, right_x, y, rail_w, row_h,
                               shoulder_label("R1", family),
                               self._buttons.get(5, False), button_index=5)
        y += row_h + row_gap
        self._draw_trigger_row(p, right_x, y, rail_w, row_h,
                               trigger_label("R2", family),
                               self._axes.get(5, -1.0), "R2")
        y += row_h + row_gap * 2
        # Top-to-bottom in the same order as the physical diamond.
        for idx in (3, 2, 1, 0):
            glyph = button_glyph(idx, family)
            name = button_label(idx, family)
            # On Xbox the glyph IS the name ("A"), so don't render "A   A".
            label = name if glyph == name else f"{glyph}   {name}"
            self._draw_control_row(p, right_x, y, rail_w, row_h, label,
                                   self._buttons.get(idx, False),
                                   button_index=idx)
            y += row_h + row_gap
        right_bottom = y

        # --- centre: both sticks side by side with numeric X/Y ---
        stick_size = min((centre_w - 20) / 2, 150)
        stick_y = top + 10
        gap = centre_w - stick_size * 2
        self._draw_stick(p, centre_x, stick_y, stick_size,
                         self._axes.get(0, 0.0), self._axes.get(1, 0.0),
                         "L STICK")
        self._draw_stick(p, centre_x + stick_size + gap, stick_y, stick_size,
                         self._axes.get(2, 0.0), self._axes.get(3, 0.0),
                         "R STICK")

        # L3 / R3 (stick clicks) sit directly under their stick.
        click_y = stick_y + stick_size + 30
        self._draw_control_row(p, centre_x, click_y, stick_size, row_h,
                               button_label(8, family),
                               self._buttons.get(8, False), button_index=8)
        self._draw_control_row(p, centre_x + stick_size + gap, click_y,
                               stick_size, row_h, button_label(9, family),
                               self._buttons.get(9, False), button_index=9)

        # Select / Start / Home across the centre, below the stick clicks.
        meta_y = click_y + row_h + row_gap * 2
        meta_w = (centre_w - row_gap * 2) / 3
        for i, idx in enumerate((6, 10, 7)):
            self._draw_control_row(
                p, centre_x + i * (meta_w + row_gap), meta_y, meta_w, row_h,
                button_label(idx, family), self._buttons.get(idx, False),
                button_index=idx)
        centre_bottom = meta_y + row_h

        # --- touchpad: PlayStation only, full width under everything ---
        self._touchpad_rect = None
        if has_touchpad(family):
            touch_y = max(left_bottom, right_bottom, centre_bottom) + 18
            touch_w = min(320, w - margin * 2)
            self._draw_touchpad(p, (w - touch_w) // 2, touch_y, touch_w, 90)

    def _draw_control_row(self, p: QPainter, x: float, y: float,
                          width: float, height: float, label: str,
                          active: bool, button_index: Optional[int] = None,
                          hat: Optional[str] = None) -> None:
        """A named control pill that lights up while held.

        Replaces the old anonymous numbered squares — "7" told the user
        nothing, "Menu" tells them exactly which physical button fired.
        """
        if button_index is not None:
            self._button_rects[button_index] = (x, y, height)
        if hat is not None:
            self._dpad_rects[hat] = (x, y, height)
        rect = QRectF(x, y, width, height)
        p.setPen(QPen(STICK_BORDER, 1))
        p.setBrush(QBrush(BUTTON_ON if active else BUTTON_OFF))
        p.drawRoundedRect(rect, 5, 5)
        p.setPen(QPen(QColor("#0e0f12") if active else TEXT_DIM))
        f = QFont()
        f.setPointSize(9)
        f.setBold(True)
        p.setFont(f)
        p.drawText(rect.adjusted(10, 0, -10, 0), Qt.AlignVCenter | Qt.AlignLeft,
                   label)

    def _draw_trigger_row(self, p: QPainter, x: float, y: float,
                          width: float, height: float, label: str,
                          raw_value: float, side: str) -> None:
        """Analogue trigger as a labelled fill bar with a live percentage."""
        normalized = max(0.0, min(1.0, (raw_value + 1.0) / 2.0))
        self._trigger_rects[side] = (x, y, width, height)
        rect = QRectF(x, y, width, height)
        p.setPen(QPen(STICK_BORDER, 1))
        p.setBrush(QBrush(STICK_BG))
        p.drawRoundedRect(rect, 5, 5)
        if normalized > 0.001:
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(STICK_DOT))
            p.drawRoundedRect(QRectF(x, y, width * normalized, height), 5, 5)
        # Text sits above the fill so it stays readable at any level.
        f = QFont()
        f.setPointSize(9)
        f.setBold(True)
        p.setFont(f)
        p.setPen(QPen(TEXT_DIM if normalized < 0.5 else QColor("#0e0f12")))
        inner = rect.adjusted(10, 0, -10, 0)
        p.drawText(inner, Qt.AlignVCenter | Qt.AlignLeft, label)
        p.drawText(inner, Qt.AlignVCenter | Qt.AlignRight,
                   f"{int(normalized * 100)}%")

    def _draw_stick(self, p: QPainter, x: float, y: float, size: float,
                    x_val: float, y_val: float, label: str) -> None:
        # Cache hitbox for clicking
        stick_name = "left" if "L" in label else "right"
        self._stick_rects[stick_name] = (x, y, size)
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

        # Label above
        p.setPen(QPen(TEXT_DIM))
        f = QFont()
        f.setPointSize(9)
        f.setBold(True)
        p.setFont(f)
        p.drawText(QRectF(x, y - 18, size, 16), Qt.AlignCenter, label)

        # Live numeric X/Y under the box — the reference device shows these
        # and they matter for calibration: a pad with stick drift reads a
        # non-zero value at rest, which is invisible on a crosshair alone.
        f2 = QFont()
        f2.setPointSize(8)
        f2.setStyleHint(QFont.Monospace)
        p.setFont(f2)
        p.setPen(QPen(TEXT_DIM))
        readout = QRectF(x, y + size + 2, size, 14)
        p.drawText(readout, Qt.AlignLeft | Qt.AlignVCenter, f" X {x_val:+.3f}")
        p.drawText(readout, Qt.AlignRight | Qt.AlignVCenter, f"Y {y_val:+.3f} ")

    def _draw_trigger(self, p: QPainter, x: float, y: float, width: float,
                      raw_value: float, label: str) -> None:
        # Trigger axis is -1 (released) to +1 (fully pressed). Normalize to 0..1.
        normalized = max(0.0, (raw_value + 1.0) / 2.0)
        # Cache hitbox for clicking
        self._trigger_rects[label] = (x, y, width, 14)
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
        # Cache hitbox for clicking
        try:
            btn_idx = int(label)
            self._button_rects[btn_idx] = (x, y, size)
        except ValueError:
            pass
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
            # Cache hitbox for clicking
            self._dpad_rects[direction] = (px, py, size)
            pressed = self._hats.get(direction, False)
            rect = QRectF(px, py, size, size)
            p.setPen(QPen(STICK_BORDER, 1))
            p.setBrush(QBrush(BUTTON_ON if pressed else BUTTON_OFF))
            p.drawRoundedRect(rect, 3, 3)

    def _draw_touchpad(self, p: QPainter, x: float, y: float,
                       width: float, height: float) -> None:
        # Cache hitbox for clicking
        self._touchpad_rect = (x, y, width, height)
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
