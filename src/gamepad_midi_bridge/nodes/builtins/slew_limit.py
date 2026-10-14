"""SlewLimit — cap the maximum rate of change per tick.

Different feel than smooth_lerp: instead of exponentially approaching the
target, the output moves by AT MOST ``max_delta`` per tick toward the
input. Result is a linear ramp rather than an asymptote. Good for VJ
work where you want predictable per-frame motion not exponential decay.
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
    if state is None:
        state = {}
    max_delta = max(0.0, float(params.get("max_delta", 0.05)))
    prev = state.get("out_prev")
    if prev is None:
        prev = v
    delta = v - prev
    if delta > max_delta:
        out = prev + max_delta
    elif delta < -max_delta:
        out = prev - max_delta
    else:
        out = v
    state["out_prev"] = out
    return {"out": out}


SPEC = NodeSpec(
    kind="slew_limit",
    label="Slew Limit",
    category="shape",
    description=(
        "Cap the absolute change per tick. The output catches up to the "
        "input via a linear ramp rather than an exponential curve. Use "
        "when you want predictable timing (e.g. fade up to full over 0.5s "
        "regardless of starting position) rather than smoothing feel."
    ),
    short_description="Max rate of change per tick.",
    params=(
        ParamSpec(
            name="max_delta", kind="float", default=0.05,
            description=(
                "Maximum absolute change per tick. Bridge default is 100 Hz "
                "so 0.05 = full 0..1 sweep in ~200 ms / 0.01 = ~1 s."
            ),
            minimum=0.0001, maximum=1.0,
        ),
    ),
    inputs=(PinSpec("in", "in", "Scalar to slew-limit.", expected="scalar"),),
    outputs=(PinSpec("out", "out", "Slew-limited scalar.", expected="scalar"),),
    wire_eligible=True,
    apply=_apply,
)

NODES = [SPEC]
