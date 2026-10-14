"""Exponential — y = e^(k * x), normalised to fit in 0..1.

Useful for filter sweeps and ear-friendly perceptual ramps. A linear
0..1 input passes through `y = (e^(k*x) - 1) / (e^k - 1)` so the
output stays in 0..1 but the curve is exponential.
"""
from __future__ import annotations

import math
from typing import Any, Dict

from ..model import NodeSpec, ParamSpec, PinSpec, PinValue


def _apply(params: Dict[str, Any], inputs: Dict[str, PinValue], state=None) -> Dict[str, PinValue]:
    raw = inputs.get("in")
    if raw is None or isinstance(raw, tuple):
        return {"out": raw}
    try:
        x = float(raw)
    except (TypeError, ValueError):
        return {"out": raw}
    sign = -1.0 if x < 0 else 1.0
    x = min(1.0, abs(x))
    k = float(params.get("k", 4.0))
    if abs(k) < 1e-6:
        return {"out": sign * x}     # k=0 → identity
    denom = math.exp(k) - 1.0
    if denom == 0:
        return {"out": sign * x}
    y = (math.exp(k * x) - 1.0) / denom
    return {"out": sign * y}


SPEC = NodeSpec(
    kind="exponential",
    label="Exponential Curve",
    category="shape",
    description=(
        "Normalised exponential curve — input 0..1 maps to output 0..1 "
        "through `y = (e^(k·x) - 1) / (e^k - 1)`. Positive k accelerates "
        "the high end (ear-friendly filter sweep); negative k accelerates "
        "the low end. Sign-preserving for bipolar inputs."
    ),
    short_description="Normalised exponential curve.",
    params=(
        ParamSpec("k", "float", 4.0,
                  "Curvature. Positive = slow start; negative = fast start; 0 = linear.",
                  minimum=-8.0, maximum=8.0),
    ),
    inputs=(PinSpec("in", "in", "Scalar input.", expected="scalar"),),
    outputs=(PinSpec("out", "out", "Exponential-shaped scalar.", expected="scalar"),),
    wire_eligible=True,
    apply=_apply,
)

NODES = [SPEC]
