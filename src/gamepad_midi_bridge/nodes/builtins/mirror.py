"""Mirror — fold the input back at a centre point.

For input ``x`` and centre ``c``: ``out = c + |x - c|`` when ``x >= c``,
else ``c + (c - x)``. Effectively reflects the lower half of the range
onto the upper half. Different from Absolute because the fold can pivot
on any value, not just zero.
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
    centre = float(params.get("centre", 0.5))
    return {"out": centre + abs(v - centre)}


SPEC = NodeSpec(
    kind="mirror",
    label="Mirror (fold)",
    category="shape",
    description=(
        "Fold the input back across a centre value — anything below `centre` "
        "mirrors to the same distance above it. With centre=0.5 on a 0..1 "
        "signal, 0.2 becomes 0.8, 0.0 becomes 1.0. Useful for symmetric "
        "control responses (sweep up either way to reach the same target)."
    ),
    short_description="Fold across a centre value.",
    params=(
        ParamSpec(
            name="centre", kind="float", default=0.5,
            description="Pivot point. Inputs below this fold up; inputs above passthrough.",
            minimum=-1.0, maximum=1.0,
        ),
    ),
    inputs=(PinSpec("in", "in", "Scalar input.", expected="scalar"),),
    outputs=(PinSpec("out", "out", "Folded scalar.", expected="scalar"),),
    wire_eligible=True,
    apply=_apply,
)

NODES = [SPEC]
