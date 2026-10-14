"""Mux2 — pick between two scalar inputs based on a bool selector.

Pattern: route stick movements to one destination when held, another
when not. Selector false → emits `a`, selector true → emits `b`. Useful
for "shift layer"-style mode switching at the wire level.
"""
from __future__ import annotations

from typing import Any, Dict

from ..model import NodeSpec, PinSpec, PinValue


def _apply(params: Dict[str, Any], inputs: Dict[str, PinValue], state=None) -> Dict[str, PinValue]:
    select = bool(inputs.get("select"))
    return {"out": inputs.get("b") if select else inputs.get("a")}


SPEC = NodeSpec(
    kind="mux_2",
    label="Mux (2-to-1)",
    category="logic",
    description=(
        "Route one of two inputs to the output based on a boolean "
        "selector. select=False emits `a`, select=True emits `b`. Lets "
        "you swap which source feeds a downstream destination mid-"
        "performance without rewiring."
    ),
    short_description="Pick a or b based on select.",
    inputs=(
        PinSpec("a", "in", "Selected when `select` is False.", expected="scalar"),
        PinSpec("b", "in", "Selected when `select` is True.", expected="scalar"),
        PinSpec("select", "in", "Boolean selector.", expected="bool"),
    ),
    outputs=(PinSpec("out", "out", "One of a or b.", expected="scalar"),),
    wire_eligible=False,
    apply=_apply,
)

NODES = [SPEC]
