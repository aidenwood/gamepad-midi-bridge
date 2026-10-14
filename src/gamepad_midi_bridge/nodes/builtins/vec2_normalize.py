"""Vec2Normalize — scale a vec2 input so its magnitude is exactly 1.

Direction-only conversion. Zero-magnitude inputs return (0, 0) to avoid
divide-by-zero. Useful when you want the stick's direction to drive a
parameter independently of how hard it's pushed.
"""
from __future__ import annotations

import math
from typing import Any, Dict

from ..model import NodeSpec, PinSpec, PinValue


def _apply(params: Dict[str, Any], inputs: Dict[str, PinValue], state=None) -> Dict[str, PinValue]:
    xy = inputs.get("in")
    if not isinstance(xy, tuple) or len(xy) != 2:
        return {"out": xy}
    x, y = float(xy[0]), float(xy[1])
    mag = math.hypot(x, y)
    if mag < 1e-9:
        return {"out": (0.0, 0.0)}
    return {"out": (x / mag, y / mag)}


SPEC = NodeSpec(
    kind="vec2_normalize",
    label="Vec2 Normalize",
    category="spatial",
    description=(
        "Scale a vec2 so its magnitude is exactly 1. Direction-only "
        "output — the stick's angle drives the result, the amount it's "
        "pushed doesn't. Centre-position (0,0) safely returns (0,0) "
        "instead of NaN."
    ),
    short_description="Force |xy| = 1, keep direction.",
    inputs=(PinSpec("in", "in", "vec2 stick input.", expected="vec2"),),
    outputs=(PinSpec("out", "out", "Normalised unit-magnitude vec2.", expected="vec2"),),
    wire_eligible=True,
    apply=_apply,
)

NODES = [SPEC]
