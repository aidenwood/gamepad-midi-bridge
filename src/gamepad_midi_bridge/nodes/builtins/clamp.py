"""Clamp — hard cap a scalar between min and max.

Wire-eligible. Stateless. Anything below `min` becomes `min`; anything
above `max` becomes `max`. Tuples pass through unchanged (clamp doesn't
make sense for a 2D stick value — the user should use range_remap or a
per-axis approach instead).
"""
from __future__ import annotations

from typing import Any, Dict

from ..model import NodeSpec, ParamSpec, PinSpec, PinValue


def _apply(params: Dict[str, Any], inputs: Dict[str, PinValue], state=None) -> Dict[str, PinValue]:
    raw = inputs.get("in")
    if raw is None or isinstance(raw, tuple):
        return {"out": raw}
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return {"out": raw}
    lo = float(params.get("min", 0.0))
    hi = float(params.get("max", 1.0))
    if lo > hi:  # user mis-typed — be tolerant
        lo, hi = hi, lo
    return {"out": max(lo, min(hi, v))}


SPEC = NodeSpec(
    kind="clamp",
    label="Clamp",
    category="shape",
    description=(
        "Hard cap a scalar between `min` and `max`. Below `min` outputs "
        "`min`, above `max` outputs `max`, everything in between passes "
        "through. The order of min/max is forgiven if you swap them by "
        "mistake. Useful as a wire-mode safety net before sending into a "
        "destination that misbehaves at extreme values."
    ),
    short_description="Hard floor + ceiling on a scalar.",
    params=(
        ParamSpec(
            name="min", kind="float", default=0.0,
            description="Lower cap. Values below this are pinned here.",
            minimum=-1.0, maximum=127.0,
        ),
        ParamSpec(
            name="max", kind="float", default=1.0,
            description="Upper cap. Values above this are pinned here.",
            minimum=-1.0, maximum=127.0,
        ),
    ),
    inputs=(PinSpec("in", "in", "Scalar input.", expected="scalar"),),
    outputs=(PinSpec("out", "out", "Clamped scalar.", expected="scalar"),),
    wire_eligible=True,
    apply=_apply,
)

NODES = [SPEC]
