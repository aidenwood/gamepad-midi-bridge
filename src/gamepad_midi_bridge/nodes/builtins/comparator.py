"""Comparator — output True iff input op threshold.

Wire-eligible scalar → bool transform. Pair to gate downstream effects
on threshold crossings ("CC > 64", "stick magnitude < 0.1").
"""
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
    threshold = float(params.get("threshold", 0.5))
    op = str(params.get("op", ">"))
    if op == ">":   res = v > threshold
    elif op == ">=": res = v >= threshold
    elif op == "<":  res = v < threshold
    elif op == "<=": res = v <= threshold
    elif op == "==": res = abs(v - threshold) < 1e-6
    elif op == "!=": res = abs(v - threshold) >= 1e-6
    else:           res = False
    return {"out": res}


SPEC = NodeSpec(
    kind="comparator",
    label="Comparator",
    category="logic",
    description=(
        "Compare a scalar input to a threshold. Output is True when the "
        "comparison holds. Useful to drive a downstream gate from an "
        "analog value — e.g. fire a sample only when the stick magnitude "
        "passes 0.85."
    ),
    short_description="Scalar → bool by comparison.",
    params=(
        ParamSpec(
            name="op", kind="choice", default=">",
            description="Comparison operator.",
            choices=(">", ">=", "<", "<=", "==", "!="),
        ),
        ParamSpec(
            name="threshold", kind="float", default=0.5,
            description="Value to compare against.",
            minimum=-127.0, maximum=127.0,
        ),
    ),
    inputs=(PinSpec("in", "in", "Scalar input.", expected="scalar"),),
    outputs=(PinSpec("out", "out", "True iff comparison holds.", expected="bool"),),
    wire_eligible=True,
    apply=_apply,
)

NODES = [SPEC]
