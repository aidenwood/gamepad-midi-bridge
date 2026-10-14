"""PeakHold — output the maximum |value| seen so far, with optional decay.

Tracks the peak magnitude across ticks. With ``decay_per_tick=0`` the
peak holds forever (manual reset only). Non-zero decay slowly forgets
the peak so a slower-moving signal can take over.
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
    peak = float(state.get("peak", 0.0))
    decay = max(0.0, float(params.get("decay_per_tick", 0.0)))
    # Decay first, then absorb new peak.
    peak = max(0.0, peak - decay)
    if v > peak:
        peak = v
    state["peak"] = peak
    return {"out": peak}


SPEC = NodeSpec(
    kind="peak_hold",
    label="Peak Hold",
    category="modulator",
    description=(
        "Track the maximum magnitude seen so far. Output never drops "
        "below its previous reading unless `decay_per_tick > 0` is set, "
        "which slowly forgets the peak so a smaller signal can take "
        "over. Useful as a 'loudest movement' meter or a max-amplitude "
        "tracker over a session segment."
    ),
    short_description="Maximum |x| seen so far, with optional decay.",
    params=(
        ParamSpec(
            name="decay_per_tick", kind="float", default=0.0,
            description="Amount subtracted from the peak every tick. 0 = hold forever.",
            minimum=0.0, maximum=1.0,
        ),
    ),
    inputs=(PinSpec("in", "in", "Scalar input (peak follows |x|).", expected="scalar"),),
    outputs=(PinSpec("out", "out", "Peak magnitude.", expected="scalar"),),
    wire_eligible=True,
    apply=_apply,
)

NODES = [SPEC]
