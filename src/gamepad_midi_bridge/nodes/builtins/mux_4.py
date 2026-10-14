"""Mux4 — pick one of four inputs based on an integer-valued selector.

Selector floor()'d to int and clamped to 0..3. Pair with the counter
node to cycle through 4 sources per button press, or with a quadrant
indicator to swap routing based on stick direction.
"""
from __future__ import annotations

from typing import Any, Dict

from ..model import NodeSpec, PinSpec, PinValue


def _apply(params: Dict[str, Any], inputs: Dict[str, PinValue], state=None) -> Dict[str, PinValue]:
    sel_raw = inputs.get("select")
    try:
        sel = int(float(sel_raw)) if sel_raw is not None else 0
    except (TypeError, ValueError):
        sel = 0
    sel = max(0, min(3, sel))
    key = f"in{sel + 1}"
    return {"out": inputs.get(key)}


SPEC = NodeSpec(
    kind="mux_4",
    label="Mux (4-to-1)",
    category="logic",
    description=(
        "Pick one of four inputs by integer selector (0..3). Pair with "
        "counter to step through 4 sources per button press, or with "
        "xy_quadrant for stick-direction routing."
    ),
    short_description="Select in1..in4 by 0..3 selector.",
    inputs=(
        PinSpec("in1", "in", "Selected when select=0.", expected="scalar"),
        PinSpec("in2", "in", "Selected when select=1.", expected="scalar"),
        PinSpec("in3", "in", "Selected when select=2.", expected="scalar"),
        PinSpec("in4", "in", "Selected when select=3.", expected="scalar"),
        PinSpec("select", "in", "Integer index 0..3.", expected="scalar"),
    ),
    outputs=(PinSpec("out", "out", "Selected input.", expected="scalar"),),
    wire_eligible=False,
    apply=_apply,
)

NODES = [SPEC]
