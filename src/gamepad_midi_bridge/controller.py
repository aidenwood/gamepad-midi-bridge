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

# Force SDL to use its bundled HIDAPI backend for game-controller enumeration.
# Without these hints, SDL2 on macOS 12+ falls back to IOHID, which silently
# misses Bluetooth-connected DualSense + Xbox controllers — the OS exposes
# them only through GameController.framework, and SDL's IOHID path doesn't
# follow that. With HIDAPI enabled, SDL talks to the controllers directly
# over USB or Bluetooth HID and sees both transports. cython-hidapi is a
# hard project dep so the backend is guaranteed available.
os.environ.setdefault("SDL_JOYSTICK_HIDAPI", "1")
os.environ.setdefault("SDL_JOYSTICK_HIDAPI_PS5", "1")
os.environ.setdefault("SDL_JOYSTICK_HIDAPI_PS4", "1")
os.environ.setdefault("SDL_JOYSTICK_HIDAPI_XBOX", "1")

import pygame  # noqa: E402


@dataclass
class ControllerInfo:
    name: str
    num_axes: int
    num_buttons: int
    num_hats: int
    guid: str


class ControllerReader:
    """Polls one connected joystick by pygame index. One reader per bridge.

    `slot_index` lets the multi-controller path bind reader 0 → joystick 0 and
    reader 1 → joystick 1 without the two stomping on each other. The default
    keeps the single-controller path byte-identical to V1.1.
    """

    def __init__(self, slot_index: int = 0) -> None:
        if not pygame.get_init():
            pygame.init()
        if not pygame.joystick.get_init():
            pygame.joystick.init()
        self._slot_index = max(0, int(slot_index))
        self._joystick: Optional[pygame.joystick.JoystickType] = None

    # ------------------------------------------------------------------ lifecycle

    def detect(self) -> Optional[ControllerInfo]:
        """Pick up the joystick at `slot_index`. Returns None if not present.

        We avoid a global `pygame.joystick.quit()` here when slot_index > 0 —
        re-initialising the subsystem would invalidate any joystick handle held
        by another reader running in parallel.
        """
        if self._slot_index == 0:
            # Preserves V1.1 behaviour: a fresh init guarantees a clean count.
            pygame.joystick.quit()
            pygame.joystick.init()
        elif not pygame.joystick.get_init():
            pygame.joystick.init()
        if pygame.joystick.get_count() <= self._slot_index:
            self._joystick = None
            return None
        js = pygame.joystick.Joystick(self._slot_index)
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
        # Only the slot-0 reader tears down the subsystem — otherwise the
        # second reader's joystick handle would dangle on the first stop.
        if self._slot_index == 0:
            pygame.joystick.quit()

    # ------------------------------------------------------------------ polling

    def _alive(self) -> bool:
        if self._joystick is None:
            return False
        if not pygame.get_init() or not pygame.joystick.get_init():
            return False
        try:
            return pygame.joystick.get_count() > self._slot_index
        except pygame.error:
            return False

    def pump(self) -> None:
        if not pygame.get_init() or not pygame.joystick.get_init():
            return
        try:
            pygame.event.pump()
        except pygame.error:
            pass

    def get_axis(self, idx: int) -> float:
        if not self._alive():
            return 0.0
        try:
            return self._joystick.get_axis(idx)
        except (pygame.error, IndexError):
            return 0.0

    def get_button(self, idx: int) -> bool:
        if not self._alive():
            return False
        try:
            return bool(self._joystick.get_button(idx))
        except (pygame.error, IndexError):
            return False

    def get_hat(self, idx: int = 0) -> Tuple[int, int]:
        if not self._alive():
            return (0, 0)
        try:
            if self._joystick.get_numhats() == 0:
                return (0, 0)
            return self._joystick.get_hat(idx)
        except (pygame.error, IndexError):
            return (0, 0)

    def num_axes(self) -> int:
        if not self._alive():
            return 0
        try:
            return self._joystick.get_numaxes()
        except pygame.error:
            return 0

    def num_buttons(self) -> int:
        if not self._alive():
            return 0
        try:
            return self._joystick.get_numbuttons()
        except pygame.error:
            return 0

    def num_hats(self) -> int:
        if not self._alive():
            return 0
        try:
            return self._joystick.get_numhats()
        except pygame.error:
            return 0


def available_count() -> int:
    """Return the number of joysticks pygame currently sees.

    Cheap helper so the multi-controller path can decide whether to spin up a
    second bridge without doing the full name-listing dance.
    """
    if not pygame.get_init():
        pygame.init()
    pygame.joystick.quit()
    pygame.joystick.init()
    return pygame.joystick.get_count()


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
