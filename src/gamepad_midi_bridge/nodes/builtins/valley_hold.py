"""ValleyHold — track the minimum |value| seen so far, with optional decay.

Mirror of peak_hold. Hold the LOWEST magnitude observed; decay slowly
walks back up so a quieter passage can establish a new valley.
"""
from __future__ import annotations

from typing import Any, Dict

from ..model import NodeSpec, ParamSpec, PinSpec, PinValue


def _apply(params: Dict[str, Any], inputs: Dict[str, PinValue], state=None) -> Dict[str, PinValue]:
    raw = inputs.get("in")
    if raw is None or isinstance(raw, tuple):
        return {"out": raw}
    try:
        v = abs(float(raw))
    except (TypeError, ValueError):
        return {"out": raw}
    if state is None:
        state = {}
    # First tick seeds; otherwise track min with optional rise.
    valley = state.get("valley")
    if valley is None:
        valley = v
    decay = max(0.0, float(params.get("decay_per_tick", 0.0)))
    # Decay first (toward 1.0), then absorb new valley.
    valley = min(1.0, valley + decay)
    if v < valley:
        valley = v
    state["valley"] = valley
    return {"out": valley}


SPEC = NodeSpec(
    kind="valley_hold",
    label="Valley Hold",
    category="modulator",
    description=(
        "Track the minimum magnitude seen so far. Mirror of peak_hold. "
        "With decay > 0, the valley slowly drifts back up so quieter "
        "later passages can take over. Useful for tracking the floor "
        "of a session's noise — drives a gate threshold automatically."
    ),
    short_description="Minimum |x| seen so far, optional decay.",
    params=(
        ParamSpec("decay_per_tick", "float", 0.0,
                  "Amount added back to the valley every tick. 0 = hold forever.",
                  minimum=0.0, maximum=1.0),
    ),
    inputs=(PinSpec("in", "in", "Scalar input (valley follows |x|).", expected="scalar"),),
    outputs=(PinSpec("out", "out", "Valley magnitude.", expected="scalar"),),
    wire_eligible=True,
    apply=_apply,
)

NODES = [SPEC]
