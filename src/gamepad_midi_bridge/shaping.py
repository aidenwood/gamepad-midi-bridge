"""Pure-function shaping transforms for analog inputs.

Every helper here takes a normalised input value in the range [0.0, 1.0]
(or [-1.0, 1.0] for bipolar sticks) and returns either a MIDI 7-bit CC
value (0..127) or another normalised float, depending on the helper.

Why a separate module instead of inlining in bridge.py:
- Lets us unit-test the math without spinning up pygame / HID.
- Adds room for new shaping modes (curves, polar, ceiling caps) without
  bloating the per-tick polling loop.
- Keeps `bridge.py` focused on I/O and side effects.

All shapers are written so that they're stateless EXCEPT for the latch
trigger mode, which needs to remember whether it's currently "on" — that
state lives in `TriggerState` and is passed in/out per tick.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


# Trigger shaping modes — kept in this tuple so the UI dropdown + validation
# only need to import one canonical list.
TRIGGER_MODES = ("linear", "ceiling", "inverted", "latch")
DEFAULT_TRIGGER_MODE = "linear"


@dataclass
class TriggerState:
    """Mutable per-trigger state that survives across ticks.

    Currently only `latched_on` matters — the latch mode flips this when
    pressure crosses the threshold in each direction. Other modes ignore it.
    """
    latched_on: bool = False


def normalise_trigger_pressure(raw: float) -> float:
    """Coerce whatever pygame returns into a clean 0..1 trigger reading.

    SDL/pygame reports triggers differently per platform:
      - Some return -1.0 at rest, +1.0 at full press (DInput-style)
      - Others return  0.0 at rest, +1.0 at full press (XInput-style)

    Both cases produce a sensible 0..1 here because we clamp the lower
    bound at 0 after a single linear remap. Values in (-1, 0) only appear
    on DInput-style platforms where the trigger sits below zero at rest;
    we map those to 0 because that IS the rest position.
    """
    # If the raw value is negative, the platform is reporting -1..1 with
    # rest at -1. Remap to 0..1.
    if raw < 0.0:
        return max(0.0, min(1.0, (raw + 1.0) / 2.0))
    # Otherwise it's already 0..1.
    return max(0.0, min(1.0, raw))


def apply_trigger(
    raw_pressure: float,
    mode: str = DEFAULT_TRIGGER_MODE,
    ceiling: int = 127,
    latch_threshold: float = 0.5,
    state: TriggerState | None = None,
) -> int:
    """Shape a trigger pressure (0..1) into a MIDI 7-bit CC value (0..127).

    Modes:
      - `linear`   : default — straight 0 → 127 ramp.
      - `ceiling`  : 0 → `ceiling` ramp; full press never exceeds the cap.
                     Useful for limiting filter sweeps or expression depth
                     so a heavy stomp doesn't blast the value to 127.
      - `inverted` : flipped — rest position is 127, full press is 0.
                     Pairs nicely with sustain-style controls where the
                     "armed" state should be the default.
      - `latch`    : footswitch-style toggle. Crossing `latch_threshold`
                     pressed flips on; crossing it released flips off.
                     5% hysteresis around the threshold prevents chatter.

    The `state` arg is only consulted by the latch mode. Pass a per-trigger
    `TriggerState` instance and reuse it across calls. Other modes are
    pure functions of `raw_pressure`.

    Returns an int in 0..127 ready to hand to a MIDI port.
    """
    p = max(0.0, min(1.0, raw_pressure))

    if mode == "ceiling":
        cap = max(0, min(127, int(ceiling)))
        return int(round(p * cap))

    if mode == "inverted":
        return int(round((1.0 - p) * 127))

    if mode == "latch":
        if state is None:
            state = TriggerState()
        # 5% hysteresis around the user's threshold — prevents rapid
        # on/off flapping when the user holds pressure right on the line.
        on_threshold = min(1.0, latch_threshold + 0.025)
        off_threshold = max(0.0, latch_threshold - 0.025)
        if state.latched_on and p < off_threshold:
            state.latched_on = False
        elif (not state.latched_on) and p > on_threshold:
            state.latched_on = True
        return 127 if state.latched_on else 0

    # Default: linear ramp.
    return int(round(p * 127))


def gate_decision(gate_held: bool, was_held: bool) -> Tuple[bool, bool]:
    """Pure-function gate logic for "hold button to enable" workflows.

    Given the current gate-button state and the previous tick's state,
    decide what the trigger emit pipeline should do this tick.

    Returns `(should_emit, send_release_value)`:
      - `gate_held=True`            → (True, False)  — emit normal value
      - `gate_held=False, was=True` → (True, True)   — gate JUST released, emit
                                                       the configured release
                                                       value once so the
                                                       receiver doesn't keep
                                                       hearing the last
                                                       trigger value forever
      - `gate_held=False, was=False`→ (False, False) — silent (ignored input)

    Caller is responsible for storing `was_held` between ticks and feeding
    it back in next call.
    """
    if gate_held:
        return (True, False)
    if was_held:
        return (True, True)
    return (False, False)


def apply_curve(value_0_1: float, curve: str = "linear", amount: float = 0.5) -> float:
    """Bend a 0..1 input through a response curve. Returns a 0..1 output.

    Curves:
      - `linear`      : identity, `amount` ignored.
      - `exponential` : pushes the response toward the high end (slow
                        near rest, sharp near full). `amount` 0..1 controls
                        the bend strength (0 = nearly linear, 1 = aggressive).
      - `logarithmic` : the opposite — sharp near rest, slow near full.
                        Good for fine control of stick centre.
      - `s-curve`     : eases into and out of both extremes for smooth
                        modulation that resists twitchy mid-range.

    All curves preserve the endpoints (0 → 0, 1 → 1) so the user always
    gets the full range, just shaped differently in the middle.
    """
    v = max(0.0, min(1.0, value_0_1))
    a = max(0.0, min(1.0, amount))

    if curve == "exponential":
        # Power curve, exponent in [1.0, 4.0]. Higher = more curved.
        exponent = 1.0 + a * 3.0
        return v ** exponent

    if curve == "logarithmic":
        # Inverse-power curve, exponent in [0.25, 1.0]. Lower = more curved.
        exponent = 1.0 - a * 0.75
        return v ** exponent

    if curve == "s-curve":
        # Smoothstep-family with adjustable steepness.
        # k=2 = standard smoothstep; k=4 = sharper sigmoid-like shape.
        k = 2.0 + a * 2.0
        # Smoothstep: 3x^2 - 2x^3, then iterate to sharpen.
        x = v
        for _ in range(int(k)):
            x = x * x * (3.0 - 2.0 * x)
        return x

    # Linear default.
    return v


def apply_stick_shape(
    raw_value: float,
    inner_deadzone: float = 0.05,
    outer_clamp: float = 0.0,
    curve: str = "linear",
    curve_amount: float = 0.5,
) -> float:
    """Shape a -1..1 stick axis into a -1..1 shaped output.

    Sequence: deadzone → re-stretch → outer clamp → curve.

    - `inner_deadzone` 0..1: magnitudes below this snap to 0, and the
      remaining range is re-stretched to -1..1 so the user keeps full travel
      after the deadzone.
    - `outer_clamp` 0..1: top fraction of travel that pegs to ±1. e.g. 0.1
      means the last 10% of stick travel saturates to full output — useful
      because most analog sticks don't reach perfect ±1 in practice.
    - `curve` + `curve_amount`: see `apply_curve` for shaping options.
      Applied to magnitude; sign is preserved.
    """
    v = max(-1.0, min(1.0, raw_value))
    sign = 1.0 if v >= 0.0 else -1.0
    mag = abs(v)

    dz = max(0.0, min(0.99, inner_deadzone))
    if mag < dz:
        return 0.0
    # Stretch (dz, 1) → (0, 1).
    mag = (mag - dz) / (1.0 - dz)

    oc = max(0.0, min(0.99, outer_clamp))
    if oc > 0.0:
        # Stretch (0, 1-oc) → (0, 1); anything above pegs to 1.
        mag = mag / (1.0 - oc)
        if mag > 1.0:
            mag = 1.0

    mag = apply_curve(mag, curve, curve_amount)
    return sign * mag


def apply_polar(
    x_value: float,
    y_value: float,
    deadzone: float = 0.05,
) -> Tuple[float, float]:
    """Convert a stick X/Y pair into (angle, magnitude) both in 0..1.

    - `angle` runs 0..1 around a full circle (0 = +X cardinal, advancing
      counter-clockwise in standard math convention). Wraps modulo 1 so
      a CC mapped to this scrolls smoothly through the value space as the
      user rotates the stick.
    - `magnitude` is the distance from centre, 0..1, with the deadzone
      already applied. While the stick is inside the deadzone, magnitude
      is 0 and angle holds its last position (a flat 0.5 here so the CC
      doesn't snap when the user lets go).

    Useful for "rotate filter / panning" controls where the user thinks in
    terms of "spin the stick" rather than "push left then up".
    """
    import math
    mag = math.sqrt(x_value * x_value + y_value * y_value)
    dz = max(0.0, min(0.99, deadzone))
    if mag < dz:
        return (0.5, 0.0)
    # Re-stretch magnitude past the deadzone, clamp at 1.
    mag = min(1.0, (mag - dz) / (1.0 - dz))
    angle = math.atan2(y_value, x_value)  # -π..π
    # Normalise to 0..1, advancing counter-clockwise from +X.
    angle_normalised = (angle / (2.0 * math.pi)) % 1.0
    return (angle_normalised, mag)


def apply_touchpad_axis(
    raw_normalised: float,
    *,
    mode: str = "absolute",
    inner_deadzone: float = 0.0,
    curve: str = "linear",
    curve_amount: float = 0.5,
    prev_value: float = 0.5,
) -> float:
    """Shape one touchpad axis (X or Y), returning a 0..1 output.

    - `mode="absolute"`: finger position IS the CC value (default behaviour).
    - `mode="relative"`: finger MOVEMENT adjusts the value smoothly without
      snapping back to where the finger lands. The caller supplies the
      previous output via `prev_value` and we return the new value.

    Curve + deadzone apply independently per axis so X and Y can be shaped
    differently (e.g. linear pitch on X, exponential filter sweep on Y).
    """
    v = max(0.0, min(1.0, raw_normalised))

    if mode == "relative":
        # Relative mode: the raw value is treated as a delta from 0.5 (the
        # touchpad centre). Each tick we nudge prev_value by that delta.
        # Scale chosen empirically so a full-finger swipe moves ~30% of CC range.
        delta = (v - 0.5) * 0.03
        return max(0.0, min(1.0, prev_value + delta))

    # Absolute mode below.
    dz = max(0.0, min(0.49, inner_deadzone))
    if dz > 0.0:
        # Deadzone is centred on 0.5 — within ±dz of centre snaps to centre.
        if abs(v - 0.5) < dz:
            return 0.5
        # Re-stretch the outer region so we keep full 0..1 range.
        if v >= 0.5:
            v = 0.5 + (v - 0.5 - dz) / (0.5 - dz) * 0.5
        else:
            v = 0.5 - (0.5 - v - dz) / (0.5 - dz) * 0.5
        v = max(0.0, min(1.0, v))

    return apply_curve(v, curve, curve_amount)


def apply_trigger_crossfade(pressure_0_1: float, curve: float = 1.0) -> Tuple[int, int]:
    """Compute two opposing CC values from a single trigger pressure.

    When enabled, a trigger can drive two CCs in opposition: as pressure rises,
    cc_a_value goes 0→127 and cc_b_value goes 127→0. This enables single-trigger
    crossfading between two filter cutoffs, dry/wet balances, effect sends, etc.

    Args:
        pressure_0_1: normalised trigger pressure, typically 0..1 from
                      normalise_trigger_pressure().
        curve: response curve (0.1..4.0, default 1.0). 1.0 = linear,
               0.5 = log-ish ease-in (biases high initially), 2.0 = exponential
               (biases low initially). Clamped to valid range on input.

    Returns:
        Tuple of (cc_a_value, cc_b_value) both in 0..127 ready for MIDI.
        At pressure=0: (0, 127). At pressure=1: (127, 0). At pressure=0.5 with
        linear curve: (~64, ~63).
    """
    # Clamp inputs to safe ranges
    p = max(0.0, min(1.0, pressure_0_1))
    c = max(0.1, min(4.0, curve))

    # Apply curve: cc_a_value = round(p^curve * 127)
    # Higher curve values push output toward low (exponential),
    # lower values push toward high (logarithmic).
    if c == 1.0:
        # Linear: no power transform needed
        cc_a_value = int(round(p * 127.0))
    else:
        # Power curve
        cc_a_value = int(round((p ** c) * 127.0))

    # Clamp just in case rounding produced an edge case
    cc_a_value = max(0, min(127, cc_a_value))

    # cc_b_value is the inverse: 127 - cc_a_value
    cc_b_value = 127 - cc_a_value

    return (cc_a_value, cc_b_value)
