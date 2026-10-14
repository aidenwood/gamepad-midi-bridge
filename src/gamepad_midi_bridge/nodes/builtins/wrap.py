"""Wrap — modular wrap of the input into a 0..max range.

For input ``x`` and ``max``: ``out = x mod max``. Useful for continuous
modulation: a stick that drives a hue (0..1, wraps), or an LFO output
that accumulates and wraps to a phase value.
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
        v = float(raw)
    except (TypeError, ValueError):
        return {"out": raw}
    mx = max(0.0001, float(params.get("max", 1.0)))
    return {"out": math.fmod(v, mx) if v >= 0 else mx - math.fmod(-v, mx)}


SPEC = NodeSpec(
    kind="wrap",
    label="Wrap",
    category="shape",
    description=(
        "Modular wrap — `out = input mod max`. Stays cleanly within "
        "[0..max] regardless of how far the input drifts. Pair with an "
        "accumulator to drive a phase value (e.g. hue cycling) that "
        "never blows past its valid range."
    ),
    short_description="Modular wrap to 0..max.",
    params=(
        ParamSpec(
            name="max", kind="float", default=1.0,
            description="Wrap modulus. Output stays in [0..max).",
            minimum=0.001, maximum=127.0,
        ),
    ),
    inputs=(PinSpec("in", "in", "Scalar input.", expected="scalar"),),
    outputs=(PinSpec("out", "out", "Wrapped scalar in [0..max).", expected="scalar"),),
    wire_eligible=True,
    apply=_apply,
)

NODES = [SPEC]
