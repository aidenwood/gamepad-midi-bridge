"""Bias — single-knob asymmetric curve. Schlick's bias function.

``out = x / ((1/b - 2)(1 - x) + 1)``. With b=0.5 it's identity. b<0.5
pushes the curve down (slow start, fast finish). b>0.5 pushes it up
(fast start, slow finish). Single intuitive knob; great wire-mode
shaper when you don't want to pick from a shape menu.
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
    sign = -1.0 if v < 0 else 1.0
    x = abs(v)
    x = min(1.0, x)
    b = max(0.001, min(0.999, float(params.get("bias", 0.5))))
    # Schlick's bias — fast + numerically stable.
    out = x / ((1.0 / b - 2.0) * (1.0 - x) + 1.0)
    return {"out": sign * out}


SPEC = NodeSpec(
    kind="bias",
    label="Bias (Schlick)",
    category="shape",
    description=(
        "Asymmetric curve shaper with a single knob. b=0.5 is identity. "
        "Below 0.5: slow start, fast finish (compresses the low end). "
        "Above 0.5: fast start, slow finish (compresses the high end). "
        "Cheaper + numerically stable alternative to power_curve when "
        "you want a single intuitive 'curve shape' control."
    ),
    short_description="Schlick's asymmetric bias.",
    params=(
        ParamSpec("bias", "float", 0.5,
                  "0..1 knob. <0.5 = slow start, >0.5 = fast start, =0.5 = passthrough.",
                  minimum=0.001, maximum=0.999),
    ),
    inputs=(PinSpec("in", "in", "Scalar input (sign preserved).", expected="scalar"),),
    outputs=(PinSpec("out", "out", "Bias-shaped scalar.", expected="scalar"),),
    wire_eligible=True,
    apply=_apply,
)

NODES = [SPEC]
