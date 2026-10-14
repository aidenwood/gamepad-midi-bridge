"""Toggle (Latch) — press to flip output state.

A press EDGE flips `out` between False ↔ True. Output stays latched until
the next press edge. Useful for "tap to turn on the effect, tap again to
turn it off" patches where the natural physical state (button held) isn't
the desired semantic state (effect on).

Stateful — needs to remember the press edge across ticks AND the current
latched output. Two keys in `state`:

    "prev_pressed": bool   — last tick's input
    "latched":      bool   — current output state, flipped on press edge
"""
from __future__ import annotations

from typing import Any, Dict

from ..model import NodeSpec, ParamSpec, PinSpec, PinValue


def _apply(params: Dict[str, Any], inputs: Dict[str, PinValue], state=None) -> Dict[str, PinValue]:
    pressed = bool(inputs.get("in"))
    if state is None:
        state = {}
    prev = state.get("prev_pressed", False)
    latched = state.get("latched", bool(params.get("start_on", False)))
    if pressed and not prev:
        # press edge — flip
        latched = not latched
    state["prev_pressed"] = pressed
    state["latched"] = latched
    return {"out": latched}


SPEC = NodeSpec(
    kind="toggle",
    label="Toggle (Latch)",
    category="gate",
    description=(
        "Flip the output between True ↔ False on every press EDGE. Output "
        "stays latched until the next press. Lets a momentary button drive "
        "a sustained effect — tap once to turn an effect on, tap again to "
        "turn it off. Inverse of the default momentary semantics."
    ),
    short_description="Press flips an on/off latch.",
    params=(
        ParamSpec(
            name="start_on",
            kind="bool",
            default=False,
            description=(
                "Initial latched state on app launch / preset load. False = "
                "off until the user presses; True = on until the user presses."
            ),
        ),
    ),
    inputs=(PinSpec("in", "in", "Button pressed state (bool).", expected="bool"),),
    outputs=(PinSpec("out", "out", "Latched bool — flips on each press edge.", expected="bool"),),
    wire_eligible=True,    # 1-in / 1-out — fine inline
    apply=_apply,
)

NODES = [SPEC]
