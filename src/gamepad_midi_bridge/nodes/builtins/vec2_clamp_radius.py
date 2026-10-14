"""Vec2ClampRadius — clamp a stick input's magnitude to a max radius.

Useful when you want a perfectly circular stick travel envelope — the
DualSense's stick can reach a corner that exceeds magnitude 1.0 (it's
square-gated mechanically). Clamping to 1.0 gives a circular range that
plays nicer with downstream polar conversion.
"""
from __future__ import annotations

import math
from typing import Any, Dict

from ..model import NodeSpec, ParamSpec, PinSpec, PinValue


def _apply(params: Dict[str, Any], inputs: Dict[str, PinValue], state=None) -> Dict[str, PinValue]:
    xy = inputs.get("in")
    if not isinstance(xy, tuple) or len(xy) != 2:
        return {"out": xy}
    x, y = float(xy[0]), float(xy[1])
    max_r = max(0.0, float(params.get("max_radius", 1.0)))
    mag = math.hypot(x, y)
    if mag <= max_r or mag == 0.0:
        return {"out": (x, y)}
    scale = max_r / mag
    return {"out": (x * scale, y * scale)}


SPEC = NodeSpec(
    kind="vec2_clamp_radius",
    label="Vec2 Clamp Radius",
    category="spatial",
    description=(
        "Project an XY stick value back onto a circle of radius "
        "`max_radius` if it goes outside. DualSense sticks can reach the "
        "corners (magnitude > 1.0); clamping to 1.0 gives a perfectly "
        "circular range that downstream polar conversion expects."
    ),
    short_description="Clamp |xy| to max_radius.",
    params=(
        ParamSpec(
            name="max_radius", kind="float", default=1.0,
            description="Maximum allowed magnitude. Inputs past this are scaled back to land on the circle.",
            minimum=0.01, maximum=2.0,
        ),
    ),
    inputs=(PinSpec("in", "in", "vec2 stick input.", expected="vec2"),),
    outputs=(PinSpec("out", "out", "Radius-clamped vec2.", expected="vec2"),),
    wire_eligible=True,
    apply=_apply,
)

NODES = [SPEC]
