"""ReleaseEdge — fire True for one tick on the FALLING edge of a bool.

Mirror of the press-edge convention. Use to trigger an event when a
button is released — e.g. play a sample on the lift instead of the
push, or end an effect when the user lets go of a modifier.
"""
from __future__ import annotations

from typing import Any, Dict

from ..model import NodeSpec, PinSpec, PinValue


def _apply(params: Dict[str, Any], inputs: Dict[str, PinValue], state=None) -> Dict[str, PinValue]:
    pressed = bool(inputs.get("in"))
    if state is None:
        state = {}
    prev = state.get("prev_pressed", False)
    fired = not pressed and prev
    state["prev_pressed"] = pressed
    return {"out": fired}


SPEC = NodeSpec(
    kind="release_edge",
    label="Release Edge",
    category="gate",
    description=(
        "Fire True for one tick on the FALLING edge of the input — the "
        "moment the button is released. Mirror of the press-edge "
        "convention. Pair with a downstream sink to play a sound on "
        "release rather than press."
    ),
    short_description="One-shot on button release.",
    inputs=(PinSpec("in", "in", "Button state (bool).", expected="bool"),),
    outputs=(PinSpec("out", "out", "True for one tick on each release.", expected="bool"),),
    wire_eligible=True,
    apply=_apply,
)

NODES = [SPEC]
