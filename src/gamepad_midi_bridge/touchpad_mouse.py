"""Touchpad -> OS cursor deltas.

Turns the DualSense / DualShock touchpad into a laptop-style trackpad for the
machine the bridge is running on. Pure stdlib: no Qt, no hardware reads, the
caller supplies normalised floats and applies the resulting delta. That keeps
it testable and keeps cursor work off the BridgeWorker poll loop — the Qt side
consumes the existing `touchpad_xy` signal and moves the cursor in a slot on
the GUI thread.

The whole problem here is lift-and-replace. A touchpad reports an *absolute*
contact position, so naively feeding it to the cursor means every time you
lift your finger and put it down somewhere else the pointer teleports. Real
trackpads solve this by tracking deltas within a single contact and discarding
the gap between contacts. That is what `TouchpadMouse` does:

    contact starts  -> seed the reference point, emit (0, 0)
    contact moves   -> emit (dx, dy) scaled by sensitivity
    contact ends    -> drop the reference so the next touch re-seeds

Coordinates in: x and y normalised 0..1, origin top-left, matching the
`touchpad_xy` signal. Deltas out: pixels, positive x right, positive y down.
"""
from __future__ import annotations

from dataclasses import dataclass

# Full-width swipe at sensitivity 1.0 travels this many pixels. Chosen so one
# edge-to-edge drag crosses a 1440-wide display a little over once, which feels
# close to a laptop trackpad rather than a drawing tablet.
BASE_TRAVEL_PX = 1600.0

# Below this movement within a contact we emit nothing. The DualSense touchpad
# jitters by a fraction of a percent while a finger rests on it, and without
# this the cursor creeps on a stationary finger.
JITTER_EPSILON = 0.0015


@dataclass
class MouseModeConfig:
    """Config for touchpad-as-mouse.

    Fields:
      - `enabled`       : master switch. Off by default — this takes over the
                          system cursor, so it is never on without being asked.
      - `toggle_button` : button index that flips mouse mode on/off while the
                          bridge runs. Defaults to 6, which is Share on a
                          DualSense (View on Xbox, Minus on Switch Pro).
      - `sensitivity`   : 0.1..5.0 multiplier on cursor travel.
      - `invert_y`      : natural-scrolling style vertical inversion.
      - `suppress_midi` : when True the touchpad stops emitting its XY CCs
                          while mouse mode is active, so you are not scrubbing
                          a filter with the same finger that is moving the
                          pointer. On by default because doing both at once is
                          almost never what you want.

    Depends on `Mapping.touchpad.enabled`. The bridge only emits `touchpad_xy`
    inside `if mapping.touchpad.enabled:`, so a preset that turns mouse mode on
    while leaving the touchpad disabled produces no cursor movement at all. Any
    UI exposing this should enable the touchpad alongside it.
    """

    enabled: bool = False
    toggle_button: int = 6
    sensitivity: float = 1.0
    invert_y: bool = False
    suppress_midi: bool = True


def clamp_sensitivity(value: float) -> float:
    """Clamp to the supported range. Zero would be a dead pointer."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 1.0
    return max(0.1, min(5.0, v))


class TouchpadMouse:
    """Converts a stream of absolute touchpad samples into cursor deltas.

    Stateful across calls — one instance per touchpad. Call `update()` with
    every sample, including the ones where contact is False, so the lift is
    observed and the next contact re-seeds instead of jumping.
    """

    def __init__(self, config: MouseModeConfig | None = None) -> None:
        self._config = config or MouseModeConfig()
        self._ref: tuple[float, float] | None = None
        self._active = self._config.enabled

    # ── mode ────────────────────────────────────────────────────────────
    @property
    def active(self) -> bool:
        """True while mouse mode is engaged."""
        return self._active

    def set_active(self, active: bool) -> None:
        """Engage or disengage. Always drops the reference point.

        Disengaging mid-drag and re-engaging must not carry a stale reference,
        or the first sample after re-engaging produces a large jump.
        """
        self._active = bool(active)
        self._ref = None

    def toggle(self) -> bool:
        """Flip mouse mode and return the new state."""
        self.set_active(not self._active)
        return self._active

    def handle_button(self, button_idx: int, pressed: bool) -> bool:
        """Feed a button event. Returns True if this toggled mouse mode.

        Only acts on the press edge — holding the button must not thrash the
        mode, and the release is ignored.
        """
        if not pressed:
            return False
        if button_idx != self._config.toggle_button:
            return False
        self.toggle()
        return True

    # ── movement ────────────────────────────────────────────────────────
    def update(self, contact: bool, x: float, y: float) -> tuple[float, float]:
        """Consume one touchpad sample, return (dx, dy) in pixels.

        Returns (0.0, 0.0) when mouse mode is off, when there is no contact,
        on the first sample of a new contact, and when movement is inside the
        jitter epsilon.
        """
        if not self._active:
            self._ref = None
            return (0.0, 0.0)

        if not contact:
            # Finger lifted — forget where it was so the next touch re-seeds.
            self._ref = None
            return (0.0, 0.0)

        if self._ref is None:
            # First sample of this contact: anchor here, move nothing.
            self._ref = (x, y)
            return (0.0, 0.0)

        prev_x, prev_y = self._ref
        raw_dx = x - prev_x
        raw_dy = y - prev_y

        if abs(raw_dx) < JITTER_EPSILON and abs(raw_dy) < JITTER_EPSILON:
            # Hold the reference: don't advance it, or slow genuine drags get
            # eaten one sub-epsilon step at a time.
            return (0.0, 0.0)

        self._ref = (x, y)

        scale = BASE_TRAVEL_PX * clamp_sensitivity(self._config.sensitivity)
        dx = raw_dx * scale
        dy = raw_dy * scale
        if self._config.invert_y:
            dy = -dy
        return (dx, dy)

    def reset(self) -> None:
        """Drop the contact reference without changing the mode."""
        self._ref = None
