"""Export current mapping as a printable A5 cheat sheet PDF.

Uses only PySide6 (QPdfWriter + QPainter) — no extra dependencies.

Usage:
    from gamepad_midi_bridge.cheatsheet import render_cheatsheet
    render_cheatsheet(mapping, Path("~/Desktop/my-mapping.pdf").expanduser())
"""
from __future__ import annotations

import math
from datetime import date
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QMarginsF, QPointF, QRectF, QSizeF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QPainter,
    QPen,
    QPageLayout,
    QPageSize,
)
from PySide6.QtWidgets import QApplication

try:
    from PySide6.QtPdf import QPdfWriter  # PySide6 ≥ 6.4
except ImportError:  # pragma: no cover — older PySide6 split
    from PySide6.QtGui import QPdfWriter  # type: ignore[no-reattr]

from .mapping import Mapping
from . import __version__

# ---------------------------------------------------------------------------
# DualSense button index constants (pygame/SDL layout for DualSense)
# Index 0=□  1=✕  2=○  3=△  4=L1  5=R1  6=L2-btn  7=R2-btn
# 8=Share  9=Options  10=L3  11=R3  12=PS  13=Touchpad-click
# D-pad: hats key "up"/"down"/"left"/"right"
# Axes: 0=Lx 1=Ly 2=Rx 3=Ry 4=L2 5=R2
# ---------------------------------------------------------------------------

_BUTTON_LABELS = {
    0:  "□",
    1:  "✕",
    2:  "○",
    3:  "△",
    4:  "L1",
    5:  "R1",
    6:  "L2 btn",
    7:  "R2 btn",
    8:  "Share",
    9:  "Options",
    10: "L3",
    11: "R3",
    12: "PS",
    13: "Touchpad",
}

_AXIS_LABELS = {
    0: "L-X",
    1: "L-Y",
    2: "R-X",
    3: "R-Y",
    4: "L2",
    5: "R2",
}

_HAT_LABELS = {
    "up":    "↑",
    "down":  "↓",
    "left":  "←",
    "right": "→",
}

# Colour palette
_BG    = QColor("#0d0d12")
_PANEL = QColor("#18181f")
_WIRE  = QColor("#3a3a4a")
_WIRE_BRIGHT = QColor("#5a5a7a")
_ACCENT = QColor("#7c6af7")        # purple
_TEXT  = QColor("#e8e8f0")
_FADED = QColor("#44445a")
_WHITE = QColor("#ffffff")


def _ensure_qapp() -> Optional[QApplication]:
    """Return existing QCoreApplication or create a headless QApplication."""
    app = QApplication.instance()
    if app is None:
        import sys
        app = QApplication.setInstance(None)  # type: ignore[call-arg]
        try:
            app = QApplication(sys.argv)
        except Exception:
            app = QApplication([])
    return app


