"""XyQuadrant — emit 0..3 quadrant of a stick vec2.

Useful for hard 4-direction switching: each quadrant lights up a
different downstream destination. Mapping: 0 = +X+Y, 1 = -X+Y, 2 = -X-Y,
3 = +X-Y. Below ``threshold`` magnitude, returns -1 with active=False.
"""
from __future__ import annotations

import math
from typing import Any, Dict

from ..model import NodeSpec, ParamSpec, PinSpec, PinValue


def _apply(params: Dict[str, Any], inputs: Dict[str, PinValue], state=None) -> Dict[str, PinValue]:
    xy = inputs.get("in")
    if not isinstance(xy, tuple) or len(xy) != 2:
        return {"quadrant": -1.0, "active": False}
    x, y = float(xy[0]), float(xy[1])
    threshold = float(params.get("threshold", 0.3))
    mag = math.hypot(x, y)
    if mag < threshold:
        return {"quadrant": -1.0, "active": False}
    if x >= 0 and y >= 0:   q = 0
    elif x < 0 and y >= 0:  q = 1
    elif x < 0 and y < 0:   q = 2
    else:                    q = 3
    return {"quadrant": float(q), "active": True}


SPEC = NodeSpec(
    kind="xy_quadrant",
    label="XY Quadrant",
    category="spatial",
    description=(
        "Emit the quadrant index (0..3) of an XY stick input — coarser "
        "than radial_sector but more readable when you only need 4 "
        "directions. 0 = upper-right, 1 = upper-left, 2 = lower-left, "
        "3 = lower-right. Returns -1 when magnitude is below threshold."
    ),
    short_description="Stick vec2 → quadrant 0..3.",
    params=(
        ParamSpec("threshold", "float", 0.3,
                  "Magnitude below which no quadrant fires (output = -1).",
                  minimum=0.0, maximum=1.0),
    ),
    inputs=(PinSpec("in", "in", "vec2 stick input.", expected="vec2"),),
    outputs=(
        PinSpec("quadrant", "out", "Quadrant index 0..3, or -1.", expected="scalar"),
        PinSpec("active", "out", "True iff magnitude past threshold.", expected="bool"),
    ),
    wire_eligible=False,
    apply=_apply,
)

NODES = [SPEC]
