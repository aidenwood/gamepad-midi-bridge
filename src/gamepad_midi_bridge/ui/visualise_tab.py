"""Visualise tab — richer post-setup live view.

Stacks a large DualSense diagram, a stats panel (battery/transport/rate/
latency/runtime), per-axis sparkline history, and a button heatmap with a
2 s decay. WHY a second tab: Live stays minimal so first-time users aren't
overwhelmed; Visualise is for power users debugging mappings live.
"""
from __future__ import annotations

import time
from collections import deque
from typing import Deque, Dict, List, Optional, Tuple

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget, QScrollArea,
)

from .axis_scope import AxisScope
from .usage_heatmap import UsageHeatmap

from .throughput_panel import ThroughputPanel

# Match controller_meter.py palette so the two views feel like one app.
STICK_BG = QColor("#16181d")
STICK_BORDER = QColor("#24262d")
STICK_DOT = QColor("#2dd4bf")
BUTTON_OFF = QColor("#1f232b")
BUTTON_ON = QColor("#2dd4bf")
TEXT_DIM = QColor("#8a9099")
PANEL_BG = QColor("#13151a")
GRID_LINE = QColor("#1f232b")

REPAINT_HZ = 30                  # cap below bridge's 100 Hz to save CPU
SPARKLINE_SAMPLES = 200
LATENCY_WINDOW = 60
HEATMAP_DECAY_S = 2.0
OSCILLOSCOPE_SAMPLES = 150       # ~5 seconds at 30 Hz repaint
OSCILLOSCOPE_WIDTH = 280
OSCILLOSCOPE_HEIGHT = 60

# Sparkline axes — sticks (0..3) + triggers (4, 5).
SPARK_AXES: List[Tuple[int, str]] = [
    (0, "L STICK X"), (1, "L STICK Y"),
    (2, "R STICK X"), (3, "R STICK Y"),
    (4, "L2"), (5, "R2"),
]

# Heatmap cells. Buttons 0..10 mirror mapping.py defaults; d-pad uses the
# direction strings emitted by BridgeWorker.hat_state.
BUTTON_CELLS: List[Tuple[str, object]] = [
    ("Cross", 0), ("Circle", 1), ("Square", 2), ("Triangle", 3), ("L1", 4),
    ("R1", 5), ("Share", 6), ("Options", 7), ("L3", 8), ("R3", 9),
    ("PS", 10), ("D-Up", "up"), ("D-Down", "down"), ("D-Left", "left"),
    ("D-Right", "right"),
]


def _font(size: int, bold: bool = False) -> QFont:
    f = QFont(); f.setPointSize(size); f.setBold(bold); return f

def _filled_rect(p: QPainter, rect: QRectF, fill: QColor,
                 radius: float = 4.0, border: QColor = STICK_BORDER) -> None:
    p.setPen(QPen(border, 1)); p.setBrush(QBrush(fill))
    p.drawRoundedRect(rect, radius, radius)

def _label(p: QPainter, rect: QRectF, text: str, color: QColor,
           size: int = 8, bold: bool = True, align=Qt.AlignCenter) -> None:
    p.setPen(QPen(color)); p.setFont(_font(size, bold))
    p.drawText(rect, align, text)


