"""AndGate — N-input boolean AND. Unwired pins ignored.

Same model as ChordDetect but without the time-based debounce — just
the boolean reduction. Pair with comparator nodes to express composite
conditions ("stick past 0.7 AND R1 held").
"""
from __future__ import annotations

from typing import Any, Dict

from ..model import NodeSpec, PinSpec, PinValue


def _apply(params: Dict[str, Any], inputs: Dict[str, PinValue], state=None) -> Dict[str, PinValue]:
    wired = [v for v in (inputs.get(f"in{i}") for i in (1, 2, 3, 4)) if v is not None]
    if not wired:
        return {"out": False}
    return {"out": all(bool(v) for v in wired)}


SPEC = NodeSpec(
    kind="and_gate",
    label="AND (N-input)",
    category="logic",
    description=(
        "Boolean AND across up to 4 inputs. Unwired pins are ignored. "
        "True iff every wired input is True. Lighter than chord_detect "
        "(no debounce timing) — pure logic reduction."
    ),
    short_description="True iff every wired input is True.",
    inputs=(
        PinSpec("in1", "in", "First input.", expected="bool"),
        PinSpec("in2", "in", "Second input — unwired = ignored.", expected="bool"),
        PinSpec("in3", "in", "Third input — unwired = ignored.", expected="bool"),
        PinSpec("in4", "in", "Fourth input — unwired = ignored.", expected="bool"),
    ),
    outputs=(PinSpec("out", "out", "Logical AND.", expected="bool"),),
    wire_eligible=False,
    apply=_apply,
)

NODES = [SPEC]
