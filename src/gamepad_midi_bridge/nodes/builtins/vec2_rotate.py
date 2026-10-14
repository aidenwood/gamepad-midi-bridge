"""Vec2Rotate — rotate a 2D input by an angle in degrees."""
from __future__ import annotations

import math
from typing import Any, Dict

from ..model import NodeSpec, ParamSpec, PinSpec, PinValue


def _apply(params: Dict[str, Any], inputs: Dict[str, PinValue], state=None) -> Dict[str, PinValue]:
    xy = inputs.get("in")
    if not isinstance(xy, tuple) or len(xy) != 2:
        return {"out": xy}
    x, y = float(xy[0]), float(xy[1])
    angle = math.radians(float(params.get("degrees", 0.0)))
    c, s = math.cos(angle), math.sin(angle)
    return {"out": (c * x - s * y, s * x + c * y)}


SPEC = NodeSpec(
    kind="vec2_rotate",
    label="Vec2 Rotate",
    category="spatial",
    description=(
        "Rotate a stick input by `degrees` around the origin. 90° turns "
        "horizontal stick motion into vertical without manually swapping "
        "axes. Useful when a controller is held at an angle on a stand "
        "and you want the mapping to feel correct."
    ),
    short_description="Rotate (x, y) by N degrees.",
    params=(
        ParamSpec(
            name="degrees", kind="float", default=0.0,
            description="Rotation angle. Positive = counter-clockwise.",
            minimum=-360.0, maximum=360.0, unit="°",
        ),
    ),
    inputs=(PinSpec("in", "in", "vec2 stick input.", expected="vec2"),),
    outputs=(PinSpec("out", "out", "Rotated vec2.", expected="vec2"),),
    wire_eligible=True,
    apply=_apply,
)

NODES = [SPEC]
