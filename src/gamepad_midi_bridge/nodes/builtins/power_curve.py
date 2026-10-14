"""PowerCurve — generic power-law curve, y = sign(x) * |x|^k.

Sign-preserving so bipolar (-1..1) stick inputs curve symmetrically.
Distinct from the existing ``curve`` node (which is a multi-shape
dispatcher); this one is a single, tight power knob — pair on the wire
when all you need is "make the response more punchy" without picking
from a shape menu.
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
    k = max(0.01, float(params.get("k", 2.0)))
    sign = -1.0 if v < 0 else 1.0
    return {"out": sign * (abs(v) ** k)}


SPEC = NodeSpec(
    kind="power_curve",
    label="Power Curve",
    category="shape",
    description=(
        "Single-knob power curve: `y = sign(x) * |x|^k`. k>1 compresses "
        "the low end (precision near rest), k<1 expands it (sensitive). "
        "Sign-preserving so bipolar sticks curve symmetrically. Lighter "
        "than the multi-shape Curve node — drop on a wire for a quick "
        "feel adjustment."
    ),
    short_description="y = sign(x) · |x|^k.",
    params=(
        ParamSpec(
            name="k", kind="float", default=2.0,
            description="Power exponent. 2.0 = compress low end; 0.5 = expand low end.",
            minimum=0.1, maximum=8.0,
        ),
    ),
    inputs=(PinSpec("in", "in", "Scalar input.", expected="scalar"),),
    outputs=(PinSpec("out", "out", "Power-shaped scalar with sign preserved.", expected="scalar"),),
    wire_eligible=True,
    apply=_apply,
)

NODES = [SPEC]
