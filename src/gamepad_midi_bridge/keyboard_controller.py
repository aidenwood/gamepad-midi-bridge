"""Hardware-free gamepad simulation using keyboard input.

Drop-in replacement for ControllerReader that reads keyboard state and
maps physical keys to gamepad axes and buttons. Useful for producers and VJs
to validate mappings without owning a controller.

Activated by `gamepad-midi-bridge --keyboard`. Uses the same interface as
ControllerReader, so the bridge doesn't need to know about it.
"""
from __future__ import annotations

from typing import Optional, Tuple

from PySide6.QtCore import Qt

from .controller import ControllerInfo
from .keyboard_bus import KeyboardBus


class KeyboardControllerReader:
    """Maps keyboard keys to gamepad axes and buttons.

    Layout:
      - WASD → left stick (axes 0, 1): W/S = Y, A/D = X
      - Arrow keys → right stick (axes 2, 3): Up/Down = Y, Left/Right = X
      - Q, E → L2, R2 triggers (axes 4, 5): pressed = 1.0, released = 0.0
      - Space → button 0 (cross/A)
      - Shift → button 1 (square/X)
      - Z → button 2 (triangle/Y)
      - X → button 3 (circle/B)
      - Tab → button 4 (L1)
      - Backspace → button 5 (R1)
      - D-pad: [reserved for future use, currently all zeros]
    """

    # Qt key constants (from PySide6.QtCore.Qt.Key)
    KEY_W = Qt.Key_W
    KEY_A = Qt.Key_A
    KEY_S = Qt.Key_S
    KEY_D = Qt.Key_D
    KEY_UP = Qt.Key_Up
    KEY_DOWN = Qt.Key_Down
    KEY_LEFT = Qt.Key_Left
    KEY_RIGHT = Qt.Key_Right
    KEY_Q = Qt.Key_Q
    KEY_E = Qt.Key_E
    KEY_SPACE = Qt.Key_Space
    KEY_SHIFT = Qt.Key_Shift
    KEY_Z = Qt.Key_Z
    KEY_X = Qt.Key_X
    KEY_TAB = Qt.Key_Tab
    KEY_BACKSPACE = Qt.Key_Backspace

    def __init__(self, slot_index: int = 0) -> None:
        """Initialize the keyboard controller reader.

        Args:
            slot_index: Unused, kept for compatibility with ControllerReader API.
        """
        self._slot_index = max(0, int(slot_index))
        self._bus = KeyboardBus.instance()
        # Cached axis values (updated by pump).
        self._axes = [0.0] * 6
        self._buttons = [False] * 11
        self._hat = (0, 0)

    # ---- lifecycle (matches ControllerReader API)

    def detect(self) -> Optional[ControllerInfo]:
        """Return a fake DualSense controller info."""
        return ControllerInfo(
            name="Keyboard Controller (hardware-free testing)",
            num_axes=6,
            num_buttons=11,
            num_hats=1,
            guid="00000000000000000000000000000000",
        )

    def close(self) -> None:
        """No cleanup needed for keyboard input."""
        pass

    def is_connected(self) -> bool:
        """Keyboard controller is always 'connected'."""
        return True

    # ---- polling

    def pump(self) -> None:
        """Update cached axis and button states from current key presses."""
        # Left stick (axes 0, 1) from WASD
        w_down = self._bus.is_key_down(self.KEY_W)
        s_down = self._bus.is_key_down(self.KEY_S)
        a_down = self._bus.is_key_down(self.KEY_A)
        d_down = self._bus.is_key_down(self.KEY_D)

        # Axis 0: X (A=−1, D=+1)
        self._axes[0] = 0.0
        if a_down:
            self._axes[0] -= 1.0
        if d_down:
            self._axes[0] += 1.0

        # Axis 1: Y (W=−1, S=+1) — note: gamepad +Y is down
        self._axes[1] = 0.0
        if w_down:
            self._axes[1] -= 1.0
        if s_down:
            self._axes[1] += 1.0

        # Right stick (axes 2, 3) from arrow keys
        up_down = self._bus.is_key_down(self.KEY_UP)
        down_down = self._bus.is_key_down(self.KEY_DOWN)
        left_down = self._bus.is_key_down(self.KEY_LEFT)
        right_down = self._bus.is_key_down(self.KEY_RIGHT)

        # Axis 2: X (Left=−1, Right=+1)
        self._axes[2] = 0.0
        if left_down:
            self._axes[2] -= 1.0
        if right_down:
            self._axes[2] += 1.0

        # Axis 3: Y (Up=−1, Down=+1)
        self._axes[3] = 0.0
        if up_down:
            self._axes[3] -= 1.0
        if down_down:
            self._axes[3] += 1.0

        # Triggers (axes 4, 5) from Q, E
        # -1.0 = released, +1.0 = fully pressed
        q_down = self._bus.is_key_down(self.KEY_Q)
        e_down = self._bus.is_key_down(self.KEY_E)
        self._axes[4] = 1.0 if q_down else -1.0
        self._axes[5] = 1.0 if e_down else -1.0

        # Face buttons (0–3)
        self._buttons[0] = self._bus.is_key_down(self.KEY_SPACE)   # cross/A
        self._buttons[1] = self._bus.is_key_down(self.KEY_SHIFT)   # square/X
        self._buttons[2] = self._bus.is_key_down(self.KEY_Z)       # triangle/Y
        self._buttons[3] = self._bus.is_key_down(self.KEY_X)       # circle/B

        # Shoulder buttons (4–5)
        self._buttons[4] = self._bus.is_key_down(self.KEY_TAB)        # L1
        self._buttons[5] = self._bus.is_key_down(self.KEY_BACKSPACE)  # R1

        # Unused buttons (6–10)
        for i in range(6, 11):
            self._buttons[i] = False

        # D-pad (unused for now)
        self._hat = (0, 0)

    def get_axis(self, idx: int) -> float:
        """Return axis value (−1.0 to +1.0)."""
        return self._axes[idx] if 0 <= idx < len(self._axes) else 0.0

    def get_button(self, idx: int) -> bool:
        """Return button state."""
        return self._buttons[idx] if 0 <= idx < len(self._buttons) else False

    def get_hat(self, idx: int = 0) -> Tuple[int, int]:
        """Return D-pad state (unused, always 0, 0)."""
        return self._hat

    def num_axes(self) -> int:
        """Return number of axes."""
        return len(self._axes)

    def num_buttons(self) -> int:
        """Return number of buttons."""
        return len(self._buttons)

    def num_hats(self) -> int:
        """Return number of hat switches."""
        return 1
