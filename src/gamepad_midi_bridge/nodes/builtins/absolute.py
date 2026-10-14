"""Absolute — y = |x|. Stick movement either direction → single positive value."""
from __future__ import annotations

from typing import Any, Dict

from ..model import NodeSpec, PinSpec, PinValue


def _apply(params: Dict[str, Any], inputs: Dict[str, PinValue], state=None) -> Dict[str, PinValue]:
    raw = inputs.get("in")
    if raw is None or isinstance(raw, tuple):
        return {"out": raw}
    try:
        return {"out": abs(float(raw))}
    except (TypeError, ValueError):
        return {"out": raw}


SPEC = NodeSpec(
    kind="absolute",
    label="Absolute",
    category="shape",
    description=(
        "Take the magnitude — `|x|`. Drops the sign so a bipolar stick "
        "(-1..1) folds into a 0..1 value where pushing in EITHER direction "
        "ramps the parameter up. Use when 'how far is the stick from "
        "centre' matters more than which way."
    ),
    short_description="y = |x|.",
    inputs=(PinSpec("in", "in", "Scalar input.", expected="scalar"),),
    outputs=(PinSpec("out", "out", "|input|.", expected="scalar"),),
    wire_eligible=True,
    apply=_apply,
)

NODES = [SPEC]
