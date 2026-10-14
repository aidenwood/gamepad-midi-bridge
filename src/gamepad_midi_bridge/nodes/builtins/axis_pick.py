"""AxisPick — collapse a 2D stick input down to one of its axes.

Wire-eligible: tiny, 1-in / 1-out, no state. Lives well on a Connection's
circular ⚙ menu without needing a full node card on the canvas.
"""
from __future__ import annotations

from typing import Any, Dict

from ..model import NodeSpec, ParamSpec, PinSpec, PinValue


def _apply(params: Dict[str, Any], inputs: Dict[str, PinValue], state=None) -> Dict[str, PinValue]:
    xy = inputs.get("in")
    axis = params.get("axis", "x")
    if not isinstance(xy, tuple) or len(xy) != 2:
        # Already 1D? Pass through unchanged so this node is safe to drop
        # on a wire that turned out not to carry vec2.
        return {"out": xy}
    return {"out": float(xy[0]) if axis == "x" else float(xy[1])}


SPEC = NodeSpec(
    kind="axis_pick",
    label="Axis Pick (XY → single axis)",
    category="spatial",
    description=(
        "Pick one axis of a 2D stick input and drop the other. Use when a "
        "destination only cares about left/right (or up/down) — e.g. you want "
        "L-stick X driving a crossfader but L-stick Y staying free for "
        "something else later."
    ),
    short_description="Keep only X or Y from a stick.",
    params=(
        ParamSpec(
            name="axis",
            kind="choice",
            default="x",
            description="Which axis to keep. `x` = left/right, `y` = up/down.",
            choices=("x", "y"),
        ),
    ),
    inputs=(PinSpec("in", "in", "vec2 stick input.", expected="vec2"),),
    outputs=(PinSpec("out", "out", "Selected axis as a scalar -1..1.", expected="scalar"),),
    wire_eligible=True,
    apply=_apply,
)

NODES = [SPEC]
