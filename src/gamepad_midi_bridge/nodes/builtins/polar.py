"""Polar — convert a stick's (x, y) into (angle, magnitude).

Angle is normalised 0..1 (one full revolution = 0..1, increases clockwise
from the +X cardinal). Magnitude is the radial distance from centre, clamped
to 0..1. Useful for "this stick controls an effect's amount AND its colour"
patches — magnitude → amount, angle → hue.

Wraps the same maths as StickConfig.polar_mode so a Phase-1 graph produces
identical output to a Phase-0 polar-flag mapping. That's deliberate: when
schema migration lowers an old preset to a default graph, behaviour is
byte-identical.
"""
from __future__ import annotations

import math
from typing import Any, Dict, Tuple

from ..model import NodeSpec, PinSpec, PinValue


def _apply(params: Dict[str, Any], inputs: Dict[str, PinValue], state=None) -> Dict[str, PinValue]:
    xy = inputs.get("xy")
    if not isinstance(xy, tuple) or len(xy) != 2:
        return {"angle": 0.0, "magnitude": 0.0}
    x, y = float(xy[0]), float(xy[1])
    mag = min(1.0, math.hypot(x, y))
    if mag < 1e-6:
        # Centred — angle is undefined; emit 0 so downstream stays stable.
        angle = 0.0
    else:
        # atan2 returns -pi..pi. Normalise to 0..1, clockwise from +X.
        a = math.atan2(y, x)
        if a < 0:
            a += 2 * math.pi
        angle = a / (2 * math.pi)
    return {"angle": angle, "magnitude": mag}


SPEC = NodeSpec(
    kind="polar",
    label="Polar (XY → angle + magnitude)",
    category="spatial",
    description=(
        "Convert a stick's cartesian (x, y) input into two scalar outputs: "
        "`angle` (0..1, clockwise from the +X cardinal) and `magnitude` "
        "(0..1, distance from centre). Useful when one stick should drive "
        "two related parameters — e.g. effect intensity (magnitude) and "
        "effect colour (angle), or filter cutoff + resonance."
    ),
    short_description="2D stick → angle + magnitude.",
    inputs=(
        PinSpec("xy", "in", "Stick value, expects vec2 in -1..1 per axis.", expected="vec2"),
    ),
    outputs=(
        PinSpec("angle", "out", "0..1, one full revolution clockwise from +X.", expected="scalar"),
        PinSpec("magnitude", "out", "0..1, radial distance from centre.", expected="scalar"),
    ),
    wire_eligible=False,   # 2 outputs — too rich for a wire
    apply=_apply,
)

NODES = [SPEC]