class _Sparkline(QWidget):
    """Single-axis sparkline. Ring buffer pinned to the right edge so older
    samples scroll off the left as fresh data arrives."""

    def __init__(self, label: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._label = label
        self._buf: Deque[float] = deque(maxlen=SPARKLINE_SAMPLES)
        # Tiny floor so the strip can collapse when the window narrows —
        # the parent scroll area handles overflow.
        self.setMinimumHeight(28)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def push(self, value: float) -> None:
        self._buf.append(max(-1.0, min(1.0, float(value))))

    def paintEvent(self, _event) -> None:
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        _filled_rect(p, QRectF(0, 0, w, h), PANEL_BG, radius=6)
        # Dashed zero baseline so the user can read sign at a glance.
        mid_y = h / 2.0
        p.setPen(QPen(GRID_LINE, 1, Qt.DashLine))
        p.drawLine(QPointF(6, mid_y), QPointF(w - 6, mid_y))
        _label(p, QRectF(6, 2, w - 12, 14), self._label, TEXT_DIM, align=Qt.AlignLeft)
        if len(self._buf) < 2:
            return
        x_end = w - 6; y_top, y_bot = 14, h - 6
        span_y = max(1.0, y_bot - y_top)
        step = (x_end - 6) / (SPARKLINE_SAMPLES - 1)
        n = len(self._buf)
        # Right-align so partial buffers look like fresh data scrolling in.
        first_x = x_end - (n - 1) * step
        poly = QPolygonF()
        for i, v in enumerate(self._buf):
            poly.append(QPointF(first_x + i * step,
                                y_top + (1.0 - (v + 1.0) / 2.0) * span_y))
        p.setPen(QPen(STICK_DOT, 1)); p.setBrush(Qt.NoBrush)
        p.drawPolyline(poly)


class _Heatmap(QWidget):
    """Decaying button-press heatmap. Cells brighten on press, fade over 2 s."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._stamps: Dict[object, float] = {}
        self._held: Dict[object, bool] = {}
        self.setMinimumHeight(60)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

    def flash(self, key: object, pressed: bool) -> None:
        # Stamp every state change so a quick tap still leaves a trail.
        self._held[key] = pressed; self._stamps[key] = time.perf_counter()

    def paintEvent(self, _event) -> None:
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        # 3 rows x 5 cols = 15 cells, exactly matches BUTTON_CELLS length.
        cols, rows, margin, gap = 5, 3, 6, 6
        cw = (w - margin * 2 - gap * (cols - 1)) / cols
        ch = (h - margin * 2 - gap * (rows - 1)) / rows
        now = time.perf_counter()
        for i, (label, key) in enumerate(BUTTON_CELLS):
            r, c = divmod(i, cols)
            rect = QRectF(margin + c * (cw + gap), margin + r * (ch + gap), cw, ch)
            if self._held.get(key):
                t = 1.0
            else:
                last = self._stamps.get(key)
                t = max(0.0, 1.0 - (now - last) / HEATMAP_DECAY_S) if last else 0.0
            _filled_rect(p, rect, self._blend(t), radius=4)
            _label(p, rect, label,
                   QColor("#0e0f12") if t > 0.45 else TEXT_DIM, size=9)

    @staticmethod
    def _blend(t: float) -> QColor:
        if t <= 0:
            return BUTTON_OFF
        return QColor(
            int(BUTTON_OFF.red()   + (BUTTON_ON.red()   - BUTTON_OFF.red())   * t),
            int(BUTTON_OFF.green() + (BUTTON_ON.green() - BUTTON_OFF.green()) * t),
            int(BUTTON_OFF.blue()  + (BUTTON_ON.blue()  - BUTTON_OFF.blue())  * t),
        )


class _DualSenseDiagram(QWidget):
    """Big DualSense silhouette with live state. Pure QPainter — proportions
    hand-tuned to read as a DualSense rather than a generic gamepad."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._axes: Dict[int, float] = {}
        self._buttons: Dict[int, bool] = {}
        self._hats: Dict[str, bool] = {}
        self._touch_contact = False
        self._touch_x = 0.5
        self._touch_y = 0.5
        # Haptic pulse markers — perf-counter timestamp per side ("L"/"R").
        # Diagram repaints fade the marker over `HEATMAP_DECAY_S` so users
        # see a brief teal dot next to each trigger when MIDI fires haptics.
        self._haptic_stamps: Dict[str, float] = {}
        # Old floor was 560×360 which forced a horizontal scrollbar on
        # narrow windows. Drop both axes; the QScrollArea wrapping the
        # tab handles overflow and the QPainter scales its drawing space
        # to whatever it's given.
        self.setMinimumSize(220, 160)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def on_haptic(self, side: str, _effect: str, _intensity: float) -> None:
        """Stamp the most recent haptic-in pulse so paintEvent can draw it."""
        self._haptic_stamps[side.upper()] = time.perf_counter()

    def on_axis(self, idx: int, value: float) -> None: self._axes[idx] = value
    def on_button(self, idx: int, pressed: bool) -> None: self._buttons[idx] = pressed
    def on_hat(self, direction: str, pressed: bool) -> None: self._hats[direction] = pressed
    def on_touchpad(self, contact: bool, x: float, y: float) -> None:
        self._touch_contact, self._touch_x, self._touch_y = contact, x, y
    def reset(self) -> None:
        self._axes.clear(); self._buttons.clear(); self._hats.clear()
        self._touch_contact = False

    def paintEvent(self, _event) -> None:
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        body_w = min(w - 20, 600); body_h = min(h - 60, 320)
        bx = (w - body_w) / 2; by = 40
        _filled_rect(p, QRectF(bx, by, body_w, body_h),
                     QColor("#10131a"), radius=60)
        # Light bar (cosmetic) above touchpad.
        bar_w = body_w * 0.18
        p.setPen(Qt.NoPen); p.setBrush(QBrush(QColor("#1c2530")))
        p.drawRoundedRect(QRectF(bx + (body_w - bar_w) / 2, by + 6, bar_w, 4), 2, 2)
        # Touchpad — broad rect, centred top.
        tp_w = body_w * 0.34; tp_h = body_h * 0.32
        tp_x = bx + (body_w - tp_w) / 2; tp_y = by + 22
        self._draw_touchpad(p, tp_x, tp_y, tp_w, tp_h)
        # Sticks — bottom row. L3=btn8, R3=btn9 light up when pressed.
        stick_size = body_h * 0.34
        stick_y = by + body_h - stick_size - 30
        for cx_pct, ax, ay, click_idx, label in (
            (0.30, 0, 1, 8, "L"), (0.70, 2, 3, 9, "R"),
        ):
            sx = bx + body_w * cx_pct - stick_size / 2
            self._draw_stick(p, sx, stick_y, stick_size,
                             self._axes.get(ax, 0.0), self._axes.get(ay, 0.0),
                             self._buttons.get(click_idx, False), label)
        # D-pad upper-left, face buttons upper-right.
        self._draw_dpad(p, bx + body_w * 0.14, by + body_h * 0.36, body_h * 0.24)
        face_size = body_h * 0.30
        self._draw_face(p, bx + body_w * 0.86 - face_size,
                        by + body_h * 0.34, face_size)
        # Shoulders + triggers — above body. Haptic pulses render as a teal
        # dot beside the L2/R2 fill bar, decaying over HEATMAP_DECAY_S.
        sh_w = body_w * 0.18; sh_h = 18; tr_h = 28
        now = time.perf_counter()
        for x_pct, btn_idx, ax_idx, sh_lbl, tr_lbl, side in (
            (0.10, 4, 4, "L1", "L2", "L"),
            (0.72, 5, 5, "R1", "R2", "R"),
        ):
            sx = bx + body_w * x_pct
            self._draw_shoulder(p, sx, by - sh_h + 4, sh_w, sh_h,
                                self._buttons.get(btn_idx, False), sh_lbl)
            self._draw_trigger(p, sx, by - sh_h - tr_h, sh_w, tr_h,
                               self._axes.get(ax_idx, -1.0), tr_lbl)
            stamp = self._haptic_stamps.get(side)
            if stamp is not None:
                t = max(0.0, 1.0 - (now - stamp) / HEATMAP_DECAY_S)
                if t > 0:
                    dot = QColor(STICK_DOT); dot.setAlpha(int(255 * t))
                    p.setPen(Qt.NoPen); p.setBrush(QBrush(dot))
                    p.drawEllipse(
                        QPointF(sx + sh_w + 6, by - sh_h - tr_h / 2), 5, 5,
                    )
        # Share / Options pills + PS button under touchpad.
        small_y = tp_y + tp_h + 6
        self._draw_pill(p, bx + body_w * 0.22, small_y, 44, 14,
                        self._buttons.get(6, False), "SHARE")
        self._draw_pill(p, bx + body_w * 0.74 - 44, small_y, 44, 14,
                        self._buttons.get(7, False), "OPT")
        ps_size = 18
        self._draw_round(p, bx + (body_w - ps_size) / 2,
                         tp_y + tp_h + 28, ps_size,
                         self._buttons.get(10, False), "PS")

    def _draw_stick(self, p, x, y, size, xv, yv, pressed, label) -> None:
        p.setPen(QPen(STICK_BORDER, 1)); p.setBrush(QBrush(STICK_BG))
        p.drawEllipse(QRectF(x, y, size, size))
        cx, cy = x + size / 2, y + size / 2
        p.setPen(QPen(GRID_LINE, 1, Qt.DashLine))
        p.drawLine(QPointF(x + 8, cy), QPointF(x + size - 8, cy))
        p.drawLine(QPointF(cx, y + 8), QPointF(cx, y + size - 8))
        dx = cx + xv * (size / 2 - 12); dy = cy + yv * (size / 2 - 12)
        # Brighter dot when L3/R3 clicked.
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor("#34e0c8") if pressed else STICK_DOT))
        p.drawEllipse(QPointF(dx, dy), 11, 11)
        _label(p, QRectF(x, y + size + 2, size, 12), label, TEXT_DIM, bold=False)

    def _draw_dpad(self, p, x, y, size) -> None:
        cell = size / 3
        for direction, (cx, cy) in (
            ("up",    (x + cell, y)),
            ("left",  (x, y + cell)),
            ("right", (x + cell * 2, y + cell)),
            ("down",  (x + cell, y + cell * 2)),
        ):
            _filled_rect(p, QRectF(cx, cy, cell - 2, cell - 2),
                         BUTTON_ON if self._hats.get(direction) else BUTTON_OFF)

    def _draw_face(self, p, x, y, size) -> None:
        # Diamond: triangle/circle/cross/square.
        r = size / 6
        for idx, (cx, cy), glyph in (
            (3, (x + size / 2, y), "△"),
            (1, (x + size, y + size / 2), "○"),
            (0, (x + size / 2, y + size), "✕"),
            (2, (x, y + size / 2), "□"),
        ):
            pressed = self._buttons.get(idx, False)
            p.setPen(QPen(STICK_BORDER, 1))
            p.setBrush(QBrush(BUTTON_ON if pressed else BUTTON_OFF))
            p.drawEllipse(QPointF(cx, cy), r, r)
            _label(p, QRectF(cx - r, cy - r, r * 2, r * 2), glyph,
                   QColor("#0e0f12") if pressed else TEXT_DIM, size=11)

    def _draw_shoulder(self, p, x, y, w, h, pressed, label) -> None:
        rect = QRectF(x, y, w, h)
        _filled_rect(p, rect, BUTTON_ON if pressed else BUTTON_OFF, radius=6)
        _label(p, rect, label, QColor("#0e0f12") if pressed else TEXT_DIM)

    def _draw_trigger(self, p, x, y, w, h, raw, label) -> None:
        # raw -1..+1 → fill rises upward.
        norm = max(0.0, (raw + 1.0) / 2.0)
        rect = QRectF(x, y, w, h)
        _filled_rect(p, rect, STICK_BG, radius=6)
        if norm > 0:
            fill_h = h * norm
            p.setPen(Qt.NoPen); p.setBrush(QBrush(STICK_DOT))
            p.drawRoundedRect(QRectF(x, y + (h - fill_h), w, fill_h), 6, 6)
        _label(p, rect, label, TEXT_DIM, size=7)

    def _draw_pill(self, p, x, y, w, h, pressed, label) -> None:
        rect = QRectF(x, y, w, h)
        _filled_rect(p, rect, BUTTON_ON if pressed else BUTTON_OFF, radius=h / 2)
        _label(p, rect, label,
               QColor("#0e0f12") if pressed else TEXT_DIM, size=7)

    def _draw_round(self, p, x, y, size, pressed, label) -> None:
        p.setPen(QPen(STICK_BORDER, 1))
        p.setBrush(QBrush(BUTTON_ON if pressed else BUTTON_OFF))
        p.drawEllipse(QRectF(x, y, size, size))
        _label(p, QRectF(x, y, size, size), label,
               QColor("#0e0f12") if pressed else TEXT_DIM, size=7)

    def _draw_touchpad(self, p, x, y, w, h) -> None:
        _filled_rect(p, QRectF(x, y, w, h), STICK_BG, radius=8)
        if not self._touch_contact:
            return
        tx = max(0.0, min(1.0, self._touch_x))
        ty = max(0.0, min(1.0, self._touch_y))
        pad = 8.0
        dx = x + pad + tx * (w - pad * 2); dy = y + pad + ty * (h - pad * 2)
        halo = QColor(STICK_DOT); halo.setAlpha(60)
        p.setPen(Qt.NoPen); p.setBrush(QBrush(halo))
        p.drawEllipse(QPointF(dx, dy), 12, 12)
        p.setBrush(QBrush(STICK_DOT))
        p.drawEllipse(QPointF(dx, dy), 6, 6)


