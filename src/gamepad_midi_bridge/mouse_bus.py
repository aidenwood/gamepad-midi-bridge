"""Singleton mouse event bus for hardware-free demo mode.

Captures mouse moves + clicks via Qt event filter and exposes state via
the same pattern as KeyboardBus, so MouseControllerReader can poll position
and button state.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QObject, Signal, QPoint
from PySide6.QtWidgets import QApplication


class MouseBus(QObject):
    """Emits mouse movements and button clicks as state snapshots.

    The bus captures QMouseEvent and QWheelEvent at the QApplication level
    and tracks cursor position relative to the active window center, plus
    button press state and scroll accumulation.

    Usage:
        bus = MouseBus.instance()
        bus.mouse_moved.connect(lambda x, y: print(f"Mouse at {x}, {y}"))
        bus.button_pressed.connect(lambda btn: print(f"Button {btn} down"))
    """

    mouse_moved = Signal(float, float)      # normalized X, Y (-1..+1)
    button_pressed = Signal(int)            # button code (0=left, 1=right, 4=middle)
    button_released = Signal(int)           # button code
    wheel_scrolled = Signal(int)            # scroll direction (1=up, -1=down)

    _instance: Optional[MouseBus] = None

    def __init__(self) -> None:
        super().__init__()
        self._buttons_down: set[int] = set()
        self._norm_x: float = 0.0            # normalized X (-1..+1)
        self._norm_y: float = 0.0            # normalized Y (-1..+1)
        self._l2_scroll: int = 0             # accumulated wheel scroll for L2 trigger

    @classmethod
    def instance(cls) -> MouseBus:
        """Return the singleton instance, creating if needed."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def is_button_down(self, button_code: int) -> bool:
        """Return True if the button is currently pressed."""
        return button_code in self._buttons_down

    def get_position(self) -> tuple[float, float]:
        """Return normalized cursor position (-1..+1)."""
        return (self._norm_x, self._norm_y)

    def get_l2_scroll(self) -> int:
        """Return accumulated scroll value (up=+1, down=-1)."""
        return self._l2_scroll

    def on_mouse_move(self, window_center: QPoint, cursor_pos: QPoint) -> None:
        """Called by the event filter when mouse moves.

        Args:
            window_center: Center of the active window in screen coords.
            cursor_pos: Cursor position in screen coords.
        """
        # Delta from window center
        dx = cursor_pos.x() - window_center.x()
        dy = cursor_pos.y() - window_center.y()

        # Assume window is ~800x600, so normalize to ~±400 for full stick range.
        # This gives smooth -1..+1 mapping for typical window sizes.
        # Clamp to [-1, +1].
        self._norm_x = max(-1.0, min(1.0, dx / 400.0))
        self._norm_y = max(-1.0, min(1.0, dy / 400.0))

        self.mouse_moved.emit(self._norm_x, self._norm_y)

    def on_button_pressed(self, button_code: int) -> None:
        """Called by the event filter when a mouse button is pressed."""
        if button_code not in self._buttons_down:
            self._buttons_down.add(button_code)
            self.button_pressed.emit(button_code)

    def on_button_released(self, button_code: int) -> None:
        """Called by the event filter when a mouse button is released."""
        if button_code in self._buttons_down:
            self._buttons_down.discard(button_code)
            self.button_released.emit(button_code)

    def on_wheel_scroll(self, delta: int) -> None:
        """Called by the event filter on mouse wheel events.

        Args:
            delta: QWheelEvent.angleDelta().y() (positive = up, negative = down)
        """
        # Coarse threshold: scroll accumulated across multiple ticks.
        # Qt wheel events come in 120-degree increments per "notch".
        if delta > 0:
            self._l2_scroll = 1  # up = pressed
        elif delta < 0:
            self._l2_scroll = -1  # down = released
        else:
            self._l2_scroll = 0

        self.wheel_scrolled.emit(1 if delta > 0 else -1 if delta < 0 else 0)


class _MouseEventFilter(QObject):
    """Qt event filter that captures global mouse events."""

    def __init__(self, bus: MouseBus) -> None:
        super().__init__()
        self._bus = bus

    def eventFilter(self, obj, event):  # type: ignore
        """Intercept MouseMove, MouseButtonPress, MouseButtonRelease, Wheel events."""
        from PySide6.QtCore import QEvent
        from PySide6.QtGui import QMouseEvent
        from PySide6.QtWidgets import QWidget

        if event.type() == QEvent.MouseMove:
            mouse_event = event
            # Get the window (top-level widget) geometry to compute center
            widget = obj
            while widget and not isinstance(widget, QWidget):
                widget = getattr(widget, "parent", lambda: None)()
            if widget:
                window = widget.window()
                geom = window.frameGeometry()
                center = geom.center()
                cursor_pos = QPoint(
                    int(mouse_event.globalPosition().x()),
                    int(mouse_event.globalPosition().y()),
                )
                self._bus.on_mouse_move(center, cursor_pos)

        elif event.type() == QEvent.MouseButtonPress:
            button_code = self._button_code(event.button())
            if button_code is not None:
                self._bus.on_button_pressed(button_code)

        elif event.type() == QEvent.MouseButtonRelease:
            button_code = self._button_code(event.button())
            if button_code is not None:
                self._bus.on_button_released(button_code)

        elif event.type() == QEvent.Wheel:
            delta = int(event.angleDelta().y())
            self._bus.on_wheel_scroll(delta)

        # Don't consume the event — let normal input handling proceed.
        return False

    @staticmethod
    def _button_code(qt_button) -> Optional[int]:  # type: ignore
        """Map Qt.MouseButton to our button codes."""
        from PySide6.QtCore import Qt
        mapping = {
            Qt.MouseButton.LeftButton: 0,
            Qt.MouseButton.RightButton: 1,
            Qt.MouseButton.MiddleButton: 4,
        }
        return mapping.get(qt_button, None)


def install_mouse_filter(app: Optional[QApplication] = None) -> MouseBus:
    """Install the global mouse event filter on QApplication.

    Returns the MouseBus instance for subscribing to mouse events.
    Safe to call multiple times — subsequent calls are no-ops.
    """
    if app is None:
        app = QApplication.instance()
    if app is None:
        # No QApplication running — return the singleton bus without installing.
        # (Graceful fallback for tests or headless modes.)
        return MouseBus.instance()

    bus = MouseBus.instance()
    # Only install once per app instance.
    if not hasattr(app, "_mouse_filter_installed"):
        filter_obj = _MouseEventFilter(bus)
        app.installEventFilter(filter_obj)
        app._mouse_filter_installed = True  # type: ignore

    return bus
