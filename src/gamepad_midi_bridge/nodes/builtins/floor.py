"""Floor — round a scalar down to the nearest integer."""
from __future__ import annotations

import math
from typing import Any, Dict

from ..model import NodeSpec, PinSpec, PinValue


def _apply(params: Dict[str, Any], inputs: Dict[str, PinValue], state=None) -> Dict[str, PinValue]:
    raw = inputs.get("in")
    if raw is None or isinstance(raw, tuple):
        return {"out": raw}
    try:
        return {"out": float(math.floor(float(raw)))}
    except (TypeError, ValueError):
        return {"out": raw}


SPEC = NodeSpec(
    kind="floor",
    label="Floor (round down)",
    category="shape",
    description=(
        "Drop fractional bits — `out = floor(input)`. Useful when the "
        "destination is a discrete index (MIDI note number, channel "
        "selector) and the upstream is continuous."
    ),
    short_description="Round toward -∞.",
    inputs=(PinSpec("in", "in", "Scalar input.", expected="scalar"),),
    outputs=(PinSpec("out", "out", "Floored integer (as float).", expected="scalar"),),
    wire_eligible=True,
    apply=_apply,
)

NODES = [SPEC]
