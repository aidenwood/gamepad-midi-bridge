"""Hardware-free gamepad simulation using mouse input.

Drop-in replacement for ControllerReader that reads mouse state and
maps cursor movement + clicks to gamepad axes and buttons. Useful for
producers and VJs to validate mappings without owning a controller.

Activated by `gamepad-midi-bridge --mouse`. Uses the same interface as
ControllerReader, so the bridge doesn't need to know about it.
"""
from __future__ import annotations

from typing import Optional, Tuple

from .controller import ControllerInfo
from .mouse_bus import MouseBus


class MouseControllerReader:
    """Maps mouse input to gamepad axes and buttons.

    Layout:
      - Mouse X/Y delta from window center → left stick (axes 0, 1): X/Y
      - Left click → button 0 (cross/A)
      - Right click → button 1 (square/X)
      - Middle click → button 4 (L1)
      - Mouse wheel up → axis 4 (L2 trigger) = +1.0 (pressed)
      - Mouse wheel down → axis 4 (L2 trigger) = -1.0 (released)
      - All other axes and buttons → 0.0 / False
    """

    # Button codes (match mouse_bus.py)
    BTN_LEFT = 0        # Left click
    BTN_RIGHT = 1       # Right click
    BTN_MIDDLE = 4      # Middle click (L1)

    def __init__(self, slot_index: int = 0) -> None:
        """Initialize the mouse controller reader.

        Args:
            slot_index: Unused, kept for compatibility with ControllerReader API.
        """
        self._slot_index = max(0, int(slot_index))
        self._bus = MouseBus.instance()
        # Cached axis values (updated by pump).
        self._axes = [0.0] * 6
        self._buttons = [False] * 11
        self._hat = (0, 0)

    # ---- lifecycle (matches ControllerReader API)

    def detect(self) -> Optional[ControllerInfo]:
        """Return a fake DualSense controller info."""
        return ControllerInfo(
            name="Mouse Controller (hardware-free demo)",
            num_axes=6,
            num_buttons=11,
            num_hats=1,
            guid="00000000000000000000000000000001",
        )

    def close(self) -> None:
        """No cleanup needed for mouse input."""
        pass

    def is_connected(self) -> bool:
        """Mouse controller is always 'connected'."""
        return True

    # ---- polling

    def pump(self) -> None:
        """Update cached axis and button states from current mouse position and presses."""
        # Left stick (axes 0, 1) from mouse position relative to window center
        norm_x, norm_y = self._bus.get_position()
        self._axes[0] = norm_x  # X
        self._axes[1] = norm_y  # Y

        # Right stick (axes 2, 3) remain unmapped
        self._axes[2] = 0.0
        self._axes[3] = 0.0

        # L2 trigger (axis 4) from mouse wheel scroll
        l2_scroll = self._bus.get_l2_scroll()
        self._axes[4] = float(l2_scroll)  # 1.0 = up (pressed), -1.0 = down (released), 0.0 = neutral

        # R2 trigger (axis 5) unmapped
        self._axes[5] = 0.0

        # Face buttons (0–3)
        self._buttons[0] = self._bus.is_button_down(self.BTN_LEFT)    # cross/A
        self._buttons[1] = self._bus.is_button_down(self.BTN_RIGHT)   # square/X
        self._buttons[2] = False  # triangle/Y unmapped
        self._buttons[3] = False  # circle/B unmapped

        # Shoulder buttons (4–5)
        self._buttons[4] = self._bus.is_button_down(self.BTN_MIDDLE)  # L1
        self._buttons[5] = False  # R1 unmapped

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
