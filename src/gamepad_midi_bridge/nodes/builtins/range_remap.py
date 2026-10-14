"""RangeRemap — rescale a scalar from [in_min..in_max] onto [out_min..out_max].

Wire-eligible: tiny, 1-in / 1-out, no state. The bread-and-butter "I want
this MIDI CC to span 30..100 instead of 0..127" transform — common enough
that it deserves to live on a wire's ⚙ menu without needing a node card.

Behaviour:
    * Input outside [in_min..in_max] is CLAMPED before remapping, so a stick
      held past its calibrated edge still emits the out_max value.
    * Zero-width input range (in_min == in_max) returns out_min.
"""
from __future__ import annotations

from typing import Any, Dict

from ..model import NodeSpec, ParamSpec, PinSpec, PinValue


def _apply(params: Dict[str, Any], inputs: Dict[str, PinValue], state=None) -> Dict[str, PinValue]:
    raw = inputs.get("in")
    if raw is None or isinstance(raw, tuple):
        return {"out": float(params.get("out_min", 0.0))}
    v = float(raw)
    in_min = float(params.get("in_min", 0.0))
    in_max = float(params.get("in_max", 1.0))
    out_min = float(params.get("out_min", 0.0))
    out_max = float(params.get("out_max", 1.0))
    if in_max == in_min:
        return {"out": out_min}
    # Clamp before remap so over-travel maps to out_max, not over-shoot.
    v = max(in_min, min(in_max, v))
    t = (v - in_min) / (in_max - in_min)
    return {"out": out_min + t * (out_max - out_min)}


SPEC = NodeSpec(
    kind="range_remap",
    label="Range Remap",
    category="shape",
    description=(
        "Rescale a scalar input from one numeric range to another. Input "
        "outside [in_min..in_max] is clamped before mapping, so over-travel "
        "(stick past its calibrated edge, trigger held longer) lands cleanly "
        "at out_max instead of overshooting. Common use: shape a stick's "
        "-1..1 into a MIDI CC's 30..100 range so a downstream effect never "
        "goes fully off or pegs the ceiling."
    ),
    short_description="Linear rescale: [in_min..in_max] → [out_min..out_max].",
    params=(
        ParamSpec("in_min", "float", 0.0,
                  "Lower bound of the input range. Inputs below this are clamped here before remapping.",
                  minimum=-1.0, maximum=1.0),
        ParamSpec("in_max", "float", 1.0,
                  "Upper bound of the input range. Inputs above this are clamped here before remapping.",
                  minimum=-1.0, maximum=1.0),
        ParamSpec("out_min", "float", 0.0,
                  "Output value when input equals in_min.",
                  minimum=0.0, maximum=127.0),
        ParamSpec("out_max", "float", 1.0,
                  "Output value when input equals in_max.",
                  minimum=0.0, maximum=127.0),
    ),
    inputs=(PinSpec("in", "in", "Scalar input.", expected="scalar"),),
    outputs=(PinSpec("out", "out", "Remapped scalar.", expected="scalar"),),
    wire_eligible=True,
    apply=_apply,
)

NODES = [SPEC]
