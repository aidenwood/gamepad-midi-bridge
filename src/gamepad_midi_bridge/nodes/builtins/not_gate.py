"""NotGate — strict logic NOT (lives in the Logic category, distinct from
the Gate-category MomentaryInverse which serves controller-button UX).

Same logic; different categorical placement makes the node-picker easier
to navigate: a user reaching for "logic NOT" finds it under Logic next
to and/or/xor, while controller-button UX inverses land under Gate.
"""
from __future__ import annotations

from typing import Any, Dict

from ..model import NodeSpec, PinSpec, PinValue


def _apply(params: Dict[str, Any], inputs: Dict[str, PinValue], state=None) -> Dict[str, PinValue]:
    return {"out": not bool(inputs.get("in"))}


SPEC = NodeSpec(
    kind="not_gate",
    label="NOT",
    category="logic",
    description=(
        "Boolean NOT — output is True iff the input is falsy. Categorised "
        "under Logic so it sits alongside and/or/xor in the picker; the "
        "Gate-category Momentary Inverse has the same logic but is "
        "framed around controller-button UX."
    ),
    short_description="Boolean NOT.",
    inputs=(PinSpec("in", "in", "Boolean.", expected="bool"),),
    outputs=(PinSpec("out", "out", "not(input).", expected="bool"),),
    wire_eligible=True,
    apply=_apply,
)

NODES = [SPEC]
