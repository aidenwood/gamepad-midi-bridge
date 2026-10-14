"""AddOffset — y = x + offset.

Wire-eligible micro-transform. Mirrors TouchDesigner's Math CHOP in its
simplest "Add" preset.
"""
from __future__ import annotations

from typing import Any, Dict

from ..model import NodeSpec, ParamSpec, PinSpec, PinValue


def _apply(params: Dict[str, Any], inputs: Dict[str, PinValue], state=None) -> Dict[str, PinValue]:
    raw = inputs.get("in")
    if raw is None or isinstance(raw, tuple):
        return {"out": raw}
    try:
        return {"out": float(raw) + float(params.get("offset", 0.0))}
    except (TypeError, ValueError):
        return {"out": raw}


SPEC = NodeSpec(
    kind="add_offset",
    label="Add Offset",
    category="shape",
    description=(
        "Add a constant offset to the input. Useful for nudging a CC into "
        "a target range (e.g. shift a -1..1 stick into 0..2 before further "
        "shaping) or biasing a button trigger value."
    ),
    short_description="y = x + offset.",
    params=(
        ParamSpec(
            name="offset", kind="float", default=0.0,
            description="Value added to the input. Can be negative.",
            minimum=-127.0, maximum=127.0,
        ),
    ),
    inputs=(PinSpec("in", "in", "Scalar input.", expected="scalar"),),
    outputs=(PinSpec("out", "out", "Input + offset.", expected="scalar"),),
    wire_eligible=True,
    apply=_apply,
)

NODES = [SPEC]
