"""pygame joystick wrapper.

Kept thin so the bridge engine can poll without caring about pygame internals.
We deliberately initialise only the joystick subsystem (not video/audio) so
PyInstaller bundles stay small and we don't pop a window.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Optional, Tuple

# Headless flag has to be set BEFORE pygame.init() — keeps SDL from probing
# for a display server (Linux servers / CI / packaged apps).
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402


@dataclass
class ControllerInfo:
    name: str
    num_axes: int
    num_buttons: int
    num_hats: int
    guid: str


class ControllerReader:
    """Polls the first connected joystick. One reader per bridge."""

    def __init__(self) -> None:
        if not pygame.get_init():
            pygame.init()
        if not pygame.joystick.get_init():
            pygame.joystick.init()
        self._joystick: Optional[pygame.joystick.JoystickType] = None

    # ------------------------------------------------------------------ lifecycle

    def detect(self) -> Optional[ControllerInfo]:
        """Pick up the first connected joystick. Returns None if none present."""
        pygame.joystick.quit()
        pygame.joystick.init()
        if pygame.joystick.get_count() == 0:
            self._joystick = None
            return None
        js = pygame.joystick.Joystick(0)
        js.init()
        self._joystick = js
        return ControllerInfo(
            name=js.get_name(),
            num_axes=js.get_numaxes(),
            num_buttons=js.get_numbuttons(),
            num_hats=js.get_numhats(),
            guid=js.get_guid(),
        )

    def is_connected(self) -> bool:
        return self._joystick is not None and pygame.joystick.get_count() > 0

    def close(self) -> None:
        if self._joystick is not None:
            try:
                self._joystick.quit()
            except Exception:
                pass
            self._joystick = None
        pygame.joystick.quit()

    # ------------------------------------------------------------------ polling

    def pump(self) -> None:
        pygame.event.pump()

    def get_axis(self, idx: int) -> float:
        return self._joystick.get_axis(idx) if self._joystick else 0.0

    def get_button(self, idx: int) -> bool:
        return bool(self._joystick.get_button(idx)) if self._joystick else False

    def get_hat(self, idx: int = 0) -> Tuple[int, int]:
        if self._joystick is None or self._joystick.get_numhats() == 0:
            return (0, 0)
        return self._joystick.get_hat(idx)

    def num_axes(self) -> int:
        return self._joystick.get_numaxes() if self._joystick else 0

    def num_buttons(self) -> int:
        return self._joystick.get_numbuttons() if self._joystick else 0

    def num_hats(self) -> int:
        return self._joystick.get_numhats() if self._joystick else 0


def available_controllers() -> List[str]:
    """List currently connected joystick names (for the settings dropdown)."""
    if not pygame.get_init():
        pygame.init()
    pygame.joystick.quit()
    pygame.joystick.init()
    names = []
    for i in range(pygame.joystick.get_count()):
        js = pygame.joystick.Joystick(i)
        js.init()
        names.append(js.get_name())
        js.quit()
    return names
