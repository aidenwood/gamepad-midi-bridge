"""Invert — flip a scalar's sign, or 1-x for unipolar 0..1 inputs.

Wire-eligible. Two `mode`s:
    "sign"     y = -x         (bipolar; flips a stick's direction)
    "unipolar" y = 1 - x      (clamps in 0..1, useful for "invert the CC")

Stateless, branches by mode parameter — minimal surface, max utility on
a wire's ⚙ menu.
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
    mode = str(params.get("mode", "sign"))
    if mode == "unipolar":
        return {"out": max(0.0, min(1.0, 1.0 - v))}
    return {"out": -v}


SPEC = NodeSpec(
    kind="invert",
    label="Invert",
    category="shape",
    description=(
        "Flip the input. `sign` mode negates (left↔right on a stick, "
        "ascending↔descending on any signed value). `unipolar` mode does "
        "1 - x, clamped to [0..1] — the right tool for 'invert this CC' "
        "where the value is already in MIDI's 0..1 normalised space."
    ),
    short_description="Negate the value (or 1-x for 0..1 mode).",
    params=(
        ParamSpec(
            name="mode", kind="choice", default="sign",
            description=(
                "`sign` for bipolar inputs (sticks at -1..1); `unipolar` for "
                "values already normalised to 0..1 (CCs, magnitudes, LFO out)."
            ),
            choices=("sign", "unipolar"),
        ),
    ),
    inputs=(PinSpec("in", "in", "Scalar input.", expected="scalar"),),
    outputs=(PinSpec("out", "out", "Inverted scalar.", expected="scalar"),),
    wire_eligible=True,
    apply=_apply,
)

NODES = [SPEC]
