"""StepQuantize — snap a scalar to one of N discrete steps in 0..1.

Continuous stick → stepped CC for hosts that want sample-trigger style
input (e.g. choosing among N presets via a single stick axis), or a
visual quantizer for an LFO output.
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
    steps = max(2, int(params.get("steps", 8)))
    # Clamp into 0..1 before quantizing — extreme inputs would produce
    # negative or >1 step indices otherwise.
    v = max(0.0, min(1.0, v))
    idx = int(v * steps)
    if idx >= steps:
        idx = steps - 1
    return {"out": idx / (steps - 1)}


SPEC = NodeSpec(
    kind="step_quantize",
    label="Step Quantize",
    category="shape",
    description=(
        "Snap the input to the nearest of N discrete steps in [0..1]. "
        "Output is also in [0..1] — useful when a downstream destination "
        "wants smooth-but-discrete control. Pair with octave shifters or "
        "scene selectors that respond to specific values."
    ),
    short_description="Snap to N evenly-spaced steps.",
    params=(
        ParamSpec(
            name="steps", kind="int", default=8,
            description="Number of distinct output values. 2 = binary, 16 = chromatic, 128 = MIDI-cc resolution.",
            minimum=2, maximum=128,
        ),
    ),
    inputs=(PinSpec("in", "in", "Scalar 0..1.", expected="scalar"),),
    outputs=(PinSpec("out", "out", "Quantized scalar 0..1.", expected="scalar"),),
    wire_eligible=True,
    apply=_apply,
)

NODES = [SPEC]
