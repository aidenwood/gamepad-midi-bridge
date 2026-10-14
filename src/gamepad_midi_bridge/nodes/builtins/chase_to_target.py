"""ChaseToTarget — like smooth_lerp but with an explicit target input pin.

Two scalar inputs: ``current`` is the source value (e.g. an LFO output)
and ``target`` is where it should chase to. Output ramps from the last
output toward target at the configured rate. Essentially a per-tick
attractor.

Different from smooth_lerp because the target is variable per tick,
allowing one wire to drive what the other 'wants' to be.
"""
from __future__ import annotations

from typing import Any, Dict

from ..model import NodeSpec, ParamSpec, PinSpec, PinValue


def _apply(params: Dict[str, Any], inputs: Dict[str, PinValue], state=None) -> Dict[str, PinValue]:
    raw = inputs.get("target")
    if raw is None or isinstance(raw, tuple):
        return {"out": raw}
    try:
        target = float(raw)
    except (TypeError, ValueError):
        return {"out": raw}
    if state is None:
        state = {}
    alpha = max(0.001, min(1.0, float(params.get("alpha", 0.1))))
    prev = state.get("out_prev")
    if prev is None:
        prev = target
    out = prev + alpha * (target - prev)
    state["out_prev"] = out
    return {"out": out}


SPEC = NodeSpec(
    kind="chase_to_target",
    label="Chase to Target",
    category="modulator",
    description=(
        "Smoothly move the output toward an externally-supplied target "
        "value. Each tick, output advances `alpha` fraction of the way "
        "toward target. Like smooth_lerp but the target comes from "
        "another wire — useful when one signal drives what another "
        "should 'want to be' (e.g. stick magnitude as a target for an "
        "LFO's centre value)."
    ),
    short_description="Smoothly chase an external target value.",
    params=(
        ParamSpec("alpha", "float", 0.1,
                  "Fraction of the gap closed per tick. 1.0 = instant snap.",
                  minimum=0.001, maximum=1.0),
    ),
    inputs=(PinSpec("target", "in", "Target scalar to chase.", expected="scalar"),),
    outputs=(PinSpec("out", "out", "Output value approaching the target.", expected="scalar"),),
    wire_eligible=True,
    apply=_apply,
)

NODES = [SPEC]
