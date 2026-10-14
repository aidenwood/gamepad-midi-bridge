"""EdgeGate — fire only when a stick reaches the outer ring.

Wire-eligible: 1-in / 1-out scalar. The wire's "value" carries the stick's
magnitude (or any axis already collapsed by an upstream node); EdgeGate
returns the value as-is when magnitude ≥ threshold, otherwise 0.

Common use: trigger a sample / send a note only when the user pushes the
stick all the way out — not during exploratory wiggle. Pair with an
upstream Polar node feeding `magnitude` into EdgeGate, then route to a
button-style destination.
"""
from __future__ import annotations

from typing import Any, Dict

from ..model import NodeSpec, ParamSpec, PinSpec, PinValue


def _apply(params: Dict[str, Any], inputs: Dict[str, PinValue], state=None) -> Dict[str, PinValue]:
    v = inputs.get("in")
    threshold = float(params.get("threshold", 0.9))
    if v is None:
        return {"out": 0.0}
    # If we got a vec2, use its magnitude — convenience for direct stick → edge_gate
    # without an intermediate axis-pick or polar node.
    if isinstance(v, tuple) and len(v) == 2:
        magnitude = (float(v[0]) ** 2 + float(v[1]) ** 2) ** 0.5
        return {"out": magnitude if magnitude >= threshold else 0.0}
    val = float(v)
    return {"out": val if abs(val) >= threshold else 0.0}


SPEC = NodeSpec(
    kind="edge_gate",
    label="Edge Gate (only outer ring)",
    category="gate",
    description=(
        "Pass the input through only when its magnitude reaches the outer "
        "edge of the stick (or for scalars: when the absolute value is past "
        "the threshold). Below the threshold, output is zero. Useful for "
        "trigger-style sticks: push all the way to fire, exploratory wiggle "
        "in the middle stays silent."
    ),
    short_description="Only fires when the stick reaches the outer ring.",
    params=(
        ParamSpec(
            name="threshold",
            kind="float",
            default=0.9,
            description=(
                "Magnitude required to open the gate. 1.0 = exactly the outer "
                "ring; 0.8 = a comfortable rim. Lower this if your stick has "
                "drifted and can no longer reach 1.0."
            ),
            minimum=0.0,
            maximum=1.0,
        ),
    ),
    inputs=(PinSpec("in", "in", "Scalar (or vec2 magnitude) from upstream.", expected="scalar"),),
    outputs=(PinSpec("out", "out", "Value when past threshold, else 0.", expected="scalar"),),
    wire_eligible=True,
    apply=_apply,
)

NODES = [SPEC]
