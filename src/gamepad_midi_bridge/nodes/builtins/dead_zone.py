"""DeadZone — zero out inputs near the centre + linearly remap the rest.

Wire-eligible standalone version of the Curve node's deadzone mode.
Pair on a stick that's drifted past its calibrated rest position — a
small dead band around zero suppresses the drift while the outer
range still maps cleanly to 0..1.
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
    dz = max(0.0, min(1.0, float(params.get("dead_zone", 0.1))))
    sign = -1.0 if v < 0 else 1.0
    mag = abs(v)
    if mag <= dz:
        return {"out": 0.0}
    if dz >= 1.0:
        return {"out": 0.0}
    # Remap (dz..1) → (0..1) so the live range still spans 0..1.
    out_mag = (mag - dz) / (1.0 - dz)
    return {"out": sign * out_mag}


SPEC = NodeSpec(
    kind="dead_zone",
    label="Dead Zone",
    category="shape",
    description=(
        "Zero out inputs whose magnitude is below `dead_zone` and remap "
        "the rest into [0..1] (sign-preserving). Calibration fix for "
        "drifty sticks — set dead_zone to just past the resting noise "
        "floor and the live response still spans the full output range."
    ),
    short_description="Suppress centre band, remap rest.",
    params=(
        ParamSpec(
            name="dead_zone", kind="float", default=0.1,
            description="Magnitude under which output is forced to 0.",
            minimum=0.0, maximum=0.5,
        ),
    ),
    inputs=(PinSpec("in", "in", "Scalar input.", expected="scalar"),),
    outputs=(PinSpec("out", "out", "0 inside band; remapped outside.", expected="scalar"),),
    wire_eligible=True,
    apply=_apply,
)

NODES = [SPEC]
