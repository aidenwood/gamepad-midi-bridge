"""Multiply — y = x * gain.

Wire-eligible scalar gain stage. Negative gain inverts.
"""
from __future__ import annotations

from typing import Any, Dict

from ..model import NodeSpec, ParamSpec, PinSpec, PinValue


def _apply(params: Dict[str, Any], inputs: Dict[str, PinValue], state=None) -> Dict[str, PinValue]:
    raw = inputs.get("in")
    if raw is None or isinstance(raw, tuple):
        return {"out": raw}
    try:
        return {"out": float(raw) * float(params.get("gain", 1.0))}
    except (TypeError, ValueError):
        return {"out": raw}


SPEC = NodeSpec(
    kind="multiply",
    label="Multiply (gain)",
    category="shape",
    description=(
        "Multiply the input by a constant gain. Negative gain flips sign. "
        "Common use: cut a stick's response in half (gain=0.5) before "
        "feeding into a sensitive parameter, or boost a slow LFO into a "
        "stronger modulation depth."
    ),
    short_description="y = x * gain.",
    params=(
        ParamSpec(
            name="gain", kind="float", default=1.0,
            description=(
                "Multiplier. 1.0 = passthrough, 0.5 = half scale, "
                "2.0 = double, -1.0 = invert. Range allows extreme "
                "scaling for chained Multiply * Multiply patches."
            ),
            minimum=-10.0, maximum=10.0,
        ),
    ),
    inputs=(PinSpec("in", "in", "Scalar input.", expected="scalar"),),
    outputs=(PinSpec("out", "out", "Input * gain.", expected="scalar"),),
    wire_eligible=True,
    apply=_apply,
)

NODES = [SPEC]
