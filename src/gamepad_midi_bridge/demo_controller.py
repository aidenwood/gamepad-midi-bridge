"""Synthetic controller for demo + QA — no hardware required.

Drop-in replacement for ControllerReader that fakes a DualSense. Sticks
sweep slow sine + cosine, triggers ramp 0→1 every few seconds, face
buttons pulse on a schedule. Useful for:

    - Recording demo videos without owning a controller
    - Smoke-testing the bridge in CI with real MIDI flowing
    - Testing connectors against a downstream DAW

Activated by `gamepad-midi-bridge --demo`. The rest of the bridge
doesn't need to know — same shape as ControllerReader.
"""
from __future__ import annotations

import math
import time
from typing import Optional, Tuple

from .controller import ControllerInfo


class SyntheticControllerReader:
    """Quacks like ControllerReader. State is generated procedurally per pump()."""

    def __init__(self, slot_index: int = 0) -> None:
        self._slot_index = slot_index
        self._start = time.perf_counter()
        # Latched values updated by pump() so reads within one tick are coherent.
        self._axes = [0.0] * 6
        self._buttons = [False] * 11
        self._hat = (0, 0)

    # ---- lifecycle (matches ControllerReader API)

    def detect(self) -> Optional[ControllerInfo]:
        return ControllerInfo(
            name="DualSense Wireless Controller (demo)",
            num_axes=6,
            num_buttons=11,
            num_hats=1,
            guid="00000000000000000000000000000000",
        )

    def close(self) -> None:
        pass

    def is_connected(self) -> bool:
        return True

    # ---- polling

    def pump(self) -> None:
        t = time.perf_counter() - self._start

        # Sticks sweep on slow Lissajous so meters look alive.
        self._axes[0] = math.sin(t * 0.7)
        self._axes[1] = math.cos(t * 0.5)
        self._axes[2] = math.sin(t * 0.9 + 1.0)
        self._axes[3] = math.cos(t * 1.1 + 0.5)
        # Triggers ramp 0→1 every 4 seconds (axis = -1 released, +1 pressed).
        ramp = (t % 4.0) / 4.0
        self._axes[4] = (ramp * 2.0) - 1.0
        self._axes[5] = (((t + 2.0) % 4.0) / 4.0) * 2.0 - 1.0

        # Buttons fire one at a time in a round-robin every ~0.6s.
        idx = int(t / 0.6) % len(self._buttons)
        phase = (t / 0.6) - int(t / 0.6)
        for i in range(len(self._buttons)):
            self._buttons[i] = (i == idx and phase < 0.4)

        # D-pad cycles direction every 2s.
        cycle = int(t / 2.0) % 4
        self._hat = [(1, 0), (0, 1), (-1, 0), (0, -1)][cycle]

    def get_axis(self, idx: int) -> float:
        return self._axes[idx] if 0 <= idx < len(self._axes) else 0.0

    def get_button(self, idx: int) -> bool:
        return self._buttons[idx] if 0 <= idx < len(self._buttons) else False

    def get_hat(self, idx: int = 0) -> Tuple[int, int]:
        return self._hat

    def num_axes(self) -> int:
        return len(self._axes)

    def num_buttons(self) -> int:
        return len(self._buttons)

    def num_hats(self) -> int:
        return 1
