"""Vec2Scale — multiply each axis of a vec2 by an independent gain.

Lets you stretch / squash a stick's coordinate system without rotating.
``scale_x = 0.5`` halves horizontal sensitivity while leaving vertical
intact — handy when one axis lands on a destination that wants a
narrower range.
"""
from __future__ import annotations

from typing import Any, Dict

from ..model import NodeSpec, ParamSpec, PinSpec, PinValue


def _apply(params: Dict[str, Any], inputs: Dict[str, PinValue], state=None) -> Dict[str, PinValue]:
    xy = inputs.get("in")
    if not isinstance(xy, tuple) or len(xy) != 2:
        return {"out": xy}
    sx = float(params.get("scale_x", 1.0))
    sy = float(params.get("scale_y", 1.0))
    return {"out": (float(xy[0]) * sx, float(xy[1]) * sy)}


SPEC = NodeSpec(
    kind="vec2_scale",
    label="Vec2 Scale",
    category="spatial",
    description=(
        "Independent gain on each axis of a vec2. Stretch or squash a "
        "stick's coordinate space — e.g. half horizontal sensitivity "
        "(scale_x=0.5) while vertical stays at full range. Negative "
        "scales flip the axis."
    ),
    short_description="Per-axis gain on a vec2.",
    params=(
        ParamSpec("scale_x", "float", 1.0,
                  "Multiplier on the X axis. Negative flips left/right.",
                  minimum=-4.0, maximum=4.0),
        ParamSpec("scale_y", "float", 1.0,
                  "Multiplier on the Y axis. Negative flips up/down.",
                  minimum=-4.0, maximum=4.0),
    ),
    inputs=(PinSpec("in", "in", "vec2 stick input.", expected="vec2"),),
    outputs=(PinSpec("out", "out", "Scaled vec2.", expected="vec2"),),
    wire_eligible=True,
    apply=_apply,
)

NODES = [SPEC]
