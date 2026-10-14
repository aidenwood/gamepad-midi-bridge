"""Ceil — round a scalar up to the nearest integer."""
from __future__ import annotations

import math
from typing import Any, Dict

from ..model import NodeSpec, PinSpec, PinValue


def _apply(params: Dict[str, Any], inputs: Dict[str, PinValue], state=None) -> Dict[str, PinValue]:
    raw = inputs.get("in")
    if raw is None or isinstance(raw, tuple):
        return {"out": raw}
    try:
        return {"out": float(math.ceil(float(raw)))}
    except (TypeError, ValueError):
        return {"out": raw}


SPEC = NodeSpec(
    kind="ceil",
    label="Ceil (round up)",
    category="shape",
    description=(
        "Round toward +∞ — `out = ceil(input)`. Mirror of floor. Use "
        "when partial values should always be promoted to the next "
        "integer slot."
    ),
    short_description="Round toward +∞.",
    inputs=(PinSpec("in", "in", "Scalar input.", expected="scalar"),),
    outputs=(PinSpec("out", "out", "Ceiling integer (as float).", expected="scalar"),),
    wire_eligible=True,
    apply=_apply,
)

NODES = [SPEC]
