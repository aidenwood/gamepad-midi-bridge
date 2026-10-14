"""Square — y = sign(x) * x², a quick nonlinear punch."""
from __future__ import annotations

from typing import Any, Dict

from ..model import NodeSpec, PinSpec, PinValue


def _apply(params: Dict[str, Any], inputs: Dict[str, PinValue], state=None) -> Dict[str, PinValue]:
    raw = inputs.get("in")
    if raw is None or isinstance(raw, tuple):
        return {"out": raw}
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return {"out": raw}
    sign = -1.0 if v < 0 else 1.0
    return {"out": sign * v * v}


SPEC = NodeSpec(
    kind="square",
    label="Square (×²)",
    category="shape",
    description=(
        "Sign-preserving square: `y = sign(x) * x²`. Compresses the low "
        "range — useful when small stick motions should map to tiny CC "
        "changes while full pushes still reach the full range. Fixed-"
        "shape alternative to power_curve when you don't need the k knob."
    ),
    short_description="y = sign(x) · x².",
    inputs=(PinSpec("in", "in", "Scalar input.", expected="scalar"),),
    outputs=(PinSpec("out", "out", "Square-shaped scalar.", expected="scalar"),),
    wire_eligible=True,
    apply=_apply,
)

NODES = [SPEC]
