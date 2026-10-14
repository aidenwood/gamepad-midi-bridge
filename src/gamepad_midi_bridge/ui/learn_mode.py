"""Learn mode — a toggleable hover-to-learn overlay.

When Learn mode is ON, hovering any widget tagged via ``learn()`` pops a small
card near the cursor explaining what the control does. OFF by default; toggled
from the toolbar so power users aren't interrupted.

Why cursor-polling instead of an event filter: ``QEvent.MouseMove`` is only
delivered to widgets with mouse tracking, and ``HoverMove`` only to widgets with
``WA_Hover`` — neither is universal. Polling ``QApplication.widgetAt(QCursor.pos())``
at ~11 Hz (only while active) reliably resolves whatever is under the cursor
across every tab, with negligible cost since it's an explicit, opt-in mode.

Usage:
    from .learn_mode import learn, LearnController
    learn(my_button, "Start", "Begins bridging your controller to MIDI.")
    controller = LearnController(self)
    learn_toggle.toggled.connect(controller.set_active)
"""
from __future__ import annotations

from typing import Optional, Tuple

from PySide6.QtCore import QObject, QPoint, Qt, QTimer
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QApplication, QFrame, QLabel, QVBoxLayout, QWidget,
)

_LEARN_TITLE = "_learnTitle"
_LEARN_TEXT = "_learnText"
_MAX_PARENT_WALK = 6  # hover a child label inside a card → still find the card's learn text


def learn(widget: QWidget, title: str, text: str = "") -> QWidget:
    """Tag a widget with hover-to-learn metadata. Returns the widget for chaining.

    Safe to call on any QWidget; tagging travels with the widget (dynamic
    properties) and is read only while Learn mode is active.
    """
    widget.setProperty(_LEARN_TITLE, title)
    widget.setProperty(_LEARN_TEXT, text)
    return widget


def _learn_for(widget: Optional[QWidget]) -> Optional[Tuple[str, str]]:
    """Walk up from `widget` to find the nearest ancestor carrying learn text."""
    w = widget
    depth = 0
    while w is not None and depth < _MAX_PARENT_WALK:
        title = w.property(_LEARN_TITLE)
        if title:
            return str(title), str(w.property(_LEARN_TEXT) or "")
        w = w.parentWidget()
        depth += 1
    return None


class LearnOverlay(QFrame):
    """Frameless tooltip-style card shown near the cursor in Learn mode."""

    def __init__(self) -> None:
        # Tool + frameless so it floats above everything without stealing focus.
        super().__init__(None, Qt.ToolTip | Qt.FramelessWindowHint)
        self.setObjectName("LearnOverlay")
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)  # never intercept hover
        self.setStyleSheet(
            "#LearnOverlay { background-color: #1b1e25; border: 1px solid #2dd4bf;"
            " border-radius: 8px; }"
            "#LearnOverlayTitle { color: #2dd4bf; font-weight: 600; font-size: 13px; }"
            "#LearnOverlayText { color: #c2c6cc; font-size: 12px; }"
        )
        v = QVBoxLayout(self)
        v.setContentsMargins(12, 10, 12, 10)
        v.setSpacing(4)
        self._title = QLabel(self)
        self._title.setObjectName("LearnOverlayTitle")
        self._text = QLabel(self)
        self._text.setObjectName("LearnOverlayText")
        self._text.setWordWrap(True)
        self._text.setMaximumWidth(300)
        v.addWidget(self._title)
        v.addWidget(self._text)

    def show_for(self, title: str, text: str, global_pos: QPoint) -> None:
        self._title.setText(title)
        self._text.setText(text)
        self._text.setVisible(bool(text))
        self.adjustSize()
        # Offset from the cursor so the card doesn't sit under the pointer; nudge
        # back on-screen if it would overflow the right/bottom edge.
        screen = QApplication.screenAt(global_pos)
        geo = screen.availableGeometry() if screen is not None else None
        x = global_pos.x() + 16
        y = global_pos.y() + 18
        if geo is not None:
            if x + self.width() > geo.right():
                x = global_pos.x() - self.width() - 16
            if y + self.height() > geo.bottom():
                y = global_pos.y() - self.height() - 18
        self.move(QPoint(x, y))
        if not self.isVisible():
            self.show()


class LearnController(QObject):
    """Owns the overlay + the cursor poll loop. Toggle with set_active()."""

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._active = False
        self._overlay: Optional[LearnOverlay] = None
        self._last_key: Optional[Tuple[str, str]] = None
        self._timer = QTimer(self)
        self._timer.setInterval(90)  # ~11 Hz, only runs while active
        self._timer.timeout.connect(self._tick)

    def is_active(self) -> bool:
        return self._active

    def set_active(self, active: bool) -> None:
        self._active = bool(active)
        if self._active:
            if self._overlay is None:
                self._overlay = LearnOverlay()
            self._timer.start()
        else:
            self._timer.stop()
            if self._overlay is not None:
                self._overlay.hide()
            self._last_key = None

    def _tick(self) -> None:
        if not self._active or self._overlay is None:
            return
        pos = QCursor.pos()
        info = _learn_for(QApplication.widgetAt(pos))
        if info is None:
            if self._overlay.isVisible():
                self._overlay.hide()
            self._last_key = None
            return
        # Reposition every tick (follows the cursor); reset content only on change.
        if info != self._last_key:
            self._last_key = info
        self._overlay.show_for(info[0], info[1], pos)
