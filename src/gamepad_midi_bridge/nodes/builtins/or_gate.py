"""OrGate — N-input boolean OR. Unwired pins ignored."""
from __future__ import annotations

from typing import Any, Dict

from ..model import NodeSpec, PinSpec, PinValue


def _apply(params: Dict[str, Any], inputs: Dict[str, PinValue], state=None) -> Dict[str, PinValue]:
    wired = [v for v in (inputs.get(f"in{i}") for i in (1, 2, 3, 4)) if v is not None]
    if not wired:
        return {"out": False}
    return {"out": any(bool(v) for v in wired)}


SPEC = NodeSpec(
    kind="or_gate",
    label="OR (N-input)",
    category="logic",
    description=(
        "Boolean OR across up to 4 inputs. Unwired pins are ignored. "
        "True iff any wired input is True. Pair with edge detection on "
        "buttons to fire one downstream destination from any of several "
        "triggers."
    ),
    short_description="True iff any wired input is True.",
    inputs=(
        PinSpec("in1", "in", "First input.", expected="bool"),
        PinSpec("in2", "in", "Second input — unwired = ignored.", expected="bool"),
        PinSpec("in3", "in", "Third input — unwired = ignored.", expected="bool"),
        PinSpec("in4", "in", "Fourth input — unwired = ignored.", expected="bool"),
    ),
    outputs=(PinSpec("out", "out", "Logical OR.", expected="bool"),),
    wire_eligible=False,
    apply=_apply,
)

NODES = [SPEC]
