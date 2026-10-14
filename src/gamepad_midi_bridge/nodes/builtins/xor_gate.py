"""XorGate — N-input boolean XOR (exactly-one or odd-count semantics).

We use the "odd count" reading because it generalises cleanly to N
inputs and matches most logic-gate libraries. Unwired pins are ignored.
"""
from __future__ import annotations

from typing import Any, Dict

from ..model import NodeSpec, PinSpec, PinValue


def _apply(params: Dict[str, Any], inputs: Dict[str, PinValue], state=None) -> Dict[str, PinValue]:
    wired = [v for v in (inputs.get(f"in{i}") for i in (1, 2, 3, 4)) if v is not None]
    if not wired:
        return {"out": False}
    return {"out": (sum(1 for v in wired if bool(v)) % 2) == 1}


SPEC = NodeSpec(
    kind="xor_gate",
    label="XOR (N-input)",
    category="logic",
    description=(
        "Boolean XOR across up to 4 inputs. True iff an odd number of "
        "wired inputs are True. For 2 inputs this is the classic "
        "'exactly one of A or B' XOR; for higher N it generalises to "
        "parity. Unwired pins are ignored."
    ),
    short_description="True iff an odd number of inputs are True.",
    inputs=(
        PinSpec("in1", "in", "First input.", expected="bool"),
        PinSpec("in2", "in", "Second input — unwired = ignored.", expected="bool"),
        PinSpec("in3", "in", "Third input — unwired = ignored.", expected="bool"),
        PinSpec("in4", "in", "Fourth input — unwired = ignored.", expected="bool"),
    ),
    outputs=(PinSpec("out", "out", "Logical XOR (parity).", expected="bool"),),
    wire_eligible=False,
    apply=_apply,
)

NODES = [SPEC]
