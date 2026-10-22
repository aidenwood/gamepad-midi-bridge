"""pygame joystick wrapper.

Kept thin so the bridge engine can poll without caring about pygame internals.
We deliberately initialise only the joystick subsystem (not video/audio) so
PyInstaller bundles stay small and we don't pop a window.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Optional, Tuple

from .control_labels import display_name
from .sdl_profiles import IDENTITY_AXES, IDENTITY_BUTTONS, profile_for

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
    # Diagnostics, so the UI can show what the app DECIDED rather than
    # leaving a user to infer it from which control moved the wrong thing.
    # Defaulted so every existing construction site still works.
    raw_name: str = ""
    # Canonical axis -> device axis, as a 6-tuple indexed by canonical.
    axis_map: tuple = ()


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
        # Canonical-index -> device-index remap, resolved per device in
        # detect(). Identity until then, so a reader that has never detected
        # behaves exactly as it did before profiles existed.
        self._axis_map = dict(IDENTITY_AXES)
        self._button_map = dict(IDENTITY_BUTTONS)
        self._dpad_buttons: Optional[Tuple[int, int, int, int]] = None
        # The untouched string SDL handed us, before display_name tidies it.
        # Shown in the UI so "what does the app think this is" is answerable.
        self._raw_name = ""

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
        # Normalise the name HERE, at the one place ControllerInfo is built,
        # so the header, LIVE STATS, telemetry, controller history and the
        # A/B/X/Y label family all correct together. SDL hands back the USB
        # product string, and Microsoft sets that to the literal word
        # "Controller" — which then classified as GENERIC and cost Xbox pads
        # their button names too. The real VID:PID is in the GUID.
        guid = js.get_guid()
        self._raw_name = js.get_name()
        # Resolve the index remap for THIS device. pygame.joystick returns
        # raw HID indices, not SDL GameController ones, so the numbers differ
        # per pad — an Xbox Wireless Controller puts its left trigger on
        # axis 2, where this app expects right-stick X.
        self._axis_map, self._button_map, self._dpad_buttons = profile_for(
            guid, js.get_numhats(), js.get_numbuttons()
        )
        return ControllerInfo(
            name=display_name(self._raw_name, guid),
            num_axes=js.get_numaxes(),
            num_buttons=js.get_numbuttons(),
            num_hats=js.get_numhats(),
            guid=guid,
            raw_name=self._raw_name,
            axis_map=tuple(self._axis_map.get(i, i) for i in range(6)),
        )

    @property
    def raw_name(self) -> str:
        """SDL's own string for the device, before display_name cleans it up."""
        return self._raw_name

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
        """Read a CANONICAL axis (0=LX 1=LY 2=RX 3=RY 4=L2 5=R2).

        The device index is looked up per pad — see sdl_profiles. Callers
        never deal in raw HID indices.
        """
        if not self._alive():
            return 0.0
        try:
            return self._joystick.get_axis(self._axis_map.get(idx, idx))
        except (pygame.error, IndexError):
            return 0.0

    def get_raw_axis(self, idx: int) -> float:
        """Read a DEVICE axis with no remapping — diagnostics only."""
        if not self._alive():
            return 0.0
        try:
            return self._joystick.get_axis(idx)
        except (pygame.error, IndexError):
            return 0.0

    def get_button(self, idx: int) -> bool:
        """Read a CANONICAL button index. See get_axis."""
        if not self._alive():
            return False
        physical = self._button_map.get(idx, idx)
        if physical is None:
            return False
        try:
            return bool(self._joystick.get_button(physical))
        except (pygame.error, IndexError):
            return False

    def get_raw_button(self, idx: int) -> bool:
        """Read a DEVICE button with no remapping — diagnostics only."""
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
            # Pads with no hat carry the d-pad on four buttons instead —
            # without this the d-pad was silently dead on those devices.
            if self._dpad_buttons is not None:
                up, down, left, right = self._dpad_buttons
                x = (1 if self.get_raw_button(right) else 0) \
                    - (1 if self.get_raw_button(left) else 0)
                y = (1 if self.get_raw_button(up) else 0) \
                    - (1 if self.get_raw_button(down) else 0)
                return (x, y)
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
        names.append(display_name(js.get_name(), js.get_guid()))
        js.quit()
    return names
