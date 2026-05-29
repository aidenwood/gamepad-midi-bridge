"""ControllerPreview — stylised controller silhouette with preset mapping labels.

Renders a minimal DualSense-style controller diagram using QPainter primitives.
Mapped controls are highlighted in teal (#5eead4); unmapped shapes are drawn dim.

Intended to sit inside the 320px inspector panel below the preset header.
"""
from __future__ import annotations

from typing import Any, Dict

from PySide6.QtCore import QRect, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget


# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------

TEAL = QColor("#5eead4")
DIM = QColor("#2c3040")
DIM_BORDER = QColor("#3a3f52")
TEXT_TEAL = QColor("#5eead4")
TEXT_DIM = QColor("#5a606b")
BG = QColor("#0a0b0e")

# ---------------------------------------------------------------------------
# Control geometry — coordinates in the 280×200 canvas
# All rects are (x, y, w, h).
# ---------------------------------------------------------------------------

# Controller body silhouette (rounded rect)
BODY_RECT = QRectF(10, 30, 260, 150)

# Left stick (circle: cx, cy, r)
LS_CX, LS_CY, LS_R = 72, 115, 18

# Right stick
RS_CX, RS_CY, RS_R = 168, 115, 18

# D-pad (four rects: up, down, left, right)
DPAD_CX, DPAD_CY = 100, 110
DPAD_ARM = 9   # half-width of each arm
DPAD_LEN = 20  # half-length of each arm

# Face buttons (cx, cy, r for each)
FACE_BUTTONS = {
    "triangle": (210, 88,  9, "△"),
    "cross":    (210, 110, 9, "✕"),
    "circle":   (222, 99,  9, "○"),
    "square":   (198, 99,  9, "□"),
}

# Shoulder buttons — L1/R1 (small rects at top)
L1_RECT = QRectF(28,  18, 44, 14)
R1_RECT = QRectF(208, 18, 44, 14)

# Triggers — L2/R2 (slightly larger, above L1/R1)
L2_RECT = QRectF(28,  4,  44, 14)
R2_RECT = QRectF(208, 4,  44, 14)

# Touchpad
TP_RECT = QRectF(108, 50, 64, 38)

# Options / Create (small circles)
OPTIONS_CX, OPTIONS_CY, OPTIONS_R = 186, 65, 7
CREATE_CX, CREATE_CY, CREATE_R = 140, 65, 7

# ---------------------------------------------------------------------------
# Mapping key → shape name (controls what lights up)
# ---------------------------------------------------------------------------

# The preset json_blob may use various key names for buttons.
# We normalise to a canonical shape name.
BUTTON_ALIASES: Dict[str, str] = {
    # buttons by index
    "0": "cross",    "cross": "cross",    "button_0": "cross",
    "1": "circle",   "circle": "circle",  "button_1": "circle",
    "2": "square",   "square": "square",  "button_2": "square",
    "3": "triangle", "triangle": "triangle", "button_3": "triangle",
    "4": "l1",       "l1": "l1",          "button_4": "l1",
    "5": "r1",       "r1": "r1",          "button_5": "r1",
    "6": "l2",       "l2": "l2",          "button_6": "l2",
    "7": "r2",       "r2": "r2",          "button_7": "r2",
    "8": "create",   "create": "create",  "button_8": "create",
    "9": "options",  "options": "options","button_9": "options",
    "10": "l3",      "l3": "l3",          "button_10": "l3",
    "11": "r3",      "r3": "r3",          "button_11": "r3",
    "12": "dpad_up",    "dpad_up": "dpad_up",
    "13": "dpad_down",  "dpad_down": "dpad_down",
    "14": "dpad_left",  "dpad_left": "dpad_left",
    "15": "dpad_right", "dpad_right": "dpad_right",
    "touchpad": "touchpad",
}

AXIS_ALIASES: Dict[str, str] = {
    "0": "ls_x",   "ls_x": "ls_x",   "axis_0": "ls_x",
    "1": "ls_y",   "ls_y": "ls_y",   "axis_1": "ls_y",
    "2": "rs_x",   "rs_x": "rs_x",   "axis_2": "rs_x",
    "3": "rs_y",   "rs_y": "rs_y",   "axis_3": "rs_y",
    "4": "l2",     "axis_4": "l2",
    "5": "r2",     "axis_5": "r2",
}

# Shape name → group (determines which region is highlighted)
LEFT_STICK_SHAPES  = {"ls_x", "ls_y", "l3"}
RIGHT_STICK_SHAPES = {"rs_x", "rs_y", "r3"}
DPAD_UP_SHAPES     = {"dpad_up"}
DPAD_DOWN_SHAPES   = {"dpad_down"}
DPAD_LEFT_SHAPES   = {"dpad_left"}
DPAD_RIGHT_SHAPES  = {"dpad_right"}
L1_SHAPES          = {"l1"}
R1_SHAPES          = {"r1"}
L2_SHAPES          = {"l2"}
R2_SHAPES          = {"r2"}
TP_SHAPES          = {"touchpad"}
OPTIONS_SHAPES     = {"options"}
CREATE_SHAPES      = {"create"}


