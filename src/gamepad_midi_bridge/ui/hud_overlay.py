"""HUD overlay — always-on-top translucent status widget for background / tray mode.

Shows the current preset name, MIDI throughput, and bridge running state so a
performer can monitor the bridge without un-minimising the main window.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QPoint, QSettings
from PySide6.QtGui import QMouseEvent, QPainter, QColor, QFont
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QVBoxLayout, QWidget


_SETTINGS_ORG = "Aidxn Design"
_SETTINGS_APP = "GamepadMidiBridge"
_KEY_POS_X = "hud/pos_x"
_KEY_POS_Y = "hud/pos_y"
_KEY_VISIBLE = "hud/visible"

_W = 240
_H = 70


def _default_pos() -> QPoint:
    """Bottom-right of the primary screen with 16px margin."""
    screen = QApplication.primaryScreen()
    if screen is None:
        return QPoint(40, 40)
    geo = screen.availableGeometry()
    return QPoint(geo.right() - _W - 16, geo.bottom() - _H - 16)


class HudOverlay(QWidget):
    """Small always-on-top translucent HUD overlay.

    Window flags:
      - FramelessWindowHint — no title bar / decorations
      - WindowStaysOnTopHint — floats above all other windows
      - Tool — hidden from the taskbar / dock
    Background:
      - WA_TranslucentBackground — OS composites the rounded semi-transparent bg

    The widget is draggable; position persists via QSettings.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedSize(_W, _H)

        # Internal state
        self._preset_name: str = "—"
        self._out_rate: int = 0
        self._in_rate: int = 0
        self._running: bool = False

        # Drag state
        self._drag_start: QPoint | None = None

        self._build_ui()
        self._restore_position()

    # ---------------------------------------------------------------------- UI

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 8, 10, 8)
        outer.setSpacing(4)

        # Row 1: preset name
        self._preset_label = QLabel(self._preset_name)
        self._preset_label.setStyleSheet(
            "color: #f5f7fa; font-size: 11px; font-weight: 700;"
            " background: transparent;"
        )
        outer.addWidget(self._preset_label)

        # Row 2: throughput + status dot
        row2 = QHBoxLayout()
        row2.setContentsMargins(0, 0, 0, 0)
        row2.setSpacing(6)

        self._throughput_label = QLabel("▲0 ▼0 msg/s")
        self._throughput_label.setStyleSheet(
            "color: #8a9099; font-size: 10px;"
            " font-family: ui-monospace, Menlo, monospace;"
            " background: transparent;"
        )
        row2.addWidget(self._throughput_label, 1)

        self._status_dot = QLabel("●")
        self._status_dot.setStyleSheet(
            "color: #2c313b; font-size: 14px; background: transparent;"
        )
        row2.addWidget(self._status_dot)
        outer.addLayout(row2)

    # ---------------------------------------------------------------------- paint

    def paintEvent(self, _event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(1, 1, -1, -1)
        bg = QColor(14, 15, 18, 210)   # ~82% opaque near-black
        painter.setBrush(bg)
        painter.setPen(QColor(44, 49, 59, 180))
        painter.drawRoundedRect(rect, 8, 8)

    # ---------------------------------------------------------------------- drag

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_start = event.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_start is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_start)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_start = None
            self._save_position()

    # ---------------------------------------------------------------------- position persistence

    def _save_position(self) -> None:
        s = QSettings(_SETTINGS_ORG, _SETTINGS_APP)
        s.setValue(_KEY_POS_X, self.x())
        s.setValue(_KEY_POS_Y, self.y())

    def _restore_position(self) -> None:
        s = QSettings(_SETTINGS_ORG, _SETTINGS_APP)
        default = _default_pos()
        x = int(s.value(_KEY_POS_X, default.x()))
        y = int(s.value(_KEY_POS_Y, default.y()))
        self.move(x, y)

    # ---------------------------------------------------------------------- public API

    def set_preset(self, name: str) -> None:
        """Update the preset name label."""
        self._preset_name = name or "—"
        self._preset_label.setText(self._preset_name)

    def set_throughput(self, out: int, in_: int = 0) -> None:
        """Update the throughput readout. ``out`` and ``in_`` are msgs/sec."""
        self._out_rate = out
        self._in_rate = in_
        self._throughput_label.setText(f"▲{out} ▼{in_} msg/s")

    def set_status(self, running: bool) -> None:
        """Update the status indicator dot — green = running, dim = stopped."""
        self._running = running
        if running:
            self._status_dot.setStyleSheet(
                "color: #2dd4bf; font-size: 14px; background: transparent;"
            )
        else:
            self._status_dot.setStyleSheet(
                "color: #2c313b; font-size: 14px; background: transparent;"
            )

    # ---------------------------------------------------------------------- QSettings helpers (static)

    @staticmethod
    def read_visible() -> bool:
        """Read the persisted hud_visible flag. Default False."""
        s = QSettings(_SETTINGS_ORG, _SETTINGS_APP)
        val = s.value(_KEY_VISIBLE, False)
        if isinstance(val, str):
            return val.lower() == "true"
        return bool(val)

    @staticmethod
    def write_visible(visible: bool) -> None:
        """Persist the hud_visible flag."""
        s = QSettings(_SETTINGS_ORG, _SETTINGS_APP)
        s.setValue(_KEY_VISIBLE, visible)
