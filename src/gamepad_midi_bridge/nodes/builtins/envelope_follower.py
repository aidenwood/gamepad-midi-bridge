"""EnvelopeFollower — track the peak of an input with separate attack /
release rates.

Output rises fast (attack) when the input value increases and falls slow
(release) when the input decreases. Mirrors a classic audio envelope
follower. Useful for taking a noisy "amplitude" signal (stick magnitude,
sample-and-hold output) and turning it into a smooth amount-meter for a
downstream effect.
"""
from __future__ import annotations

from typing import Any, Dict

from ..model import NodeSpec, ParamSpec, PinSpec, PinValue


def _apply(params: Dict[str, Any], inputs: Dict[str, PinValue], state=None) -> Dict[str, PinValue]:
    raw = inputs.get("in")
    if raw is None or isinstance(raw, tuple):
        return {"out": raw}
    try:
        v = abs(float(raw))   # envelope follows magnitude
    except (TypeError, ValueError):
        return {"out": raw}
    if state is None:
        state = {}
    attack = max(0.001, min(1.0, float(params.get("attack", 0.5))))
    release = max(0.001, min(1.0, float(params.get("release", 0.05))))
    prev = state.get("out_prev", 0.0)
    rate = attack if v > prev else release
    out = prev + rate * (v - prev)
    state["out_prev"] = out
    return {"out": out}


SPEC = NodeSpec(
    kind="envelope_follower",
    label="Envelope Follower",
    category="modulator",
    description=(
        "Track the magnitude of an input with separate rates for rising "
        "and falling. Fast attack snaps to peaks; slow release lets the "
        "output decay smoothly. Classic 'amount-of-motion' meter — drives "
        "an effect amount that fades out when you stop wiggling the stick."
    ),
    short_description="Peak follower with attack / release.",
    params=(
        ParamSpec(
            name="attack", kind="float", default=0.5,
            description="Rate the output rises per tick when input increases. 1.0 = instant.",
            minimum=0.001, maximum=1.0,
        ),
        ParamSpec(
            name="release", kind="float", default=0.05,
            description="Rate the output falls per tick when input decreases. 0.02 ≈ slow decay.",
            minimum=0.001, maximum=1.0,
        ),
    ),
    inputs=(PinSpec("in", "in", "Scalar input (follows |x|).", expected="scalar"),),
    outputs=(PinSpec("out", "out", "Envelope-followed magnitude.", expected="scalar"),),
    wire_eligible=True,
    apply=_apply,
)

NODES = [SPEC]