class ControllerPreview(QWidget):
    """280×200 px controller silhouette showing a preset's button/axis assignments.

    Call ``set_mapping_data(data)`` with the raw ``json_blob`` dict from a
    marketplace preset.  Mapped controls are highlighted teal; unmapped are dim.
    Short MIDI-channel/note labels are drawn next to each control.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(280, 200)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self._active: Dict[str, str] = {}  # shape_name → short label

    # ---------------------------------------------------------------- public

    def set_mapping_data(self, data: Dict[str, Any]) -> None:
        """Accept a preset json_blob and extract shape→label pairs.

        Handles several common json_blob layouts:
        - Flat dict: ``{"button_0": {"note": 60, "channel": 1}, ...}``
        - Nested under 'buttons'/'axes' keys
        - Raw list entries with 'input'/'output' sub-keys
        """
        self._active = {}
        if not isinstance(data, dict):
            self.update()
            return

        # Try flat layout first (most common in this project)
        self._parse_flat(data)

        # Try nested buttons / axes sub-dicts
        if "buttons" in data and isinstance(data["buttons"], dict):
            self._parse_flat(data["buttons"])
        if "axes" in data and isinstance(data["axes"], dict):
            self._parse_flat(data["axes"])

        # Try list-of-mappings layout
        if "mappings" in data and isinstance(data["mappings"], list):
            for entry in data["mappings"]:
                if not isinstance(entry, dict):
                    continue
                inp = entry.get("input", {}) or {}
                out = entry.get("output", {}) or {}
                kind = str(inp.get("kind", "")).lower()
                idx = str(inp.get("index", ""))
                key = f"{kind}_{idx}" if kind else idx
                note = out.get("note") or out.get("cc") or ""
                ch = out.get("channel", "")
                label = f"N{note}" if note != "" else (f"Ch{ch}" if ch != "" else "●")
                # Resolve alias
                aliases = AXIS_ALIASES if kind == "axis" else BUTTON_ALIASES
                shape = aliases.get(idx) or aliases.get(key)
                if shape:
                    self._active.setdefault(shape, str(label)[:5])

        self.update()

    # ---------------------------------------------------------------- private

    def _parse_flat(self, data: Dict[str, Any]) -> None:
        """Parse a flat key→value or key→dict blob."""
        for raw_key, val in data.items():
            key = str(raw_key).lower().replace("-", "_")
            # Determine shape
            shape = (
                BUTTON_ALIASES.get(key)
                or AXIS_ALIASES.get(key)
            )
            if not shape:
                continue
            # Build short label from the value
            if isinstance(val, dict):
                note = val.get("note") or val.get("cc") or val.get("midi_note")
                ch   = val.get("channel") or val.get("ch")
                if note is not None:
                    label = f"N{note}"
                elif ch is not None:
                    label = f"Ch{ch}"
                else:
                    label = "●"
            elif isinstance(val, (int, float)):
                label = str(int(val))
            elif isinstance(val, str) and val:
                label = val[:5]
            else:
                label = "●"
            self._active.setdefault(shape, label[:5])

    # ---------------------------------------------------------------- painting

    def paintEvent(self, _event: Any) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        # Background
        p.fillRect(self.rect(), BG)

        # ---- Controller body ----
        p.setPen(QPen(DIM_BORDER, 1.5))
        p.setBrush(DIM)
        p.drawRoundedRect(BODY_RECT, 30, 30)

        # ---- Shoulder buttons L1 / R1 ----
        self._draw_rect_control(p, L1_RECT, "l1", "L1", label_above=False)
        self._draw_rect_control(p, R1_RECT, "r1", "R1", label_above=False)

        # ---- Triggers L2 / R2 ----
        self._draw_rect_control(p, L2_RECT, "l2", "L2", label_above=True)
        self._draw_rect_control(p, R2_RECT, "r2", "R2", label_above=True)

        # ---- Touchpad ----
        self._draw_rect_control(p, TP_RECT, "touchpad", "TP")

        # ---- D-pad ----
        self._draw_dpad(p)

        # ---- Left stick ----
        self._draw_circle_control(p, LS_CX, LS_CY, LS_R, "ls_x", "LS")

        # ---- Right stick ----
        self._draw_circle_control(p, RS_CX, RS_CY, RS_R, "rs_x", "RS")

        # ---- Face buttons ----
        for shape, (cx, cy, r, sym) in FACE_BUTTONS.items():
            active = shape in self._active
            fill = TEAL if active else DIM
            border = TEAL if active else DIM_BORDER
            p.setPen(QPen(border, 1.5))
            p.setBrush(fill)
            p.drawEllipse(int(cx - r), int(cy - r), r * 2, r * 2)
            # Symbol
            p.setPen(TEXT_TEAL if active else TEXT_DIM)
            font = QFont()
            font.setPixelSize(7)
            p.setFont(font)
            p.drawText(
                QRect(int(cx - r), int(cy - r), r * 2, r * 2),
                Qt.AlignCenter, sym,
            )
            # MIDI label
            if active and shape in self._active:
                self._draw_label(p, cx + r + 2, cy, self._active[shape])

        # ---- Options / Create small buttons ----
        self._draw_small_btn(p, OPTIONS_CX, OPTIONS_CY, OPTIONS_R, "options", "⋯")
        self._draw_small_btn(p, CREATE_CX, CREATE_CY, CREATE_R, "create", "+")

        p.end()

    # ---------------------------------------------------------------- helpers

    def _is_active(self, *shapes: str) -> bool:
        return any(s in self._active for s in shapes)

    def _shape_label(self, *shapes: str) -> str:
        for s in shapes:
            if s in self._active:
                return self._active[s]
        return ""

    def _draw_rect_control(
        self,
        p: QPainter,
        rect: QRectF,
        shape: str,
        fallback_label: str,
        label_above: bool = False,
    ) -> None:
        active = shape in self._active
        fill = TEAL if active else DIM
        border = TEAL if active else DIM_BORDER
        p.setPen(QPen(border, 1.5))
        p.setBrush(fill)
        p.drawRoundedRect(rect, 4, 4)
        # Always draw the short key name inside
        p.setPen(TEXT_TEAL if active else TEXT_DIM)
        font = QFont()
        font.setPixelSize(7)
        font.setBold(active)
        p.setFont(font)
        display = self._active.get(shape, fallback_label)
        p.drawText(rect.toRect(), Qt.AlignCenter, display)

    def _draw_circle_control(
        self,
        p: QPainter,
        cx: int, cy: int, r: int,
        shape: str,
        fallback_label: str,
    ) -> None:
        active = self._is_active(shape, shape.replace("_x", "_y"), shape.replace("_x", "").replace("_y", "") + "3")
        fill = TEAL if active else DIM
        border = TEAL if active else DIM_BORDER
        p.setPen(QPen(border, 1.5))
        p.setBrush(fill)
        p.drawEllipse(cx - r, cy - r, r * 2, r * 2)
        p.setPen(TEXT_TEAL if active else TEXT_DIM)
        font = QFont()
        font.setPixelSize(7)
        p.setFont(font)
        display = self._active.get(shape) or fallback_label
        p.drawText(QRect(cx - r, cy - r, r * 2, r * 2), Qt.AlignCenter, display)

    def _draw_dpad(self, p: QPainter) -> None:
        cx, cy = DPAD_CX, DPAD_CY
        arms = [
            ("dpad_up",    QRect(cx - DPAD_ARM, cy - DPAD_LEN - DPAD_ARM, DPAD_ARM*2, DPAD_LEN)),
            ("dpad_down",  QRect(cx - DPAD_ARM, cy + DPAD_ARM, DPAD_ARM*2, DPAD_LEN)),
            ("dpad_left",  QRect(cx - DPAD_LEN - DPAD_ARM, cy - DPAD_ARM, DPAD_LEN, DPAD_ARM*2)),
            ("dpad_right", QRect(cx + DPAD_ARM, cy - DPAD_ARM, DPAD_LEN, DPAD_ARM*2)),
        ]
        for shape, rect in arms:
            active = shape in self._active
            fill = TEAL if active else DIM
            border = TEAL if active else DIM_BORDER
            p.setPen(QPen(border, 1.0))
            p.setBrush(fill)
            p.drawRect(rect)
            if active and shape in self._active:
                # label next to arm
                lx = rect.right() + 2 if "right" in shape else (
                    rect.left() - 16 if "left" in shape else rect.right() + 2
                )
                ly = rect.center().y()
                self._draw_label(p, lx, ly, self._active[shape])

    def _draw_small_btn(
        self,
        p: QPainter,
        cx: int, cy: int, r: int,
        shape: str,
        sym: str,
    ) -> None:
        active = shape in self._active
        fill = TEAL if active else DIM
        border = TEAL if active else DIM_BORDER
        p.setPen(QPen(border, 1.0))
        p.setBrush(fill)
        p.drawEllipse(cx - r, cy - r, r * 2, r * 2)
        p.setPen(TEXT_TEAL if active else TEXT_DIM)
        font = QFont()
        font.setPixelSize(6)
        p.setFont(font)
        p.drawText(QRect(cx - r, cy - r, r * 2, r * 2), Qt.AlignCenter, sym)

    def _draw_label(self, p: QPainter, x: float, y: float, text: str) -> None:
        p.setPen(TEXT_TEAL)
        font = QFont()
        font.setPixelSize(7)
        p.setFont(font)
        p.drawText(QRect(int(x), int(y) - 5, 30, 10), Qt.AlignLeft | Qt.AlignVCenter, text)
