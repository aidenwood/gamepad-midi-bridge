"""SampleHold — capture the input value on each trigger edge, hold until next.

Two inputs:
    value   — the signal to sample (scalar or vec2; preserved through hold)
    trigger — bool; rising edge captures value into the held output

Classic synth idiom. Pair with an LFO upstream + a `trigger` from a button
to "freeze the random parameter wherever the LFO was when I pressed". Or
sample a stick position to lock an effect at the angle/magnitude at the
moment a downstream cue fires.

Stateful — the held value AND the previous trigger (for edge detection):
    "held":         PinValue   — last captured value, or initial None
    "prev_trigger": bool       — to detect rising edges
"""
from __future__ import annotations

from typing import Any, Dict

from ..model import NodeSpec, PinSpec, PinValue


def _apply(params: Dict[str, Any], inputs: Dict[str, PinValue], state=None) -> Dict[str, PinValue]:
    if state is None:
        state = {}
    trigger = bool(inputs.get("trigger"))
    prev = state.get("prev_trigger", False)
    if trigger and not prev:
        # rising edge — sample
        state["held"] = inputs.get("value")
    state["prev_trigger"] = trigger
    return {"out": state.get("held", 0.0)}


SPEC = NodeSpec(
    kind="sample_hold",
    label="Sample & Hold",
    category="modulator",
    description=(
        "Capture the input value on each rising trigger edge and hold it "
        "until the next trigger. Output stays constant between triggers. "
        "Classic synth idiom — pair with an upstream LFO and a button "
        "trigger to 'freeze the modulator at the moment I pressed', or "
        "lock a stick angle for a cue. Any value shape (scalar, bool, "
        "vec2) flows through unchanged."
    ),
    short_description="Capture on trigger edge, hold until next.",
    inputs=(
        PinSpec("value", "in", "Signal to sample. Any value type — preserved as-is.", expected="scalar"),
        PinSpec("trigger", "in", "Rising edge captures `value` into the held output.", expected="bool"),
    ),
    outputs=(PinSpec("out", "out", "Most recently captured value (until next trigger).", expected="scalar"),),
    wire_eligible=False,
    apply=_apply,
)

NODES = [SPEC]
