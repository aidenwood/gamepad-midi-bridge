"""Singleton keyboard event bus for hardware-free testing.

Subscribes to Qt key events app-wide and broadcasts them as signals,
so KeyboardControllerReader can poll the current key state.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication


class KeyboardBus(QObject):
    """Emits Qt key codes as key-press/release signals.

    The bus captures KeyPress and KeyRelease events at the QApplication level
    and re-broadcasts them so subscribers (like KeyboardControllerReader) can
    track which keys are currently held down.

    Usage:
        bus = KeyboardBus.instance()
        bus.key_pressed.connect(lambda code: print(f"Key {code} down"))
        bus.key_released.connect(lambda code: print(f"Key {code} up"))
    """

    key_pressed = Signal(int)      # Qt key code
    key_released = Signal(int)     # Qt key code

    _instance: Optional[KeyboardBus] = None

    def __init__(self) -> None:
        super().__init__()
        self._keys_down: set[int] = set()

    @classmethod
    def instance(cls) -> KeyboardBus:
        """Return the singleton instance, creating if needed."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def is_key_down(self, qt_key_code: int) -> bool:
        """Return True if the key is currently pressed."""
        return qt_key_code in self._keys_down

    def on_key_pressed(self, qt_key_code: int) -> None:
        """Called by the event filter when a key is pressed."""
        if qt_key_code not in self._keys_down:
            self._keys_down.add(qt_key_code)
            self.key_pressed.emit(qt_key_code)

    def on_key_released(self, qt_key_code: int) -> None:
        """Called by the event filter when a key is released."""
        if qt_key_code in self._keys_down:
            self._keys_down.discard(qt_key_code)
            self.key_released.emit(qt_key_code)


class _KeyboardEventFilter(QObject):
    """Qt event filter that captures global key events."""

    def __init__(self, bus: KeyboardBus) -> None:
        super().__init__()
        self._bus = bus

    def eventFilter(self, obj, event):  # type: ignore
        """Intercept KeyPress and KeyRelease events."""
        from PySide6.QtCore import QEvent
        if event.type() == QEvent.KeyPress and not event.isAutoRepeat():
            self._bus.on_key_pressed(event.key())
        elif event.type() == QEvent.KeyRelease and not event.isAutoRepeat():
            self._bus.on_key_released(event.key())
        # Don't consume the event — let normal text input and UI handlers proceed.
        return False


def install_keyboard_filter(app: Optional[QApplication] = None) -> KeyboardBus:
    """Install the global keyboard event filter on QApplication.

    Returns the KeyboardBus instance for subscribing to key events.
    Safe to call multiple times — subsequent calls are no-ops.
    """
    if app is None:
        app = QApplication.instance()
    if app is None:
        # No QApplication running — return the singleton bus without installing.
        # (Graceful fallback for tests or headless modes.)
        return KeyboardBus.instance()

    bus = KeyboardBus.instance()
    # Only install once per app instance.
    if not hasattr(app, "_keyboard_filter_installed"):
        filter_obj = _KeyboardEventFilter(bus)
        app.installEventFilter(filter_obj)
        app._keyboard_filter_installed = True  # type: ignore

    return bus
