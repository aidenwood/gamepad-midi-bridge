"""Sign — output -1, 0, or 1 based on input sign."""
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
    if v > 0.0:
        return {"out": 1.0}
    if v < 0.0:
        return {"out": -1.0}
    return {"out": 0.0}


SPEC = NodeSpec(
    kind="sign",
    label="Sign",
    category="shape",
    description=(
        "Direction-only output: -1 / 0 / +1 based on input sign. Strip "
        "magnitude entirely. Pair with a downstream gate to fire only "
        "when a stick moves in a specific direction."
    ),
    short_description="Direction-only signum.",
    inputs=(PinSpec("in", "in", "Scalar input.", expected="scalar"),),
    outputs=(PinSpec("out", "out", "-1 / 0 / +1.", expected="scalar"),),
    wire_eligible=True,
    apply=_apply,
)

NODES = [SPEC]