class VisualiseTab(QWidget):
    """Top-level tab. Owns diagram + stats + sparklines + heatmap, plus a
    30 Hz repaint timer to keep CPU cheap despite the bridge's 100 Hz."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._build_ui()

        # Latency: each input signal pushes a timestamp; midi_sent pops one
        # and records the delta. They fire roughly simultaneously inside the
        # bridge so this measures Qt signal-dispatch overhead.
        self._pending_input_ts: Deque[float] = deque(maxlen=LATENCY_WINDOW * 4)
        self._latency_samples: Deque[float] = deque(maxlen=LATENCY_WINDOW)
        self._midi_count = 0
        self._midi_total = 0
        self._connected_name = "—"
        self._battery_pct = -1
        self._battery_charging = False
        self._wired = True
        self._runtime_start: Optional[float] = None

        # Throughput tracking: counters for tick() — reset every 1s
        self._midi_out_counter = 0
        self._midi_in_counter = 0

        self._repaint_timer = QTimer(self)
        self._repaint_timer.setInterval(int(1000 / REPAINT_HZ))
        self._repaint_timer.timeout.connect(self._tick)
        self._repaint_timer.start()

        self._rate_timer = QTimer(self)
        self._rate_timer.setInterval(1000)
        self._rate_timer.timeout.connect(self._flush_rate)
        self._rate_timer.start()

        self._throughput_timer = QTimer(self)
        self._throughput_timer.setInterval(1000)
        self._throughput_timer.timeout.connect(self._tick_throughput)
        self._throughput_timer.start()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20); root.setSpacing(14)

        # MIDI throughput dashboard
        throughput_frame = self._panel_frame()
        throughput_v = QVBoxLayout(throughput_frame)
        throughput_v.setContentsMargins(10, 8, 10, 10); throughput_v.setSpacing(4)
        throughput_v.addWidget(self._section_title("MIDI THROUGHPUT (60 SEC HISTORY)"))
        self._throughput_panel = ThroughputPanel()
        throughput_v.addWidget(self._throughput_panel)
        root.addWidget(throughput_frame, 1)

        top = QHBoxLayout(); top.setSpacing(14)
        self._diagram = _DualSenseDiagram()
        top.addWidget(self._diagram, 3)
        top.addWidget(self._build_stats_panel(), 1)
        root.addLayout(top, 3)

        # Oscilloscope grid — 6 rows (one per axis: LX, LY, RX, RY, L2, R2).
        scope_frame = self._panel_frame()
        scope_v = QVBoxLayout(scope_frame)
        scope_v.setContentsMargins(10, 8, 10, 10); scope_v.setSpacing(4)
        scope_v.addWidget(self._section_title("INPUT OSCILLOSCOPE (5 SECOND TRACE)"))
        scope_container = QWidget()
        scope_layout = QVBoxLayout(scope_container)
        scope_layout.setContentsMargins(0, 0, 0, 0); scope_layout.setSpacing(6)
        self._oscilloscopes: Dict[int, AxisScope] = {}
        for axis_idx, label in SPARK_AXES:
            scope = AxisScope(axis_idx, label)
            self._oscilloscopes[axis_idx] = scope
            scope_layout.addWidget(scope)
        scope_layout.addStretch()
        scope_scroll = QScrollArea()
        scope_scroll.setWidget(scope_container)
        scope_scroll.setWidgetResizable(True)
        scope_scroll.setStyleSheet("border: none;")
        scope_v.addWidget(scope_scroll, 1)
        root.addWidget(scope_frame, 2)

        # Sparkline grid — 3 cols x 2 rows even split.
        spark_frame = self._panel_frame()
        spark_grid = QGridLayout(spark_frame)
        spark_grid.setContentsMargins(10, 10, 10, 10); spark_grid.setSpacing(8)
        self._sparklines: Dict[int, _Sparkline] = {}
        for i, (axis_idx, label) in enumerate(SPARK_AXES):
            spark = _Sparkline(label)
            self._sparklines[axis_idx] = spark
            spark_grid.addWidget(spark, i // 3, i % 3)
        root.addWidget(spark_frame, 2)

        heat_frame = self._panel_frame()
        heat_v = QVBoxLayout(heat_frame)
        heat_v.setContentsMargins(10, 8, 10, 10); heat_v.setSpacing(4)
        heat_v.addWidget(self._section_title("BUTTON ACTIVITY"))
        self._heatmap = _Heatmap()
        heat_v.addWidget(self._heatmap, 1)
        root.addWidget(heat_frame, 2)

        # Usage heatmap — session-accumulated press counts on the silhouette.
        usage_frame = self._panel_frame()
        usage_v = QVBoxLayout(usage_frame)
        usage_v.setContentsMargins(10, 8, 10, 10); usage_v.setSpacing(4)
        self._usage_heatmap = UsageHeatmap()
        usage_v.addWidget(self._usage_heatmap)
        root.addWidget(usage_frame, 3)

    @staticmethod
    def _panel_frame() -> QFrame:
        f = QFrame()
        f.setStyleSheet(f"background-color: {PANEL_BG.name()}; border-radius: 8px;")
        return f

    @staticmethod
    def _section_title(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            "color: #8a9099; font-size: 10px; font-weight: 700; letter-spacing: 1px;"
        )
        return lbl

    def _build_stats_panel(self) -> QWidget:
        panel = self._panel_frame()
        v = QVBoxLayout(panel)
        v.setContentsMargins(16, 16, 16, 16); v.setSpacing(10)
        v.addWidget(self._section_title("LIVE STATS"))
        self._stat_name     = self._make_stat(v, "Controller", "—")
        self._stat_transport = self._make_stat(v, "Transport", "—")
        self._stat_battery  = self._make_stat(v, "Battery", "—")
        self._stat_rate     = self._make_stat(v, "MIDI msg/s", "0")
        self._stat_total    = self._make_stat(v, "Total messages", "0")
        self._stat_latency  = self._make_stat(v, "Latency", "—")
        self._stat_runtime  = self._make_stat(v, "Runtime", "—")
        v.addStretch(1)
        return panel

    @staticmethod
    def _make_stat(layout: QVBoxLayout, label: str, value: str) -> QLabel:
        """Build label+value pair, return the value QLabel for later mutation."""
        row = QVBoxLayout(); row.setSpacing(2)
        lbl = QLabel(label.upper())
        lbl.setStyleSheet("color: #5a606b; font-size: 9px; font-weight: 600;")
        val = QLabel(value)
        val.setStyleSheet("color: #f5f7fa; font-size: 14px; font-weight: 600;")
        row.addWidget(lbl); row.addWidget(val)
        layout.addLayout(row)
        return val

    def attach_bridge_signals(self, worker) -> None:
        """Hook the BridgeWorker. Called by MainWindow during _wire_signals."""
        worker.axis_value.connect(self._on_axis)
        worker.button_state.connect(self._on_button)
        worker.hat_state.connect(self._on_hat)
        worker.battery_changed.connect(self._on_battery)
        worker.touchpad_xy.connect(self._on_touchpad)
        worker.transport_changed.connect(self._on_transport)
        worker.midi_sent.connect(self._on_midi_sent)
        worker.midi_message.connect(self._on_midi_message)
        worker.controller_info.connect(self._on_controller_info)
        worker.started.connect(self._on_started)
        worker.stopped.connect(self._on_stopped)
        # Optional: older worker builds may not expose `haptic_event` yet.
        # Guard so plugging this tab into legacy bridges still works.
        if hasattr(worker, "haptic_event"):
            worker.haptic_event.connect(self._diagram.on_haptic)

    def _on_axis(self, idx: int, value: float) -> None:
        self._diagram.on_axis(idx, value)
        spark = self._sparklines.get(idx)
        if spark is not None:
            spark.push(value)
        scope = self._oscilloscopes.get(idx)
        if scope is not None:
            scope.add_sample(value)
        self._pending_input_ts.append(time.perf_counter())

    def _on_button(self, idx: int, pressed: bool) -> None:
        self._diagram.on_button(idx, pressed)
        self._heatmap.flash(idx, pressed)
        self._pending_input_ts.append(time.perf_counter())

    def _on_hat(self, direction: str, pressed: bool) -> None:
        self._diagram.on_hat(direction, pressed)
        self._heatmap.flash(direction, pressed)
        self._pending_input_ts.append(time.perf_counter())

    def _on_battery(self, percent: int, charging: bool, _full: bool) -> None:
        self._battery_pct = percent; self._battery_charging = charging
    def _on_touchpad(self, contact: bool, x: float, y: float) -> None:
        self._diagram.on_touchpad(contact, x, y)
    def _on_transport(self, wired: bool) -> None:
        self._wired = wired

    def _on_midi_sent(self) -> None:
        self._midi_count += 1; self._midi_total += 1
        self._midi_out_counter += 1
        if self._pending_input_ts:
            ts = self._pending_input_ts.popleft()
            self._latency_samples.append(time.perf_counter() - ts)

    def _on_midi_message(self, direction: str, channel: int, status: int, data1: int, data2: int, label: str) -> None:
        """Track incoming MIDI for throughput counting."""
        if direction == "received":
            self._midi_in_counter += 1

    def _on_controller_info(self, info) -> None:
        if info is None:
            self._connected_name = "—"; self._diagram.reset()
            self._runtime_start = None
        else:
            self._connected_name = info.name

    def _on_started(self, controller_name: str, _port_name: str) -> None:
        self._connected_name = controller_name
        self._runtime_start = time.perf_counter()

    def _on_stopped(self) -> None:
        self._runtime_start = None; self._diagram.reset()

    def _tick(self) -> None:
        """30 Hz repaint pass — drives everything that animates."""
        self._diagram.update()
        for scope in self._oscilloscopes.values(): scope.update()
        for spark in self._sparklines.values(): spark.update()
        self._heatmap.update(); self._refresh_stats()

    def _flush_rate(self) -> None:
        self._stat_rate.setText(str(self._midi_count)); self._midi_count = 0

    def _tick_throughput(self) -> None:
        """Called every 1 second to push throughput data to the panel."""
        self._throughput_panel.tick(self._midi_out_counter, self._midi_in_counter)
        self._midi_out_counter = 0
        self._midi_in_counter = 0

    def _refresh_stats(self) -> None:
        self._stat_name.setText(self._connected_name or "—")
        self._stat_transport.setText("USB" if self._wired else "Bluetooth")
        if self._battery_pct < 0:
            self._stat_battery.setText("—")
        else:
            charge = " ⚡" if self._battery_charging else ""
            self._stat_battery.setText(f"{self._battery_pct}%{charge}")
        self._stat_total.setText(str(self._midi_total))
        # <1 ms fixed label — stops jitter on signal-dispatch noise.
        if self._latency_samples:
            ms = (sum(self._latency_samples) / len(self._latency_samples)) * 1000.0
            self._stat_latency.setText("<1 ms" if ms < 1.0 else f"{ms:.1f} ms")
        else:
            self._stat_latency.setText("—")
        if self._runtime_start is None:
            self._stat_runtime.setText("—")
        else:
            secs = int(time.perf_counter() - self._runtime_start)
            h, rem = divmod(secs, 3600); m, s = divmod(rem, 60)
            self._stat_runtime.setText(
                f"{h}h {m:02d}m {s:02d}s" if h else f"{m:02d}:{s:02d}"
            )
