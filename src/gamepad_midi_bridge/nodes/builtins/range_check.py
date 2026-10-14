"""RangeCheck — output True iff input is within [min..max] inclusive."""
from __future__ import annotations

from typing import Any, Dict

from ..model import NodeSpec, ParamSpec, PinSpec, PinValue


def _apply(params: Dict[str, Any], inputs: Dict[str, PinValue], state=None) -> Dict[str, PinValue]:
    raw = inputs.get("in")
    if raw is None or isinstance(raw, tuple):
        return {"out": False}
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return {"out": False}
    lo = float(params.get("min", 0.0))
    hi = float(params.get("max", 1.0))
    if lo > hi:
        lo, hi = hi, lo
    return {"out": lo <= v <= hi}


SPEC = NodeSpec(
    kind="range_check",
    label="Range Check",
    category="logic",
    description=(
        "Output True iff the input scalar falls within [min..max]. Two-"
        "sided variant of comparator. Use to drive a gate when a CC is "
        "in a specific band — e.g. fire only when velocity is between "
        "64 and 100."
    ),
    short_description="True iff min ≤ input ≤ max.",
    params=(
        ParamSpec("min", "float", 0.0,
                  "Lower bound (inclusive).", minimum=-127.0, maximum=127.0),
        ParamSpec("max", "float", 1.0,
                  "Upper bound (inclusive).", minimum=-127.0, maximum=127.0),
    ),
    inputs=(PinSpec("in", "in", "Scalar input.", expected="scalar"),),
    outputs=(PinSpec("out", "out", "True iff in range.", expected="bool"),),
    wire_eligible=True,
    apply=_apply,
)

NODES = [SPEC]