def render_cheatsheet(mapping: Mapping, output_path: Path) -> None:
    """Render *mapping* as an A5 portrait PDF at *output_path*.

    Raises:
        RuntimeError: if QPdfWriter fails to open the output path.
        OSError: if the parent directory cannot be created.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    _ensure_qapp()

    writer = QPdfWriter(str(output_path))
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A5))
    writer.setPageOrientation(QPageLayout.Orientation.Portrait)
    writer.setPageMargins(QMarginsF(0, 0, 0, 0))
    writer.setResolution(150)  # 150 dpi — crisp enough for print, compact file

    # Physical page dimensions in pixels at the writer's resolution
    page_rect = writer.pageLayout().fullRectPixels(writer.resolution())
    W = page_rect.width()
    H = page_rect.height()

    painter = QPainter()
    if not painter.begin(writer):
        raise RuntimeError(f"QPdfWriter could not open: {output_path}")

    try:
        _draw_page(painter, mapping, W, H)
    finally:
        painter.end()


# ---------------------------------------------------------------------------
# Internal drawing helpers
# ---------------------------------------------------------------------------

def _draw_page(p: QPainter, m: Mapping, W: int, H: int) -> None:
    """Draw everything onto the QPainter at full-page coordinates."""

    # Background
    p.fillRect(0, 0, W, H, _BG)

    # --- Title bar ---
    title_h = int(H * 0.10)
    p.fillRect(0, 0, W, title_h, _PANEL)
    _draw_title(p, m, W, title_h)

    # --- Controller silhouette (centred in the middle 55% of height) ---
    sil_top = title_h + int(H * 0.02)
    sil_h = int(H * 0.55)
    _draw_silhouette(p, m, 0, sil_top, W, sil_h)

    # --- Legend table (remaining space above footer) ---
    legend_top = sil_top + sil_h + int(H * 0.01)
    footer_h = int(H * 0.06)
    legend_h = H - legend_top - footer_h
    _draw_legend(p, m, 0, legend_top, W, legend_h)

    # --- Footer ---
    _draw_footer(p, m, W, H, footer_h)


def _draw_title(p: QPainter, m: Mapping, W: int, title_h: int) -> None:
    app_name = "Universal Controller MIDI"
    font_big = QFont("Helvetica Neue", 11, QFont.Weight.Bold)
    font_small = QFont("Helvetica Neue", 7)
    p.setPen(_WHITE)
    p.setFont(font_big)
    p.drawText(
        QRectF(10, 2, W - 20, title_h * 0.6),
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        app_name,
    )
    p.setPen(_ACCENT)
    p.setFont(font_small)
    p.drawText(
        QRectF(10, title_h * 0.5, W - 20, title_h * 0.5),
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        f"Mapping: {m.name}   ·   v{__version__}",
    )


def _draw_silhouette(
    p: QPainter, m: Mapping, x: int, y: int, W: int, H: int
) -> None:
    """Draw a stylised DualSense wireframe and label each control."""
    # We'll work in a normalised [0..1] coordinate space then scale.
    cx = x + W / 2
    cy = y + H / 2

    # Controller body width at 80% of page width
    body_w = W * 0.80
    body_h = body_w * 0.52
    bx = cx - body_w / 2
    by = cy - body_h / 2

    # Outer body — rounded rect
    pen_wire = QPen(_WIRE_BRIGHT, 1.4)
    p.setPen(pen_wire)
    p.setBrush(_PANEL)
    body_rect = QRectF(bx, by, body_w, body_h)
    p.drawRoundedRect(body_rect, body_w * 0.12, body_h * 0.25)

    # Grips (lower left + right extensions)
    grip_w = body_w * 0.22
    grip_h = body_h * 0.40
    p.setPen(QPen(_WIRE, 1.0))
    p.setBrush(_PANEL)
    # Left grip
    p.drawRoundedRect(
        QRectF(bx + body_w * 0.08, by + body_h * 0.70, grip_w, grip_h), 8, 8
    )
    # Right grip
    p.drawRoundedRect(
        QRectF(bx + body_w - grip_w - body_w * 0.08, by + body_h * 0.70, grip_w, grip_h), 8, 8
    )

    # --- Touchpad ---
    tp_w = body_w * 0.28
    tp_h = body_h * 0.28
    tp_rect = QRectF(cx - tp_w / 2, by + body_h * 0.22, tp_w, tp_h)
    p.setPen(QPen(_WIRE_BRIGHT, 0.8))
    p.setBrush(QColor("#22222d"))
    p.drawRoundedRect(tp_rect, 4, 4)

    # --- D-pad ---
    dp_cx = bx + body_w * 0.22
    dp_cy = by + body_h * 0.55
    _draw_dpad(p, m, dp_cx, dp_cy, body_w * 0.15)

    # --- Left stick ---
    ls_cx = bx + body_w * 0.34
    ls_cy = by + body_h * 0.68
    _draw_stick(p, m, ls_cx, ls_cy, body_w * 0.09, "L", 0, 1)

    # --- Right stick ---
    rs_cx = bx + body_w * 0.62
    rs_cy = by + body_h * 0.68
    _draw_stick(p, m, rs_cx, rs_cy, body_w * 0.09, "R", 2, 3)

    # --- Face buttons ---
    fb_cx = bx + body_w * 0.78
    fb_cy = by + body_h * 0.46
    _draw_face_buttons(p, m, fb_cx, fb_cy, body_w * 0.085)

    # --- L1 / R1 ---
    shoulder_y = by - body_h * 0.04
    l1_rect = QRectF(bx + body_w * 0.08, shoulder_y, body_w * 0.17, body_h * 0.13)
    r1_rect = QRectF(bx + body_w * 0.75, shoulder_y, body_w * 0.17, body_h * 0.13)
    _draw_shoulder(p, m, l1_rect, 4, "L1")   # button idx 4
    _draw_shoulder(p, m, r1_rect, 5, "R1")   # button idx 5

    # --- L2 / R2 (triggers) ---
    l2_rect = QRectF(bx + body_w * 0.06, shoulder_y - body_h * 0.14, body_w * 0.17, body_h * 0.13)
    r2_rect = QRectF(bx + body_w * 0.77, shoulder_y - body_h * 0.14, body_w * 0.17, body_h * 0.13)
    _draw_trigger(p, m, l2_rect, 4, "L2")    # axis idx 4
    _draw_trigger(p, m, r2_rect, 5, "R2")    # axis idx 5

    # --- Touchpad label ---
    _label_control(
        p,
        f"Touchpad\n{_tp_label(m)}",
        tp_rect.center().x(),
        tp_rect.center().y(),
        mapped=m.touchpad.enabled,
        small=True,
    )


def _tp_label(m: Mapping) -> str:
    if not m.touchpad.enabled:
        return "—"
    parts = [f"CC{m.touchpad.x_cc}/CC{m.touchpad.y_cc}"]
    if m.touchpad.two_finger:
        parts.append(f"2F CC{m.touchpad.b_x_cc}/CC{m.touchpad.b_y_cc}")
    return " ".join(parts)


def _draw_dpad(p: QPainter, m: Mapping, cx: float, cy: float, size: float) -> None:
    """Draw a plus-shaped D-pad with per-direction MIDI labels."""
    arm_w = size * 0.38
    arm_h = size * 0.38

    dirs = [
        ("up",    0,    -size * 0.31),
        ("down",  0,    +size * 0.31),
        ("left",  -size * 0.31, 0),
        ("right", +size * 0.31, 0),
    ]
    for key, dx, dy in dirs:
        note = m.hats.get(key)
        rect = QRectF(cx + dx - arm_w / 2, cy + dy - arm_h / 2, arm_w, arm_h)
        p.setPen(QPen(_WIRE_BRIGHT, 0.8))
        p.setBrush(QColor("#1e1e28"))
        p.drawRect(rect)
        mapped = note is not None
        sym = _HAT_LABELS.get(key, key)
        label = f"{sym}\nN{note}" if mapped else sym
        _label_control(p, label, cx + dx, cy + dy, mapped=mapped, small=True)


def _draw_stick(
    p: QPainter, m: Mapping,
    cx: float, cy: float, r: float,
    side: str, x_ax: int, y_ax: int
) -> None:
    cc_x = m.axes.get(x_ax)
    cc_y = m.axes.get(y_ax)
    mapped = (cc_x is not None) or (cc_y is not None)

    pen = QPen(_WIRE_BRIGHT if mapped else _WIRE, 1.2)
    p.setPen(pen)
    p.setBrush(QColor("#1a1a24"))
    p.drawEllipse(QPointF(cx, cy), r, r)

    # Inner dot
    p.setBrush(_ACCENT if mapped else _FADED)
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(QPointF(cx, cy), r * 0.25, r * 0.25)

    parts = [side]
    if cc_x is not None:
        parts.append(f"X→CC{cc_x}")
    if cc_y is not None:
        parts.append(f"Y→CC{cc_y}")
    text = "\n".join(parts)
    _label_control(p, text, cx, cy - r * 1.5, mapped=mapped, small=True)


def _draw_face_buttons(
    p: QPainter, m: Mapping, cx: float, cy: float, spacing: float
) -> None:
    """Draw □△○✕ in the standard PlayStation diamond layout."""
    positions = [
        (0,  "□",  0,           -spacing),   # top    = △ in PS but SDL 0=□
        (3,  "△",  0,           -spacing),   # actually let's use correct SDL layout
        (1,  "✕",  0,           +spacing),
        (2,  "○",  +spacing,    0),
        (3,  "△",  0,           -spacing),
        (0,  "□",  -spacing,    0),
    ]
    # Correct standard DualSense / SDL layout: cross(✕)=0 circle(○)=1 square(□)=2 triangle(△)=3
    # BUT for pygame DualSense: square=0 cross=1 circle=2 triangle=3
    # Matching _BUTTON_LABELS above: 0=□ 1=✕ 2=○ 3=△
    layout = [
        (3, "△", 0,        -spacing),
        (0, "□", -spacing, 0),
        (1, "✕", 0,        +spacing),
        (2, "○", +spacing, 0),
    ]
    r = spacing * 0.38
    for btn_idx, sym, dx, dy in layout:
        note = m.buttons.get(btn_idx)
        mapped = note is not None
        btn_cx = cx + dx
        btn_cy = cy + dy
        pen = QPen(_WIRE_BRIGHT if mapped else _WIRE, 0.8)
        p.setPen(pen)
        p.setBrush(_ACCENT.darker(150) if mapped else QColor("#1e1e28"))
        p.drawEllipse(QPointF(btn_cx, btn_cy), r, r)
        label = f"{sym}\nN{note}" if mapped else sym
        _label_control(p, label, btn_cx, btn_cy, mapped=mapped, small=True)


def _draw_shoulder(
    p: QPainter, m: Mapping, rect: QRectF, btn_idx: int, name: str
) -> None:
    note = m.buttons.get(btn_idx)
    mapped = note is not None
    p.setPen(QPen(_WIRE_BRIGHT if mapped else _WIRE, 0.8))
    p.setBrush(_ACCENT.darker(150) if mapped else QColor("#1e1e28"))
    p.drawRoundedRect(rect, 4, 4)
    label = f"{name}\nN{note}" if mapped else name
    _label_control(p, label, rect.center().x(), rect.center().y(), mapped=mapped, small=True)


def _draw_trigger(
    p: QPainter, m: Mapping, rect: QRectF, axis_idx: int, name: str
) -> None:
    cc = m.axes.get(axis_idx)
    mapped = cc is not None
    p.setPen(QPen(_WIRE_BRIGHT if mapped else _WIRE, 0.8))
    p.setBrush(_ACCENT.darker(120) if mapped else QColor("#1a1a24"))
    p.drawRoundedRect(rect, 3, 3)
    label = f"{name}\nCC{cc}" if mapped else name
    _label_control(p, label, rect.center().x(), rect.center().y(), mapped=mapped, small=True)


def _label_control(
    p: QPainter,
    text: str,
    cx: float,
    cy: float,
    *,
    mapped: bool = True,
    small: bool = False,
) -> None:
    size = 5 if small else 6
    font = QFont("Helvetica Neue", size)
    p.setFont(font)
    p.setPen(_TEXT if mapped else _FADED)
    rect = QRectF(cx - 40, cy - 14, 80, 28)
    p.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)


# ---------------------------------------------------------------------------
# Legend table
# ---------------------------------------------------------------------------

def _draw_legend(
    p: QPainter, m: Mapping, x: int, y: int, W: int, H: int
) -> None:
    """Draw a compact two-column table of all assignments."""
    entries: list[tuple[str, str, bool]] = []

    # Buttons
    for idx, label in sorted(_BUTTON_LABELS.items()):
        note = m.buttons.get(idx)
        if note is not None:
            ch = m.button_channels.get(idx, m.midi_channel)
            ch_str = f" ch{ch+1}" if ch != m.midi_channel else ""
            entries.append((label, f"Note {note}{ch_str}", True))
        else:
            entries.append((label, "—", False))

    # Axes
    for idx, label in sorted(_AXIS_LABELS.items()):
        cc = m.axes.get(idx)
        if cc is not None:
            ch = m.axis_channels.get(idx, m.midi_channel)
            ch_str = f" ch{ch+1}" if ch != m.midi_channel else ""
            entries.append((label, f"CC {cc}{ch_str}", True))
        else:
            entries.append((label, "—", False))

    # D-pad / hats
    for key, sym in _HAT_LABELS.items():
        note = m.hats.get(key)
        if note is not None:
            entries.append((f"D-pad {sym}", f"Note {note}", True))
        else:
            entries.append((f"D-pad {sym}", "—", False))

    # Layout: two columns
    row_h = max(10, H / max(len(entries) / 2, 1))
    row_h = min(row_h, 16)  # cap so it doesn't get huge with few entries
    col_w = W / 2 - 8

    font_head = QFont("Helvetica Neue", 5, QFont.Weight.Bold)
    font_body = QFont("Helvetica Neue", 5)

    # Section header
    p.setFont(font_head)
    p.setPen(_ACCENT)
    p.drawText(
        QRectF(x + 8, y, W - 16, 12),
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        "ASSIGNMENT REFERENCE",
    )
    y += 14

    for i, (ctrl, assign, mapped) in enumerate(entries):
        col = i % 2
        row = i // 2
        ex = x + 8 + col * (col_w + 8)
        ey = y + row * row_h
        if ey + row_h > y + H:
            break  # stop if we'd overflow

        p.setFont(font_body)
        p.setPen(_TEXT if mapped else _FADED)
        label_rect = QRectF(ex, ey, col_w * 0.42, row_h)
        p.drawText(label_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, ctrl)

        p.setPen(_ACCENT if mapped else _FADED)
        assign_rect = QRectF(ex + col_w * 0.44, ey, col_w * 0.56, row_h)
        p.drawText(assign_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, assign)


# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------

def _draw_footer(
    p: QPainter, m: Mapping, W: int, H: int, footer_h: int
) -> None:
    fy = H - footer_h
    p.fillRect(0, fy, W, footer_h, _PANEL)
    font = QFont("Helvetica Neue", 5)
    p.setFont(font)
    p.setPen(_FADED)
    today = date.today().strftime("%Y-%m-%d")
    text = (
        f"Generated {today}  ·  MIDI ch default: {m.midi_channel + 1}"
        f"  ·  Universal Controller MIDI v{__version__}"
    )
    p.drawText(
        QRectF(8, fy, W - 16, footer_h),
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        text,
    )
