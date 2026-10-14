"""MomentaryInverse — output is True UNLESS the button is held.

Stateless flip of a boolean. The same shape as a "release detector":
fires when nothing is pressed, blocks while a key is held. Pair with
chord_detect to fire on the release edge of a chord (start a fade when
you let go of the active layer modifier).
"""
from __future__ import annotations

from typing import Any, Dict

from ..model import NodeSpec, PinSpec, PinValue


def _apply(params: Dict[str, Any], inputs: Dict[str, PinValue], state=None) -> Dict[str, PinValue]:
    pressed = bool(inputs.get("in"))
    return {"out": not pressed}


SPEC = NodeSpec(
    kind="momentary_inverse",
    label="Momentary Inverse",
    category="gate",
    description=(
        "True UNLESS the button is held. Inverts the natural sense of a "
        "controller button — useful when you want 'release to trigger' "
        "or 'gate the effect WHILE the controller is in pocket'. The "
        "inverse of the usual momentary-fire pattern."
    ),
    short_description="True when input is False.",
    inputs=(PinSpec("in", "in", "Boolean input.", expected="bool"),),
    outputs=(PinSpec("out", "out", "not(input).", expected="bool"),),
    wire_eligible=True,
    apply=_apply,
)

NODES = [SPEC]
